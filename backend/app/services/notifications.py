"""Best-effort Telegram notifications for order status changes.

Sends via the Bot API when configured; in mock/test mode just logs. Failures
never break order processing.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import OrderStatus
from app.models.order import Order
from app.models.user import User

logger = logging.getLogger(__name__)

STATUS_MESSAGES = {
    OrderStatus.AWAITING_PAYMENT: "Заявка создана. Ожидаем оплату.",
    OrderStatus.PAYMENT_DETECTED: "Платёж обнаружен.",
    OrderStatus.PAYMENT_CONFIRMING: "Платёж подтверждается.",
    OrderStatus.PROCESSING: "Заявка в обработке.",
    OrderStatus.PAYOUT_SENT: "Выплата отправлена.",
    OrderStatus.COMPLETED: "Заявка выполнена ✅",
    OrderStatus.EXPIRED: "Срок оплаты истёк, заявка закрыта.",
    OrderStatus.FAILED: "Заявка завершилась с ошибкой.",
    OrderStatus.CANCELLED: "Заявка отменена.",
    OrderStatus.DISPUTED: "По заявке открыт спор.",
    OrderStatus.REFUND_REQUESTED: "Запрошен возврат средств.",
    OrderStatus.REFUND_PROCESSING: "Возврат в обработке.",
    OrderStatus.REFUNDED: "Возврат по заявке выполнен.",
    OrderStatus.REFUND_FAILED: "Возврат не удался — обратитесь в поддержку.",
}


async def notify_order_status(session: AsyncSession, order: Order) -> None:
    message = STATUS_MESSAGES.get(order.status)
    if message is None:
        return
    settings = get_settings()
    user = (
        await session.execute(select(User).where(User.id == order.user_id))
    ).scalar_one_or_none()
    if user is None:
        return
    text = f"RootSwap: {message}\nЗаявка {order.id[:8]} · {order.status.value}"
    if not (settings.notifications_enabled and settings.telegram_bot_token):
        logger.info(
            "notification (log-only mode)",
            extra={"ctx": {"order_id": order.id, "status": order.status.value}},
        )
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": user.telegram_id, "text": text},
            )
    except httpx.HTTPError:
        logger.warning(
            "telegram notification failed",
            extra={"ctx": {"order_id": order.id}},
        )
