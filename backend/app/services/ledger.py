"""Immutable ledger with idempotent postings.

Accounting identity (per order, all amounts RUB):
  +GROSS_SERVICE_FEE  (service fee collected from the user)
  -REFERRAL_LIABILITY (share owed to the referrer, if any)
  -REALIZED_NET_PROFIT (the remainder recognized as profit)
  => per-order sum == 0

Partner/network fees are pass-through costs charged on top of the service fee and
are tracked as informational paired postings (PARTNER_COST/NETWORK_COST with
matching ADJUSTMENT), keeping the per-order sum at zero.

Refund reverses the recognition with REFUND_LIABILITY + ADJUSTMENT postings.
Duplicate posting_keys are silently skipped => webhook replays never double-post.
"""

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LedgerEntryType, OrderStatus
from app.models.ledger import LedgerEntry
from app.models.order import Order
from app.observability.metrics import metrics

logger = logging.getLogger(__name__)

RUB = "RUB"


async def post_entry(
    session: AsyncSession,
    order_id: str,
    posting_key: str,
    entry_type: LedgerEntryType,
    currency: str,
    amount: Decimal,
    source: str | None = None,
    recipient: str | None = None,
    metadata: dict | None = None,
) -> LedgerEntry | None:
    """Idempotent posting: returns None if posting_key already exists."""
    existing = (
        await session.execute(
            select(LedgerEntry.id).where(LedgerEntry.posting_key == posting_key)
        )
    ).scalar_one_or_none()
    if existing is not None:
        metrics.inc("ledger_duplicate_posting_skipped_total")
        return None
    entry = LedgerEntry(
        order_id=order_id,
        posting_key=posting_key,
        entry_type=entry_type,
        currency=currency,
        amount=amount,
        source=source,
        recipient=recipient,
        metadata_=metadata,
    )
    session.add(entry)
    await session.flush()
    metrics.inc("ledger_posting_total", entry_type=entry_type.value)
    return entry


async def post_completed_order(
    session: AsyncSession, order: Order, referral_reward_amount: Decimal = Decimal("0")
) -> None:
    """Recognize revenue exactly once for a COMPLETED order."""
    if order.status != OrderStatus.COMPLETED:
        raise ValueError("ledger recognition requires COMPLETED order")

    service_fee = Decimal(order.service_fee)
    referral = min(Decimal(referral_reward_amount), service_fee)
    profit = service_fee - referral

    await post_entry(
        session, order.id, f"order:{order.id}:gross_service_fee",
        LedgerEntryType.GROSS_SERVICE_FEE, RUB, service_fee,
        source="user", recipient="rootswap",
    )
    if referral > 0:
        await post_entry(
            session, order.id, f"order:{order.id}:referral_liability",
            LedgerEntryType.REFERRAL_LIABILITY, RUB, -referral,
            source="rootswap", recipient="referrer",
        )
    await post_entry(
        session, order.id, f"order:{order.id}:realized_net_profit",
        LedgerEntryType.REALIZED_NET_PROFIT, RUB, -profit,
        source="rootswap", recipient="pnl",
    )
    # informational pass-through cost postings (paired, net zero)
    partner_fee = Decimal(order.partner_fee)
    if partner_fee:
        await post_entry(
            session, order.id, f"order:{order.id}:partner_cost",
            LedgerEntryType.PARTNER_COST, RUB, -partner_fee,
            source="user", recipient="partner",
        )
        await post_entry(
            session, order.id, f"order:{order.id}:partner_cost_passthrough",
            LedgerEntryType.ADJUSTMENT, RUB, partner_fee,
            metadata={"reason": "partner fee charged to user on top"},
        )
    network_fee = Decimal(order.network_fee)
    if network_fee:
        await post_entry(
            session, order.id, f"order:{order.id}:network_cost",
            LedgerEntryType.NETWORK_COST, RUB, -network_fee,
            source="user", recipient="network",
        )
        await post_entry(
            session, order.id, f"order:{order.id}:network_cost_passthrough",
            LedgerEntryType.ADJUSTMENT, RUB, network_fee,
            metadata={"reason": "network fee charged to user on top"},
        )


async def post_refund(session: AsyncSession, order: Order) -> None:
    """Reverse recognized revenue for a refunded order (idempotent)."""
    service_fee = Decimal(order.service_fee)
    referral_entry = (
        await session.execute(
            select(LedgerEntry).where(
                LedgerEntry.posting_key == f"order:{order.id}:referral_liability"
            )
        )
    ).scalar_one_or_none()
    referral = -Decimal(referral_entry.amount) if referral_entry else Decimal("0")
    profit = service_fee - referral

    await post_entry(
        session, order.id, f"order:{order.id}:refund_liability",
        LedgerEntryType.REFUND_LIABILITY, RUB, -service_fee,
        source="rootswap", recipient="user",
    )
    await post_entry(
        session, order.id, f"order:{order.id}:refund_profit_reversal",
        LedgerEntryType.ADJUSTMENT, RUB, profit,
        metadata={"reason": "reverse realized profit on refund"},
    )
    if referral > 0:
        await post_entry(
            session, order.id, f"order:{order.id}:refund_referral_reversal",
            LedgerEntryType.ADJUSTMENT, RUB, referral,
            metadata={"reason": "reverse referral liability on refund"},
        )
    await post_entry(
        session, order.id, f"order:{order.id}:refund_paid",
        LedgerEntryType.REFUND_PAID, RUB, service_fee,
        source="rootswap", recipient="user",
        metadata={"reason": "refund executed by partner (mock)"},
    )
    await post_entry(
        session, order.id, f"order:{order.id}:refund_paid_offset",
        LedgerEntryType.ADJUSTMENT, RUB, -service_fee,
        metadata={"reason": "cash offset for refund_paid"},
    )


async def reconcile(session: AsyncSession) -> dict:
    """Global and per-order reconciliation. Per design every order nets to zero."""
    total = (
        await session.execute(select(func.coalesce(func.sum(LedgerEntry.amount), 0)))
    ).scalar_one()
    per_order_rows = (
        await session.execute(
            select(LedgerEntry.order_id, func.sum(LedgerEntry.amount))
            .group_by(LedgerEntry.order_id)
        )
    ).all()
    def fmt(value) -> str:
        return format(Decimal(value).normalize(), "f")

    discrepancies = [
        {"order_id": order_id, "residual": fmt(residual)}
        for order_id, residual in per_order_rows
        if Decimal(residual) != 0
    ]
    return {
        "total_residual": fmt(total),
        "orders_with_discrepancy": discrepancies,
        "balanced": Decimal(total) == 0 and not discrepancies,
    }
