# Partner adapters

Interfaces: `backend/app/partners/base.py`

| Adapter | Status | Money |
|---------|--------|-------|
| `mock_fiat_alpha` / `mock_fiat_beta` | Mock | Synthetic only |
| `mock_crypto` | Mock | Synthetic only |
| REAL partners | None | — |

Mock adapters are forbidden in production startup validation.
Scenarios are test-only via per-instance `set_scenario()` — never exposed on public API.
