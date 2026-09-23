"""Intent classifier node: LLM structured classification + rule-based fallback.

简历点：混合路由——LLM 主分类（JSON 结构化输出），解析失败/低置信时
降级到关键词规则引擎，再兜底默认意图，保证路由 100% 可达。
"""
import json
import re

from app.agent.prompts import load_prompt
from app.agent.state import ReviewState
from app.core.config import get_settings
from app.rag.client import get_sf_client

settings = get_settings()

INTENT_KEYWORDS: dict[str, list[str]] = {
    "review": ["审阅", "审查", "风险", "审一下", "看看问题", "评估", "条款"],
    "compare": ["比对", "对比", "差异", "两个合同", "区别"],
    "admin": ["配置", "合同类型", "模型", "提示词", "prompt", "管理"],
    "chat": ["问答", "咨询", "是什么", "怎么", "请问", "解释"],
}

RULE_FALLBACK_INTENT = "chat"


def _rule_classify(text: str) -> tuple[str, float]:
    best_intent, best_score = RULE_FALLBACK_INTENT, 0.0
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_intent, best_score = intent, float(score)
    return best_intent, min(best_score * 0.2, 0.6)


async def _llm_classify(text: str) -> tuple[str, float] | None:
    try:
        prompt = load_prompt("intent")
        raw = await get_sf_client().chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"用户请求：{text[:2000]}"},
            ],
            model=settings.llm_intent_model,
            temperature=0,
            max_tokens=256,
        )
        data = _parse_json(raw)
        intent = data.get("intent")
        if intent not in {"review", "compare", "chat", "admin"}:
            return None
        confidence = float(data.get("confidence", 0.0))
        return intent, confidence
    except Exception:
        return None


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}
    return {}


async def intent_node(state: ReviewState) -> dict:
    """审阅任务入口：请求描述/意图确认。默认 review，识别失败走规则降级。"""
    text = state.get("description") or f"{state.get('contract_type', '')}合同审阅"
    intent, confidence = "review", 1.0

    if text:
        llm_result = await _llm_classify(text)
        if llm_result and llm_result[1] >= 0.5:
            intent, confidence = llm_result
        else:
            # 规则降级
            rule_intent, rule_conf = _rule_classify(text)
            if llm_result and llm_result[0] == "review":
                intent = "review"
            else:
                intent, confidence = rule_intent, rule_conf

    return {"intent": intent, "intent_confidence": confidence, "errors": []}
