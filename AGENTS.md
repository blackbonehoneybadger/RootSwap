# AGENTS.md — RootSwap local development (scaffold)

> Scaffold lives under **`rootswap/`** (PR branch `cursor/mvp-polish-e6c2` /
> base `cursor/rootswap-initial-e6c2`). Canonical product code may also exist
> on `main` at repo root — prefer this `rootswap/` tree when working the MVP PR.

## Honest demo MVP path

1. Auth: Telegram `initData` **or** `POST /api/v1/auth/dev` (requires `ENABLE_DEV_ENDPOINTS=true`)
2. `GET /api/v1/assets` — supported routes (USDT TRC20, BTC, XMR ↔ RUB)
3. `POST /api/v1/quotes` — RootScore ranking in `best` / `all`
4. `POST /api/v1/orders` — BUY needs `wallet_address`; SELL needs `payout_details.account`
5. Response includes MOCK/SANDBOX `payment_instructions` (plaintext revealed for demo)
6. `POST /api/v1/orders/{id}/simulate-payment` — DEMO → `COMPLETED` (dev endpoints only)
7. Poll `GET /api/v1/orders/{id}` for status

**Dev endpoints are OFF by default** (`ENABLE_DEV_ENDPOINTS=false`).  
They are **forced off in production** even if the env var is set.

## Layout

```
rootswap/
  backend/   FastAPI + Alembic + pytest
  bot/       aiogram Telegram bot
  mini-app/  React/Vite Telegram Mini App
  deploy/    nginx
.github/workflows/ci.yml   # repo-root CI (Postgres + Redis + backend + frontend)
```

## Order / payment instructions schema

- **Owning FK + UNIQUE:** `payment_instructions.order_id → orders.id` (1:1)
- **Soft pointer:** `orders.payment_instructions_id` (UUID, **no DB FK**)
- Do not reintroduce a bidirectional FK — PostgreSQL rejects the circular insert.

## Backend

```bash
cd rootswap/backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt aiosqlite ruff

export TELEGRAM_BOT_TOKEN=0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER
export ENABLE_DEV_ENDPOINTS=true
export DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap

./.venv/bin/alembic upgrade head

# SQLite suite (default) + Postgres MVP when POSTGRES_TEST_DATABASE_URL is set
POSTGRES_TEST_DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap_test \
PYTHONPATH=. ./.venv/bin/pytest -v
./.venv/bin/ruff check .
```

Main suite DB override: `TEST_DATABASE_URL` (optional Postgres for all tests).  
Dedicated MVP / FK tests: `POSTGRES_TEST_DATABASE_URL`.

## Mini App

```bash
cd rootswap/mini-app
npm ci
npm run typecheck
npm run build
npm run dev   # proxies /api → http://127.0.0.1:8000
```

Browser without Telegram: calls `/auth/dev` only when `ENABLE_DEV_ENDPOINTS=true` on API.  
Telegram auth failure does **not** silently fall back to DEV auth.

## Local API run

```bash
cd rootswap
cp -n .env.example .env   # set ENABLE_DEV_ENDPOINTS=true for demo
# Avoid bash history expansion if ENCRYPTION_KEY ends with !! → set +H

cd backend
set +H
export $(grep -v '^#' ../.env | xargs)   # or export vars manually
PYTHONPATH=. ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Supported assets (MVP)

| Symbol | Network | Status |
|--------|---------|--------|
| RUB | — | supported (fiat) |
| USDT | TRC20 | supported |
| BTC | BTC | supported |
| XMR | XMR | supported (mock partners) |
| USDT | ERC20 | planned / disabled |
| SOL | SOL | planned / disabled |

## Status transitions

Central map: `app/services/state_machine.py` (`ALLOWED_TRANSITIONS`).  
Happy path: `CREATED → QUOTE_CONFIRMED → AWAITING_PAYMENT → … → COMPLETED`.  
`USER` may only target `CANCELLED` / `DISPUTED`. Simulate-payment uses `SYSTEM`.

## Remaining before real money (cannot be finished in this repo alone)

These require external work — **not** implemented as live REAL rails:

1. Partner contracts + REAL adapters
2. Security audit + legal/KYC review
3. Ops on-call / insurance / reserve policy

Code-side production guards already block weak secrets, MOCK in production,
DEV endpoints, and CORS `*`.
