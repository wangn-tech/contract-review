"""Retrieval quality metrics: Recall@K, Precision@K, MRR, NDCG@K.

纯函数实现，可在无 LLM 环境下单元测试。
"""
from __future__ import annotations


def hit_at_k(relevant: set[str], retrieved: list[str], k: int) -> int:
    return int(any(doc in relevant for doc in retrieved[:k]))


def recall_at_k(relevant: set[str], retrieved: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    hit = sum(1 for doc in retrieved[:k] if doc in relevant)
    return hit / len(relevant)


def precision_at_k(relevant: set[str], retrieved: list[str], k: int) -> float:
    if k <= 0 or not retrieved:
        return 0.0
    hit = sum(1 for doc in retrieved[:k] if doc in relevant)
    return hit / min(k, len(retrieved))


def mrr(relevant: set[str], retrieved: list[str]) -> float:
    for i, doc in enumerate(retrieved):
        if doc in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(relevant: set[str], retrieved: list[str], k: int) -> float:
    import math

    dcg = 0.0
    for i, doc in enumerate(retrieved[:k]):
        if doc in relevant:
            dcg += 1.0 / math.log2(i + 2)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal > 0 else 0.0


def evaluate_retrieval(
    cases: list[tuple[set[str], list[str]]], k: int = 5
) -> dict:
    """cases: [(relevant_docs_set, retrieved_docs_list)] → 聚合指标。"""
    if not cases:
        return {"recall@k": 0.0, "precision@k": 0.0, "mrr": 0.0, "ndcg@k": 0.0, "hit@k": 0.0}
    n = len(cases)
    return {
        "recall@k": sum(recall_at_k(r, ret, k) for r, ret in cases) / n,
        "precision@k": sum(precision_at_k(r, ret, k) for r, ret in cases) / n,
        "mrr": sum(mrr(r, ret) for r, ret in cases) / n,
        "ndcg@k": sum(ndcg_at_k(r, ret, k) for r, ret in cases) / n,
        "hit@k": sum(hit_at_k(r, ret, k) for r, ret in cases) / n,
    }
