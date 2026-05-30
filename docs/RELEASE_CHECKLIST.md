# Pre-Release Checklist

Use this checklist to verify the stability, security, and setup readiness of NestyAI before tag and release.

- [ ] **Run Full Test Suite**
  - Command: `python -m pytest -q`
  - Ensure all 320+ unit and integration tests pass successfully.

- [ ] **Run Project Doctor Script**
  - Command: `python scripts/doctor.py`
  - Ensure all critical checks pass and warnings are reviewed.

- [ ] **Verify Environment Template (`.env.example`)**
  - Ensure no actual secrets (API keys, admin tokens) are committed in the repository or template file.
  - Review that all environment variables have default descriptions or safe defaults.

- [ ] **Verify Docker Build**
  - Command: `docker compose build` or `docker build -t nesty-ai:latest .`
  - Confirm the image builds successfully without warnings or packaging failures.

- [ ] **Secret Hygiene Audit**
  - Check for any accidental hardcoded keys or hash secrets in git history (`git diff` or pre-commit hooks).

- [ ] **Verify Base and Health Endpoints**
  - Start the app: `python run.py`
  - Query health checks: `curl http://127.0.0.1:8000/health` (should return 200 OK).
  - Query ready checks: `curl http://127.0.0.1:8000/ready` (should return 200 OK).

- [ ] **Verify API Key Management**
  - Run the key generator: `python scripts/create_api_key.py --name test-key --env dev`
  - Verify that the prefix and generated key are displayed and saved to SQLite database correctly.

- [ ] **Verify Chat Completion (Non-Streaming)**
  - Send a simple POST request to `/v1/chat/completions` using a generated key and confirm response format matches OpenAI specs.

- [ ] **Verify Chat Completion (Streaming)**
  - Send a POST request with `"stream": true` to `/v1/chat/completions` and verify SSE chunks are generated and terminate with `data: [DONE]`.

- [ ] **Verify Provider Diagnostics**
  - Run diagnostics: `python scripts/benchmark_provider_chains.py --include-roles --dry-run`
  - Confirm provider paths can be resolved and simulated health check processes succeed.

- [ ] **Backup Database Before Upgrades**
  - Back up `data/nesty.db` before applying migrations or upgrading local databases in case rollback is needed.

- [ ] **Tag Release**
  - Tag the release version: `git tag -a vX.Y.Z -m "Release version X.Y.Z"`
  - Push tags: `git push origin vX.Y.Z`
