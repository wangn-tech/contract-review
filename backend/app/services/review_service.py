"""Review task orchestration: chunk -> LangGraph agent -> SSE streaming output."""
import asyncio
import json
import re
from datetime import UTC, datetime

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.agent.graph import get_graph
from app.agent.state import ReviewState
from app.models.contract import ContractFile
from app.models.review import ReviewResult, ReviewTask
from app.models.session_message import Session
from app.models.user import User
from app.rag.service import RAGService, get_rag_service
from app.schemas.review import ReviewStartRequest

CLAUSE_RE = re.compile(r"^第[一二三四五六七八九十百千0-9]+[条款]")


def split_contract_clauses(text: str, max_chars: int = 1500) -> list[str]:
    """按 '第X条' 切分；无条款结构时按长度切分。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    clauses: list[str] = []
    buf: list[str] = []
    for line in lines:
        if CLAUSE_RE.match(line):
            if buf:
                clauses.append("\n".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        clauses.append("\n".join(buf))

    # 超长块再切
    out: list[str] = []
    for c in clauses:
        if len(c) <= max_chars:
            out.append(c)
        else:
            for i in range(0, len(c), max_chars):
                out.append(c[i : i + max_chars])
    return out or [text[:max_chars]]


async def stream_review_events(
    request: ReviewStartRequest,
    current_user: User,
    db: DBSession,
    rag: RAGService | None = None,
) -> StreamingResponse:
    rag = rag or get_rag_service()

    session = db.get(Session, request.session_id)
    if session is None or session.user_id != current_user.id:
        raise PermissionError("session not found")
    contract = db.get(ContractFile, session.file_id) if session.file_id else None
    if contract is None:
        raise PermissionError("contract file not found")
    if contract.parse_status != "parsed" or not contract.content_path:
        raise PermissionError("file not parsed, review unsupported")

    # 清理旧任务
    old_task = db.query(ReviewTask).filter(ReviewTask.session_id == request.session_id).first()
    if old_task:
        db.query(ReviewResult).filter(ReviewResult.task_id == old_task.id).delete()
        db.delete(old_task)
        db.commit()

    task = ReviewTask(
        session_id=request.session_id,
        file_id=contract.id,
        user_id=current_user.id,
        stance=request.stance,
        intensity=request.intensity,
        description=request.description or "",
        contract_type=request.contract_type or "",
        status="processing",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    with open(contract.content_path, encoding="utf-8") as f:
        content = f.read()
    chunks = split_contract_clauses(content)

    state: ReviewState = {
        "session_id": request.session_id,
        "file_id": contract.id,
        "user_id": current_user.id,
        "contract_type": request.contract_type or "",
        "stance": request.stance,
        "intensity": request.intensity,
        "description": request.description or "",
        "max_concurrent": request.max_concurrent,
        "chunks": chunks,
        "intent": "review",
        "intent_confidence": 1.0,
        "routed": [],
        "specialist_outputs": [],
        "gated": [],
        "final_risk_points": [],
        "summary": {},
        "errors": [],
    }

    async def gen():
        try:
            graph = get_graph(rag)
            # 流式执行：custom 模式推送专家实时结果，updates 模式收集仲裁后的最终状态
            stream = graph.astream(state, stream_mode=["custom", "updates"])
            final_points: list[dict] = []
            summary: dict = {}
            async for mode, payload in stream:
                if mode == "custom":
                    if isinstance(payload, dict) and payload.get("type") == "risk_point":
                        for p in payload.get("points", []):
                            if isinstance(p, dict):
                                yield f"data: {json.dumps({'event': 'message', 'data': p}, ensure_ascii=False)}\n\n"
                                await asyncio.sleep(0.01)
                elif mode == "updates":
                    for node, upd in payload.items():
                        if node == "arbitration" and isinstance(upd, dict):
                            final_points = upd.get("final_risk_points") or []
                            summary = upd.get("summary") or {}

            points = final_points

            # 写入 DB 并按序 SSE 输出
            for idx, point in enumerate(points, start=1):
                record = ReviewResult(
                    task_id=task.id,
                    session_id=request.session_id,
                    index=idx,
                    original_content=point.get("original_content", ""),
                    risk_analysis=point.get("risk_analysis", ""),
                    risk_level=point.get("risk_level", "中"),
                    suggested_content=point.get("suggested_content", ""),
                    risk_dim=point.get("risk_dim", ""),
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                msg = json.dumps(
                    {
                        "event": "message",
                        "data": {
                            "id": record.id,
                            "task_id": task.id,
                            "session_id": request.session_id,
                            "index": idx,
                            "original_content": record.original_content,
                            "risk_analysis": record.risk_analysis,
                            "risk_level": record.risk_level,
                            "suggested_content": record.suggested_content,
                            "risk_dim": record.risk_dim,
                        },
                    },
                    ensure_ascii=False,
                )
                yield f"data: {msg}\n\n"
                await asyncio.sleep(0.01)  # 让出事件循环，保证流式可见

            task.status = "completed"
            task.completed_at = datetime.now(UTC)
            db.commit()

            end_msg = json.dumps(
                {
                    "event": "end",
                    "data": {
                        "type": "summary",
                        "summary": summary.get("summary", ""),
                        "suggestion": summary.get("suggestion", ""),
                        "overall_risk": summary.get("overall_risk", "低"),
                    },
                },
                ensure_ascii=False,
            )
            yield f"data: {end_msg}\n\n"
        except Exception as exc:  # noqa: BLE001
            task.status = "failed"
            db.commit()
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(exc)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
