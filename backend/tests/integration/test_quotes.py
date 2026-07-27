from datetime import timedelta

from sqlalchemy import select

from app.core.enums import CircuitBreakerState
from app.db.base import utcnow
from app.models.partner import Partner
from app.models.quote import Quote
from tests.conftest import authed_user, create_quote_via_api


async def test_create_quotes_returns_both_partners(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    partners = {q["partner_code"] for q in quotes}
    assert partners == {"mock_fiat_alpha", "mock_fiat_beta"}
    for quote in quotes:
        assert quote["quote_source_type"] == "MOCK"
        assert float(quote["amount_out"]) > 0
        assert float(quote["root_score"]) > 0
        assert quote["expires_at"]


async def test_quotes_have_labels(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    all_labels = {label for q in quotes for label in q["labels"]}
    assert {"best", "fastest", "lowest_fee"} <= all_labels


async def test_quotes_persisted_with_expiry(client, session):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    row = (
        await session.execute(select(Quote).where(Quote.id == quotes[0]["quote_id"]))
    ).scalar_one()
    assert row.expires_at > utcnow()
    assert row.expires_at < utcnow() + timedelta(minutes=5)
    assert row.consumed_at is None


async def test_sell_direction_quotes(client):
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(
        client, headers, direction="SELL", from_asset="XMR", from_network="XMR",
        to_asset="RUB", to_network=None, amount_in="2",
    )
    assert quotes
    assert float(quotes[0]["amount_out"]) > 30000


async def test_unsupported_route_rejected(client):
    headers, _ = await authed_user(client)
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "DOGE",
            "to_network": "DOGE",
            "amount_in": "1000",
        },
        headers=headers,
    )
    # Planned assets are rejected by the registry before partner fan-out.
    assert resp.status_code == 422
    assert "planned" in resp.text.lower()


async def test_partner_quote_failure_excluded(client, partners):
    partners["alpha"].set_scenario("quote_failure")
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    assert {q["partner_code"] for q in quotes} == {"mock_fiat_beta"}


async def test_insufficient_reserve_excluded(client, partners):
    partners["alpha"].set_scenario("insufficient_reserve")
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    assert {q["partner_code"] for q in quotes} == {"mock_fiat_beta"}


async def test_disabled_partner_excluded(client, session, partners):
    from app.partners.registry import registry

    await registry.disable_partner(session, "mock_fiat_alpha", "test")
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    assert {q["partner_code"] for q in quotes} == {"mock_fiat_beta"}


async def test_open_circuit_breaker_excluded(client, session, partners):
    row = (
        await session.execute(select(Partner).where(Partner.code == "mock_fiat_alpha"))
    ).scalar_one()
    row.circuit_breaker_state = CircuitBreakerState.OPEN
    row.cooldown_until = utcnow() + timedelta(minutes=5)
    await session.commit()
    headers, _ = await authed_user(client)
    quotes = await create_quote_via_api(client, headers)
    assert {q["partner_code"] for q in quotes} == {"mock_fiat_beta"}


async def test_production_rejects_mock_quotes(client, monkeypatch, session):
    """In production, MOCK/SANDBOX sources are excluded => no partners => 502."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    headers, _ = await authed_user(client)
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": "50000",
        },
        headers=headers,
    )
    assert resp.status_code == 502


async def test_production_rejects_sandbox_quotes(client, monkeypatch, partners):
    from app.core.config import get_settings
    from app.core.enums import QuoteSourceType

    # turn beta into a sandbox partner, then switch to production
    partners["beta"].quote_source_type = QuoteSourceType.SANDBOX
    partners["beta"].environment = "sandbox"
    partners["alpha"].quote_source_type = QuoteSourceType.SANDBOX
    partners["alpha"].environment = "sandbox"
    settings = get_settings()
    headers, _ = await authed_user(client)
    monkeypatch.setattr(settings, "environment", "production")
    resp = await client.post(
        "/api/v1/quotes",
        json={
            "direction": "BUY",
            "from_asset": "RUB",
            "to_asset": "XMR",
            "to_network": "XMR",
            "amount_in": "50000",
        },
        headers=headers,
    )
    assert resp.status_code == 502
