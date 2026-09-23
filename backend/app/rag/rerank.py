"""Rerank with bge-reranker-v2-m3 (cross-encoder) for precision."""
from app.core.config import get_settings
from app.rag.client import get_sf_client
from app.rag.retrievers.hybrid import RetrievedChunk

settings = get_settings()


async def rerank_chunks(
    query: str,
    candidates: list[RetrievedChunk],
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Cross-encoder 精排：对候选重排并取 Top-K。"""
    top_k = top_k or settings.rag_rerank_top_k
    if not candidates:
        return []
    if len(candidates) <= 1:
        return candidates[:top_k]

    documents = [c.chunk.text for c in candidates]
    results = await get_sf_client().rerank(query, documents, top_n=min(top_k, len(candidates)))
    score_map = {r["index"]: r["score"] for r in results}
    ordered = sorted(candidates, key=lambda c: score_map.get(id(c), 0.0), reverse=True)
    return [RetrievedChunk(chunk=c.chunk, score=score_map.get(id(c), 0.0)) for c in ordered[:top_k]]
