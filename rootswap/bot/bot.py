import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "0000000000:DEV_TELEGRAM_BOT_TOKEN_PLACEHOLDER")
MINI_APP_URL = os.getenv("MINI_APP_URL", "http://localhost:5173")
API_URL = os.getenv("API_URL", "http://localhost:8000")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DESCRIPTION = (
    "RootSwap — privacy-focused, non-custodial where possible crypto exchange aggregator.\n\n"
    "Partner requirements may vary. Fiat payments may be identifiable.\n"
    "RootSwap never asks for seed phrases or private keys.\n\n"
    "⚠️ Mock/Sandbox mode only. Real money is disabled in this version."
)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть RootSwap", web_app=WebAppInfo(url=MINI_APP_URL))],
        ]
    )


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    referral_code = None
    if message.text and " " in message.text:
        param = message.text.split(" ", 1)[1]
        if param.startswith("ref_"):
            referral_code = param[4:]
        elif param.startswith("ref"):
            referral_code = param.replace("ref", "", 1).strip("_")

    text = DESCRIPTION
    if referral_code:
        text += f"\n\nReferral code detected: {referral_code}"

    await message.answer(text, reply_markup=main_keyboard())


async def send_order_notification(telegram_id: int, text: str) -> None:
    try:
        await bot.send_message(telegram_id, text)
    except Exception as exc:
        logger.warning("Failed to send notification: %s", exc)


async def main() -> None:
    logger.info("Starting RootSwap bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
