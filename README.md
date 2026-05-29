# NestyAI (Phase 4: API Key Auth, Rate Limit, Usage Tracking)

NestyAI is a personal FastAPI AI Gateway with OpenAI-compatible chat, provider fallback routing, safety guards, web search, and server-side tools.

## Core Endpoints

- `GET /`
- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

## Model Aliases

- `nesty-flash-1.0`
- `nesty-combined-1.0`
- `nesty-pro-1.0`

## Tool System Overview

- Central `ToolRegistry`
- Rule-based `ToolPlanner`
- Tools selected server-side only
- Tool outputs sanitized by `ContextGuard` as untrusted external context
- `tools` request mode:
  - `"auto"`
  - `"off"`
  - `list[str]`

Supported tools:

- `calculator`
- `wikipedia_lookup`
- `package_version_lookup`
- `weather_lookup` (Open-Meteo)
- `exchange_rate` (Frankfurter)

## Cache Overview

In-memory TTL cache for tool/search reliability:

- In-memory only
- No Redis yet
- Cache resets on server restart

## Phase 4 Auth Overview

- API keys are stored as hashes in local SQLite (`data/nesty.db` by default).
- Chat endpoint (`/v1/chat/completions`) supports:
  - `Authorization: Bearer <key>`
  - `X-Nesty-API-Key: <key>`
- If `REQUIRE_API_KEY=true`, chat always requires a valid active key.
- `/health` and `/v1/models` remain public when:
  - `PUBLIC_HEALTH=true`
  - `PUBLIC_MODELS=true`
- Recommended for deployment:
  - `REQUIRE_API_KEY=true`
  - set `NESTY_API_KEY_HASH_SECRET`

If `NESTY_API_KEY_HASH_SECRET` is set, key hashes use HMAC-SHA256.
If unset, fallback is plain SHA256 (works for local dev, not recommended for deployment).

## Rate Limit and Quota

- In-memory rate limiter (per API key, or per client IP when unauthenticated).
- Config:
  - `RATE_LIMIT_ENABLED=true`
  - `RATE_LIMIT_REQUESTS_PER_MINUTE=60`
- Quotas are request-count based (not token billing):
  - `daily_limit`
  - `monthly_limit`
- Quota checks apply per API key.

## Usage Tracking

Each chat request attempts to write a usage log row:

- `api_key_id` (or `null` for unauthenticated calls)
- `request_id`
- `model`, `provider`
- token usage if available
- `tools_used`, `search_used`
- `latency_ms`
- `status` (`success` / `error`)
- `error_code` when present

NestyAI does not log raw API keys, raw prompts, or raw model outputs in usage storage.

## Setup

1. Create Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Create `.env` from `.env.example` and configure keys:

- Provider keys:
  - `GROQ_API_KEY`
  - `OPENROUTER_API_KEY`
  - `NVIDIA_API_KEY` (optional)
- Phase 4:
  - `NESTY_DB_PATH=data/nesty.db`
  - `NESTY_API_KEY_HASH_SECRET=...` (recommended)
  - `REQUIRE_API_KEY=false` (set `true` in deployment)
  - `PUBLIC_HEALTH=true`
  - `PUBLIC_MODELS=true`
  - `RATE_LIMIT_ENABLED=true`
  - `RATE_LIMIT_REQUESTS_PER_MINUTE=60`
  - `SAFE_DEBUG_AUTH=false`

## API Key Scripts

Create key:

```bash
python scripts/create_api_key.py --name local-dev --env dev --daily-limit 1000 --models nesty-flash-1.0,nesty-combined-1.0
```

List keys:

```bash
python scripts/list_api_keys.py
```

Revoke key:

```bash
python scripts/revoke_api_key.py --id key_xxxxxxxxxxxxxxxx
```

Usage summary:

```bash
python scripts/usage_summary.py --days 7
```

## Call Chat with API Key

```bash
curl -X POST "http://127.0.0.1:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer nsk_dev_xxx" \
  -d '{
    "model": "nesty-combined-1.0",
    "messages": [{"role": "user", "content": "Hello"}],
    "search": "off",
    "tools": "auto"
  }'
```

## Streaming (Phase 5)

NestyAI now supports `stream=true` on `/v1/chat/completions` using Server-Sent Events (SSE).

Response stream format:

- `data: {json chunk}`
- `data: [DONE]`

Chunk object shape:

- `object: "chat.completion.chunk"`
- `choices[0].delta.content` for text deltas
- final chunk includes `finish_reason`

Metadata event:

- Before `[DONE]`, NestyAI emits:
  - `object: "chat.completion.metadata"`
  - includes `guard`, `tools`, `sources`, `usage`

Streaming example (Windows PowerShell):

```bash
curl -N -X POST "http://127.0.0.1:8000/v1/chat/completions" ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer YOUR_KEY" ^
  -d "{\"model\":\"nesty-combined-1.0\",\"messages\":[{\"role\":\"user\",\"content\":\"Write a short intro about NestyAI\"}],\"stream\":true,\"search\":\"off\",\"tools\":\"off\"}"
```

Streaming notes:

- OutputGuard currently runs after stream completion (MVP safety model).
- If output sanitation is detected, stream metadata indicates redaction and a guard notice chunk can be emitted.
- Usage logging is recorded after stream completion when possible.

## Streaming Client Examples (Phase 5.1)

Reference client examples are available under `examples/`:

- Python:
  - `examples/python/chat_non_stream.py`
  - `examples/python/chat_stream.py`
- JavaScript (Node 18+):
  - `examples/javascript/chat_non_stream.js`
  - `examples/javascript/chat_stream_fetch.js`
- Kotlin/Android reference:
  - `examples/kotlin/android_sse_example.kt`

Run Python stream example:

```bash
python examples/python/chat_stream.py
```

Run JavaScript stream example:

```bash
node examples/javascript/chat_stream_fetch.js
```

Stream event types:

- `chat.completion.chunk`: incremental assistant delta tokens.
- `chat.completion.metadata`: final NestyAI metadata (`guard`, `tools`, `sources`, `usage`).
- `chat.completion.error`: stream interruption notification.
- `[DONE]`: stream completion marker.

Metadata may include:

- `guard`
- `tools`
- `sources`
- `usage`

CORS note:

- If you call NestyAI directly from browser/mobile web in development, configure CORS intentionally.
- Do not use wildcard CORS in production when private API keys are involved.

## Conversation Session + Memory Foundation (Phase 6)

NestyAI supports optional short-session memory via `conversation_id` + `store`.

Key behavior:

- `store=false` (default): existing stateless behavior, no conversation load/save.
- `store=true`:
  - if `conversation_id` missing: create a new conversation automatically.
  - if `conversation_id` provided: load recent stored messages and append new turn.
  - save sanitized user/assistant messages to SQLite.

Example start request:

```json
{
  "model": "nesty-combined-1.0",
  "messages": [
    {
      "role": "user",
      "content": "Remember this conversation context for later in this session."
    }
  ],
  "store": true
}
```

Example follow-up request:

```json
{
  "model": "nesty-combined-1.0",
  "conversation_id": "conv_xxxxxxxxxxxxxxxx",
  "messages": [
    {
      "role": "user",
      "content": "What did I ask earlier?"
    }
  ],
  "store": true
}
```

Conversation endpoints:

- `GET /v1/conversations?limit=20&offset=0`
- `GET /v1/conversations/{conversation_id}`
- `PATCH /v1/conversations/{conversation_id}` with `{ "title": "..." }`
- `DELETE /v1/conversations/{conversation_id}` (soft archive)

Privacy note:

- NestyAI stores sanitized messages when `store=true`.
- `store=false` keeps stateless behavior and does not persist messages.

## Conversation Summarization + History Compression (Phase 6.1)

Phase 6.1 adds lightweight conversation summarization for long sessions.

How it works:

- Recent history window:
  - still used for short conversations and as fallback.
- Conversation summary:
  - when a conversation grows past a threshold, older messages are compressed into a sanitized summary.
  - prompt injection uses:
    - summary context message
    - recent unsummarized tail messages
- Future long-term memory:
  - not included yet in Phase 6.1 (no embeddings/vector DB).

Summary config env:

```bash
CONVERSATION_SUMMARY_ENABLED=true
CONVERSATION_SUMMARY_TRIGGER_MESSAGES=30
CONVERSATION_SUMMARY_KEEP_RECENT_MESSAGES=12
CONVERSATION_SUMMARY_MAX_CHARS=4000
CONVERSATION_SUMMARY_MODEL=nesty-flash-1.0
```

Behavior notes:

- Summarization is best-effort and must not fail chat responses.
- Summaries are sanitized by guard logic before being saved.
- `store=false` still disables conversation storage and summary logic.
- Streaming and non-streaming flows both preserve existing API contract.

## Conversation Quality, Controls, and Export (Phase 6.2)

Phase 6.2 adds runtime controls for per-request summary behavior and conversation management endpoints.

Per-request summary mode (`/v1/chat/completions`):

- `summary: "auto"`: default behavior (use summary when available and summarize by trigger policy).
- `summary: "off"`: do not inject summary and do not run post-response summarization for this request.
- `summary: "force"`: use existing summary and force post-response summarization when `store=true`.

Control and export endpoints:

- `POST /v1/conversations/{conversation_id}/summarize`
- `POST /v1/conversations/{conversation_id}/clear` with `{ "keep_summary": false }`
- `POST /v1/conversations/{conversation_id}/reset-summary`
- `GET /v1/conversations/{conversation_id}/export`

Conversation metadata now includes:

- `message_count`
- `last_message_at`
- `summary_exists`
- `summary_message_count`
- `summary_updated_at`

Privacy notes:

- Export returns stored sanitized conversation data (`conversation`, `summary`, `messages`).
- Export does not include API key hash/raw key secrets.
- Usage logs and provider secret config are not included in export.

## Run

```bash
python run.py
```

## Run Tests

```bash
python -m pytest -q
```

## Phase 4.1 Runtime Verification

Run full test suite:

```bash
python -m pytest -q
```

Verify scripts:

```bash
python scripts/create_api_key.py --name local-dev --env dev --daily-limit 1000 --models nesty-flash-1.0,nesty-combined-1.0
python scripts/list_api_keys.py
python scripts/usage_summary.py --days 7
```

Manual auth verification:

```bash
REQUIRE_API_KEY=true
PUBLIC_HEALTH=true
PUBLIC_MODELS=true
```

Then verify:

- `GET /health` is public.
- `GET /v1/models` is public.
- `POST /v1/chat/completions` requires API key.

Runtime note:

- FastAPI startup init is migrated from `@app.on_event("startup")` to lifespan.
- A specific TestClient deprecation warning may be filtered in pytest when it is upstream-only.
- In restricted environments, pytest cache warnings can appear and do not affect pass/fail.

Troubleshooting:

- If `.pytest_cache` cannot be written due to environment restrictions, test outcomes are still valid.
- If `python` is not in PATH, run tests with your interpreter launcher path directly.

## Deployment Recommendations

- Set `REQUIRE_API_KEY=true`.
- Set `NESTY_API_KEY_HASH_SECRET`.
- Do not commit `.env`.
- Do not commit `data/nesty.db`.
- Keep `SAFE_DEBUG_AUTH=false` in production.

## Deployment Hardening (Phase 5.2)

Recommended production env:

```bash
APP_ENV=production
REQUIRE_API_KEY=true
NESTY_API_KEY_HASH_SECRET=your_secret_here
CORS_ENABLED=true
CORS_ALLOW_ORIGINS=https://your-app.example.com
TRUSTED_HOSTS=your-api.example.com
SECURITY_HEADERS_ENABLED=true
ENABLE_HSTS=false
```

CORS guidance:

- Enable CORS only if browser/mobile-web clients need direct API access.
- Do not use wildcard CORS (`*`) in production when `REQUIRE_API_KEY=true`.
- Configure exact allowed origins.

Health vs readiness:

- `GET /health`: lightweight liveness signal.
- `GET /ready`: readiness signal with local database connectivity check.

Docker Compose quick start:

```bash
docker compose up --build -d
```

This uses `docker-compose.yml` with:

- `env_file: .env`
- persistent data mount `./data:/app/data`
- port mapping `8000:8000`

Reverse proxy note:

- In production, run NestyAI behind Nginx/Caddy/Traefik for TLS termination and request filtering.
- If TLS is guaranteed end-to-end, you may enable `ENABLE_HSTS=true`.

## Notes

- No billing implementation in Phase 4.
- No user accounts/login/OAuth in Phase 4.
- No admin HTTP endpoints yet (scripts only). Admin API can be Phase 4.5.
