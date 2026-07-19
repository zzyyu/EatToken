import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient

from eattoken.web.app import create_app
import eattoken.web.routes as routes


class _MockLLMHandler(BaseHTTPRequestHandler):
    prompts: list[str] = []
    model_requests = 0

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path.endswith("/models"):
            type(self).model_requests += 1
            self._json(200, {"object": "list", "data": [{"id": "step-3.7-flash"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        content = payload["messages"][0]["content"]
        type(self).prompts.append(content)
        self._json(
            200,
            {
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        )

    def _json(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def test_auto_detect_adaptive_run_varies_real_outbound_payloads_and_restores_state():
    _MockLLMHandler.prompts = []
    _MockLLMHandler.model_requests = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockLLMHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    routes._active_runs.clear()
    routes._latest_run_id = None

    try:
        base_url = f"http://127.0.0.1:{server.server_port}/v1"
        with TestClient(create_app()) as client:
            started = client.post(
                "/run",
                data={
                    "api_url": base_url,
                    "api_key": "test-key",
                    "provider": "auto",
                    "model": "step-3.7-flash",
                    "target_tokens": "90",
                    "max_input_tokens": "20",
                },
            )
            assert started.status_code == 200
            assert started.json()["detected"]["provider"] == "openai"
            assert started.json()["detected"]["protocol_source"] == "models_endpoint"
            assert started.json()["detected"]["adaptive_concurrency"] is True

            run = None
            for _ in range(100):
                run = client.get("/api/run/current").json()["run"]
                if run and not run["running"]:
                    break
                time.sleep(0.01)

            assert run is not None and run["total_tokens"] >= 90
            assert _MockLLMHandler.model_requests >= 1
            assert len(_MockLLMHandler.prompts) == 3
            assert len(set(_MockLLMHandler.prompts)) == 3
            assert any("language=en" in item["message"] for item in run["logs"])
            assert any("language=zh" in item["message"] for item in run["logs"])
            assert any("Concurrency adjusted | value=2" in item["message"] for item in run["logs"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
