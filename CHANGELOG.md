# Changelog

All notable changes to the NestyAI project are documented in this file.

## [Phase 8.1] - Health-Aware Routing & Diagnostics Polish
- Add health-aware routing capabilities to route chat requests away from unhealthy providers.
- Implement provider health summary endpoint and CLI reporting.
- Polish provider diagnostics script error checking.
- Refactor test suite mocks to prevent unwanted health DB access in test runs.

## [Phase 8.0] - Provider Diagnostics
- Implement lightweight provider and model chẩn đoán checks using small prompts.
- Save diagnostics outputs locally under `provider_health_checks` table.
- Create admin-protected chẩn đoán utility endpoints.
- Add provider benchmark CLI utility scripts.

## [Phase 7.3] - Memory Safety & Pinned Recall Boosts
- Add support for message-level memory overrides (`memory_pinned`, `memory_excluded`, `memory_tags`).
- Implement recall filters to prevent duplicated or overly redundant retrieval items.
- Ensure cross-user and cross-key memory boundaries remain strictly isolated.

## [Phase 7.2] - Local Semantic Recall
- Add local cosine similarity retrieval over SQLite-stored embedding records.
- Implement contextual-only memory injections for completions.
- Add test utilities to evaluate similarity performance.

## [Phase 7.1] - Embedding Abstraction
- Support OpenRouter and NVIDIA embedding providers.
- Save message-level embeddings to `embedding_records` automatically on chat completions.
- Implement CLI tool to backfill and rebuild database embeddings.

## [Phase 7.0d] - Provider Chain Tuning
- Configure stable provider fallbacks for `nesty-flash-1.0` and `nesty-combined-1.0` aliases.

## [Phase 7.0c] - Runtime Model Config API
- Add admin endpoints (`/internal/model-configs/*`) to fetch, patch, reset, and test model routing strategies on the fly.
- Maintain configuration audits in `model_config_audit_logs`.

## [Phase 7.0b] - Orchestration Cost Safety
- Enforce call boundaries and token limit gates during deep synthesis orchestration roles.

## [Phase 7.0a] - Model Behavior & Pro Orchestration
- Build multi-model synthesis strategy for the `nesty-pro-1.0` profile.
- Orchestrate planner, researcher, critic, and finalizer roles.

## [Phase 7.0] - SQLite FTS Message Search
- Add SQLite FTS5 table indexing for conversation messages with keyword LIKE fallback.

## [Phase 6.3] - Conversation Search Endpoints
- Implement `GET /v1/conversations/search` endpoint to query historic sessions.

## [Phase 6.2] - Conversation Controls & Export
- Implement conversation controls: clear, reset summary, and export endpoints.

## [Phase 6.1] - Session Summaries
- Add automatic contextual summarization (`summary=auto|off|force`) when message thresholds are crossed.

## [Phase 6.0] - Conversation Sessions
- Implement sqlite-backed stateful chat sessions. Clients can query and load previous history by passing `conversation_id`.

## [Phase 5.2] - Deployment Hardening
- Implement BodySizeLimitMiddleware, TrustedHostMiddleware, and SecurityHeadersMiddleware.
- Enforce strict wildcard CORS policies in production.

## [Phase 5.1] - Client Examples
- Add stream/non-stream implementation examples in Python, JavaScript, and Kotlin/Android.

## [Phase 5] - Streaming Completions
- Implement SSE (Server-Sent Events) streaming contract for model responses.

## [Phase 4.1] - Runtime Polish
- Hardened model router and fallback selection rules.

## [Phase 4] - Auth, Rate Limiting & Quota
- Implement API key authorization via SHA-256 HMAC prefix verification.
- Enforce rate-limits and daily/monthly quotas.

## [Phase 3.5] - Cache & Data Providers
- Implement caching for internal Web search and currency exchanges.

## [Phase 3] - Tool Integration
- Integrate calculator, Wikipedia, and weather lookup tools.

## [Phase 2.5] - QA & Hardening
- Stabilize fallback routing logic and add basic tests.

## [Phase 2] - Search & Context Guard
- Implement InputGuard, OutputGuard, and ContextGuard modules.

## [Phase 1] - MVP Gateway
- Initialize FastAPI app setup with basic chat completion route (`POST /v1/chat/completions`).
