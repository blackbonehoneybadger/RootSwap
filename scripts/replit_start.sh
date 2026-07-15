#!/usr/bin/env bash
# RootSwap single-process launcher for Replit (and any bare VM without Docker).
#
# Runs everything in one Repl:
#   - FastAPI backend (uvicorn) on $PORT, SQLite instead of Postgres,
#     in-memory rate limiting instead of Redis
#   - built Mini App served by the backend at /
#   - aiogram bot (long polling) when TELEGRAM_BOT_TOKEN is set
#
# Mock/sandbox only: no real money. Set TELEGRAM_BOT_TOKEN in Replit Secrets
# to make the bot and Mini App auth work with your real Telegram bot.

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

export ENVIRONMENT="${ENVIRONMENT:-development}"
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$ROOT/rootswap.db}"
export ALLOW_MOCK_PARTNERS="${ALLOW_MOCK_PARTNERS:-true}"
export POLLING_ENABLED="${POLLING_ENABLED:-true}"
export MINI_APP_STATIC_DIR="${MINI_APP_STATIC_DIR:-$ROOT/mini-app/dist}"
PORT="${PORT:-8000}"

# Public HTTPS URL of this Repl -> Mini App URL for the bot button.
if [ -z "${MINI_APP_URL:-}" ]; then
  if [ -n "${REPLIT_DOMAINS:-}" ]; then
    export MINI_APP_URL="https://${REPLIT_DOMAINS%%,*}"
  elif [ -n "${REPLIT_DEV_DOMAIN:-}" ]; then
    export MINI_APP_URL="https://${REPLIT_DEV_DOMAIN}"
  fi
fi

echo "==> RootSwap (mock/sandbox) starting"
echo "    ENVIRONMENT=$ENVIRONMENT  DATABASE_URL=$DATABASE_URL"
echo "    MINI_APP_URL=${MINI_APP_URL:-<not set>}"

# --- Python deps (backend + bot in one interpreter) -------------------------
VENV="$ROOT/.venv-replit"
if [ ! -x "$VENV/bin/python" ]; then
  echo "==> Creating virtualenv"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --disable-pip-version-check \
  -r backend/requirements.txt -r bot/requirements.txt

# --- Mini App build ----------------------------------------------------------
if [ ! -f "$MINI_APP_STATIC_DIR/index.html" ]; then
  echo "==> Building Mini App (first run only)"
  (cd mini-app && npm ci --no-audit --no-fund && npm run build)
fi

# --- Database migrations ------------------------------------------------------
echo "==> Running migrations"
(cd backend && "$VENV/bin/alembic" upgrade head)

# --- Telegram bot (background) ------------------------------------------------
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  export NOTIFICATIONS_ENABLED="${NOTIFICATIONS_ENABLED:-true}"
  echo "==> Starting Telegram bot (long polling)"
  (cd bot && exec "$VENV/bin/python" bot.py) &
  BOT_PID=$!
  trap 'kill "$BOT_PID" 2>/dev/null || true' EXIT
else
  echo "==> TELEGRAM_BOT_TOKEN is not set: bot skipped."
  echo "    Add it in Replit Secrets to enable the bot and Mini App auth."
fi

# --- API + Mini App -------------------------------------------------------------
echo "==> Starting API on port $PORT (Mini App served at /)"
cd backend
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port "$PORT"
