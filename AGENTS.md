# AGENTS.md — RootSwap local development (scaffold branch)

> This file documents how to run and test the **rootswap/** scaffold on branch
> `cursor/rootswap-initial-e6c2` (and feature branches based on it). Canonical
> merged code also lives on `main` at the repository root; prefer `main` for
> production-bound work if layouts diverge.

## MVP happy path (mock)

1. Auth: Telegram `initData` **or** `POST /api/v1/auth/dev` (non-production)
2. `POST /api/v1/quotes` — BUY RUB→crypto or SELL crypto→RUB
3. `POST /api/v1/orders` — BUY needs `wallet_address`; SELL needs `payout_details.account`
4. Response includes MOCK/SANDBOX `payment_instructions` (revealed plaintext fields)
5. `POST /api/v1/orders/{id}/simulate-payment` — DEMO jump to `COMPLETED`
6. Mini App polls order status / timeline until a final status

## Layout

```
rootswap/
  backend/   FastAPI + Alembic + pytest
  bot/       aiogram Telegram bot
  mini-app/  React/Vite Telegram Mini App
  deploy/    nginx
  docker-compose.dev.yml
  docker-compose.prod.yml
```

## Backend local setup

```bash
cd rootswap/backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt aiosqlite ruff
```

### SQLite tests (default — always run these)

```bash
cd rootswap/backend
PYTHONPATH=. TELEGRAM_BOT_TOKEN=0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER \
  ./.venv/bin/pytest -v
./.venv/bin/ruff check .
```

### PostgreSQL integration (order create / FK + full suite)

Without Docker (system Postgres/Redis):

```bash
# DB: rootswap / rootswap_test, user/password rootswap
sudo -u postgres createuser -s rootswap  # once, if needed
createdb -U rootswap rootswap
createdb -U rootswap rootswap_test
```

With Docker:

```bash
cd rootswap
docker compose -f docker-compose.dev.yml up -d postgres redis
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U rootswap -d rootswap -c "CREATE DATABASE rootswap_test;" || true
```

Migrations + tests:

```bash
cd rootswap/backend
DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap \
  ./.venv/bin/alembic upgrade head

POSTGRES_TEST_DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap_test \
PYTHONPATH=. TELEGRAM_BOT_TOKEN=0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER \
  ./.venv/bin/pytest -v
```

## Mini App

```bash
cd rootswap/mini-app
npm install
npm run typecheck
npm run build
```

Vite proxies `/api` → `http://127.0.0.1:8000` in dev. Without Telegram,
the app calls `/api/v1/auth/dev` automatically.

## Full stack (manual E2E)

```bash
cd rootswap
cp -n .env.example .env
# Avoid bash history expansion on ENCRYPTION_KEY if it ends with !! — use set +H
# or change the key in .env

# Docker:
docker compose -f docker-compose.dev.yml up --build

# Or local API (Postgres + Redis already up):
cd backend
set +H
export DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap
export REDIS_URL=redis://localhost:6379/0
export TELEGRAM_BOT_TOKEN=0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER
export JWT_SECRET=rootswap-dev-jwt-secret-change-in-production
export ENCRYPTION_KEY='dev-encryption-key-32bytes-long!!'
export TELEGRAM_WEBHOOK_SECRET=dev-webhook-secret
export ADMIN_API_KEYS=ADMIN:dev-admin-key
PYTHONPATH=. ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# Mini App (another terminal):
cd ../mini-app && npm run dev
```

- API: http://localhost:8000/docs
- Mini App: http://localhost:5173

Manual API check:

```bash
# health → auth/dev → quotes → orders → simulate-payment
curl -s http://127.0.0.1:8000/health
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/dev \
  -H 'Content-Type: application/json' \
  -d '{"telegram_id":900001,"username":"dev_user"}' | jq -r .access_token)
# ... then quotes / orders with Authorization: Bearer $TOKEN
```

Verify DB rows after order create:

```sql
SELECT o.id, o.status, o.payment_instructions_id, pi.id, pi.order_id
FROM orders o
JOIN payment_instructions pi ON pi.id = o.payment_instructions_id
ORDER BY o.created_at DESC LIMIT 5;
```

## Architecture notes (order / payment instructions)

- **Owning FK:** `payment_instructions.order_id → orders.id`
- **Soft pointer:** `orders.payment_instructions_id` (UUID, nullable, **no DB FK**)
- Do not reintroduce a bidirectional FK between these tables — PostgreSQL
  rejects the circular insert that SQLite tests historically masked.

## DEMO endpoints (disabled in production)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/auth/dev` | Browser auth without Telegram |
| `POST /api/v1/orders/{id}/simulate-payment` | Complete MOCK/SANDBOX order |

## Secrets

Never commit real secrets. Dev placeholders are fine in local `.env` only.
Production startup rejects weak secrets and MOCK/SANDBOX quote sources.
