"""LLM 客户端：基于 OpenAI SDK 接入任意 OpenAI-compatible 供应商。

默认 BASE_URL=https://api.siliconflow.cn/v1（SiliconFlow），更换供应商只需
修改 .env 中的 LLM_BASE_URL / LLM_API_KEY（或兼容的 SILICONFLOW_*）。
chat / embeddings 走 OpenAI SDK；rerank 为供应商扩展接口，SDK 无对应
能力，保留轻量 HTTP 调用。
"""
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings

settings = get_settings()


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url or settings.siliconflow_base_url
        self.api_key = settings.llm_api_key or settings.siliconflow_api_key
        self.timeout = 120.0
        self._openai = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=1,
        )
        self._http: httpx.AsyncClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        """供 rerank 等供应商扩展接口使用。"""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        return self._http

    async def aclose(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ---------- chat（OpenAI SDK） ----------
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        model = model or settings.llm_review_model
        resp = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return resp.choices[0].message.content or ""

    async def chat_stream(self, messages: list[dict], model: str | None = None, **kwargs: Any):
        """OpenAI SDK 流式：返回增量文本的异步生成器。"""
        model = model or settings.llm_chat_model
        stream = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ---------- embedding（OpenAI SDK） ----------
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model = model or settings.embedding_model
        resp = await self._openai.embeddings.create(
            model=model,
            input=texts,
            encoding_format="float",
        )
        ordered = sorted(resp.data, key=lambda x: x.index)
        return [item.embedding for item in ordered]

    # ---------- rerank（供应商扩展接口） ----------
    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str | None = None,
        top_n: int = 5,
    ) -> list[dict]:
        model = model or settings.rerank_model
        resp = await self.http.post(
            "/rerank",
            json={"model": model, "query": query, "documents": documents, "top_n": top_n},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


# 兼容旧调用方（agent 节点 / rag / 服务层）
get_sf_client = get_llm_client
