from __future__ import annotations
import aiohttp
import tiktoken
from typing import Any
from eattoken.providers.base import Provider
from eattoken.core.models import Capabilities, ProviderType, RequestResult, Turn
from eattoken.known_models.registry import lookup


def _result_from_usage(usage: dict[str, Any]) -> RequestResult:
    uncached_input = int(usage.get("input_tokens", 0) or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    prompt_tokens = uncached_input + cache_creation + cache_read
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    return RequestResult(
        success=True,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cached_tokens=cache_creation + cache_read,
    )


class AnthropicProvider(Provider):
    def __init__(self, api_url: str, api_key: str, model: str):
        super().__init__(api_url=api_url, api_key=api_key, model=model)
        self._encoding = None

    def _get_encoding(self):
        if self._encoding is None:
            try:
                self._encoding = tiktoken.encoding_for_model(self.model)
            except KeyError:
                self._encoding = tiktoken.get_encoding("cl100k_base")
        return self._encoding

    async def detect_capabilities(self) -> Capabilities:
        info = lookup(self.model)
        if info:
            return Capabilities(
                provider=ProviderType.anthropic,
                model=self.model,
                context_size=info.context_size,
                rate_limit_rpm=info.rate_limit_rpm,
                recommended_concurrency=info.recommended_concurrency,
                context_source="registry",
                concurrency_source="registry",
            )
        return Capabilities(
            provider=ProviderType.anthropic,
            model=self.model,
            context_size=200000,
            rate_limit_rpm=50,
            context_source="fallback",
            concurrency_source="fallback",
        )

    async def _do_post(self, url: str, headers: dict, payload: dict) -> RequestResult:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                body = await resp.json()
                if resp.status != 200:
                    return RequestResult(
                        success=False,
                        error=f"HTTP {resp.status}: {body.get('error', {}).get('message', str(body))}",
                    )
                return _result_from_usage(body.get("usage", {}))

    async def send(self, messages: list[Turn], options: dict[str, Any]) -> RequestResult:
        base = self.api_url.rstrip("/")
        url = f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system = options.pop("system", None)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": self.format_messages(messages),
        }
        if system:
            payload["system"] = system
        payload.update(options)
        return await self._do_post(url=url, headers=headers, payload=payload)

    def count_tokens(self, text: str) -> int:
        enc = self._get_encoding()
        return len(enc.encode(text))

    def format_messages(self, turns: list[Turn]) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in turns]
