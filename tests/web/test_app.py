from fastapi.testclient import TestClient
from eattoken.web.app import create_app


def test_dashboard_returns_html():
    client = TestClient(create_app())
    resp = client.get("/")
    assert resp.status_code == 200
    assert "EatToken" in resp.text
    assert "app.js" in resp.text
    assert 'window.__I18N__ = {"en":' in resp.text
    assert '"zh":' in resp.text
    assert 'class="app-layout"' in resp.text
    assert 'class="runtime-panel"' in resp.text
    assert resp.text.index('name="target_tokens"') < resp.text.index('name="api_url"')
    assert 'name="target_tokens" type="number"' in resp.text
    assert 'name="api_url" placeholder="https://api.openai.com/v1" data-i18n-placeholder="placeholder_api_url" required' in resp.text
    assert 'name="api_key" type="password" placeholder="sk-..." data-i18n-placeholder="placeholder_api_key" required' in resp.text
    assert 'name="model" placeholder="gpt-4o" data-i18n-placeholder="placeholder_model" required' in resp.text
    assert 'name="max_input_tokens" type="number" value="1024"' in resp.text
    assert 'name="max_output_tokens" type="number" value="256"' in resp.text
    assert 'name="request_timeout_seconds" type="number" value="30"' in resp.text
    assert 'id="stat-in-flight"' in resp.text
    assert 'data-i18n="form_saved_local"' in resp.text
    assert '<option value="auto" data-i18n="provider_auto" selected>' in resp.text
    assert resp.text.index('data-i18n="advanced_options"') < resp.text.index('name="max_input_tokens"')


def test_dashboard_assets_include_split_layout_and_infinite_progress():
    client = TestClient(create_app())
    css = client.get("/static/style.css")
    js = client.get("/static/app.js")
    assert css.status_code == 200
    assert "grid-template-columns" in css.text
    assert ".progress-bar.is-indeterminate" in css.text
    assert js.status_code == 200
    assert 'classList.toggle("is-indeterminate", isInfinite)' in js.text
    assert 'textContent = hasTarget ? pct.toFixed(1) + "%" : "∞"' in js.text
    assert 'fetch("/api/run/current")' in js.text
    assert "appendServerLogs(data.logs)" in js.text
    assert 'placeholder_max_input: "1024 tokens per request"' in js.text
    assert 'placeholder_max_input: "每个请求期望服务端实际收到 1024 Token"' in js.text
    assert 'progress_prompt: "实际输入 Token"' in js.text
    assert "Provider credits are billing units" in js.text
    assert 'const FORM_STORAGE_KEY = "eattoken-form-config-v1"' in js.text
    assert "localStorage.setItem(FORM_STORAGE_KEY" in js.text
    assert "restoreSavedForm();" in js.text
