# Telegram Mini App & BotFather setup

Canonical code lives at repo root (`backend/`, `mini-app/`, `bot/`).

## BotFather

1. `/newbot` — create bot, store token in secrets (never git).
2. Set Menu Button / Web App URL to `MINI_APP_URL` (HTTPS in production).
3. `/setdescription` and short description — include sandbox disclaimer.
4. Domain allowlist for the Mini App host.
5. CORS on API must allow that origin (no `*` in production).

## Env

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot API + initData HMAC |
| `MINI_APP_URL` | Web App URL |
| `JWT_SECRET` | HS256 secret (≥32 chars) |
| `ALLOW_MOCK_PARTNERS` | false in production |
| `TELEGRAM_AUTH_INSECURE_SKIP` | never in production |

## Auth

Frontend (`mini-app/src/lib/telegram.ts`) sends signed `initData` once at boot.
Locale / theme changes must **not** re-authenticate (replay protection).
