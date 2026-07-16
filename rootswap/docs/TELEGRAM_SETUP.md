# Telegram Mini App & BotFather setup

RootSwap opens as a **Telegram Mini App** via a bot Web App button.  
Do **not** commit a real bot token. Use environment variables only.

## 1. Create the bot (BotFather)

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` and follow prompts (display name + username ending in `bot`).
3. Copy the **bot token** into your secrets store / `.env`:

```bash
TELEGRAM_BOT_TOKEN=<from BotFather — never commit>
```

## 2. Set Mini App URL

HTTPS is required for production Telegram Mini Apps.

1. Host the Mini App behind HTTPS (see `deploy/OPS_RUNBOOK.md`).
2. Set:

```bash
MINI_APP_URL=https://app.example.com
```

3. In BotFather:
   - `/setmenubutton` → choose your bot → **Configure menu button** → URL = `MINI_APP_URL`
   - Or `/mybots` → Bot Settings → Menu Button → Configure menu button

## 3. Web App button (already in code)

`rootswap/bot/bot.py` sends `/start` with an inline **«Открыть RootSwap»** button using `WebAppInfo(url=MINI_APP_URL)`.

Local HTTP URLs work only with Telegram Desktop in some cases; mobile clients need HTTPS.

## 4. Description & short description

In BotFather:

- `/setdescription` — longer text (aggregator, sandbox disclaimer, no seed phrases)
- `/setabouttext` or short description — one-line summary
- `/setuserpic` — optional logo

Suggested short description:

> RootSwap — crypto exchange aggregator in Telegram (demo/sandbox). Real money disabled.

## 5. Domain allowlist

1. Deploy Mini App on a stable HTTPS domain.
2. BotFather → Bot Settings → Domain → set the Mini App host (no path).
3. Backend CORS must allow that origin (`CORS_ORIGINS` / `ALLOWED_ORIGINS` — never `*` in production).

## 6. Required environment variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot API + initData HMAC verification |
| `MINI_APP_URL` | Web App / Menu Button URL |
| `JWT_SECRET` | Strong secret; no default in production |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRE_MINUTES` | Short-lived access tokens |
| `DATABASE_URL` | PostgreSQL |
| `REDIS_URL` | Rate limit, initData replay store |
| `ENABLE_DEV_ENDPOINTS` | Must be `false` in production |
| `ENABLE_MOCK_PARTNERS` | Sandbox only; production forbids MOCK quotes |
| `ENVIRONMENT` | `development` / `staging` / `production` |
| `CORS_ORIGINS` | Explicit allowlist |
| `WEBHOOK_SECRET` / partner secrets | Partner webhook HMAC |

See `rootswap/.env.example`.

## 7. Auth flow

1. User opens Mini App → official `telegram-web-app.js` loads.
2. Frontend (`src/lib/telegram.ts`) calls `ready()` / `expand()`, reads `initData`.
3. `POST /api/v1/auth/telegram` with raw `init_data`.
4. Backend verifies hash, `auth_date`, replay, user payload → JWT.
5. Never trust `initDataUnsafe` alone.

## 8. Local development without Telegram

1. `ENABLE_DEV_ENDPOINTS=true` on backend.
2. Vite `npm run dev` — Mini App uses `/auth/dev` only when `import.meta.env.DEV`.
3. Production builds must not call `/auth/dev`.

## 9. Checklist before showing users a demo

- [ ] HTTPS Mini App URL configured in BotFather
- [ ] Menu Button + `/start` Web App button open the same URL
- [ ] Backend verifies initData with the **same** bot token
- [ ] Demo banner visible (sandbox / no real money)
- [ ] DEV endpoints off if the API is reachable from the internet
