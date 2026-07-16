# RootSwap Operations Runbook (Mock/Sandbox MVP)

> Real money is disabled. This runbook covers demo/staging operations and
> production **blockers**. Legal review and partner contracts are out of band.

## Environments

| Env | MOCK quotes | DEV endpoints | CORS | Notes |
|-----|-------------|---------------|------|-------|
| development | yes | `ENABLE_DEV_ENDPOINTS=true` | `*` ok | Local only |
| staging | sandbox OK | false recommended | allowlist | Use `nginx.staging-https.conf` |
| production | **forbidden** | **forced false** | allowlist required | Startup validates secrets |

## Health & monitoring

- Liveness: `GET /health` → process up
- Readiness: `GET /health/ready` → **503** if Postgres or Redis down
- Metrics: `GET /metrics` (Prometheus text; nginx ACL to private nets)
- Structlog JSON on stdout — ship to your log aggregator

Alert suggestions:
- `health/ready` != 200 for > 1 min
- `rate_limit_redis_unavailable` / 503 spike
- `emergency_stop` gauge == 1
- webhook `DEAD_LETTER` growth

## Emergency stop

Persisted in Redis key `rootswap:emergency_stop` (survives API restart).

```bash
# Activate
curl -X POST https://$HOST/api/v1/admin/emergency-stop -H "X-Admin-Key: $ADMIN_KEY"
# Deactivate
curl -X DELETE https://$HOST/api/v1/admin/emergency-stop -H "X-Admin-Key: $ADMIN_KEY"
```

Effect: new order creates return 503 (`EmergencyStopError`).

## Staging HTTPS

1. Obtain certs (Let's Encrypt or corp CA)
2. Mount `fullchain.pem` + `privkey.pem` at `/etc/nginx/certs/`
3. Use `deploy/nginx/nginx.staging-https.conf` (HTTP→HTTPS redirect + HSTS)
4. Set `CORS_ORIGINS=https://your-mini-app.example`
5. Keep `ENABLE_DEV_ENDPOINTS=false`

## Demo flow (safe)

1. `ENABLE_DEV_ENDPOINTS=true` **only** on local/dev
2. Mini App browser → `/auth/dev` (sessionStorage JWT, 1h TTL)
3. Quotes → order → simulate-payment → COMPLETED
4. Never enable simulate-payment or DEV auth in production (startup forbids)

## Before real money (blockers — not done in code)

1. Partner contract + REAL adapters (not MOCK)
2. Independent security audit
3. Legal/KYC/AML per jurisdiction
4. Disable MOCK/SANDBOX quote sources
5. Strong secrets; no placeholder bot token; Redis password; CORS allowlist
6. Financial reconciliation ops + on-call
7. Penetration test of webhooks
8. Insurance / reserve policy

## Supported assets (code registry)

| Asset | Status |
|-------|--------|
| RUB, USDT/TRC20, BTC, XMR | **Sandbox only** (mock partner) |
| ETH, TON, XRP, DOGE, DASH, BNB/BSC, USDT/USDC other nets | **Planned** |

See `docs/TELEGRAM_SETUP.md` and `docs/PARTNER_ADAPTERS.md`.

## Security checklist (runtime)

- [ ] `ENVIRONMENT=production` with all `validate_production` secrets rotated
- [ ] `TRUSTED_PROXY_IPS` set to nginx container/host IPs
- [ ] OpenAPI `/docs` disabled (automatic in production)
- [ ] TLS via `nginx.staging-https.conf` (or equivalent)
- [ ] Telegram bot token never logged; admin keys ≥24 chars
- [ ] Monitor 401 webhook spikes and rate-limit 429/503
