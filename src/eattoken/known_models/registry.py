from __future__ import annotations
from eattoken.core.models import ModelInfo

KNOWN_MODELS: dict[str, ModelInfo] = {
    "gpt-4o": ModelInfo(
        model_name="gpt-4o", context_size=128000, rate_limit_rpm=500, recommended_concurrency=20
    ),
    "gpt-4o-mini": ModelInfo(
        model_name="gpt-4o-mini", context_size=128000, rate_limit_rpm=1500, recommended_concurrency=50
    ),
    "gpt-4-turbo": ModelInfo(
        model_name="gpt-4-turbo", context_size=128000, rate_limit_rpm=500, recommended_concurrency=20
    ),
    "claude-sonnet-4": ModelInfo(
        model_name="claude-sonnet-4", context_size=200000, rate_limit_rpm=50, recommended_concurrency=10
    ),
    "claude-3-5-sonnet": ModelInfo(
        model_name="claude-3-5-sonnet", context_size=200000, rate_limit_rpm=50, recommended_concurrency=10
    ),
    "deepseek-chat": ModelInfo(
        model_name="deepseek-chat", context_size=64000, rate_limit_rpm=100, recommended_concurrency=10
    ),
    "gemini-2.0-flash": ModelInfo(
        model_name="gemini-2.0-flash", context_size=1000000, rate_limit_rpm=15, recommended_concurrency=5
    ),
    "gemini-1.5-pro": ModelInfo(
        model_name="gemini-1.5-pro", context_size=2000000, rate_limit_rpm=15, recommended_concurrency=5
    ),
}


def lookup(model_name: str) -> ModelInfo | None:
    return KNOWN_MODELS.get(model_name)
