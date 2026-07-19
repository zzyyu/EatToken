from __future__ import annotations
import click
from eattoken.core.models import ProviderType
from eattoken.providers.factory import create_provider, detect_provider


def _provider_type(value: str) -> ProviderType | None:
    if value == "auto":
        return None
    try:
        return ProviderType(value)
    except ValueError:
        raise click.BadParameter(
            f"Unknown provider: {value}. Choose from: auto, {', '.join(p.value for p in ProviderType)}"
        )


@click.group()
def cli() -> None:
    """EatToken: rapidly consume LLM API tokens."""


@cli.command()
@click.option("--api-url", required=True, help="API base URL, e.g. https://api.openai.com/v1")
@click.option("--api-key", required=True, help="API key")
@click.option("--provider", default="auto", show_default=True, type=str, callback=lambda ctx, param, value: _provider_type(value))
@click.option("--model", required=True, help="Model name, e.g. gpt-4o")
@click.option("--context-size", type=int, default=None, help="Override context window size")
def probe(api_url: str, api_key: str, provider: ProviderType | None, model: str, context_size: int | None) -> None:
    """Probe API capabilities: context size, rate limits, concurrency."""
    import asyncio

    async def _run() -> None:
        detection = await detect_provider(api_url, api_key, model) if provider is None else None
        actual_provider = detection.provider if detection else provider
        p = create_provider(provider=actual_provider, api_url=api_url, api_key=api_key, model=model)
        caps = await p.detect_capabilities()
        effective_ctx = context_size or caps.context_size
        click.echo(f"provider={caps.provider.value}")
        click.echo(f"protocol_source={detection.source if detection else 'user_override'}")
        click.echo(f"model={caps.model}")
        click.echo(f"context_size={effective_ctx}")
        click.echo(f"context_source={'user_override' if context_size else caps.context_source}")
        click.echo(f"rate_limit_rpm={caps.rate_limit_rpm}")
        click.echo(
            f"recommended_concurrency={caps.recommended_concurrency or max(1, caps.rate_limit_rpm // 30)}"
        )

    asyncio.run(_run())


@cli.command()
@click.option("--api-url", required=True)
@click.option("--api-key", required=True)
@click.option("--provider", default="auto", show_default=True, type=str, callback=lambda ctx, param, value: _provider_type(value))
@click.option("--model", required=True)
@click.option("--context-size", type=int, default=None)
@click.option("--concurrency", type=int, default=None, help="Parallel request count (auto-detected by default)")
@click.option("--target-tokens", type=int, default=None, help="Stop after consuming this many tokens")
@click.option("--max-input-tokens", type=int, default=1024, show_default=True, help="Input tokens per request")
@click.option("--max-output-tokens", type=int, default=256, show_default=True, help="Maximum output tokens per request")
@click.option("--request-timeout", type=int, default=30, show_default=True, help="Request timeout in seconds")
def run(
    api_url: str,
    api_key: str,
    provider: ProviderType | None,
    model: str,
    context_size: int | None,
    concurrency: int | None,
    target_tokens: int | None,
    max_input_tokens: int | None,
    max_output_tokens: int | None,
    request_timeout: int,
) -> None:
    """Run parallel token consumption (CLI mode)."""
    import asyncio
    from eattoken.core.engine import Engine
    from eattoken.core.profiler import Profiler
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        TextColumn,
        TimeElapsedColumn,
    )

    async def _run() -> None:
        detection = await detect_provider(api_url, api_key, model) if provider is None else None
        actual_provider = detection.provider if detection else provider
        p = create_provider(provider=actual_provider, api_url=api_url, api_key=api_key, model=model)
        profiler = Profiler(provider=p)
        caps = await profiler.detect_capabilities()
        effective_ctx = context_size or caps.context_size
        effective_concurrency = concurrency or caps.recommended_concurrency or max(1, caps.rate_limit_rpm // 30)

        console = Console()
        console.print(f"[bold]EatToken[/bold] — {caps.provider.value} / {caps.model}")
        context_source = "user_override" if context_size else caps.context_source
        concurrency_label = str(effective_concurrency) if concurrency else f"auto 1→{effective_concurrency}"
        console.print(
            f"Protocol source: {detection.source if detection else 'user_override'} | "
            f"Context: {effective_ctx} ({context_source}) | Concurrency: {concurrency_label}\n"
        )

        summary = {"total_tokens": 0, "total_requests": 0, "failed_requests": 0, "start_time": None}

        def on_progress(result, _elapsed) -> None:  # noqa: A002
            summary["total_tokens"] += result.total_tokens
            summary["total_requests"] += 1
            if not result.success:
                summary["failed_requests"] += 1
            request_no = result.request_id
            if result.success:
                accuracy = (
                    result.prompt_tokens / result.requested_input_tokens * 100
                    if result.requested_input_tokens > 0
                    else 0
                )
                console.print(
                    f"[green]OK[/green] Request #{request_no} | "
                    f"prompt={result.prompt_tokens:,} completion={result.completion_tokens:,} "
                    f"total={result.total_tokens:,} target_input={result.requested_input_tokens:,} "
                    f"accuracy={accuracy:.1f}% cached={result.cached_tokens:,} "
                    f"reasoning={result.reasoning_tokens:,} latency={result.latency_ms:.0f}ms"
                )
            else:
                console.print(
                    f"[red]FAILED[/red] Request #{request_no} | "
                    f"latency={result.latency_ms:.0f}ms | {result.error or 'unknown error'}"
                )

        def on_dispatch(metadata) -> None:
            console.print(
                f"[cyan]SENDING[/cyan] Request #{metadata.request_id} | "
                f"target_input={metadata.input_tokens:,} "
                f"local_estimate={metadata.local_estimated_input_tokens:,} "
                f"language={metadata.language} topic={metadata.topic}"
            )

        def on_concurrency_change(value: int, reason: str) -> None:
            console.print(f"[yellow]Concurrency[/yellow] → {value} ({reason})")

        def on_wait(metadata, elapsed: float) -> None:
            console.print(
                f"[yellow]WAITING[/yellow] Request #{metadata.request_id} | "
                f"elapsed={elapsed:.0f}s timeout={request_timeout}s"
            )

        engine = Engine(
            provider=p,
            concurrency=effective_concurrency,
            target_tokens=target_tokens,
            on_progress=on_progress,
            context_size=effective_ctx,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
            adaptive_concurrency=concurrency is None,
            on_dispatch=on_dispatch,
            on_concurrency_change=on_concurrency_change,
            on_wait=on_wait,
            request_timeout_seconds=request_timeout,
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
            f"\nDone. API tokens: {engine_summary.total_tokens:,} | "
            f"Prompt: {engine_summary.prompt_tokens:,} | "
            f"Completion: {engine_summary.completion_tokens:,} | "
            f"Cached: {engine_summary.cached_tokens:,} | "
            f"Reasoning: {engine_summary.reasoning_tokens:,} | "
            f"Requests: {engine_summary.total_requests} | Failed: {engine_summary.failed_requests}"
        )

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
