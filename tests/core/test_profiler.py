import pytest
from unittest.mock import AsyncMock
from eattoken.core.profiler import Profiler
from eattoken.core.models import ProviderType, Capabilities, RequestResult, Turn
from eattoken.providers.base import Provider


class FakeProvider(Provider):
    def __init__(self, fail_with_rate_limit: bool = False):
        super().__init__(api_url="http://x", api_key="k", model="m")
        self.fail_with_rate_limit = fail_with_rate_limit
        self.calls = 0
    async def detect_capabilities(self) -> Capabilities:
        return Capabilities(provider=ProviderType.openai, model=self.model, context_size=100, rate_limit_rpm=60)
    async def send(self, messages, options):
        self.calls += 1
        if self.fail_with_rate_limit and self.calls >= 3:
            return RequestResult(success=False, error="rate limit exceeded")
        return RequestResult(success=True, total_tokens=1)
    def count_tokens(self, text):
        return len(text)
    def format_messages(self, turns):
        return turns


@pytest.mark.anyio
async def test_profiler_stops_on_rate_limit():
    provider = FakeProvider(fail_with_rate_limit=True)
    profiler = Profiler(provider=provider)
    result = await profiler.probe_concurrency(max_workers=20)
    assert result.safe_concurrency <= 20
