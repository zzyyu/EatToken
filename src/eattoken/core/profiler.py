from __future__ import annotations
import asyncio
from dataclasses import dataclass
from eattoken.core.models import Capabilities, RequestResult, Turn
from eattoken.providers.base import Provider


@dataclass
class ConcurrencyProbeResult:
    tested_workers: int
    safe_concurrency: int
    rate_limit_hit: bool


class Profiler:
    def __init__(self, provider: Provider):
        self.provider = provider

    async def detect_capabilities(self) -> Capabilities:
        return await self.provider.detect_capabilities()

    async def probe_concurrency(self, max_workers: int) -> ConcurrencyProbeResult:
        tested = 0
        safe = 1
        for workers in [1, 2, 5, 10, max_workers]:
            tested = workers
            rate_limit_hit = False
            semaphore = asyncio.Semaphore(workers)

            async def _probe():
                async with semaphore:
                    return await self.provider.send(messages=[Turn(role="user", content="ping")], options={})

            tasks = [asyncio.create_task(_probe()) for _ in range(workers)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    rate_limit_hit = True
                    break
                if isinstance(r, RequestResult) and not r.success and "rate" in (r.error or "").lower():
                    rate_limit_hit = True
                    break
            if rate_limit_hit:
                safe = max(1, workers // 2)
                break
            safe = workers
        return ConcurrencyProbeResult(tested_workers=tested, safe_concurrency=safe, rate_limit_hit=rate_limit_hit)
