"""PostgreSQL-specific: UNIQUE payment_instructions.order_id + migration safety.

Skipped unless POSTGRES_TEST_DATABASE_URL is set.
"""

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

POSTGRES_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="POSTGRES_TEST_DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def pg_engine():
    engine = create_async_engine(POSTGRES_URL)
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: None)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_unique_pi_constraint_rejects_duplicate(pg_engine):
    from app import models  # noqa: F401
    from app.db.base import Base

    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    from datetime import datetime, timedelta
    from decimal import Decimal

    from app.core.enums import OrderDirection, OrderStatus, QuoteSourceType
    from app.models.order import Order
    from app.models.payment_instructions import PaymentInstructions
    from app.models.quote import Quote
    from app.models.user import User
    from app.services.referral import generate_referral_code

    async with factory() as session:
        user = User(
            telegram_id=991001,
            username="pg_unique",
            first_name="PG",
            referral_code=generate_referral_code(),
        )
        session.add(user)
        await session.flush()
        quote = Quote(
            user_id=user.id,
            partner_code="mock_fiat_alpha",
            direction=OrderDirection.BUY,
            from_asset="RUB",
            from_network=None,
            to_asset="XMR",
            to_network="XMR",
            amount_in=Decimal("10000"),
            amount_out=Decimal("0.5"),
            exchange_rate=Decimal("20000"),
            service_fee=Decimal("90"),
            partner_fee=Decimal("40"),
            network_fee=Decimal("20"),
            total_fee=Decimal("150"),
            root_score=Decimal("1"),
            quote_source_type=QuoteSourceType.MOCK,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        session.add(quote)
        await session.flush()
        order = Order(
            user_id=user.id,
            quote_id=quote.id,
            partner_code="mock_fiat_alpha",
            direction=OrderDirection.BUY,
            status=OrderStatus.AWAITING_PAYMENT,
            from_asset="RUB",
            to_asset="XMR",
            to_network="XMR",
            amount_in=Decimal("10000"),
            amount_out=Decimal("0.5"),
            exchange_rate=Decimal("20000"),
            service_fee=Decimal("90"),
            partner_fee=Decimal("40"),
            network_fee=Decimal("20"),
            total_fee=Decimal("150"),
            quote_source_type=QuoteSourceType.MOCK,
            idempotency_key=uuid.uuid4().hex,
        )
        session.add(order)
        await session.flush()
        pi1 = PaymentInstructions(
            order_id=order.id,
            payment_method="SBP",
            amount=Decimal("10000"),
            currency="RUB",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        session.add(pi1)
        await session.commit()

        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            async with factory() as session2:
                pi2 = PaymentInstructions(
                    order_id=order.id,
                    payment_method="SBP",
                    amount=Decimal("10000"),
                    currency="RUB",
                    expires_at=datetime.utcnow() + timedelta(minutes=15),
                )
                session2.add(pi2)
                await session2.commit()
