from __future__ import annotations
import asyncio
import aiohttp
import tiktoken
from typing import Any
from eattoken.providers.base import Provider
from eattoken.core.models import Capabilities, ProviderType, RequestResult, Turn
from eattoken.known_models.registry import lookup


def _result_from_usage(usage: dict[str, Any]) -> RequestResult:
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    return RequestResult(
        success=True,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cached_tokens=int(prompt_details.get("cached_tokens", usage.get("cached_tokens", 0)) or 0),
        reasoning_tokens=int(completion_details.get("reasoning_tokens", 0) or 0),
    )


class OpenAIProvider(Provider):
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
                provider=ProviderType.openai,
                model=self.model,
                context_size=info.context_size,
                rate_limit_rpm=info.rate_limit_rpm,
                recommended_concurrency=info.recommended_concurrency,
                context_source="registry",
                concurrency_source="registry",
            )
        return Capabilities(
            provider=ProviderType.openai,
            model=self.model,
            context_size=8192,
            rate_limit_rpm=60,
            context_source="fallback",
            concurrency_source="fallback",
        )

    async def _do_post(self, url: str, headers: dict, payload: dict) -> RequestResult:
        timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=600)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    try:
                        body = await resp.json()
                    except (aiohttp.ContentTypeError, ValueError):
                        body = {"error": {"message": await resp.text()}}
                    if resp.status != 200:
                        return RequestResult(
                            success=False,
                            error=f"HTTP {resp.status}: {body.get('error', {}).get('message', str(body))}",
                        )
                    return _result_from_usage(body.get("usage", {}))
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return RequestResult(success=False, error=f"{type(exc).__name__}: {exc}")

    async def send(self, messages: list[Turn], options: dict[str, Any]) -> RequestResult:
        url = f"{self.api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": self.format_messages(messages),
            "stream": False,
        }
        payload.update(options)
        return await self._do_post(url=url, headers=headers, payload=payload)

    def count_tokens(self, text: str) -> int:
        enc = self._get_encoding()
        return len(enc.encode(text))

    def format_messages(self, turns: list[Turn]) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in turns]
