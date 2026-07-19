import pytest
from unittest.mock import AsyncMock, patch
from eattoken.providers.openai import OpenAIProvider, _result_from_usage
from eattoken.core.models import Capabilities, ProviderType, Turn, RequestResult


@pytest.mark.anyio
async def test_openai_detect_capabilities_from_registry():
    provider = OpenAIProvider(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
    )
    caps = await provider.detect_capabilities()
    assert caps.provider == ProviderType.openai
    assert caps.model == "gpt-4o"
    assert caps.context_size == 128000
    assert caps.rate_limit_rpm == 500


@pytest.mark.anyio
async def test_openai_send_returns_usage():
    provider = OpenAIProvider(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
    )
    fake_result = RequestResult(success=True, prompt_tokens=10, completion_tokens=2, total_tokens=12)
    with patch.object(provider, "_do_post", new_callable=AsyncMock, return_value=fake_result):
        result = await provider.send(
            messages=[Turn(role="user", content="hello")],
            options={},
        )
    assert result.success is True
    assert result.total_tokens == 12


def test_openai_count_tokens():
    provider = OpenAIProvider(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
    )
    n = provider.count_tokens("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_openai_format_messages():
    provider = OpenAIProvider(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
    )
    turns = [Turn(role="user", content="hi"), Turn(role="assistant", content="bye")]
    out = provider.format_messages(turns)
    assert out == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "bye"}]


def test_openai_uses_api_usage_values():
    result = _result_from_usage({
        "prompt_tokens": 101,
        "completion_tokens": 23,
        "total_tokens": 124,
        "prompt_tokens_details": {"cached_tokens": 40},
        "completion_tokens_details": {"reasoning_tokens": 7},
    })
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (101, 23, 124)
    assert (result.cached_tokens, result.reasoning_tokens) == (40, 7)
