# Deployment Guide

This guide describes how to deploy NestyAI in development and production environments.

---

## 1. Local Run

To deploy NestyAI locally for development or testing:

1. **Install Python 3.11+**
2. **Clone and Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
3. **Configure Environment**:
   ```bash
   copy .env.example .env
   ```
   Edit `.env` and set at least one provider API key (`GROQ_API_KEY`, `OPENROUTER_API_KEY`, etc.).
4. **Run Diagnostics**:
   ```bash
   python scripts/doctor.py
   ```
5. **Start App**:
   ```bash
   python run.py
   ```
   The gateway will be available at `http://127.0.0.1:8000`.

---

## 2. Docker Compose (Self-Hosting)

Docker is the recommended approach for hosting NestyAI continuously.

1. **Verify `docker-compose.yml`**:
   The default setup mounts the `data` directory to persist SQLite databases.
2. **Build and Start Container**:
   ```bash
   docker compose up --build -d
   ```
3. **Verify Logs**:
   ```bash
   docker compose logs -f
   ```
4. **Execute CLI Scripts Inside Container**:
   ```bash
   docker compose exec nesty-ai python scripts/create_api_key.py --name my-key
   ```

---

## 3. Cloudflare Tunnel Deployment

For a secure personal deployment without opening ports on your home router:

1. **Set Up Cloudflare Tunnel**:
   - Install `cloudflared` on your host.
   - Run `cloudflared tunnel create <tunnel-name>`.
2. **Route Traffic**:
   Route your public domain (e.g. `gateway.example.com`) to the local port `http://localhost:8000`.
3. **Configure CORS & Trusted Hosts**:
   In `.env`, set:
   ```env
   TRUSTED_HOSTS=gateway.example.com
   CORS_ALLOW_ORIGINS=https://your-ui-app.example.com
   ```
   This prevents unauthorized domain hosts or unsafe browsers from querying your gateway.

---

## 4. Production Hardening Settings

When deploying NestyAI to production, configure these security and optimization settings in your `.env`:

```env
# Enforce production mode (disables generic stack trace details in generic errors)
APP_ENV=production

# Security - Enforce API Keys
REQUIRE_API_KEY=true

# Security - Set a strong hash secret (crucial to secure API key matching)
NESTY_API_KEY_HASH_SECRET=your_long_random_secure_secret_string

# Admin API Access - Disable unless active config changes are required
INTERNAL_ADMIN_ENABLED=false

# CORS - NEVER use wildcard '*' in production when REQUIRE_API_KEY=true
CORS_ENABLED=true
CORS_ALLOW_ORIGINS=https://your-exact-app-domain.com

# Hosts - Accept only requests targeted to your host
TRUSTED_HOSTS=your-gateway-host.com
```

---

## 5. Operational Notes

> [!WARNING]
> **Provider Diagnostics & Quotas**: 
> Enabling periodic health checks (like running `benchmark_provider_chains.py` via cron) consumes normal provider token quotas. Adjust check frequencies to be conservative (e.g., once every 15-30 minutes) to prevent hitting provider rate limits.

> [!IMPORTANT]
> **Semantic Recall & Backfill**:
> To use semantic recall, you must enable embeddings (`EMBEDDINGS_ENABLED=true`) and embedding storage (`EMBEDDINGS_STORE_MESSAGE_EMBEDDINGS=true`). For conversations that occurred while embeddings were disabled, run the backfill script:
> ```bash
> python scripts/rebuild_embeddings.py
> ```
