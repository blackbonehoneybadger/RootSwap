# RootSwap deployment guide

This guide covers **mock/sandbox demo deployment** on a single VPS with Docker Compose. Real-money production requires the checklist in the root [README.md](../README.md).

## Architecture

```
Internet → nginx:80/443
              ├── /          → mini-app (static React build)
              ├── /api/*     → FastAPI backend
              └── /health    → backend health probe

Internal (not exposed in prod):
  postgres:5432, redis:6379, bot (Telegram long-polling/webhook)
```

## Prerequisites

- Linux host with Docker Engine 24+ and Docker Compose v2
- Domain name pointing to the server (required for Telegram Mini App HTTPS)
- Telegram Bot created via [@BotFather](https://t.me/BotFather)
- TLS certificates (Let's Encrypt recommended)

## 1. Clone and configure

```bash
git clone https://github.com/blackbonehoneybadger/RootSwap.git
cd RootSwap
git checkout main   # canonical branch with full v0.1 codebase
cp .env.example .env
```

Generate secrets:

```bash
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
python3 -c "import secrets; print('PARTNER_WEBHOOK_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))"
```

Fill `.env` (minimum for **demo/mock** on a staging host):

| Variable | Example | Notes |
|---|---|---|
| `ENVIRONMENT` | `staging` | Use `production` only after audit + real partners |
| `TELEGRAM_BOT_TOKEN` | from BotFather | Same token for `api` and `bot` services |
| `TELEGRAM_BOT_USERNAME` | `YourBotName` | Without `@`; used in referral links |
| `BOT_USERNAME` | same as above | Mini App build arg |
| `MINI_APP_URL` | `https://swap.example.com` | Public HTTPS URL of the Mini App |
| `PUBLIC_ORIGIN` | `https://swap.example.com` | CORS + nginx origin |
| `ADMIN_TELEGRAM_IDS` | `{"123456789": "ADMIN"}` | Your Telegram user id → role |

For **mock demo** you may keep `ALLOW_MOCK_PARTNERS=true`. For anything resembling production, set both mock/sandbox gates to `false`.

## 2. TLS certificates

Place certificates in `deploy/certs/`:

```
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

Then uncomment the HTTPS `server { listen 443 ... }` block in [nginx/nginx.conf](./nginx/nginx.conf) and set `server_name` to your domain. Redirect HTTP → HTTPS in the port-80 block.

## 3. Build and start

```bash
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml ps
curl -fsS http://localhost/health
```

First boot runs Alembic migrations automatically via [backend/entrypoint.sh](../backend/entrypoint.sh).

## 4. Telegram Bot setup

In [@BotFather](https://t.me/BotFather):

1. `/setdomain` — set your domain for the Mini App
2. Menu button → Web App → URL = `MINI_APP_URL`
3. Optional: `/setdescription` with DEMO disclaimer

The `bot` container handles `/start` and opens the Mini App. Order status notifications are sent by the **backend** when `NOTIFICATIONS_ENABLED=true` (enabled in prod compose).

## 5. Smoke checks

```bash
# API health
curl -fsS https://swap.example.com/health

# Readiness (DB connected)
curl -fsS https://swap.example.com/health/ready

# Open bot in Telegram → start Mini App → complete a mock BUY flow
```

Backend test suite (run on CI or locally before deploy):

```bash
cd backend && pytest -q          # 131 tests
cd backend && pytest -q tests/e2e # mock flows only
```

## 6. Operations

| Action | Command / endpoint |
|---|---|
| View logs | `docker compose -f docker-compose.prod.yml logs -f api` |
| Emergency stop | `POST /api/v1/admin/emergency-stop` (ADMIN role) |
| Ledger check | `GET /api/v1/admin/ledger/reconciliation` (FINANCE) |
| Partner status | `GET /api/v1/admin/partners` |
| Dead-letter webhooks | `GET /api/v1/admin/webhooks` |

See root README runbooks for dispute/refund procedures.

## 7. Backups (required before real money)

```bash
# Example daily Postgres dump (adjust paths/cron)
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U rootswap rootswap | gzip > rootswap-$(date +%F).sql.gz
```

Test restore on a staging instance before relying on backups.

## 8. Branch reference

| Branch | Purpose |
|---|---|
| `main` | **Canonical** — merged v0.1 + ongoing fixes |
| `cursor/rootswap-polish-e6c2` | Polish PR (audit fixes); merge into `main` |
| `cursor/rootswap-initial-e6c2` | **Obsolete** — early scaffold only; do not deploy |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Mini App shows "Open in Telegram" | Opened outside Telegram; `initData` missing |
| Auth 401 | Wrong `TELEGRAM_BOT_TOKEN` or clock skew |
| API 503 on quotes | Emergency stop active |
| Prod container exits on start | Weak/missing secrets — check `docker logs api` |
| Notifications silent | `NOTIFICATIONS_ENABLED=false` or bot token missing |
