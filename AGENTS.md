# AGENTS.md — RootSwap local development (scaffold branch)

> This file documents how to run and test the **rootswap/** scaffold on branch
> `cursor/rootswap-initial-e6c2`. Canonical merged code also lives on `main` at
> the repository root; prefer `main` for production-bound work.

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

### PostgreSQL integration test (order create / circular FK guard)

Start Postgres (and Redis if running the full stack):

```bash
cd rootswap
docker compose -f docker-compose.dev.yml up -d postgres redis
# create the isolated test database once
docker compose -f docker-compose.dev.yml exec -T postgres \
  psql -U rootswap -d rootswap -c "CREATE DATABASE rootswap_test;" || true
```

Apply migrations against a real database:

```bash
cd rootswap/backend
DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap \
  ./.venv/bin/alembic upgrade head
```

Run the full suite including the Postgres order-create test:

```bash
cd rootswap/backend
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

## Full stack (manual E2E)

```bash
cd rootswap
cp -n .env.example .env   # if present; otherwise export TELEGRAM_BOT_TOKEN
docker compose -f docker-compose.dev.yml up --build
```

- API: http://localhost:8000/docs
- Mini App: http://localhost:5173
- Postgres: localhost:5432 (user/password/db: `rootswap`)

Manual check path:

1. `POST /api/v1/auth/telegram` (or open Mini App inside Telegram / DEV mode)
2. `POST /api/v1/quotes` BUY RUB→XMR
3. `POST /api/v1/orders` with wallet + idempotency key
4. Confirm `payment_instructions` in the response
5. Verify DB rows:
   ```sql
   SELECT o.id, o.payment_instructions_id, pi.id, pi.order_id
   FROM orders o
   JOIN payment_instructions pi ON pi.id = o.payment_instructions_id
   ORDER BY o.created_at DESC LIMIT 5;
   ```

## Architecture notes (order / payment instructions)

- **Owning FK:** `payment_instructions.order_id → orders.id`
- **Soft pointer:** `orders.payment_instructions_id` (UUID, nullable, **no DB FK**)
- Do not reintroduce a bidirectional FK between these tables — PostgreSQL
  rejects the circular insert that SQLite tests historically masked.

## Secrets

Never commit real secrets. Dev placeholders are fine in local `.env` only.
