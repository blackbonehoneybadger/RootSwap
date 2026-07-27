# Candidate external providers — research only

**Integration status: NONE. No provider below is wired into RootSwap.**
Real money remains disabled and the quote engine still runs on mock/sandbox
partners. This document is a shortlist for future evaluation, not a plan of
record and not an endorsement.

## How this shortlist was produced

Source: the [public-apis](https://github.com/public-apis/public-apis) catalog
(README snapshot fetched 2026-07-24) — **1625 catalogued APIs across 52
categories**. The catalog is a markdown directory of links; it publishes no
package or SDK, so there is nothing to install from it.

Of those 52 categories, only four have any bearing on a fiat↔crypto exchange:
fiat FX, crypto rates, sanctions screening, and payout-detail validation.
Everything else (weather, anime, games, recipes, …) is irrelevant here and was
discarded. Entries below were filtered to `HTTPS = Yes`; the `Auth` column is
reproduced from the catalog.

## 1. Fiat FX (RUB is the base fiat leg)

| Provider | Auth | Notes |
|---|---|---|
| Bank of Russia | No | Central-bank reference rates. Authoritative for RUB, but publishes an official daily fixing — not a tradeable market rate. |
| Frankfurter | No | ECB-derived rates, conversion and time series. CORS enabled. |
| Exchangerate.host | No | FX plus crypto rates. |
| Currency-api | No | 150+ currencies, catalog notes no rate limit. |
| National Bank of Poland | No | Another central-bank set; useful only as a cross-check. |
| VATComply.com | No | Rates plus VAT-number validation and geolocation. |

Central-bank feeds answer "what is the official rate", which is **not** the same
question as "what can we actually fill an order at". They are usable as a
sanity-check band around partner quotes, not as a pricing source.

## 2. Crypto rates

| Provider | Auth | Notes |
|---|---|---|
| CoinGecko | No | Broad asset coverage, market + developer/social data. CORS enabled. |
| Coinpaprika | No | Prices and volume. CORS enabled. |
| CoinCap | No | Real-time prices over REST. |
| CryptoCompare | No | Cross-exchange comparison. |
| Messari | No | Coverage across thousands of assets. |
| Mempool | No | Bitcoin fee/mempool data — relevant to network-fee estimation, not pricing. |

## 3. Sanctions / AML screening

| Provider | Auth | Notes |
|---|---|---|
| OpenSanctions | No | International sanctions lists, crime and politically exposed persons (PEP). |

This is the only sanctions/PEP source in the entire 1625-entry catalog — the
directory has no meaningful AML tooling beyond it. Screening is a **regulated
compliance function**: an open dataset can support a control, but does not by
itself constitute a compliant KYC/AML programme, and choosing to screen users
is a legal decision, not an engineering one.

## 4. Payout-detail validation

Phone/address validation (Veriphone, Numverify, Numlookup, Cloudmersive
Validate, VeriRoute Intel) is relevant to SBP/card payout details. **Every
phone-validation option in the catalog requires an API key**, and each one means
transmitting a user's phone number to a third party.

That directly conflicts with how the codebase treats payout data today: account
numbers, cards and phones are encrypted at rest and masked in logs, with tests
asserting they never leak (`test_masking_security.py`, `test_mock_flows.py`).
Sending the same values to an external validator would route around that
protection. Prefer offline format validation (the existing
`wallet_validation.py` approach) unless there is a concrete, justified need.

## Hard constraints that still apply

These are unchanged by anything in this document:

- **Real money stays disabled.** Adding a live rate feed does not change that.
- **BestChange remains a stub.** No scraping, no invented endpoints, no
  fabricated quotes — see `bestchange.md`.
- **No provider may be presented in the UI as available until it actually is.**

## Checklist before any provider is wired in

A free public endpoint is not a dependency you can put in a money path
casually. Before an adapter ships:

1. **Terms of service reviewed** — several "free" tiers forbid commercial use.
2. **No SLA is assumed.** Free endpoints carry no uptime guarantee, so any
   provider must sit behind the existing circuit breaker and have a defined
   fallback and cache, exactly like the partner adapters.
3. **Rate limits measured**, not guessed, with backoff.
4. **Credentials via environment only.** Every keyed provider adds a secret; it
   must never be committed. The repository's `.gitleaks.toml` and the
   pre-commit hook cover this — do not add exceptions for it.
5. **PII boundary explicit.** Document exactly what user data, if any, leaves
   the system. The default answer should be none.
6. **Failure mode is degradation, never a wrong price.** A stale or unreachable
   feed must not silently produce a quote a user can act on.

Status: **research only — nothing selected, nothing integrated.**
