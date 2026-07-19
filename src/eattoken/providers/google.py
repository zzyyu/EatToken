from __future__ import annotations
import aiohttp
import tiktoken
from typing import Any
from eattoken.providers.base import Provider
from eattoken.core.models import Capabilities, ProviderType, RequestResult, Turn
from eattoken.known_models.registry import lookup


def _result_from_usage(usage: dict[str, Any]) -> RequestResult:
    prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
    completion_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
    reasoning_tokens = int(usage.get("thoughtsTokenCount", 0) or 0)
    total_tokens = int(usage.get("totalTokenCount", 0) or 0)
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
    return RequestResult(
        success=True,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_tokens=int(usage.get("cachedContentTokenCount", 0) or 0),
        reasoning_tokens=reasoning_tokens,
    )


class GoogleProvider(Provider):
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
                provider=ProviderType.google,
                model=self.model,
                context_size=info.context_size,
                rate_limit_rpm=info.rate_limit_rpm,
                recommended_concurrency=info.recommended_concurrency,
                context_source="registry",
                concurrency_source="registry",
            )
        return Capabilities(
            provider=ProviderType.google,
            model=self.model,
            context_size=1000000,
            rate_limit_rpm=15,
            context_source="fallback",
            concurrency_source="fallback",
        )

    async def _do_post(self, url: str, headers: dict, payload: dict) -> RequestResult:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                body = await resp.json()
                if resp.status != 200:
                    return RequestResult(success=False, error=f"HTTP {resp.status}: {body}")
                return _result_from_usage(body.get("usageMetadata", {}))

    async def send(self, messages: list[Turn], options: dict[str, Any]) -> RequestResult:
        api_key = self.api_key
        base = self.api_url.rstrip("/")
        prefix = base if base.endswith("/v1beta") else f"{base}/v1beta"
        url = f"{prefix}/models/{self.model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": self.format_messages(messages),
        }
        payload.update(options)
        return await self._do_post(url=url, headers=headers, payload=payload)

    def count_tokens(self, text: str) -> int:
        enc = self._get_encoding()
        return len(enc.encode(text))

    def format_messages(self, turns: list[Turn]) -> list[dict]:
        out = []
        for t in turns:
            out.append({"role": t.role, "parts": [{"text": t.content}]})
        return out
