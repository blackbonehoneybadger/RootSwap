"""Notification delivery when enabled."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import get_settings
from app.core.enums import OrderStatus
from app.services.notifications import notify_order_status
from tests.conftest import create_user


@pytest.fixture
def notifications_enabled(monkeypatch):
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567:test-bot-token-for-hmac")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_notify_sends_telegram_message(session, notifications_enabled):
    user = await create_user(session, telegram_id=424242)
    order = MagicMock()
    order.id = "ord-notify-1"
    order.status = OrderStatus.COMPLETED
    order.user_id = user.id

    with patch("app.services.notifications.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock()
        mock_client_cls.return_value = mock_client

        await notify_order_status(session, order)

        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.await_args
        assert "sendMessage" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["chat_id"] == 424242
        assert "COMPLETED" in payload["text"]


async def test_notify_skipped_when_disabled(session, monkeypatch):
    monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
    get_settings.cache_clear()
    user = await create_user(session, telegram_id=424243)
    order = MagicMock()
    order.id = "ord-notify-2"
    order.status = OrderStatus.CANCELLED
    order.user_id = user.id

    with patch("app.services.notifications.httpx.AsyncClient") as mock_client_cls:
        await notify_order_status(session, order)
        mock_client_cls.assert_not_called()

    get_settings.cache_clear()
