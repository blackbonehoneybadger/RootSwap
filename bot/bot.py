"""RootSwap Telegram Bot (aiogram 3).

- /start with optional referral parameter (start=ref_CODE)
- /help repeats the intro and opens the Mini App
- opens the RootSwap Mini App via WebApp button (the referral code travels to the
  Mini App through Telegram's start_param and is applied during /auth/telegram)
- never asks for seed phrases or private keys and says so explicitly

Order notifications are sent by the backend (services/notifications.py) using the
same bot token, so the bot process stays a thin entry point.
"""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("rootswap.bot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.environ.get("MINI_APP_URL", "")

WELCOME = (
    "👋 Это RootSwap — privacy-focused агрегатор обмена криптовалют.\n\n"
    "• Направления: RUB ⇄ XMR, RUB ⇄ USDT (TRC20), RUB ⇄ BTC\n"
    "• Non-custodial where possible: мы не храним ваши средства\n"
    "• Partner requirements may vary; fiat payments may be identifiable\n\n"
    "⚠️ ТЕКУЩАЯ ВЕРСИЯ РАБОТАЕТ В DEMO-РЕЖИМЕ: реальные деньги отключены, "
    "все партнёры — синтетические (mock/sandbox).\n\n"
    "🔐 Безопасность: RootSwap НИКОГДА не запрашивает seed-фразы или приватные "
    "ключи. Если кто-то просит их от нашего имени — это мошенники."
)

# Telegram WebApp buttons require a reachable HTTPS URL; otherwise sendMessage
# fails. When the URL is missing or not HTTPS we degrade to a plain reply so the
# bot still responds instead of crashing on every message.
_MINI_APP_READY = MINI_APP_URL.startswith("https://")


def main_keyboard(start_param: str | None = None) -> InlineKeyboardMarkup | None:
    if not _MINI_APP_READY:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть RootSwap",
                    web_app=WebAppInfo(url=MINI_APP_URL),
                )
            ]
        ]
    )


async def _reply_intro(message: Message, extra: str = "") -> None:
    text = WELCOME + extra
    keyboard = main_keyboard()
    if keyboard is None:
        text += (
            "\n\nℹ️ Mini App пока не настроен (MINI_APP_URL не задан). "
            "Администратор должен указать публичный HTTPS-адрес приложения."
        )
    await message.answer(text, reply_markup=keyboard)


async def cmd_start(message: Message, command: CommandObject) -> None:
    extra = ""
    if command.args and command.args.startswith("ref_"):
        referral_code = command.args.removeprefix("ref_")[:16]
        logger.info("start with referral code (masked): %s***", referral_code[:3])
        extra = "\n\n🎁 Вы пришли по реферальной ссылке — она будет учтена при входе в приложение."
    await _reply_intro(message, extra)


async def cmd_help(message: Message) -> None:
    await _reply_intro(message)


async def fallback(message: Message) -> None:
    await message.answer(
        "Откройте RootSwap кнопкой ниже или отправьте /start.",
        reply_markup=main_keyboard(),
    )


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set; bot cannot start")
        sys.exit(1)
    if not _MINI_APP_READY:
        logger.warning(
            "MINI_APP_URL is not an https URL (%r); the Mini App button is disabled. "
            "Set MINI_APP_URL to your public HTTPS address.",
            MINI_APP_URL,
        )
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(fallback, F.text)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть RootSwap"),
            BotCommand(command="help", description="Помощь и информация"),
        ]
    )
    logger.info("RootSwap bot started (long polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
