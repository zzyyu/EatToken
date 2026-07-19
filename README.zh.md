# EatToken

> 快速消耗 LLM API token 的工具。

EatToken 是一个轻量级工具，通过并行请求向 LLM API 发送大量请求以消耗 token。它自动识别 API 格式，探测模型能力，并用生成的内容填满上下文窗口，支持 OpenAI、Anthropic、Google 等多个提供方。

**免责声明：** 本项目没有实际价值，仅用于消耗多余的 API 配额 / token。请勿将其用于任何有意义的用途。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Web 界面（默认 — 自动打开浏览器）
python run.py

# CLI 模式（带 rich 进度条）
python run.py --no-ui --api-url https://api.openai.com/v1 --api-key $OPENAI_API_KEY --provider openai --model gpt-4o
```

## Web 界面

运行 `python run.py`，浏览器会自动打开。在表单中填写配置：

| 字段 | 是否必填 | 说明 |
|------|----------|------|
| API 地址 | 是 | API 端点基础 URL |
| API Key | 是 | 你的 API 密钥 |
| 协议类型 | 是 | `openai`、`anthropic` 或 `google` |
| 模型名称 | 是 | 模型名称，如 `gpt-4o` |
| 目标 Token 数 | 否 | 消耗到指定数量后停止 |
| 上下文长度 | 否 | 最大上下文窗口（自动从模型探测） |
| 单次最大输入 | 否 | 单次请求的最大输入 token |
| 单次最大输出 | 否 | 单次请求的最大输出 token |
| 并发数 | 否 | 并行请求数（从速率限制自动探测） |

选填字段留空时，系统会自动探测。

## CLI 模式

```bash
python run.py --no-ui --api-url URL --api-key KEY --provider openai --model gpt-4o --concurrency 10 --target-tokens 500000
```

## 支持的协议

- **OpenAI 兼容**：OpenAI、DeepSeek、Groq、Ollama 及所有 OpenAI 兼容接口
- **Anthropic**：Claude Sonnet、Claude Opus、Claude Haiku
- **Google**：Gemini 1.5 Pro、Gemini 2.0 Flash

## 已知模型表

EatToken 内置了常见模型的上下文长度和速率限制数据。未知模型会自动探测。

## 依赖

| 包 | 用途 |
|---------|---------|
| `click` | CLI 参数解析 |
| `fastapi` | Web 服务框架 |
| `aiohttp` | 异步 HTTP 客户端（调用 API） |
| `aiosqlite` | 异步 SQLite（后续持久化） |
| `tiktoken` | OpenAI token 计数 |
| `transformers` | Anthropic/Google 模型 tokenizer |
| `jinja2` | HTML 模板引擎 |
| `python-multipart` | 表单数据解析（FastAPI） |
| `uvicorn` | ASGI 服务器 |
| `sse-starlette` | Server-Sent Events（实时进度推送） |
| `pyyaml` | YAML 配置 / i18n 加载 |
| `rich` | 终端进度条（CLI 模式） |
| `pyperclip` | 剪贴板工具 |

开发依赖：`pytest`、`pytest-asyncio`。

## 开发

```bash
pip install -r requirements.txt
pytest
```

## 协议

MIT — 详见 [LICENSE](LICENSE)。
