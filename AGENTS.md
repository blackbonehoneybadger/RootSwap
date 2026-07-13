# AGENTS.md

## Cursor Cloud specific instructions

The entire project lives in `rootswap/` (repo root only has `README.md`). See `rootswap/README.md` for the canonical command list; notes below cover non-obvious caveats for this cloud VM.

### Services & how they run (dev, no Docker)

The VM runs services natively (no Docker). System services are installed via the snapshot and started with `sudo service postgresql start` / `sudo service redis-server start`.

| Service | Port | Run from | Command |
|---------|------|----------|---------|
| PostgreSQL 16 | 5432 | — | `sudo service postgresql start` (role/db: `rootswap`/`rootswap`, password `rootswap`; DBs `rootswap` + `rootswap_test`) |
| Redis 7 | 6379 | — | `sudo service redis-server start` (optional; rate-limit middleware degrades gracefully if absent) |
| Backend API (FastAPI) | 8000 | `rootswap/backend` | `./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Mini App (Vite/React) | 5173 | `rootswap/mini-app` | `VITE_API_URL=http://localhost:8000/api npm run dev` |

- Python deps live in a venv at `rootswap/backend/.venv` (repo requires Python 3.12). Activate it or call binaries directly (`./.venv/bin/...`).
- The backend `config.py` **rejects any non-`postgresql` `DATABASE_URL`**, so the app must run against Postgres. Dev defaults in `config.py` already point at the local Postgres above, so no `.env` is required to run it.
- Before running the backend, apply migrations from `rootswap/backend`: `./.venv/bin/alembic upgrade head`. This also seeds the two `mock_fiat` partners needed for quotes.

### Tests / lint / build

- Backend tests (from `rootswap/backend`): set `PYTHONPATH=.` and `TELEGRAM_BOT_TOKEN=0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER`, then `./.venv/bin/pytest -v`. Without `PYTHONPATH=.` collection fails with `ModuleNotFoundError: No module named 'app'`.
- Tests default to SQLite (`sqlite+aiosqlite:///./test_rootswap.db`). Running them against Postgres via `TEST_DATABASE_URL` currently fails with `asyncpg` "attached to a different loop" errors because the engine fixture is session-scoped — prefer the default SQLite run locally.
- Lint (from `rootswap/backend`): `./.venv/bin/ruff check .`. There are pre-existing lint failures in the repo (import ordering in `services/*.py` and an undefined name in `tests/test_e2e.py`); they are not caused by environment setup.
- Mini app (from `rootswap/mini-app`): `npm run typecheck` and `npm run build` both pass.

### Known gotchas

- **Order creation fails on Postgres (pre-existing app bug).** `Order.payment_instructions_id` ↔ `PaymentInstructions.order_id` form a circular FK declared without `use_alter`/`post_update`, so the orchestrator's flush emits the `orders` UPDATE before the `payment_instructions` INSERT and Postgres raises `ForeignKeyViolationError`. SQLite hides this (FK enforcement off by default), which is why the SQLite test suite passes. Auth and quote endpoints work end-to-end on Postgres.
- The Mini App authenticates from Telegram `initData`; in a plain browser that is empty, so the app loads unauthenticated and authed API calls 401. To exercise authed flows in a browser, mint a JWT via `POST /api/v1/auth/telegram` (see `backend/tests/conftest.py` `make_init_data`) and set it as `localStorage.rootswap_token`, then reload.
