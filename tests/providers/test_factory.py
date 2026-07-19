import pytest

import eattoken.providers.factory as factory
from eattoken.core.models import ProviderType


@pytest.mark.anyio
async def test_detect_provider_uses_models_endpoint_without_chat_request(monkeypatch):
    calls = []

    async def fake_probe(url, headers):
        calls.append(url)
        return 200 if url == "https://example.test/v1/models" else 404

    monkeypatch.setattr(factory, "_probe_get", fake_probe)
    detected = await factory.detect_provider(
        "https://example.test/v1", "secret", "step-3.7-flash"
    )

    assert detected.provider == ProviderType.openai
    assert detected.source == "models_endpoint"
    assert all("chat/completions" not in url and ":generateContent" not in url for url in calls)


@pytest.mark.anyio
async def test_detect_provider_falls_back_to_model_name(monkeypatch):
    async def unavailable(url, headers):
        return None

    monkeypatch.setattr(factory, "_probe_get", unavailable)
    detected = await factory.detect_provider("https://proxy.test", "secret", "claude-sonnet")

    assert detected.provider == ProviderType.anthropic
    assert detected.source == "name_heuristic"
