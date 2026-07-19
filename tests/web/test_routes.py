from fastapi.testclient import TestClient
from eattoken.web.app import create_app
from eattoken.core.models import Capabilities, ProviderType, RequestResult
import time


def test_run_post_returns_run_id():
    client = TestClient(create_app())
    resp = client.post("/run", data={
        "api_url": "http://x",
        "api_key": "k",
        "provider": "openai",
        "model": "gpt-4o",
        "concurrency": "1",
    })
    assert resp.status_code == 200
    assert "run_id" in resp.text


def test_run_rejects_missing_credentials():
    client = TestClient(create_app())
    resp = client.post("/run", data={"provider": "openai", "model": "gpt-4o"})
    assert resp.status_code == 400


def test_stop_rejects_unknown_run():
    client = TestClient(create_app())
    resp = client.post("/stop/does-not-exist")
    assert resp.status_code == 404


def test_backend_logs_are_mirrored_to_terminal(monkeypatch):
    import eattoken.web.routes as routes

    terminal_messages = []
    monkeypatch.setattr(
        routes._terminal_logger,
        "info",
        lambda message, *args: terminal_messages.append(message % args),
    )
    state = {"id": "1234567890", "next_log_id": 1, "logs": []}

    routes._append_log(state, "Request #1 SENDING")

    assert terminal_messages == ["[EatToken run=12345678] Request #1 SENDING"]


def test_current_run_restores_backend_stats_config_and_request_logs(monkeypatch):
    import eattoken.web.routes as routes

    class FakeProvider:
        async def detect_capabilities(self):
            return Capabilities(
                provider=ProviderType.openai,
                model="gpt-4o",
                context_size=100,
                rate_limit_rpm=60,
                recommended_concurrency=1,
            )

        async def send(self, messages, options):
            return RequestResult(
                success=True,
                prompt_tokens=8,
                completion_tokens=2,
                total_tokens=10,
            )

        def count_tokens(self, text):
            return len(text)

    routes._active_runs.clear()
    routes._latest_run_id = None
    monkeypatch.setattr(routes, "create_provider", lambda **kwargs: FakeProvider())

    with TestClient(create_app()) as client:
        started = client.post("/run", data={
            "api_url": "http://fake/v1",
            "api_key": "secret-not-returned",
            "provider": "openai",
            "model": "gpt-4o",
            "target_tokens": "20",
            "max_input_tokens": "8",
            "max_output_tokens": "2",
            "concurrency": "1",
        })
        assert started.status_code == 200

        run = None
        for _ in range(100):
            run = client.get("/api/run/current").json()["run"]
            if run and not run["running"]:
                break
            time.sleep(0.01)

        assert run is not None
        assert run["total_tokens"] >= 20
        assert run["prompt_tokens"] >= 16
        assert run["completion_tokens"] >= 4
        assert run["cached_tokens"] == 0
        assert run["reasoning_tokens"] == 0
        assert run["config"]["target_tokens"] == 20
        assert run["config"]["api_url"] == "http://fake/v1"
        assert "api_key" not in run["config"]
        assert any("Capabilities | protocol=openai" in entry["message"] for entry in run["logs"])
        assert any("Request #1 SENDING" in entry["message"] for entry in run["logs"])
        assert any("target_input=8" in entry["message"] for entry in run["logs"])
        assert any("local_estimate=8" in entry["message"] for entry in run["logs"])
        assert any("Request #1 OK" in entry["message"] for entry in run["logs"])
        assert any("prompt=8" in entry["message"] for entry in run["logs"])
        assert any("Run finished" in entry["message"] for entry in run["logs"])
