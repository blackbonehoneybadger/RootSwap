# RootSwap

RootSwap is a **privacy-focused, non-custodial where possible** crypto exchange aggregator delivered as a Telegram Bot + Telegram Mini App + Backend API.

> **Real money is disabled in this version.**  
> **Mock partners are synthetic.**  
> **Sandbox does not move real funds.**  
> **Production launch requires partner contract, security audit, legal review, and operational runbook.**

## Current Status: Mock/Sandbox Only

This first version implements a fully working mock/sandbox flow for:

| Direction | Route |
|-----------|-------|
| BUY | RUB → XMR |
| BUY | RUB → USDT TRC20 |
| BUY | RUB → BTC |
| SELL | USDT TRC20 → RUB |
| SELL | BTC → RUB |
| SELL | XMR → RUB |

### What Works

- Telegram Bot with Mini App button and referral `start=ref_CODE`
- Mini App UI: buy/sell, quotes, orders, history, referrals, profile
- Mock partner engine with deterministic scenarios
- Quote engine with RootScore, parallel partner polling, circuit breaker
- Order orchestrator with state machine, idempotency, encrypted payment instructions
- Webhook processing with signature verification, replay protection, deduplication
- Polling fallback worker for active orders
- Immutable ledger with reconciliation
- Single-level referral rewards (paid once on COMPLETED)
- Admin API with RBAC and audit logging
- Emergency stop
- Production startup guards (rejects weak secrets, MOCK/SANDBOX in production)

### What Does NOT Work

- Real money movement
- Real bank accounts or production partner APIs
- Custodial wallet
- KYC/AML bypass
- Automatic Monero treasury/withdrawals
- Token, DAO, NFT, staking, AI features

## Architecture

```
Telegram User
     │
     ├── Telegram Bot (aiogram) ── notifications
     │
     └── Mini App (React/Vite) ── REST ── Backend (FastAPI)
                                              │
                                    ┌─────────┴─────────┐
                                    │  Partner Engine   │
                                    │  MockFiatAdapter  │
                                    └─────────┬─────────┘
                                              │
                                    PostgreSQL + Redis
```

## Quick Start (Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.12 (for local tests)
- Node.js 20 (for mini-app build)

### Run with Docker

```bash
cd rootswap
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

Services:
- API: http://localhost:8000
- Mini App: http://localhost:5173
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Run Tests

```bash
# Start dependencies
docker compose -f docker-compose.dev.yml up -d postgres redis

# Backend tests
cd backend
pip install -r requirements.txt
export TEST_DATABASE_URL=postgresql+asyncpg://rootswap:rootswap@localhost:5432/rootswap_test
export TELEGRAM_BOT_TOKEN="0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER"
pytest -v
ruff check .

# Mini App build
cd ../mini-app
npm install
npm run typecheck
npm run build
```

## Project Structure

```
rootswap/
├── backend/          # FastAPI, SQLAlchemy, Alembic, pytest
├── bot/              # aiogram Telegram bot
├── mini-app/         # React + Vite Mini App
├── deploy/nginx/     # Production nginx config
├── docker-compose.dev.yml
├── docker-compose.prod.yml
└── .github/workflows/
```

## Threat Model

| Threat | Mitigation |
|--------|------------|
| Stolen JWT | Short-lived tokens, Telegram initData validation |
| Webhook replay | Timestamp check, external_event_id dedup |
| Sensitive data leak | Encryption at rest, masked logs, no full wallet/bank in logs |
| Partner failure | Circuit breaker, failover to backup mock partner |
| Duplicate payouts | Idempotency keys, unique ledger posting_key |
| Unauthorized admin | RBAC, audit log, API key auth |
| Production misconfig | Startup validation blocks weak secrets and MOCK in production |

## Privacy Limitations

- RootSwap is **privacy-focused**, not anonymous
- **Non-custodial where possible** — users provide their own wallet addresses
- **Partner requirements may vary** — some partners may require KYC
- **Fiat payments may be identifiable** depending on payment method and partner
- RootSwap **never asks for seed phrases or private keys**

## Production Blockers

Before enabling real money:

1. Partner contract and REAL adapter integration
2. Independent security audit
3. Legal/compliance review (KYC/AML per jurisdiction)
4. Operational runbook (on-call, dispute handling)
5. Strong secrets (JWT, encryption key, Redis password, webhook secret)
6. Disable MOCK/SANDBOX quote sources in production
7. Penetration test of webhook endpoints
8. Financial reconciliation procedures

## Emergency Stop Runbook

1. Activate: `POST /api/v1/admin/emergency-stop` with `X-Admin-Key`
2. Verify: new orders return 503
3. Monitor active orders via admin API
4. Investigate root cause
5. Deactivate: `DELETE /api/v1/admin/emergency-stop`
6. Resume processing only after approval

## Dispute / Refund Runbook

1. User opens dispute via Mini App or support
2. Support reviews: `GET /api/v1/admin/orders/{id}`
3. Transition to DISPUTED if needed
4. Finance initiates refund: `POST /api/v1/admin/orders/{id}/refund`
5. Verify ledger reconciliation: `GET /api/v1/admin/ledger/reconciliation`

## Partner Integration Guide

1. Implement `FiatPartnerAdapter` or `CryptoPartnerAdapter` in `backend/app/partners/`
2. Register in `PartnerRegistry`
3. Add partner row in DB with `quote_source_type=REAL`
4. Configure webhook secret and endpoint: `POST /api/v1/webhooks/partners/{partner_code}`
5. Test in SANDBOX environment first
6. Enable via admin API after health check passes

## Webhook Guide

Partners send POST to `/api/v1/webhooks/partners/{partner_code}`.

Requirements:
- Valid signature header (partner-specific)
- Timestamp within 5 minutes
- Unique `event_id` per event
- Status mapping to internal OrderStatus

Mock partner uses headers: `X-Mock-Signature`, `X-Mock-Timestamp`.

## Legal / Compliance Warning

Cryptocurrency exchange services may require licensing depending on jurisdiction. This software is provided for development purposes. Operators are responsible for compliance with applicable laws including KYC/AML requirements. RootSwap does not bypass KYC/AML.

## Before Real Money Checklist

- [ ] Partner contract signed
- [ ] Security audit completed
- [ ] Legal review completed
- [ ] Operational runbook approved
- [ ] Production secrets configured
- [ ] MOCK/SANDBOX disabled in production
- [ ] Monitoring and alerting configured
- [ ] Incident response team assigned
- [ ] Financial reconciliation tested
- [ ] Insurance / reserve policy defined

## License

Proprietary — all rights reserved.
