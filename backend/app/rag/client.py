"""SiliconFlow API client: chat / embedding / rerank (async)."""
from typing import Any

import httpx

from app.core.config import get_settings

settings = get_settings()


class SiliconFlowClient:
    def __init__(self) -> None:
        self.base_url = settings.siliconflow_base_url
        self.api_key = settings.siliconflow_api_key
        self.timeout = httpx.Timeout(120.0, connect=10.0)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ---------- chat ----------
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        model = model or settings.llm_review_model
        resp = await self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                **kwargs,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def chat_stream(self, messages: list[dict], model: str | None = None, **kwargs: Any):
        """返回增量文本的异步生成器。"""
        model = model or settings.llm_chat_model
        async with self.client.stream(
            "POST",
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                **kwargs,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                import json

                obj = json.loads(payload)
                delta = obj["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content

    # ---------- embedding ----------
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """BAAI/bge-m3 dense embedding（SiliconFlow /embeddings 接口）。"""
        model = model or settings.embedding_model
        resp = await self.client.post(
            "/embeddings",
            json={"model": model, "input": texts, "encoding_format": "float"},
        )
        resp.raise_for_status()
        data = resp.json()
        ordered = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in ordered]

    # ---------- rerank ----------
    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str | None = None,
        top_n: int = 5,
    ) -> list[dict]:
        """bge-reranker-v2-m3 精排，返回 [{index, score}] 按分降序。"""
        model = model or settings.rerank_model
        resp = await self.client.post(
            "/rerank",
            json={"model": model, "query": query, "documents": documents, "top_n": top_n},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


_sf_client: SiliconFlowClient | None = None


def get_sf_client() -> SiliconFlowClient:
    global _sf_client
    if _sf_client is None:
        _sf_client = SiliconFlowClient()
    return _sf_client
