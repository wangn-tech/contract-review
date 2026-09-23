"""LLMClient 工程化测试：应用层并发限流 + prompt cache 参数透传。"""
from __future__ import annotations

import asyncio

import pytest

from app.rag.client import LLMClient


class _FakeChoice:
    def __init__(self, text: str = "ok", tool_calls=None):
        self.message = type(
            "Msg",
            (),
            {"content": text, "tool_calls": tool_calls, "finish_reason": "stop"},
        )()


class _FakeResp:
    def __init__(self, text: str = "ok"):
        self.choices = [_FakeChoice(text)]


@pytest.mark.asyncio
async def test_chat_acquires_semaphore(monkeypatch):
    """并发上限：超过 MAX_CONCURRENT_LLM 的调用必须排队（信号量生效）。"""
    client = LLMClient()
    client._sem = asyncio.Semaphore(2)

    active = 0
    peak = 0
    gate = asyncio.Event()

    async def fake_create(**kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        gate.set()
        return _FakeResp()

    monkeypatch.setattr(client._openai.chat.completions, "create", fake_create)

    results = await asyncio.gather(*[client.chat([{"role": "user", "content": "x"}]) for _ in range(6)])
    assert results == ["ok"] * 6
    assert peak <= 2, f"并发峰值 {peak} 超出信号量上限 2"


@pytest.mark.asyncio
async def test_chat_with_tools_acquires_semaphore(monkeypatch):
    client = LLMClient()
    client._sem = asyncio.Semaphore(1)

    async def fake_create(**kwargs):
        await asyncio.sleep(0.02)
        return _FakeResp()

    monkeypatch.setattr(client._openai.chat.completions, "create", fake_create)
    msg = await client.chat_with_tools([{"role": "user", "content": "x"}], tools=[{"type": "function", "function": {"name": "f", "parameters": {"type": "object"}}}])
    assert msg.content == "ok"


@pytest.mark.asyncio
async def test_prompt_cache_extra_body(monkeypatch):
    """开启 prompt cache 时 extra_body 带 cache_prompt=True。"""
    client = LLMClient()
    client._prompt_cache = True
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeResp()

    monkeypatch.setattr(client._openai.chat.completions, "create", fake_create)
    await client.chat([{"role": "user", "content": "hi"}])
    assert captured["extra_body"]["cache_prompt"] is True


@pytest.mark.asyncio
async def test_prompt_cache_disabled(monkeypatch):
    client = LLMClient()
    client._prompt_cache = False
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeResp()

    monkeypatch.setattr(client._openai.chat.completions, "create", fake_create)
    await client.chat([{"role": "user", "content": "hi"}])
    assert "extra_body" not in captured


@pytest.mark.asyncio
async def test_chat_stream_events_cache_and_semaphore(monkeypatch):
    client = LLMClient()
    client._sem = asyncio.Semaphore(1)
    client._prompt_cache = True
    captured = {}

    class _FakeChunk:
        def __init__(self):
            self.usage = None
            self.choices = [type("C", (), {"delta": type("D", (), {"content": "a"})()})()]

    class _FakeStream:
        def __init__(self):
            self._chunks = [_FakeChunk()]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._chunks:
                raise StopAsyncIteration
            return self._chunks.pop(0)

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeStream()

    monkeypatch.setattr(client._openai.chat.completions, "create", fake_create)
    events = [e async for e in client.chat_stream_events([{"role": "user", "content": "hi"}])]
    assert events[0] == ("start", None)
    assert events[-1] == ("delta", "a")
    assert captured["extra_body"]["cache_prompt"] is True
