from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from eattoken.core.generator import Generator
from eattoken.core.models import RequestMetadata, RequestResult, Turn
from eattoken.providers.base import Provider


@dataclass
class EngineSummary:
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_error: str | None = None
    stop_reason: str | None = None


ProgressCallback = Callable[[RequestResult, float], None]
DispatchCallback = Callable[[RequestMetadata], None]
ConcurrencyCallback = Callable[[int, str], None]
WaitCallback = Callable[[RequestMetadata, float], None]


class Engine:
    """Run bounded waves of requests until a target is reached or stop is called."""

    def __init__(
        self,
        provider: Provider,
        concurrency: int,
        target_tokens: int | None = None,
        on_progress: ProgressCallback | None = None,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        context_size: int | None = None,
        adaptive_concurrency: bool = False,
        on_dispatch: DispatchCallback | None = None,
        on_concurrency_change: ConcurrencyCallback | None = None,
        on_wait: WaitCallback | None = None,
        request_timeout_seconds: float = 30.0,
        wait_log_interval_seconds: float = 5.0,
    ):
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if target_tokens is not None and target_tokens < 1:
            raise ValueError("target_tokens must be at least 1")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be greater than 0")
        if wait_log_interval_seconds <= 0:
            raise ValueError("wait_log_interval_seconds must be greater than 0")

        self.provider = provider
        self.concurrency = concurrency
        self.target_tokens = target_tokens
        self.summary = EngineSummary()
        self._on_progress = on_progress
        self._max_input = max_input_tokens
        self._max_output = max_output_tokens
        self._context_size = context_size or getattr(provider, "_last_context_size", 8192)
        self._adaptive_concurrency = adaptive_concurrency
        self._on_dispatch = on_dispatch
        self._on_concurrency_change = on_concurrency_change
        self._on_wait = on_wait
        self._request_timeout = request_timeout_seconds
        self._wait_log_interval = wait_log_interval_seconds
        self._generator = Generator(provider, context_size=self._context_size, language="mixed")
        self._request_sequence = 0
        self._token_ratio_by_language: dict[str, float] = {"en": 1.0, "zh": 1.0}
        self._stop_event = asyncio.Event()
        self._active_tasks: set[asyncio.Task[RequestResult]] = set()

    def stop(self) -> None:
        """Request a prompt stop and cancel requests that are still in flight."""
        self._stop_event.set()
        for task in tuple(self._active_tasks):
            task.cancel()

    async def _fire(self, messages: Sequence[Turn], metadata: RequestMetadata) -> RequestResult:
        options: dict[str, int] = {}
        if self._max_output is not None:
            options["max_tokens"] = self._max_output

        started = time.monotonic()
        request_task: asyncio.Task[RequestResult] | None = None
        try:
            if self._on_dispatch is not None:
                self._on_dispatch(metadata)
            request_task = asyncio.create_task(self.provider.send(list(messages), options=options))
            deadline = started + self._request_timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    request_task.cancel()
                    await asyncio.gather(request_task, return_exceptions=True)
                    result = RequestResult(
                        success=False,
                        error=f"request timed out after {self._request_timeout:g}s",
                    )
                    break
                done, _ = await asyncio.wait(
                    {request_task},
                    timeout=min(self._wait_log_interval, remaining),
                )
                if done:
                    result = await request_task
                    break
                if self._on_wait is not None:
                    self._on_wait(metadata, time.monotonic() - started)
        except asyncio.CancelledError:
            if request_task is not None and not request_task.done():
                request_task.cancel()
                await asyncio.gather(request_task, return_exceptions=True)
            raise
        except Exception as exc:  # Providers should return failures, but plugins may raise.
            result = RequestResult(success=False, error=f"{type(exc).__name__}: {exc}")

        elapsed = time.monotonic() - started
        result.latency_ms = elapsed * 1000
        result.request_id = metadata.request_id
        result.requested_input_tokens = metadata.input_tokens
        result.prompt_language = metadata.language
        result.prompt_topic = metadata.topic
        self.summary.total_requests += 1
        if result.success:
            self.summary.total_tokens += result.total_tokens
            self.summary.prompt_tokens += result.prompt_tokens
            self.summary.completion_tokens += result.completion_tokens
            self.summary.cached_tokens += result.cached_tokens
            self.summary.reasoning_tokens += result.reasoning_tokens
            if metadata.local_estimated_input_tokens > 0 and result.prompt_tokens > 0:
                observed_ratio = result.prompt_tokens / metadata.local_estimated_input_tokens
                previous_ratio = self._token_ratio_by_language[metadata.language]
                self._token_ratio_by_language[metadata.language] = (
                    observed_ratio if previous_ratio == 1.0 else previous_ratio * 0.25 + observed_ratio * 0.75
                )
        else:
            self.summary.failed_requests += 1
            self.summary.last_error = result.error or "request failed"
        if self._on_progress is not None:
            self._on_progress(result, elapsed)
        return result

    async def run(self) -> EngineSummary:
        current_concurrency = 1 if self._adaptive_concurrency else self.concurrency
        failed_waves = 0

        while not self._stop_event.is_set():
            if self.target_tokens is not None:
                remaining = self.target_tokens - self.summary.total_tokens
                if remaining <= 0:
                    self.summary.stop_reason = "target_reached"
                    break
            else:
                remaining = None

            input_cap = self._input_cap()
            request_count = current_concurrency
            if remaining is not None:
                estimated_request = max(1, input_cap + (self._max_output or 0))
                request_count = min(request_count, max(1, math.ceil(remaining / estimated_request)))
                output_reserve = (self._max_output or 0) * request_count
                input_budget = max(1, (remaining - output_reserve) // request_count)
                input_budget = min(input_cap, input_budget)
            else:
                input_budget = input_cap

            before_tokens = self.summary.total_tokens

            tasks: set[asyncio.Task[RequestResult]] = set()
            for _ in range(request_count):
                self._request_sequence += 1
                language = "zh" if self._request_sequence % 2 == 0 else "en"
                ratio = max(0.25, self._token_ratio_by_language[language])
                local_target = max(1, math.ceil(input_budget / ratio))
                generated = self._generator.build(local_target, self._request_sequence)
                metadata = RequestMetadata(
                    request_id=self._request_sequence,
                    input_tokens=input_budget,
                    local_estimated_input_tokens=generated.token_count,
                    language=generated.language,
                    topic=generated.topic,
                )
                messages = [Turn(role="user", content=generated.content)]
                tasks.add(asyncio.create_task(self._fire(messages, metadata)))
            self._active_tasks = tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            self._active_tasks.clear()

            if self._stop_event.is_set():
                self.summary.stop_reason = self.summary.stop_reason or "stopped"
                break

            made_progress = self.summary.total_tokens > before_tokens
            errors = [r.error for r in results if isinstance(r, RequestResult) and not r.success]
            error_text = " ".join(e for e in errors if e).lower()
            rate_limited = "rate" in error_text or "429" in error_text or "too many requests" in error_text

            if rate_limited:
                previous = current_concurrency
                current_concurrency = max(1, current_concurrency // 2)
                if self._on_concurrency_change is not None and current_concurrency != previous:
                    self._on_concurrency_change(current_concurrency, "rate_limited")

            if made_progress:
                failed_waves = 0
                if self._adaptive_concurrency and not rate_limited:
                    previous = current_concurrency
                    current_concurrency = min(self.concurrency, current_concurrency + 1)
                    if self._on_concurrency_change is not None and current_concurrency != previous:
                        self._on_concurrency_change(current_concurrency, "probe_succeeded")
                elif rate_limited:
                    await asyncio.sleep(1.0)
                continue

            failed_waves += 1
            if rate_limited:
                if failed_waves < 3:
                    await asyncio.sleep(float(failed_waves))
                    continue
                self.summary.stop_reason = "rate_limited"
            else:
                self.summary.stop_reason = "request_failed"
            break

        if self.summary.stop_reason is None:
            self.summary.stop_reason = "stopped"
        return self.summary

    def _input_cap(self) -> int:
        context_size = max(1, self._context_size)
        output_reserve = max(0, self._max_output or 0)
        available_input = max(1, context_size - output_reserve)
        if self._max_input is not None:
            return max(1, min(self._max_input, available_input))
        return max(1, int(available_input * 0.8))

    def _build_prompt(self, target_input: int | None = None) -> str:
        """Compatibility helper retained for callers and tests."""
        target = max(1, target_input or self._input_cap())
        return self._generator.build(target, request_id=1).content
