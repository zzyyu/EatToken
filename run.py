#!/usr/bin/env python3
"""EatToken — Rapidly consume LLM API tokens.

Usage:
    python run.py                        # Launch web UI (default)
    python run.py --no-ui                # CLI mode with rich progress
    python run.py --no-ui --api-url ...  # CLI with all options

Run without arguments to open the web dashboard in your browser.
"""
from __future__ import annotations
import argparse
import asyncio
import sys
import webbrowser
from pathlib import Path

# Ensure src is importable when run directly
SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _run_web(args: argparse.Namespace) -> None:
    import threading
    from eattoken.web.app import create_app
    import uvicorn

    host = args.host or "127.0.0.1"
    port = args.port or 8080
    url = f"http://{host}:{port}"

    # Auto-open browser after server starts
    def _open_browser() -> None:
        import time

        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"Starting EatToken web UI at {url}")
    uvicorn.run(create_app(), host=host, port=port)


def _run_cli(args: argparse.Namespace) -> None:
    from eattoken.core.engine import Engine
    from eattoken.core.profiler import Profiler
    from eattoken.providers.factory import create_provider, detect_provider
    from eattoken.core.models import ProviderType
    from eattoken.i18n import t, detect_language

    lang = detect_language()

    if not args.api_url or not args.api_key or not args.model:
        print(t("error_missing_required", lang=lang))
        sys.exit(1)

    requested_provider = args.provider or "auto"
    try:
        provider_type = None if requested_provider == "auto" else ProviderType(requested_provider)
    except ValueError:
        print(f"Unknown provider: {requested_provider}. Choose from: auto, openai, anthropic, google")
        sys.exit(2)
    model = args.model
    api_url = args.api_url
    api_key = args.api_key
    concurrency = args.concurrency
    target_tokens = args.target_tokens
    context_size = args.context_size

    async def _run() -> None:
        detection = await detect_provider(api_url, api_key, model) if provider_type is None else None
        actual_provider = detection.provider if detection else provider_type
        p = create_provider(provider=actual_provider, api_url=api_url, api_key=api_key, model=model)
        profiler = Profiler(provider=p)
        caps = await profiler.detect_capabilities()
        effective_ctx = context_size or caps.context_size
        effective_concurrency = concurrency or caps.recommended_concurrency or max(1, caps.rate_limit_rpm // 30)

        from rich.console import Console
        from rich.progress import (
            BarColumn,
            Progress,
            TextColumn,
            TimeElapsedColumn,
        )
        from rich.panel import Panel

        console = Console()
        console.print(
            Panel(
                f"[bold]{t('app_title', lang=lang)}[/bold]\n"
                f"{t('app_subtitle', lang=lang)}\n\n"
                f"Provider: {caps.provider.value} ({detection.source if detection else 'user_override'})\n"
                f"Model: {caps.model}\n"
                f"Context: {effective_ctx} ({'user_override' if context_size else caps.context_source})\n"
                f"Concurrency: {effective_concurrency if concurrency else f'auto 1→{effective_concurrency}'}",
                title="Config",
            )
        )

        summary = {"total_tokens": 0, "total_requests": 0, "failed_requests": 0, "start_time": None}

        def _on_progress(result, elapsed) -> None:  # noqa: A002
            import time
            if summary["start_time"] is None:
                summary["start_time"] = time.time()
            summary["total_tokens"] += result.total_tokens
            summary["total_requests"] += 1
            if not result.success:
                summary["failed_requests"] += 1
            request_no = result.request_id
            if result.success:
                console.print(
                    f"[green]OK[/green] Request #{request_no} | "
                    f"prompt={result.prompt_tokens:,} completion={result.completion_tokens:,} "
                    f"total={result.total_tokens:,} latency={result.latency_ms:.0f}ms"
                )
            else:
                console.print(
                    f"[red]FAILED[/red] Request #{request_no} | "
                    f"latency={result.latency_ms:.0f}ms | {result.error or 'unknown error'}"
                )

        def _on_dispatch(metadata) -> None:
            console.print(
                f"[cyan]SENDING[/cyan] Request #{metadata.request_id} | input≈{metadata.input_tokens:,} "
                f"language={metadata.language} topic={metadata.topic}"
            )

        def _on_concurrency_change(value: int, reason: str) -> None:
            console.print(f"[yellow]Concurrency[/yellow] → {value} ({reason})")

        def _on_wait(metadata, elapsed: float) -> None:
            console.print(
                f"[yellow]WAITING[/yellow] Request #{metadata.request_id} | "
                f"elapsed={elapsed:.0f}s timeout={args.request_timeout}s"
            )

        engine = Engine(
            provider=p,
            concurrency=effective_concurrency,
            target_tokens=target_tokens,
            on_progress=_on_progress,
            context_size=effective_ctx,
            max_input_tokens=args.max_input_tokens,
            max_output_tokens=args.max_output_tokens,
            adaptive_concurrency=concurrency is None,
            on_dispatch=_on_dispatch,
            on_concurrency_change=_on_concurrency_change,
            on_wait=_on_wait,
            request_timeout_seconds=args.request_timeout,
        )

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            TextColumn("•"),
            TextColumn("[cyan]{task.fields[tokens]:,} tokens"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            if target_tokens:
                task = progress.add_task("Consuming", total=target_tokens, tokens=0)
            else:
                task = progress.add_task("Consuming", total=None, tokens=0)

            async def _update():
                import time

                while True:
                    await asyncio.sleep(0.5)
                    progress.update(task, tokens=summary["total_tokens"])
                    if target_tokens and summary["total_tokens"] >= target_tokens:
                        break

            updater = asyncio.create_task(_update())
            engine_summary = await engine.run()
            updater.cancel()
            update = {"tokens": engine_summary.total_tokens}
            if target_tokens:
                update["completed"] = min(engine_summary.total_tokens, target_tokens)
            progress.update(task, **update)

        console.print(
            f"\n[green]{t('status_done', lang=lang)}[/green] "
            f"Total tokens: {summary['total_tokens']:,} | "
            f"Requests: {summary['total_requests']} | "
            f"Failed: {summary['failed_requests']}"
        )

    asyncio.run(_run())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="eattoken",
        description="EatToken — Rapidly consume LLM API tokens",
    )
    parser.add_argument("--no-ui", action="store_true", help="Run in CLI mode without web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    parser.add_argument("--api-url", default=None, help="API base URL")
    parser.add_argument("--api-key", default=None, help="API key")
    parser.add_argument("--provider", default="auto", help="Provider: auto, openai, anthropic, google")
    parser.add_argument("--model", default=None, help="Model name (required)")
    parser.add_argument("--context-size", type=int, default=None, help="Override context window size")
    parser.add_argument("--concurrency", type=int, default=None, help="Parallel request count")
    parser.add_argument("--target-tokens", type=int, default=None, help="Stop after consuming this many tokens")
    parser.add_argument("--max-input-tokens", type=int, default=1024, help="Input tokens per request (default: 1024)")
    parser.add_argument("--max-output-tokens", type=int, default=256, help="Maximum output tokens per request")
    parser.add_argument("--request-timeout", type=int, default=30, help="Request timeout in seconds")

    args = parser.parse_args()

    if args.no_ui:
        _run_cli(args)
    else:
        _run_web(args)


if __name__ == "__main__":
    main()
