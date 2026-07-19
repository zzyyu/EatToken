import pytest
from unittest.mock import AsyncMock, patch
from eattoken.providers.anthropic import AnthropicProvider, _result_from_usage
from eattoken.core.models import Capabilities, ProviderType, Turn, RequestResult


@pytest.mark.anyio
async def test_anthropic_detect_capabilities():
    p = AnthropicProvider(api_url="https://api.anthropic.com", api_key="sk-ant", model="claude-sonnet-4")
    caps = await p.detect_capabilities()
    assert caps.provider == ProviderType.anthropic
    assert caps.context_size == 200000


@pytest.mark.anyio
async def test_anthropic_send_success():
    p = AnthropicProvider(api_url="https://api.anthropic.com", api_key="sk-ant", model="claude-sonnet-4")
    fake_result = RequestResult(success=True, prompt_tokens=10, completion_tokens=2, total_tokens=12)
    with patch.object(p, "_do_post", new_callable=AsyncMock, return_value=fake_result):
        result = await p.send(messages=[Turn(role="user", content="hello")], options={})
    assert result.success is True
    assert result.total_tokens == 12


def test_anthropic_count_tokens():
    p = AnthropicProvider(api_url="https://api.anthropic.com", api_key="sk-ant", model="claude-sonnet-4")
    n = p.count_tokens("hello world")
    assert isinstance(n, int)
    assert n > 0


def test_anthropic_format_messages():
    p = AnthropicProvider(api_url="https://api.anthropic.com", api_key="sk-ant", model="claude-sonnet-4")
    turns = [Turn(role="user", content="hi"), Turn(role="assistant", content="bye")]
    out = p.format_messages(turns)
    assert out == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "bye"}]


def test_anthropic_sums_all_api_input_usage_categories():
    result = _result_from_usage({
        "input_tokens": 10,
        "cache_creation_input_tokens": 20,
        "cache_read_input_tokens": 30,
        "output_tokens": 5,
    })
    assert result.prompt_tokens == 60
    assert result.completion_tokens == 5
    assert result.total_tokens == 65
    assert result.cached_tokens == 50
