import importlib
import subprocess
import sys

def test_package_importable():
    result = subprocess.run(
        [sys.executable, "-c", "import eattoken; print(eattoken.__version__)"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_provider_base_importable():
    from eattoken.providers.base import Provider
    assert issubclass(Provider, Exception) is False


def test_registry_has_known_models():
    from eattoken.known_models.registry import KNOWN_MODELS
    assert "gpt-4o" in KNOWN_MODELS
    assert "claude-sonnet-4" in KNOWN_MODELS
    entry = KNOWN_MODELS["gpt-4o"]
    assert entry.context_size > 0
    assert entry.rate_limit_rpm > 0
