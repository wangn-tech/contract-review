"""RAG service facade: single entry for agent tool calls (search_regulations)."""
from pathlib import Path

from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.rag.context import build_context
from app.rag.ingest.loader import ensure_collection
from app.rag.rerank import rerank_chunks
from app.rag.retrievers.hybrid import HybridRetriever, RetrievedChunk
from app.rag.retrievers.sparse_bm25 import BM25Index

settings = get_settings()

# 风险维度 → 优先检索的知识库层
DIM_TO_COLLECTION = {
    "主体资格与合规": settings.qdrant_collection_institution,
    "财务与付款": settings.qdrant_collection_institution,
    "知识产权与保密": settings.qdrant_collection_regulations,
    "违约责任与解除": settings.qdrant_collection_regulations,
    "验收交付与质保": settings.qdrant_collection_regulations,
    "争议解决与管辖": settings.qdrant_collection_regulations,
}

DIM_TO_DOC_TYPE = {
    "主体资格与合规": "institution",
    "财务与付款": "institution",
    "知识产权与保密": "regulation",
    "违约责任与解除": "regulation",
    "验收交付与质保": "regulation",
    "争议解决与管辖": "regulation",
}


class RAGService:
    def __init__(
        self,
        qdrant: AsyncQdrantClient | None = None,
        bm25: BM25Index | None = None,
        bm25_path: str | Path | None = None,
    ) -> None:
        self.qdrant = qdrant or AsyncQdrantClient(
            url=settings.qdrant_url, timeout=30.0
        )
        if bm25 is not None:
            self.bm25 = bm25
        elif bm25_path and Path(bm25_path).exists():
            self.bm25 = BM25Index.load(bm25_path)
        else:
            self.bm25 = BM25Index()
        self.retriever = HybridRetriever(self.qdrant, self.bm25)

    async def ensure_ready(self, vector_size: int = 1024) -> None:
        for collection in {
            settings.qdrant_collection_regulations,
            settings.qdrant_collection_institution,
            settings.qdrant_collection_templates,
        }:
            await ensure_collection(self.qdrant, collection, vector_size)

    async def search(
        self,
        query: str,
        risk_dim: str | None = None,
        top_k: int = 10,
        doc_type: str | None = None,
    ) -> list[RetrievedChunk]:
        """检索入口：跨知识库层（法规/校内制度/模板）多路召回 → RRF 融合 → rerank。

        风险维度不再限定单一 collection——同一问题（如"财务与付款"）可能同时命中
        法规条文、校内制度和合同模板，限定单库会损失召回（Recall 实测 0.40→0.25）。
        """
        # risk_dim 不再推导 doc_type：风险维度与语料层不是一一对应，
        # 一旦按维度过滤单层，法规/模板/制度中的相关条款会被整体排除（实测 Recall 骤降）。
        # doc_type 仅保留显式业务过滤能力。
        candidates: list[RetrievedChunk] = []
        for collection in (
            settings.qdrant_collection_regulations,
            settings.qdrant_collection_institution,
            settings.qdrant_collection_templates,
        ):
            cands = await self.retriever.retrieve(
                query, collection, top_k=settings.rag_hybrid_top_k, doc_type=doc_type
            )
            candidates.extend(cands)
        return await rerank_chunks(query, candidates, top_k=top_k)

    async def search_with_context(
        self,
        query: str,
        risk_dim: str | None = None,
        top_k: int = 5,
    ) -> tuple[str, list[RetrievedChunk]]:
        evidence = await self.search(query, risk_dim=risk_dim, top_k=top_k)
        return build_context(evidence), evidence

    async def close(self) -> None:
        await self.qdrant.close()


_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        bm25_path = settings.kb_bm25_path or str(
            Path(settings.oss_bucket_dir).parent / "kb_bm25.pkl"
        )
        _rag_service = RAGService(bm25_path=bm25_path)
    return _rag_service
