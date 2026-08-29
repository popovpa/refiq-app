import httpx
import pytest

from app.modules.ai.generation import StructuredGenerationRequest, TextGenerationRequest
from app.modules.ai.providers.deepseek_text import DeepSeekTextGenerationProvider
from app.modules.ai.providers.selection import promo_text_model, text_provider_name


def _request() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        system_prompt="Return JSON.",
        user_prompt="brief",
        schema={"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False},
        schema_name="promo_brief",
        operation="PROMO_BRIEF_GENERATE",
        prompt_version="promo-brief-v3",
        model="deepseek-v4-pro",
        reasoning_effort="high",
    )


def _client(monkeypatch, handler):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *args, **kwargs):
            return handler(url, kwargs.get("headers") or {}, kwargs.get("json") or {})

    monkeypatch.setattr("app.modules.ai.providers.deepseek_text.httpx.AsyncClient", FakeAsyncClient)


def test_deepseek_default_models(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_TEXT_PROVIDER", "deepseek")
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    assert text_provider_name() == "deepseek"
    assert promo_text_model() == "deepseek-v4-pro"
    assert promo_text_model(fast=True) == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_deepseek_structured_request_shape(monkeypatch):
    captured: dict = {}

    def handler(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = payload
        return httpx.Response(
            200,
            json={
                "id": "ds-1",
                "model": "deepseek-v4-pro",
                "choices": [{"message": {"content": '{"a":"ok"}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12},
            },
        )

    _client(monkeypatch, handler)
    provider = DeepSeekTextGenerationProvider(
        api_key="sk-deepseek-test",
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        max_retries=0,
    )
    result = await provider.generate_structured(_request())
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-deepseek-test"
    assert captured["json"]["model"] == "deepseek-v4-pro"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["thinking"] == {"type": "enabled"}
    assert captured["json"]["reasoning_effort"] == "high"
    assert '"a"' in captured["json"]["messages"][0]["content"]
    assert result.provider == "deepseek"
    assert result.structured_data == {"a": "ok"}
    assert result.usage.input_tokens == 9


@pytest.mark.asyncio
async def test_deepseek_parses_fenced_json(monkeypatch):
    def handler(url, headers, payload):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "```json\n{\"a\":\"ok\"}\n```"}}]},
        )

    _client(monkeypatch, handler)
    provider = DeepSeekTextGenerationProvider(api_key="sk-test", max_retries=0)
    result = await provider.generate_structured(_request())
    assert result.structured_data == {"a": "ok"}


@pytest.mark.asyncio
async def test_deepseek_malformed_json(monkeypatch):
    def handler(url, headers, payload):
        return httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]})

    _client(monkeypatch, handler)
    provider = DeepSeekTextGenerationProvider(api_key="sk-test", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate_structured(_request())
    assert exc.value.code == "AI_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_deepseek_timeout(monkeypatch):
    def handler(url, headers, payload):
        raise httpx.TimeoutException("timeout")

    _client(monkeypatch, handler)
    provider = DeepSeekTextGenerationProvider(api_key="sk-test", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate(TextGenerationRequest("s", "u", "X", "v1"))
    assert exc.value.code == "AI_TIMEOUT"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [(401, "AI_UNAUTHORIZED"), (403, "AI_UNAUTHORIZED"), (429, "AI_RATE_LIMIT"), (500, "AI_UNAVAILABLE")])
async def test_deepseek_http_errors(monkeypatch, status, code):
    def handler(url, headers, payload):
        return httpx.Response(status, json={"error": {"message": "denied", "code": "auth", "type": "auth"}})

    _client(monkeypatch, handler)
    provider = DeepSeekTextGenerationProvider(api_key="sk-test", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate_structured(_request())
    assert exc.value.code == code


@pytest.mark.asyncio
async def test_deepseek_invalid_model(monkeypatch):
    def handler(url, headers, payload):
        return httpx.Response(
            400,
            json={"error": {"message": "Model not found", "code": "model_not_found", "type": "invalid_request_error"}},
        )

    _client(monkeypatch, handler)
    provider = DeepSeekTextGenerationProvider(api_key="sk-test", max_retries=0)
    with pytest.raises(Exception) as exc:
        await provider.generate_structured(_request())
    assert exc.value.code == "AI_MODEL_UNAVAILABLE"

