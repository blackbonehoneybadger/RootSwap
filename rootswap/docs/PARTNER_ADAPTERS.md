# Partner adapter guide

RootSwap talks to exchange/fiat partners only through adapter interfaces in
`backend/app/partners/base.py`.

## Interfaces

- `FiatPartnerAdapter` — RUB ↔ crypto (quotes, orders, payment instructions, status, cancel, refund, webhook verify)
- `CryptoPartnerAdapter` — crypto ↔ crypto (structure ready; no production adapter yet)

## Current adapters

| Code | Type | Environment | Money |
|------|------|-------------|-------|
| `mock_fiat` | Mock | sandbox | **Synthetic only** |
| `mock_fiat_backup` | Mock | sandbox | **Synthetic only** |

There are **no REAL partner adapters** in this repository.

## Rules

1. Mock adapters must set `quote_source_type` to `MOCK` or `SANDBOX`.
2. Production startup **rejects** MOCK quotes when `ENVIRONMENT=production`.
3. Do not invent quotes for assets without an adapter route (`SUPPORTED_ROUTES` + registry status).
4. Webhooks must verify HMAC + timestamp; use unique `external_event_id` for idempotency.
5. Never log plaintext payment credentials or JWT / Telegram initData.

## Adding a real partner

1. Implement `FiatPartnerAdapter` (or crypto) under `app/partners/<name>.py`.
2. Register factory wiring (partner `adapter_type` → class).
3. Add supported asset/network rows with `status=supported` only after E2E passes.
4. Keep mock adapter behind `ENABLE_MOCK_PARTNERS` / non-production.
5. Document KYC, limits, and fee disclosure honestly in the Mini App.

Until a contracted REAL adapter exists, UI must show **Sandbox** / **Coming soon**, not “supported for money”.
