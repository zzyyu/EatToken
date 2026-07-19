# EatToken Design Spec

## Overview

A CLI + lightweight Web UI tool that rapidly consumes LLM API tokens by automatically detecting API format, model capabilities, and then flooding the context window with parallel requests.

## Tech Stack

| Layer       | Choice            | Rationale |
|-------------|-------------------|-----------|
| Language    | Python 3.10+      | Best HTTP + tokenizer ecosystem |
| CLI         | Click             | Mature, good subcommand support |
| Web UI      | FastAPI + HTMX    | Async-native, no frontend build step |
| Concurrency | asyncio + aiohttp | Single-threaded high concurrency |
| Storage     | SQLite (aiosqlite)| Single-file, zero-config |
| Token count | tiktoken + transformers tokenizers | Covers all major providers |

## Architecture

```
eat-token/
├── providers/
│   ├── base.py          # Abstract provider interface
│   ├── openai.py        # OpenAI / DeepSeek / Groq / Ollama
│   ├── anthropic.py     # Anthropic Claude native protocol
│   └── google.py        # Google Gemini native protocol
├── core/
│   ├── engine.py        # Concurrency control, progress tracking
│   ├── profiler.py      # Initial probing: context size, rate limits
│   ├── generator.py     # Content/question pool to fill context
│   └── models.py        # Shared data structures
├── known_models/
│   └── registry.py      # Built-in model database (context, rate limits)
├── cli/
│   └── main.py
├── web/
│   ├── app.py           # FastAPI app
│   └── templates/       # HTMX templates
├── config/
│   └── default.yaml     # Default config (question pools, concurrency strategy)
└── tests/
```

## Provider Plugin Architecture

Each provider implements a unified interface. The core engine is protocol-agnostic:

```python
class Provider(ABC):
    @abstractmethod
    async def detect_capabilities(self) -> Capabilities
    @abstractmethod
    async def send(self, messages: list[dict], options: dict) -> Response
    @abstractmethod
    def count_tokens(self, text: str) -> int
    @abstractmethod
    def format_messages(self, turns: list[Turn]) -> list[dict]
```

## Core Flow

```
Init Probe → Generate Plan → Parallel Execution
```

### Init Probe

1. Look up model name in built-in `known_models` registry
2. If found: use registry values (context_size, rate_limit_rpm, recommended_concurrency) as defaults
3. If not found: run probing sequence (incremental length requests, observe `context_length_exceeded`)
4. User can override context size via `--context-size` flag at any time
5. Probe runs with automatic throttling; stops immediately on rate-limit response

### Content Generation

- Maintain a bilingual question/topic pool (Chinese + English, diverse topics)
- For each request: measure remaining context window, select content of appropriate length
- Construct messages and fire requests

### Parallel Execution

- `asyncio.Semaphore` for concurrency control
- Each request independently tracks token usage
- Real-time progress pushed to Web UI via SSE

## Web UI (Lightweight)

Single-page HTMX-driven dashboard, no build step required:

- **Dashboard**: token consumption progress bar, QPS, cumulative usage
- **Config**: API URL, API Key, provider selection, concurrency slider
- **Live Log**: SSE stream of request results
- **History**: SQLite-backed task summaries

## Multilingual & Documentation

- **README**: Chinese (quick start, CLI usage, Docker deploy)
- **Docs/**: English (API reference, provider development guide, architecture)
- **Question pool**: Bilingual CN/EN, diverse topics

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Model context source | Built-in registry first, probe fallback | Avoids wasted error requests on known models |
| User override | `--context-size` flag | Lets users force a value when registry is outdated |
| Error handling | Auto-throttle + stop on rate-limit | Prevents account bans during probing |
| Web UI framework | HTMX | Zero build step, fits single-file dashboard needs |

## CLI Interface (draft)

```
eat-token probe --api-url URL --api-key KEY --provider openai --model gpt-4o
eat-token run   --api-url URL --api-key KEY --provider openai --model gpt-4o --concurrency 10
eat-token web                    # Launch web dashboard
```

## Known Models Registry (example entries)

| Model              | Context  | Rate Limit (RPM) | Recommended Concurrency |
|--------------------|----------|-----------------|------------------------|
| gpt-4o             | 128000   | 500             | 20                     |
| gpt-4o-mini        | 128000   | 1500            | 50                     |
| claude-sonnet-4    | 200000   | 50              | 10                     |
| deepseek-chat      | 64000    | 100             | 10                     |
| gemini-2.0-flash   | 1000000  | 15              | 5                      |
