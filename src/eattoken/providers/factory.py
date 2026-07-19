from __future__ import annotations
import asyncio
from dataclasses import dataclass

import aiohttp

from eattoken.providers.base import Provider
from eattoken.providers.openai import OpenAIProvider
from eattoken.providers.anthropic import AnthropicProvider
from eattoken.providers.google import GoogleProvider
from eattoken.core.models import ProviderType


@dataclass(frozen=True)
class ProviderDetection:
    provider: ProviderType
    source: str


async def _probe_get(url: str, headers: dict[str, str]) -> int | None:
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                await response.read()
                return response.status
    except (aiohttp.ClientError, TimeoutError):
        return None


def _models_url(api_url: str, provider: ProviderType, api_key: str) -> tuple[str, dict[str, str]]:
    base = api_url.rstrip("/")
    if provider == ProviderType.openai:
        return f"{base}/models", {"Authorization": f"Bearer {api_key}"}
    if provider == ProviderType.anthropic:
        prefix = base if base.endswith("/v1") else f"{base}/v1"
        return f"{prefix}/models", {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    prefix = base if base.endswith("/v1beta") else f"{base}/v1beta"
    return f"{prefix}/models?key={api_key}", {}


def _heuristic_provider(api_url: str, model: str) -> ProviderDetection:
    haystack = f"{api_url} {model}".lower()
    if any(marker in haystack for marker in ("anthropic", "claude")):
        return ProviderDetection(ProviderType.anthropic, "name_heuristic")
    if any(marker in haystack for marker in ("generativelanguage", "gemini", "googleapis")):
        return ProviderDetection(ProviderType.google, "name_heuristic")
    return ProviderDetection(ProviderType.openai, "fallback")


async def detect_provider(api_url: str, api_key: str, model: str) -> ProviderDetection:
    """Detect protocol with non-consuming model-list requests, then safe heuristics."""
    heuristic = _heuristic_provider(api_url, model)
    order = [heuristic.provider] + [p for p in ProviderType if p != heuristic.provider]
    probes = []
    for candidate in order:
        url, headers = _models_url(api_url, candidate, api_key)
        probes.append(_probe_get(url, headers))
    statuses = await asyncio.gather(*probes)
    for candidate, status in zip(order, statuses):
        if status == 200:
            return ProviderDetection(candidate, "models_endpoint")
    return heuristic


def create_provider(provider: ProviderType, api_url: str, api_key: str, model: str) -> Provider:
    if provider == ProviderType.openai:
        return OpenAIProvider(api_url=api_url, api_key=api_key, model=model)
    if provider == ProviderType.anthropic:
        return AnthropicProvider(api_url=api_url, api_key=api_key, model=model)
    if provider == ProviderType.google:
        return GoogleProvider(api_url=api_url, api_key=api_key, model=model)
    raise ValueError(f"Unsupported provider: {provider}")
