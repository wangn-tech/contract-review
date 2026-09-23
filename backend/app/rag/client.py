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


def _extract_json(raw: str) -> dict | None:
    """容错 JSON 提取：先整体解析，再取首个 {…} 块。"""
    import json
    import re

    raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except Exception:  # noqa: BLE001
                return None
    return None


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

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tool_choice: str | dict = "auto",
        **kwargs: Any,
    ):
        """OpenAI SDK Tool Calling：返回完整 message（含 tool_calls / content）。

        调用方负责工具循环（见 app/agent/tools/executor.py）。
        """
        model = model or settings.llm_review_model
        resp = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return resp.choices[0].message

    async def chat_structured(
        self,
        messages: list[dict],
        json_schema: dict,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> dict | None:
        """Structured output：response_format=json_schema 返回解析后的 dict。

        供应商不支持 strict json_schema 时回退普通 chat + 正则提取 JSON；
        解析失败返回 None，由调用方降级。
        """
        model = model or settings.llm_intent_model
        try:
            resp = await self._openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "structured_output", "strict": True, "schema": json_schema},
                },
                **kwargs,
            )
            content = resp.choices[0].message.content or ""
            parsed = _extract_json(content)
            if parsed is not None:
                return parsed
        except Exception:  # noqa: BLE001 供应商不支持 json_schema → 走降级路径
            pass
        try:
            raw = await self.chat(
                messages, model=model, temperature=temperature, max_tokens=max_tokens, **kwargs
            )
            return _extract_json(raw)
        except Exception:  # noqa: BLE001
            return None

    async def collect_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict]:
        """流式聚合：收集完整文本 + usage（include_usage）。

        供非增量场景（gate/arbitration）复用流式通道，顺带统计 token。
        """
        model = model or settings.llm_chat_model
        full: list[str] = []
        usage: dict = {}
        kwargs.setdefault("stream_options", {"include_usage": True})
        stream = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                full.append(chunk.choices[0].delta.content)
        return "".join(full), usage

    async def chat_stream(self, messages: list[dict], model: str | None = None, **kwargs: Any):
        """OpenAI SDK 流式：返回增量文本的异步生成器。

        调用方传 stream_options={"include_usage": True} 时，末尾会收到 usage chunk
        （无 content），由调用方统计；生成器本身只产出增量文本。
        """
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

    async def chat_stream_events(self, messages: list[dict], model: str | None = None, **kwargs: Any):
        """流式事件生成器：yield ("start", None) → ("delta", text)… → ("usage", dict)。

        供需要 TTFT / token 统计的流式链路（chat_service）使用。
        """
        model = model or settings.llm_chat_model
        kwargs.setdefault("stream_options", {"include_usage": True})
        stream = await self._openai.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        yield ("start", None)
        async for chunk in stream:
            # 独立判断：部分供应商 usage 与 content 可能同 chunk，用 if 而非 elif 避免吞 delta
            if chunk.usage:
                yield (
                    "usage",
                    {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    },
                )
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield ("delta", chunk.choices[0].delta.content)

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
