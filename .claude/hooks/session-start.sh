#!/bin/bash
# SessionStart hook for Claude Code on the web.
# Installs backend, bot and mini-app dependencies so ruff/pytest and the
# frontend toolchain work immediately in a fresh remote session.
# Synchronous + idempotent. Only runs in the remote (web) environment.
set -euo pipefail

# Only meaningful in Claude Code on the web; local shells set up their own env.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

echo "[session-start] Setting up RootSwap dependencies..."

# --- Backend (+ bot): one virtualenv with dev deps and the bot runtime -------
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "[session-start] Creating backend virtualenv"
  python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
echo "[session-start] Installing backend dev requirements"
"$VENV/bin/pip" install --quiet -r "$BACKEND/requirements-dev.txt"
echo "[session-start] Installing bot requirements"
"$VENV/bin/pip" install --quiet -r "$ROOT/bot/requirements.txt"

# Expose the venv on PATH for the session so `ruff`/`pytest` resolve directly.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export PATH=\"$VENV/bin:\$PATH\""
    echo "export VIRTUAL_ENV=\"$VENV\""
  } >> "$CLAUDE_ENV_FILE"
fi

# --- Mini App: npm dependencies ----------------------------------------------
echo "[session-start] Installing mini-app npm dependencies"
( cd "$ROOT/mini-app" && npm install --no-audit --no-fund )

echo "[session-start] Dependencies ready."
