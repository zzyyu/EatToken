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
    supports_streaming: bool = True


@dataclass
class Turn:
    role: str
    content: str


@dataclass
class RequestResult:
    success: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None
    latency_ms: float = 0.0
