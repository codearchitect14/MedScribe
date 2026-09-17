"""Unit tests for the Groq/Gemini adapters' request/response handling.

No network calls are made: httpx.AsyncClient is monkeypatched with a stand-in
that returns a canned httpx.Response, so these tests verify payload shape and
response parsing without needing real API keys.
"""

import httpx
import pytest

from app.llm.adapters.gemini_adapter import GeminiAdapter
from app.llm.adapters.groq_adapter import GroqAdapter
from app.llm.exceptions import ProviderError, RateLimitExceededError


class FakeAsyncClient:
    def __init__(self, response: httpx.Response, *, capture: dict, **kwargs):
        self._response = response
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, **kwargs):
        self._capture["url"] = url
        self._capture.update(kwargs)
        return self._response


def _patch_client(monkeypatch, module, response: httpx.Response) -> dict:
    capture: dict = {}

    def factory(*args, **kwargs):
        return FakeAsyncClient(response, capture=capture)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)
    return capture


@pytest.mark.asyncio(loop_scope="session")
async def test_groq_adapter_parses_success(monkeypatch):
    from app.llm.adapters import groq_adapter as module

    monkeypatch.setattr(module.get_settings(), "groq_api_key", "test-key")
    body = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    response = httpx.Response(200, json=body, request=httpx.Request("POST", "https://example.com"))
    capture = _patch_client(monkeypatch, module, response)

    adapter = GroqAdapter()
    result = await adapter.complete(
        system_prompt="sys", user_prompt="user", max_tokens=100, json_mode=True
    )

    assert result.content == '{"ok": true}'
    assert result.tokens_input == 10
    assert result.tokens_output == 5
    sent_payload = capture["json"]
    assert sent_payload["messages"][0] == {"role": "system", "content": "sys"}
    assert sent_payload["messages"][1] == {"role": "user", "content": "user"}
    assert sent_payload["max_tokens"] == 100
    assert sent_payload["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio(loop_scope="session")
async def test_groq_adapter_raises_on_429(monkeypatch):
    from app.llm.adapters import groq_adapter as module

    monkeypatch.setattr(module.get_settings(), "groq_api_key", "test-key")
    response = httpx.Response(429, text="rate limited", request=httpx.Request("POST", "https://example.com"))
    _patch_client(monkeypatch, module, response)

    adapter = GroqAdapter()
    with pytest.raises(RateLimitExceededError):
        await adapter.complete(system_prompt="s", user_prompt="u", max_tokens=10)


@pytest.mark.asyncio(loop_scope="session")
async def test_groq_adapter_raises_without_api_key(monkeypatch):
    from app.llm.adapters import groq_adapter as module

    monkeypatch.setattr(module.get_settings(), "groq_api_key", None)

    adapter = GroqAdapter()
    with pytest.raises(ProviderError):
        await adapter.complete(system_prompt="s", user_prompt="u", max_tokens=10)


@pytest.mark.asyncio(loop_scope="session")
async def test_gemini_adapter_parses_success(monkeypatch):
    from app.llm.adapters import gemini_adapter as module

    monkeypatch.setattr(module.get_settings(), "gemini_api_key", "test-key")
    body = {
        "candidates": [{"content": {"parts": [{"text": '{"ok"'}, {"text": ": true}"}]}}],
        "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 8},
    }
    response = httpx.Response(200, json=body, request=httpx.Request("POST", "https://example.com"))
    capture = _patch_client(monkeypatch, module, response)

    adapter = GeminiAdapter()
    result = await adapter.complete(
        system_prompt="sys", user_prompt="user", max_tokens=100, json_mode=True
    )

    assert result.content == '{"ok": true}'
    assert result.tokens_input == 20
    assert result.tokens_output == 8
    sent_payload = capture["json"]
    assert sent_payload["system_instruction"]["parts"][0]["text"] == "sys"
    assert sent_payload["contents"][0]["parts"][0]["text"] == "user"
    assert sent_payload["generationConfig"]["maxOutputTokens"] == 100
    assert sent_payload["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.asyncio(loop_scope="session")
async def test_gemini_adapter_raises_on_429(monkeypatch):
    from app.llm.adapters import gemini_adapter as module

    monkeypatch.setattr(module.get_settings(), "gemini_api_key", "test-key")
    response = httpx.Response(429, text="rate limited", request=httpx.Request("POST", "https://example.com"))
    _patch_client(monkeypatch, module, response)

    adapter = GeminiAdapter()
    with pytest.raises(RateLimitExceededError):
        await adapter.complete(system_prompt="s", user_prompt="u", max_tokens=10)
