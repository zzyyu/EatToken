import pytest
from eattoken.core.generator import Generator
from eattoken.core.models import Turn


class FakeCounter:
    def count_tokens(self, text):
        return max(1, len(text) // 4)


def test_generator_produces_messages():
    gen = Generator(counter=FakeCounter(), context_size=100)
    turns = gen.fill(already_used=10)
    total = sum(t.content.count(" ") + 1 for t in turns)
    assert len(turns) > 0


def test_generator_rotates_language_topic_and_trace_id():
    gen = Generator(counter=FakeCounter(), context_size=200, language="mixed")
    first = gen.build(target_tokens=100, request_id=1)
    second = gen.build(target_tokens=100, request_id=2)

    assert first.language == "en"
    assert second.language == "zh"
    assert first.topic != second.topic
    assert first.content.startswith("1|")
    assert second.content.startswith("2|")
    assert first.content != second.content
    assert first.token_count <= 100
    assert second.token_count <= 100
