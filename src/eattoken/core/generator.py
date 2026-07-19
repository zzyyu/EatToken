from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import yaml

from eattoken.core.models import Turn


@dataclass(frozen=True)
class GeneratedPrompt:
    content: str
    token_count: int
    language: str
    topic: str


class Generator:
    """Build traceable, varied prompts for benign API throughput testing."""

    def __init__(self, counter, context_size: int, language: str = "mixed"):
        self.counter = counter
        self.context_size = context_size
        self.language = language
        config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.questions = cfg.get("question_pool", {})
        self.topics = cfg.get("topics", {})
        self.fillers = cfg.get("filler_pool", {})

    def _language_for(self, request_id: int) -> str:
        if self.language in {"en", "zh"}:
            return self.language
        return "zh" if request_id % 2 == 0 else "en"

    def build(self, target_tokens: int, request_id: int) -> GeneratedPrompt:
        # The provider tokenizer may differ from the local estimator. Engine
        # calibrates the target after observing real usage, so the local target
        # can legitimately be larger than the provider context number.
        target = max(1, target_tokens)
        language = self._language_for(request_id)
        questions = self.questions.get(language, []) or ["Discuss {topic} in detail."]
        topics = self.topics.get(language, []) or ["technology"]
        fillers = self.fillers.get(language, []) or [
            "Cover definitions, examples, trade-offs, edge cases, and future directions."
        ]
        topic = topics[(request_id - 1) % len(topics)]
        question = questions[((request_id - 1) // len(topics)) % len(questions)]
        trace = (
            f"{request_id}| Benign API throughput test. "
            if language == "en"
            else f"{request_id}| 正常 API 吞吐测试。"
        )
        prompt = trace + question.format(topic=topic)
        filler_index = request_id % len(fillers)
        while self.counter.count_tokens(prompt) < target:
            candidate = prompt + " " + fillers[filler_index % len(fillers)]
            if self.counter.count_tokens(candidate) > target:
                break
            prompt = candidate
            filler_index += 1

        if self.counter.count_tokens(prompt) > target:
            prompt = self._truncate_to_tokens(prompt, target)
        elif self.counter.count_tokens(prompt) < target:
            # Character-level padding gives counters with coarse token estimates a
            # chance to approach the requested size without exceeding it.
            seed = fillers[filler_index % len(fillers)]
            remaining = seed
            while remaining:
                low, high = 0, len(remaining)
                while low < high:
                    mid = (low + high + 1) // 2
                    candidate = prompt + " " + remaining[:mid]
                    if self.counter.count_tokens(candidate) <= target:
                        low = mid
                    else:
                        high = mid - 1
                if low == 0:
                    break
                prompt += " " + remaining[:low]
                remaining = remaining[low:]

        return GeneratedPrompt(
            content=prompt,
            token_count=self.counter.count_tokens(prompt),
            language=language,
            topic=topic,
        )

    def _truncate_to_tokens(self, text: str, target: int) -> str:
        low, high = 1, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if self.counter.count_tokens(text[:mid]) <= target:
                low = mid
            else:
                high = mid - 1
        return text[:low]

    def fill(self, already_used: int) -> list[Turn]:
        remaining = self.context_size - already_used
        if remaining <= 0:
            return []
        generated = self.build(remaining, request_id=1)
        return [Turn(role="user", content=generated.content)]
