"""RootSwap Telegram Bot (aiogram 3).

- /start with optional referral parameter (start=ref_CODE)
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

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("rootswap.bot")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://example.invalid/miniapp")

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


def main_keyboard(start_param: str | None = None) -> InlineKeyboardMarkup:
    url = MINI_APP_URL
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть RootSwap",
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )


async def cmd_start(message: Message, command: CommandObject) -> None:
    referral_code: str | None = None
    if command.args and command.args.startswith("ref_"):
        referral_code = command.args.removeprefix("ref_")[:16]
        logger.info("start with referral code (masked): %s***", referral_code[:3])

    text = WELCOME
    if referral_code:
        text += "\n\n🎁 Вы пришли по реферальной ссылке — она будет учтена при входе в приложение."

    await message.answer(text, reply_markup=main_keyboard(command.args))


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set; bot cannot start")
        sys.exit(1)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(cmd_start, CommandStart())
    logger.info("RootSwap bot started (long polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
