# EatToken

快速消耗 LLM API token 的 CLI + Web 工具。

## 快速开始

```bash
pip install -e .
```

### CLI

```bash
# 探测模型能力
eat-token probe --api-url https://api.openai.com/v1 --api-key $OPENAI_API_KEY --provider openai --model gpt-4o

# 并行消耗 token
eat-token run --api-url https://api.openai.com/v1 --api-key $OPENAI_API_KEY --provider openai --model gpt-4o --concurrency 10 --target-tokens 500000

# 启动 Web 控制台
eat-token web --port 8080
```

### Web Dashboard

访问 `http://127.0.0.1:8080` 填写配置并开始消耗。

## Docker

```bash
docker build -t eat-token .
docker run -p 8080:8080 eat-token web --host 0.0.0.0
```

## 已知模型表

系统内置常见模型的上下文长度与并发建议。未知模型将自动探测。

## 开发

```bash
pip install -e ".[dev]"
pytest
```
