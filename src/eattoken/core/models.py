from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class ProviderType(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"


@dataclass
class ModelInfo:
    model_name: str
    context_size: int
    rate_limit_rpm: int
    recommended_concurrency: int


@dataclass
class Capabilities:
    provider: ProviderType
    model: str
    context_size: int
    rate_limit_rpm: int
    recommended_concurrency: int | None = None
    supports_streaming: bool = True
    context_source: str = "fallback"
    concurrency_source: str = "fallback"


@dataclass
class Turn:
    role: str
    content: str


@dataclass
class RequestMetadata:
    request_id: int
    input_tokens: int
    local_estimated_input_tokens: int
    language: str
    topic: str


@dataclass
class RequestResult:
    success: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    error: str | None = None
    latency_ms: float = 0.0
    request_id: int = 0
    requested_input_tokens: int = 0
    prompt_language: str = ""
    prompt_topic: str = ""
