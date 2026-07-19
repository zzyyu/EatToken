# EatToken

> Rapidly consume LLM API tokens with parallel requests.

EatToken is a lightweight tool for sending controlled parallel LLM requests. It auto-detects API format, resolves model capabilities, adapts concurrency, and generates traceable varied test content across multiple providers.

**Honest disclaimer:** This project has no practical value. It exists solely to burn excess API quota/tokens. Do not use it for anything meaningful.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run with web UI (default — opens browser automatically)
python run.py

# Run in CLI mode with rich progress display
python run.py --no-ui --api-url https://api.openai.com/v1 --api-key $OPENAI_API_KEY --provider openai --model gpt-4o
```

## Web UI

Run `python run.py` and a browser window opens automatically. Fill in the form:

| Field | Required | Description |
|-------|----------|-------------|
| API URL | Yes | Base URL of the API endpoint |
| API Key | Yes | Your API key |
| Provider | Yes | `auto` (default), `openai`, `anthropic`, or `google` |
| Model | Yes | Model name, e.g. `gpt-4o` |
| Target Tokens | No | Stop after consuming this many tokens |
| Context Size Override | No | Override the registry/fallback context window |
| Request Size | No | Input tokens per request (default: 1024) |
| Max Output Tokens | No | Max tokens per response (default: 256) |
| Request Timeout | No | Abort a request that does not finish within this many seconds (default: 30) |
| Concurrency Override | No | Fixed parallelism; blank starts at 1 and adapts to the recommended ceiling |

Leave Target Tokens blank to run until manually stopped. Protocol detection uses non-generating model-list requests. Each generated request has a distinct ID and rotates English/Chinese topics so concurrent payloads are not identical.

Both the Web request panel and the server terminal print `SENDING`, five-second `WAITING` heartbeats, and the final `OK`, `FAILED`, or timeout result. This makes a slow upstream response distinguishable from a request that was never sent.

## CLI Mode

```bash
python run.py --no-ui --api-url URL --api-key KEY --provider openai --model gpt-4o --concurrency 10 --target-tokens 500000
```

## Supported Providers

- **OpenAI-compatible**: OpenAI, DeepSeek, Groq, Ollama, and any OpenAI-compatible API
- **Anthropic**: Claude Sonnet, Claude Opus, Claude Haiku
- **Google**: Gemini 1.5 Pro, Gemini 2.0 Flash

## Known Models

EatToken ships with a built-in registry of context window sizes and rate-limit recommendations for popular models. Unknown models use provider-specific conservative fallbacks; the Web/CLI logs identify whether a value came from the registry, a fallback, or a user override.

## Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI argument parsing |
| `fastapi` | Web server framework |
| `aiohttp` | Async HTTP client for API calls |
| `aiosqlite` | Async SQLite (future persistence) |
| `tiktoken` | OpenAI token counting |
| `transformers` | Tokenizers for Anthropic/Google models |
| `jinja2` | HTML template engine |
| `python-multipart` | Form data parsing (FastAPI) |
| `uvicorn` | ASGI server |
| `sse-starlette` | Server-Sent Events for real-time progress |
| `pyyaml` | YAML config / i18n loading |
| `rich` | Rich terminal progress bars (CLI mode) |
| `pyperclip` | Clipboard utilities |

Dev dependencies: `pytest`, `pytest-asyncio`.

## Development

```bash
pip install -r requirements.txt
pytest
```

## License

MIT — see [LICENSE](LICENSE).
