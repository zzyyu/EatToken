from __future__ import annotations
import asyncio
import json
import logging
import time
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette import EventSourceResponse
from pathlib import Path
from eattoken.core.engine import Engine, EngineSummary
from eattoken.core.profiler import Profiler
from eattoken.providers.factory import create_provider, detect_provider
from eattoken.core.models import ProviderType, RequestMetadata, RequestResult
from eattoken.i18n import detect_language, _load

router = APIRouter()
_terminal_logger = logging.getLogger("uvicorn.error")

# Global state for active runs (simple in-memory store)
_active_runs: dict[str, dict] = {}
_latest_run_id: str | None = None


def _append_log(state: dict, message: str, level: str = "info") -> None:
    log_id = state["next_log_id"]
    state["next_log_id"] += 1
    state["logs"].append({
        "id": log_id,
        "time": time.strftime("%H:%M:%S"),
        "level": level,
        "message": message,
    })
    if len(state["logs"]) > 2000:
        del state["logs"][:-2000]
    log_method = _terminal_logger.error if level == "error" else _terminal_logger.info
    log_method("[EatToken run=%s] %s", state["id"][:8], message)


def _logs_after(state: dict, after_log_id: int) -> list[dict]:
    return [entry for entry in state["logs"] if entry["id"] > after_log_id]


def _public_state(state: dict, logs: list[dict] | None = None) -> dict:
    summary: EngineSummary = state["summary"]
    finished_at = state.get("end_time") or time.time()
    return {
        "run_id": state["id"],
        "provider": state["provider"],
        "model": state["model"],
        "config": state["config"],
        "running": state["running"],
        "target": state["target_tokens"],
        "total_tokens": summary.total_tokens,
        "prompt_tokens": summary.prompt_tokens,
        "completion_tokens": summary.completion_tokens,
        "cached_tokens": summary.cached_tokens,
        "reasoning_tokens": summary.reasoning_tokens,
        "total_requests": summary.total_requests,
        "failed_requests": summary.failed_requests,
        "in_flight": state.get("in_flight", 0),
        "qps": round(state["qps"], 1),
        "elapsed": round(finished_at - state["start_time"], 1),
        "error": state.get("error") or summary.last_error,
        "stop_reason": summary.stop_reason,
        "logs": state["logs"] if logs is None else logs,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> str:
    lang = detect_language()
    translations = {"en": _load("en"), "zh": _load("zh")}
    base = Path(__file__).resolve().parent
    html = (base / "templates" / "index.html").read_text(encoding="utf-8")
    script = (
        f'<script>'
        f'window.__I18N__ = {json.dumps(translations, ensure_ascii=False)};'
        f'window.__I18N_LANG__ = "{lang}";'
        f'</script>'
    )
    html = html.replace('</head>', f'{script}</head>')
    html = html.replace('<html lang="en">', f'<html lang="{lang}">')
    return html


@router.get("/api/lang")
async def get_lang() -> JSONResponse:
    lang = detect_language()
    return JSONResponse({"lang": lang})


@router.post("/api/lang")
async def set_lang(request: Request) -> JSONResponse:
    body = await request.json()
    lang = body.get("lang", "en")
    return JSONResponse({"lang": lang})


@router.post("/run")
async def start_run(request: Request) -> JSONResponse:
    global _latest_run_id
    form = await request.form()
    api_url = str(form.get("api_url", "")).strip()
    api_key = str(form.get("api_key", "")).strip()
    requested_provider = str(form.get("provider", "auto")).strip() or "auto"
    model = str(form.get("model", "")).strip()
    target_tokens_raw = str(form.get("target_tokens", "")).strip()
    context_size_raw = str(form.get("context_size", "")).strip()
    max_input_raw = str(form.get("max_input_tokens", "")).strip()
    max_output_raw = str(form.get("max_output_tokens", "")).strip()
    request_timeout_raw = str(form.get("request_timeout_seconds", "")).strip()
    concurrency_raw = str(form.get("concurrency", "")).strip()

    if not api_url or not api_key or not model:
        raise HTTPException(status_code=400, detail="api_url, api_key and model are required")
    if requested_provider == "auto":
        detection = await detect_provider(api_url=api_url, api_key=api_key, model=model)
        provider = detection.provider
        protocol_source = detection.source
    else:
        try:
            provider = ProviderType(requested_provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"unknown provider: {requested_provider}") from exc
        protocol_source = "user_override"

    p = create_provider(provider=provider, api_url=api_url, api_key=api_key, model=model)
    profiler = Profiler(provider=p)
    caps = await profiler.detect_capabilities()

    try:
        target_tokens = int(target_tokens_raw) if target_tokens_raw else None
        context_size = int(context_size_raw) if context_size_raw else caps.context_size
        max_input = int(max_input_raw) if max_input_raw else 1024
        max_output = int(max_output_raw) if max_output_raw else 256
        request_timeout = int(request_timeout_raw) if request_timeout_raw else 30
        concurrency = int(concurrency_raw) if concurrency_raw else (
            caps.recommended_concurrency or max(1, caps.rate_limit_rpm // 30)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="numeric options must be integers") from exc
    if any(
        v is not None and v < 1
        for v in (target_tokens, context_size, max_input, max_output, request_timeout, concurrency)
    ):
        raise HTTPException(status_code=400, detail="numeric options must be at least 1")

    context_source = "user_override" if context_size_raw else caps.context_source
    concurrency_source = "user_override" if concurrency_raw else caps.concurrency_source
    adaptive_concurrency = not bool(concurrency_raw)

    run_id = uuid.uuid4().hex
    state: dict = {
        "id": run_id,
        "provider": provider.value,
        "model": model,
        "target_tokens": target_tokens,
        "config": {
            "api_url": api_url,
            "provider": requested_provider,
            "model": model,
            "target_tokens": target_tokens,
            "context_size": int(context_size_raw) if context_size_raw else None,
            "max_input_tokens": max_input,
            "max_output_tokens": max_output,
            "request_timeout_seconds": request_timeout,
            "concurrency": int(concurrency_raw) if concurrency_raw else None,
        },
        "summary": EngineSummary(),
        "running": True,
        "start_time": time.time(),
        "end_time": None,
        "qps": 0.0,
        "in_flight": 0,
        "error": None,
        "engine": None,
        "task": None,
        "logs": [],
        "next_log_id": 1,
    }
    _active_runs[run_id] = state
    _latest_run_id = run_id
    target_label = f"{target_tokens:,}" if target_tokens is not None else "infinite"
    _append_log(
        state,
        f"Capabilities | protocol={provider.value} source={protocol_source} | "
        f"context={context_size:,} source={context_source} | "
        f"concurrency={'auto 1→' if adaptive_concurrency else ''}{concurrency} source={concurrency_source}",
    )
    _append_log(
        state,
        f"Run started | model={model} target={target_label} request_size={max_input} "
        f"max_output={max_output} timeout={request_timeout}s endpoint={api_url}",
    )

    async def _run():
        def on_dispatch(metadata: RequestMetadata) -> None:
            _active_runs[run_id]["in_flight"] += 1
            _append_log(
                _active_runs[run_id],
                f"Request #{metadata.request_id} SENDING | target_input={metadata.input_tokens:,} "
                f"local_estimate={metadata.local_estimated_input_tokens:,} "
                f"language={metadata.language} topic={metadata.topic}",
            )

        def on_wait(metadata: RequestMetadata, elapsed: float) -> None:
            st = _active_runs[run_id]
            _append_log(
                st,
                f"Request #{metadata.request_id} WAITING | elapsed={elapsed:.0f}s "
                f"in_flight={st['in_flight']} timeout={request_timeout}s",
            )

        def on_concurrency_change(value: int, reason: str) -> None:
            _append_log(
                _active_runs[run_id],
                f"Concurrency adjusted | value={value} reason={reason}",
                level="error" if reason == "rate_limited" else "info",
            )

        def on_progress(result: RequestResult, _elapsed: float) -> None:
            st = _active_runs[run_id]
            st["in_flight"] = max(0, st["in_flight"] - 1)
            elapsed = time.time() - st["start_time"]
            if elapsed > 0:
                st["qps"] = st["summary"].total_requests / elapsed
            request_no = result.request_id
            if result.success:
                accuracy = (
                    result.prompt_tokens / result.requested_input_tokens * 100
                    if result.requested_input_tokens > 0
                    else 0
                )
                _append_log(
                    st,
                    f"Request #{request_no} OK | prompt={result.prompt_tokens:,} "
                    f"completion={result.completion_tokens:,} total={result.total_tokens:,} "
                    f"target_input={result.requested_input_tokens:,} accuracy={accuracy:.1f}% "
                    f"cached={result.cached_tokens:,} reasoning={result.reasoning_tokens:,} "
                    f"latency={result.latency_ms:.0f}ms",
                )
            else:
                _append_log(
                    st,
                    f"Request #{request_no} FAILED | latency={result.latency_ms:.0f}ms | "
                    f"error={result.error or 'unknown error'}",
                    level="error",
                )

        engine = Engine(
            provider=p,
            concurrency=concurrency,
            target_tokens=target_tokens,
            on_progress=on_progress,
            max_input_tokens=max_input,
            max_output_tokens=max_output,
            context_size=context_size,
            adaptive_concurrency=adaptive_concurrency,
            on_dispatch=on_dispatch,
            on_concurrency_change=on_concurrency_change,
            on_wait=on_wait,
            request_timeout_seconds=request_timeout,
        )
        state["engine"] = engine
        state["summary"] = engine.summary
        try:
            await engine.run()
        except asyncio.CancelledError:
            engine.stop()
            engine.summary.stop_reason = "stopped"
        except Exception as exc:
            state["error"] = f"{type(exc).__name__}: {exc}"
            _append_log(state, state["error"], level="error")
        finally:
            state["in_flight"] = 0
            state["running"] = False
            state["end_time"] = time.time()
            summary = state["summary"]
            _append_log(
                state,
                f"Run finished | reason={summary.stop_reason or 'unknown'} "
                f"requests={summary.total_requests:,} api_tokens={summary.total_tokens:,} "
                f"prompt={summary.prompt_tokens:,} completion={summary.completion_tokens:,} "
                f"cached={summary.cached_tokens:,} reasoning={summary.reasoning_tokens:,} "
                f"failed={summary.failed_requests:,}",
            )

    state["task"] = asyncio.create_task(_run())
    return JSONResponse({
        "run_id": run_id,
        "message": "started",
        "run": _public_state(state),
        "detected": {
            "provider": provider.value,
            "protocol_source": protocol_source,
            "context_size": context_size,
            "context_source": context_source,
            "concurrency": concurrency,
            "concurrency_source": concurrency_source,
            "adaptive_concurrency": adaptive_concurrency,
            "rate_limit_rpm": caps.rate_limit_rpm,
        },
    })


@router.get("/api/run/current")
async def current_run() -> JSONResponse:
    if _latest_run_id is None:
        return JSONResponse({"run": None})
    state = _active_runs.get(_latest_run_id)
    return JSONResponse({"run": _public_state(state) if state else None})


@router.post("/stop/{run_id}")
async def stop_run(run_id: str) -> JSONResponse:
    state = _active_runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="unknown run_id")
    _append_log(state, "Stop requested by user")
    engine: Engine | None = state.get("engine")
    if engine is not None:
        engine.stop()
    task: asyncio.Task | None = state.get("task")
    if task is not None and not task.done() and engine is None:
        task.cancel()
        state["running"] = False
        state["end_time"] = time.time()
        state["summary"].stop_reason = "stopped"
        _append_log(state, "Run finished | reason=stopped requests=0 tokens=0 failed=0")
    return JSONResponse({"run_id": run_id, "message": "stopping"})


@router.get("/events/{run_id}")
async def events(run_id: str, after_log_id: int = 0) -> EventSourceResponse:
    async def _gen():
        state = _active_runs.get(run_id)
        if not state:
            yield {"event": "error", "data": "unknown run_id"}
            return

        log_cursor = after_log_id
        while state["running"]:
            new_logs = _logs_after(state, log_cursor)
            if new_logs:
                log_cursor = new_logs[-1]["id"]
            payload = _public_state(state, logs=new_logs)
            yield {"event": "progress", "data": json.dumps(payload)}
            await asyncio.sleep(0.5)

        new_logs = _logs_after(state, log_cursor)
        payload = _public_state(state, logs=new_logs)
        yield {"event": "done", "data": json.dumps(payload)}

    return EventSourceResponse(_gen())
