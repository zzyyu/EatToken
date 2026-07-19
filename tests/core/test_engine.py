import pytest
import asyncio
from unittest.mock import AsyncMock
from eattoken.core.engine import Engine
from eattoken.core.models import ProviderType, Capabilities, RequestResult, Turn
from eattoken.providers.base import Provider


class FakeProvider(Provider):
    async def detect_capabilities(self) -> Capabilities:
        return Capabilities(provider=ProviderType.openai, model=self.model, context_size=100, rate_limit_rpm=60)
    async def send(self, messages, options):
        return RequestResult(success=True, total_tokens=10)
    def count_tokens(self, text):
        return len(text)
    def format_messages(self, turns):
        return turns


@pytest.mark.anyio
async def test_engine_runs_with_concurrency():
    provider = FakeProvider(api_url="http://x", api_key="k", model="m")
    engine = Engine(provider=provider, concurrency=2, target_tokens=50)
    summary = await engine.run()
    assert summary.total_tokens >= 50
    assert summary.total_requests >= 5


class TrackingProvider(FakeProvider):
    def __init__(self):
        super().__init__(api_url="http://x", api_key="k", model="m")
        self.active = 0
        self.max_active = 0
        self.prompt_sizes = []
        self.prompts = []

    async def send(self, messages, options):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.prompt_sizes.append(self.count_tokens(messages[0].content))
        self.prompts.append(messages[0].content)
        await asyncio.sleep(0.01)
        self.active -= 1
        return RequestResult(success=True, total_tokens=self.prompt_sizes[-1])


@pytest.mark.anyio
async def test_engine_honors_limits_and_does_not_launch_fixed_twenty_requests():
    provider = TrackingProvider()
    engine = Engine(
        provider=provider,
        concurrency=3,
        target_tokens=100,
        context_size=1000,
        max_input_tokens=40,
        max_output_tokens=1,
    )
    summary = await engine.run()
    assert summary.stop_reason == "target_reached"
    assert summary.total_requests < 20
    assert provider.max_active <= 3
    assert max(provider.prompt_sizes) <= 40
    assert len(set(provider.prompts[:3])) == 3


@pytest.mark.anyio
async def test_engine_runs_until_explicitly_stopped_without_target():
    provider = TrackingProvider()
    engine = Engine(provider=provider, concurrency=2, context_size=100, max_input_tokens=10)
    task = asyncio.create_task(engine.run())
    while engine.summary.total_requests < 2:
        await asyncio.sleep(0.01)
    engine.stop()
    summary = await task
    assert summary.stop_reason == "stopped"
    assert summary.total_requests >= 2


@pytest.mark.anyio
async def test_adaptive_concurrency_starts_at_one_and_increases():
    provider = TrackingProvider()
    changes = []
    engine = Engine(
        provider=provider,
        concurrency=3,
        adaptive_concurrency=True,
        target_tokens=120,
        context_size=100,
        max_input_tokens=20,
        on_concurrency_change=lambda value, reason: changes.append((value, reason)),
    )
    summary = await engine.run()

    assert summary.stop_reason == "target_reached"
    assert (2, "probe_succeeded") in changes
    assert provider.max_active >= 2


@pytest.mark.anyio
async def test_dispatch_callback_runs_before_completion_with_metadata():
    provider = TrackingProvider()
    dispatched = []
    completed = []
    engine = Engine(
        provider=provider,
        concurrency=2,
        target_tokens=40,
        context_size=100,
        max_input_tokens=20,
        on_dispatch=lambda metadata: dispatched.append(metadata),
        on_progress=lambda result, elapsed: completed.append(result),
    )
    await engine.run()

    assert [item.request_id for item in dispatched] == [1, 2]
    assert {item.language for item in dispatched} == {"en", "zh"}
    assert {item.request_id for item in completed} == {1, 2}


class LanguageSkewProvider(FakeProvider):
    def __init__(self):
        super().__init__(api_url="http://x", api_key="k", model="m")
        self.zh_prompt_sizes = []

    async def send(self, messages, options):
        prompt = messages[0].content
        local_size = self.count_tokens(prompt)
        is_zh = "正常 API 吞吐测试" in prompt
        if is_zh:
            self.zh_prompt_sizes.append(local_size)
        provider_prompt_tokens = local_size // 2 if is_zh else local_size
        return RequestResult(
            success=True,
            prompt_tokens=provider_prompt_tokens,
            total_tokens=provider_prompt_tokens,
        )


@pytest.mark.anyio
async def test_engine_calibrates_each_language_from_provider_usage():
    provider = LanguageSkewProvider()
    engine = Engine(
        provider=provider,
        concurrency=1,
        target_tokens=100,
        context_size=100,
        max_input_tokens=20,
    )

    summary = await engine.run()

    assert summary.prompt_tokens >= 100
    assert len(provider.zh_prompt_sizes) >= 2
    assert provider.zh_prompt_sizes[1] > provider.zh_prompt_sizes[0]


class HangingProvider(FakeProvider):
    async def send(self, messages, options):
        await asyncio.sleep(1)
        return RequestResult(success=True, total_tokens=1)


@pytest.mark.anyio
async def test_engine_reports_waiting_and_times_out_hung_request():
    provider = HangingProvider(api_url="http://x", api_key="k", model="m")
    waits = []
    engine = Engine(
        provider=provider,
        concurrency=1,
        target_tokens=1,
        on_wait=lambda metadata, elapsed: waits.append((metadata.request_id, elapsed)),
        request_timeout_seconds=0.04,
        wait_log_interval_seconds=0.01,
    )
    summary = await engine.run()

    assert waits
    assert waits[0][0] == 1
    assert summary.stop_reason == "request_failed"
    assert summary.failed_requests == 1
    assert "timed out after" in (summary.last_error or "")
