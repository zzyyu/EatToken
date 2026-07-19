# EatToken

> 快速消耗 LLM API token 的工具。

EatToken 是一个轻量级工具，通过并行请求向 LLM API 发送大量请求以消耗 token。它支持协议自动探测、模型能力探测、自适应并发，以及可追踪的动态请求内容，支持 OpenAI 兼容接口、Anthropic 和 Google 等提供方。

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
| 协议类型 | 是 | `auto`（默认）、`openai`、`anthropic` 或 `google` |
| 模型名称 | 是 | 模型名称，如 `gpt-4o` |
| 目标 API Token 数 | 否 | 以 API 返回的实际 `total_tokens` 达到目标后停止；不是供应商 Credit 目标 |
| 上下文长度覆盖 | 否 | 覆盖模型注册表或回退值 |
| 单个请求大小 | 否 | 每个请求期望发送的服务端输入 Token，默认 1024 |
| 单次最大输出 | 否 | 每个请求允许的最大输出 Token，默认 256 |
| 单请求超时 | 否 | 请求超过该秒数仍未完成则中止，默认 30 秒 |
| 并发数覆盖 | 否 | 固定并发数；留空时从 1 开始自适应探测 |

目标 API Token 数留空时会持续运行，直到手动停止。协议为 `auto` 时会先执行非生成式探测请求。每个生成请求都有唯一编号，并轮换中英文主题，避免并发请求发送完全相同的内容。

### 实际用量与校准

运行面板和终端日志使用供应商 API 返回的实际用量字段：

- OpenAI 兼容接口使用 `usage.prompt_tokens`、`completion_tokens` 和 `total_tokens`。
- Anthropic 会合并普通输入、缓存创建输入和缓存读取输入，并分别统计输出 Token。
- Google 使用 `usageMetadata` 中的输入、候选输出、缓存和思考 Token。

本地 tokenizer 只用于生成下一次请求的填充内容，不参与实际消耗、进度百分比或目标停止判断。系统会按中英文分别根据接口返回的实际输入 Token 自动校准填充长度，因此中文 tokenizer 与服务端 tokenizer 不一致时也能逐步逼近目标。

供应商控制台可能显示 Step Plan Credit 等计费单位。Credit 根据模型用量和价格换算，不等同于 API Token，不能按 1:1 对比。

### 刷新与配置保存

Web 表单输入会自动保存到当前浏览器的 `localStorage`，刷新页面或下次重新进入时会自动回填，包括 API 地址、API Key、模型、目标数量和高级选项。API Key 以明文保存在浏览器本地存储中，请只在可信设备上使用。

右侧运行面板由后端状态驱动，即使刷新页面也会恢复当前运行的统计数据和请求日志。页面和服务器终端都会输出 `SENDING`、每 5 秒一次的 `WAITING` 心跳，以及最终的 `OK`、`FAILED` 或超时记录。

## CLI 模式

```bash
python run.py --no-ui --api-url URL --api-key KEY --provider openai --model gpt-4o --concurrency 10 --target-tokens 500000
```

## 支持的协议

- **OpenAI 兼容**：OpenAI、DeepSeek、Groq、Ollama 及所有 OpenAI 兼容接口
- **Anthropic**：Claude Sonnet、Claude Opus、Claude Haiku
- **Google**：Gemini 1.5 Pro、Gemini 2.0 Flash

## 已知模型表

EatToken 内置了常见模型的上下文长度、速率限制和并发建议。未知模型会使用供应商回退值；Web 和 CLI 日志会标记数据来自注册表、回退值还是用户覆盖。

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
