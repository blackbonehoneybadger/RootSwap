# Canonicalization notes

## Baseline (pre-integration)

- Branch: `feature/canonical-telegram-mini-app`
- Base: `main` @ `d7bed4cb35cff936e640d6302b028d49198fb315`
- Layout: `backend/`, `mini-app/`, `bot/`, `deploy/` (no `rootswap/` runtime)
- Backend tests: **133 passed** (`pytest -q`, clean env — do not export a different `TELEGRAM_BOT_TOKEN` before tests)
- Frontend: typecheck + build OK; `npm audit --audit-level=high` → 0
- Bot: `compileall` + ruff OK

## Why PR #7 / #8 must not be merged

Those PRs nest a second codebase under `rootswap/` on top of an obsolete Cursor scaffold.
Merging them would duplicate models, Alembic history, and CI paths.

Useful pieces are ported **manually** into the canonical tree.
