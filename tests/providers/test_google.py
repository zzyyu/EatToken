import pytest
from unittest.mock import AsyncMock, patch
from eattoken.providers.google import GoogleProvider, _result_from_usage
from eattoken.core.models import Capabilities, ProviderType, Turn, RequestResult


@pytest.mark.anyio
async def test_google_detect_capabilities():
    p = GoogleProvider(api_url="https://generativelanguage.googleapis.com", api_key="key", model="gemini-2.0-flash")
    caps = await p.detect_capabilities()
    assert caps.provider == ProviderType.google
    assert caps.context_size == 1000000


@pytest.mark.anyio
async def test_google_send_success():
    p = GoogleProvider(api_url="https://generativelanguage.googleapis.com", api_key="key", model="gemini-2.0-flash")
    fake_result = RequestResult(success=True, prompt_tokens=10, completion_tokens=2, total_tokens=12)
    with patch.object(p, "_do_post", new_callable=AsyncMock, return_value=fake_result):
        result = await p.send(messages=[Turn(role="user", content="hello")], options={})
    assert result.success is True
    assert result.total_tokens == 12


def test_google_count_tokens():
    p = GoogleProvider(api_url="https://generativelanguage.googleapis.com", api_key="key", model="gemini-2.0-flash")
    n = p.count_tokens("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_google_format_messages():
    p = GoogleProvider(api_url="https://generativelanguage.googleapis.com", api_key="key", model="gemini-2.0-flash")
    turns = [Turn(role="user", content="hi"), Turn(role="assistant", content="bye")]
    out = p.format_messages(turns)
    assert out == [{"role": "user", "parts": [{"text": "hi"}]}, {"role": "assistant", "parts": [{"text": "bye"}]}]


def test_google_uses_all_api_usage_metadata_fields():
    result = _result_from_usage({
        "promptTokenCount": 100,
        "candidatesTokenCount": 20,
        "thoughtsTokenCount": 30,
        "cachedContentTokenCount": 40,
        "totalTokenCount": 150,
    })
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (100, 20, 150)
    assert (result.cached_tokens, result.reasoning_tokens) == (40, 30)
