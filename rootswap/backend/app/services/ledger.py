import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LedgerEntryType, OrderStatus
from app.models import LedgerEntry, Order


class LedgerService:
    async def post_completed_order(self, session: AsyncSession, order: Order) -> None:
        if order.status != OrderStatus.COMPLETED:
            return
        posting_base = f"order:{order.id}:completed"
        entries = [
            (
                f"{posting_base}:gross_service_fee",
                LedgerEntryType.GROSS_SERVICE_FEE,
                "RUB",
                float(order.service_fee),
                "partner",
                "rootswap",
            ),
            (
                f"{posting_base}:partner_cost",
                LedgerEntryType.PARTNER_COST,
                "RUB",
                float(order.partner_fee),
                "rootswap",
                order.partner_code,
            ),
            (
                f"{posting_base}:network_cost",
                LedgerEntryType.NETWORK_COST,
                "RUB",
                float(order.network_fee),
                "rootswap",
                "network",
            ),
            (
                f"{posting_base}:realized_net_profit",
                LedgerEntryType.REALIZED_NET_PROFIT,
                "RUB",
                float(order.service_fee) - float(order.partner_fee) - float(order.network_fee),
                "rootswap",
                "treasury",
            ),
        ]
        for posting_key, entry_type, currency, amount, source, recipient in entries:
            await self._post_entry(session, order.id, posting_key, entry_type, currency, amount, source, recipient)

    async def post_referral_liability(
        self, session: AsyncSession, order_id: uuid.UUID, posting_key: str, amount: float
    ) -> None:
        await self._post_entry(
            session,
            order_id,
            posting_key,
            LedgerEntryType.REFERRAL_LIABILITY,
            "RUB",
            amount,
            "rootswap",
            "referral_pool",
        )

    async def post_referral_paid(
        self, session: AsyncSession, order_id: uuid.UUID, posting_key: str, amount: float
    ) -> None:
        await self._post_entry(
            session,
            order_id,
            posting_key,
            LedgerEntryType.REFERRAL_PAID,
            "RUB",
            amount,
            "referral_pool",
            "referrer",
        )

    async def post_refund(self, session: AsyncSession, order: Order, amount: float) -> None:
        base = f"order:{order.id}:refund"
        await self._post_entry(
            session, order.id, f"{base}:liability", LedgerEntryType.REFUND_LIABILITY, "RUB", amount, "rootswap", "user"
        )
        await self._post_entry(
            session, order.id, f"{base}:paid", LedgerEntryType.REFUND_PAID, "RUB", amount, "rootswap", "user"
        )
        await self._post_entry(
            session,
            order.id,
            f"{base}:adjustment",
            LedgerEntryType.ADJUSTMENT,
            "RUB",
            -amount,
            "treasury",
            "user",
        )

    async def _post_entry(
        self,
        session: AsyncSession,
        order_id: uuid.UUID,
        posting_key: str,
        entry_type: LedgerEntryType,
        currency: str,
        amount: float,
        source: str,
        recipient: str,
    ) -> LedgerEntry | None:
        existing = await session.execute(
            select(LedgerEntry).where(LedgerEntry.posting_key == posting_key)
        )
        if existing.scalar_one_or_none():
            return None
        entry = LedgerEntry(
            order_id=order_id,
            posting_key=posting_key,
            entry_type=entry_type,
            currency=currency,
            amount=amount,
            source=source,
            recipient=recipient,
        )
        session.add(entry)
        return entry

    async def reconcile(self, session: AsyncSession) -> dict:
        result = await session.execute(
            select(LedgerEntry.entry_type, func.sum(LedgerEntry.amount)).group_by(LedgerEntry.entry_type)
        )
        totals = {row[0].value: float(row[1]) for row in result.all()}
        gross = totals.get(LedgerEntryType.GROSS_SERVICE_FEE.value, 0)
        adjustments = totals.get(LedgerEntryType.ADJUSTMENT.value, 0)
        realized = totals.get(LedgerEntryType.REALIZED_NET_PROFIT.value, 0)
        expected_realized = gross - totals.get(LedgerEntryType.PARTNER_COST.value, 0) - totals.get(
            LedgerEntryType.NETWORK_COST.value, 0
        )
        discrepancy = round(realized - expected_realized + adjustments, 8)
        return {
            "totals": totals,
            "discrepancy": discrepancy,
            "balanced": abs(discrepancy) < 0.0001,
        }
