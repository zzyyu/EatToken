from click.testing import CliRunner
from eattoken.cli.main import cli


def test_run_with_mocked_provider(monkeypatch):
    from eattoken.core.models import RequestResult
    captured = {}

    class FakeProvider:
        def __init__(self, api_url, api_key, model):
            self.api_url = api_url
            self.api_key = api_key
            self.model = model
        async def detect_capabilities(self):
            from eattoken.core.models import Capabilities, ProviderType
            return Capabilities(provider=ProviderType.openai, model=self.model, context_size=100, rate_limit_rpm=60)
        async def send(self, messages, options):
            captured["calls"] = captured.get("calls", 0) + 1
            return RequestResult(success=True, total_tokens=1)
        def count_tokens(self, text):
            return len(text)
        def format_messages(self, turns):
            return turns

    import eattoken.providers.factory as factory_mod
    monkeypatch.setattr(factory_mod, "OpenAIProvider", FakeProvider)

    runner = CliRunner()
    result = runner.invoke(cli, [
        "run",
        "--api-url", "http://x",
        "--api-key", "k",
        "--provider", "openai",
        "--model", "gpt-4o",
        "--concurrency", "2",
        "--target-tokens", "3",
        "--max-input-tokens", "2",
    ])
    assert result.exit_code == 0
    assert captured.get("calls", 0) > 0
    assert "Request #1" in result.output
