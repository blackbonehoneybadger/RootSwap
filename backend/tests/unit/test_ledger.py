from decimal import Decimal

from sqlalchemy import select

from app.core.enums import LedgerEntryType, OrderStatus
from app.models.ledger import LedgerEntry
from app.services.ledger import post_completed_order, post_entry, post_refund, reconcile
from tests.conftest import create_user
from tests.unit.test_state_machine import make_order


async def test_duplicate_posting_key_skipped(session):
    user = await create_user(session, 20)
    order = await make_order(session, user, status=OrderStatus.COMPLETED)
    first = await post_entry(
        session, order.id, "dup-key", LedgerEntryType.ADJUSTMENT, "RUB", Decimal("10")
    )
    second = await post_entry(
        session, order.id, "dup-key", LedgerEntryType.ADJUSTMENT, "RUB", Decimal("10")
    )
    assert first is not None
    assert second is None
    rows = (
        (await session.execute(select(LedgerEntry).where(LedgerEntry.posting_key == "dup-key")))
        .scalars().all()
    )
    assert len(rows) == 1


async def test_completed_order_posts_once(session):
    user = await create_user(session, 21)
    order = await make_order(session, user, status=OrderStatus.COMPLETED)
    await post_completed_order(session, order)
    await post_completed_order(session, order)  # replay: no duplicates
    await session.commit()
    entries = (
        (await session.execute(select(LedgerEntry).where(LedgerEntry.order_id == order.id)))
        .scalars().all()
    )
    gross = [e for e in entries if e.entry_type == LedgerEntryType.GROSS_SERVICE_FEE]
    profit = [e for e in entries if e.entry_type == LedgerEntryType.REALIZED_NET_PROFIT]
    assert len(gross) == 1
    assert len(profit) == 1
    assert Decimal(gross[0].amount) == Decimal("450")


async def test_referral_share_reduces_profit(session):
    user = await create_user(session, 22)
    order = await make_order(session, user, status=OrderStatus.COMPLETED)
    await post_completed_order(session, order, referral_reward_amount=Decimal("90"))
    entries = (
        (await session.execute(select(LedgerEntry).where(LedgerEntry.order_id == order.id)))
        .scalars().all()
    )
    by_type = {e.entry_type: Decimal(e.amount) for e in entries}
    assert by_type[LedgerEntryType.REFERRAL_LIABILITY] == Decimal("-90")
    assert by_type[LedgerEntryType.REALIZED_NET_PROFIT] == Decimal("-360")


async def test_reconciliation_zero_after_completion_and_refund(session):
    user = await create_user(session, 23)
    order = await make_order(session, user, status=OrderStatus.COMPLETED)
    await post_completed_order(session, order, referral_reward_amount=Decimal("90"))
    result = await reconcile(session)
    assert result["balanced"], result
    await post_refund(session, order)
    await post_refund(session, order)  # replay safe
    result = await reconcile(session)
    assert result["balanced"], result
    assert result["total_residual"] == "0"


async def test_non_completed_order_rejected(session):
    user = await create_user(session, 24)
    order = await make_order(session, user, status=OrderStatus.PROCESSING)
    try:
        await post_completed_order(session, order)
        raise AssertionError("should have raised")
    except ValueError:
        pass
