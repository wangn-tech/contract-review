"""RAGAS evaluation: faithfulness / answer relevancy / context precision / context recall.

需要 ragas 依赖（optional extra: eval）。运行入口见 scripts/eval_rag.py。
"""
from __future__ import annotations


def build_ragas_dataset(
    cases: list[dict],
) -> list[dict]:
    """把 golden set 转换为 RAGAS 输入格式。

    case: {question, answer, contexts: [chunk_text], ground_truth}
    """
    return [
        {
            "user_input": c["question"],
            "response": c["answer"],
            "retrieved_contexts": c["contexts"],
            "reference": c["ground_truth"],
        }
        for c in cases
    ]


async def run_ragas_eval(dataset: list[dict], llm_model: str | None = None) -> dict:
    """执行 RAGAS 四指标评估（LLM-as-judge）。"""
    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    from app.core.config import get_settings

    settings = get_settings()
    llm = ChatOpenAI(
        model=llm_model or settings.llm_chat_model,
        base_url=settings.siliconflow_base_url,
        api_key=settings.siliconflow_api_key,
        temperature=0,
    )
    wrapper = LangchainLLMWrapper(llm)
    eval_dataset = EvaluationDataset.from_list(dataset)
    result = evaluate(
        dataset=eval_dataset,
        metrics=[
            Faithfulness(llm=wrapper),
            ResponseRelevancy(llm=wrapper),
            LLMContextPrecisionWithoutReference(llm=wrapper),
            LLMContextRecall(llm=wrapper),
        ],
    )
    return result.to_pandas().to_dict(orient="records")
