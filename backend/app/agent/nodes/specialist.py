"""Specialist node: ReAct loop (think -> retrieve evidence -> generate risk point).

简历点：每个风险维度专家在 ReAct 循环中调用 RAG 检索工具
（search_regulations），用制度/法规证据支撑判断，最多 N 轮。
"""
import asyncio
import json
import re

from app.agent.prompts import load_prompt, load_risk_dim_prompt
from app.agent.state import ReviewState
from app.core.config import get_settings
from app.rag.client import get_sf_client
from app.rag.service import RAGService

settings = get_settings()

MAX_REACT_ROUNDS = 3


def _parse_risk_points(raw: str) -> list[dict]:
    """解析专家输出 JSON；兼容 ```json 包裹。"""
    text = raw.strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except Exception:
        return []
    points = data.get("risk_points", [])
    if not isinstance(points, list):
        return []
    cleaned = []
    for p in points:
        if isinstance(p, dict) and p.get("original_content"):
            cleaned.append(
                {
                    "original_content": str(p.get("original_content", ""))[:2000],
                    "risk_analysis": str(p.get("risk_analysis", ""))[:2000],
                    "risk_level": p.get("risk_level", "中") if p.get("risk_level") in {"高", "中", "低"} else "中",
                    "suggested_content": str(p.get("suggested_content", ""))[:2000],
                }
            )
    return cleaned


async def _run_specialist(
    sem: asyncio.Semaphore,
    chunk: str,
    risk_dim: str,
    state: ReviewState,
    rag: RAGService,
) -> dict:
    """单个 (chunk, risk_dim) 专家任务：ReAct 循环 + 故障隔离（失败重试 1 次）。"""
    async with sem:
        sf = get_sf_client()
        dim_prompt = load_risk_dim_prompt(risk_dim)
        system = load_prompt(
            "specialist_base",
            risk_dim=risk_dim,
            stance=state["stance"],
            intensity=state["intensity"],
        )
        if dim_prompt:
            system += f"\n\n【{risk_dim}审阅细则】\n{dim_prompt}"

        # ReAct 循环：思考 → 检索 → 生成（本轮实现 1 次检索 + 生成，轮次可配）
        evidence_ctx = ""
        for _ in range(MAX_REACT_ROUNDS):
            user_msg = f"【合同条款】\n{chunk}\n\n【检索证据】\n{evidence_ctx or '（未检索）'}\n\n请完成审阅并输出 JSON。"
            try:
                raw = await sf.chat(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    model=settings.llm_review_model,
                    temperature=0.2,
                    max_tokens=2048,
                )
            except Exception as exc:  # noqa: BLE001
                # 故障隔离：LLM 调用失败不拖垮整体，记录后重试一轮（再失败返回空结果）
                state.setdefault("errors", []).append(
                    f"specialist[{risk_dim}] llm error: {exc}"
                )
                if evidence_ctx:
                    break
                evidence_ctx, _ = await rag.search_with_context(chunk, risk_dim=risk_dim, top_k=3)
                continue
            points = _parse_risk_points(raw)
            if points:
                # 流式推送：单个专家任务完成即推 SSE（LangGraph custom stream mode）
                try:
                    from langgraph.config import get_stream_writer

                    get_stream_writer()(
                        {
                            "type": "risk_point",
                            "risk_dim": risk_dim,
                            "points": points,
                        }
                    )
                except Exception:  # noqa: BLE001  writer 不可用时静默降级（非流式上下文）
                    pass
                return {"chunk_index": state["chunks"].index(chunk), "risk_dim": risk_dim, "result": points}
            # 未解析出风险点 → 检索证据后再试
            evidence_ctx, _ = await rag.search_with_context(chunk, risk_dim=risk_dim, top_k=3)
            if not evidence_ctx or evidence_ctx.startswith("（未检索"):
                break

        return {"chunk_index": state["chunks"].index(chunk), "risk_dim": risk_dim, "result": []}


async def specialist_node(state: ReviewState, rag: RAGService) -> dict:
    """map：并行执行所有 (chunk, risk_dim) 专家任务，信号量限流。"""
    sem = asyncio.Semaphore(state.get("max_concurrent", 20))
    tasks = [
        _run_specialist(sem, state["chunks"][r["chunk_index"]], dim, state, rag)
        for r in state["routed"]
        for dim in r["risk_dims"]
    ]
    outputs = await asyncio.gather(*tasks)
    return {"specialist_outputs": outputs}
