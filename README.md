<p align="center">
  <img src="public/NestyAI_Full.svg" alt="NestyAI" width="560" />
</p>

<p align="center">
  <strong>Your personal, production-ready FastAPI AI Gateway.</strong><br/>
  OpenAI-compatible chat, streaming SSE, provider fallback, guardrails, tools, and session memory.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-Production%20Ready-009688" alt="FastAPI" />
  <img src="https://img.shields.io/badge/tests-151%20passed-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/API-OpenAI%20Compatible-orange" alt="OpenAI Compatible" />
  <img src="https://img.shields.io/badge/streaming-SSE-ff9800" alt="SSE" />
</p>

---

## NestyAI At A Glance

NestyAI helps you run your own AI gateway with strong defaults for real deployment.

- OpenAI-style `POST /v1/chat/completions`
- stream + non-stream support
- provider fallback routing (Groq, OpenRouter, NVIDIA route)
- API key auth, rate limiting, quota, usage tracking
- input/output/context guardrails
- server-side tools + web search
- conversation memory with summary controls (`auto`, `off`, `force`)
- conversation search, filtering, export, and pagination

## Why Teams Use It

- Keep control over routing, safety, and data flow
- Replace one-off scripts with a consistent gateway layer
- Ship faster with a stable API surface for web/mobile/apps
- Start lightweight (SQLite) and stay testable

## Quick Start

### 1) Install

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2) Configure

```bash
copy .env.example .env
```

Set at least one provider key:

- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `NVIDIA_API_KEY` (optional)

### 3) Run

```bash
python run.py
```

Server:

- `http://127.0.0.1:8000`

## First Request

```bash
curl -X POST "http://127.0.0.1:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nesty-combined-1.0",
    "messages": [{"role": "user", "content": "Hello NestyAI"}],
    "search": "off"
  }'
```

Streaming:

```bash
curl -N -X POST "http://127.0.0.1:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nesty-combined-1.0",
    "messages": [{"role": "user", "content": "Give me a short status update"}],
    "stream": true,
    "tools": "off"
  }'
```

## Production Checklist

Recommended baseline:

```bash
APP_ENV=production
REQUIRE_API_KEY=true
NESTY_API_KEY_HASH_SECRET=replace_with_a_strong_secret
RATE_LIMIT_ENABLED=true
SECURITY_HEADERS_ENABLED=true
TRUSTED_HOSTS=your-api.example.com
CORS_ENABLED=true
CORS_ALLOW_ORIGINS=https://your-app.example.com
SAFE_DEBUG_AUTH=false
```

Also:

- do not commit `.env`
- do not commit `data/nesty.db`
- avoid wildcard CORS in production

## API Surface

Core:

- `GET /health`
- `GET /ready`
- `GET /v1/models`
- `POST /v1/chat/completions`

Conversation:

- `GET /v1/conversations`
- `GET /v1/conversations/search`
- `GET /v1/conversations/{conversation_id}`
- `GET /v1/conversations/{conversation_id}/messages`
- `POST /v1/conversations/{conversation_id}/summarize`
- `POST /v1/conversations/{conversation_id}/clear`
- `POST /v1/conversations/{conversation_id}/reset-summary`
- `GET /v1/conversations/{conversation_id}/export`

## Docs And Examples

- Full technical documentation: [`docs/README_TECHNICAL.md`](docs/README_TECHNICAL.md)
- Environment template: [`.env.example`](.env.example)
- Client examples: [`examples/`](examples)
- Utility scripts: [`scripts/`](scripts)

## Quality Status

- Test suite: **151 passed**
- Streaming contract: enabled
- Conversation controls/search: enabled

## Roadmap

Next target: Phase 7 semantic memory foundation (embeddings + vector retrieval policy), while preserving current guardrails and API compatibility.
