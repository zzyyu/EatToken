from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from eattoken.core.models import Capabilities, Turn, RequestResult


class Provider(ABC):
    def __init__(self, api_url: str, api_key: str, model: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def detect_capabilities(self) -> Capabilities:
        ...

    @abstractmethod
    async def send(self, messages: list[Turn], options: dict[str, Any]) -> RequestResult:
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        ...

    @abstractmethod
    def format_messages(self, turns: list[Turn]) -> list[dict]:
        ...
