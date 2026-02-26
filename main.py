import os
from dotenv import load_dotenv

load_dotenv()
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.states import OnboardingStates
from bot.handlers import start, menu, onboarding, level_test, zero, a1, a2, b1, review, voice
from bot.db.session import init_db



# ─────────────────────────────
# Конфигурация
# ─────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден. Проверь файл .env")



# ─────────────────────────────
# Логирование
# ─────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)


# ─────────────────────────────
# Инициализация бота
# ─────────────────────────────

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(start.router)
dp.include_router(onboarding.router)
dp.include_router(level_test.router)
dp.include_router(zero.router)
dp.include_router(a2.router)
dp.include_router(b1.router)
dp.include_router(a1.router)
dp.include_router(review.router)
dp.include_router(voice.router)
dp.include_router(menu.router)


# ─────────────────────────────
# Хендлеры
# ─────────────────────────────

# @dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        """👋 Привет!
Я твой AI-тренер по испанскому 🇪🇸

Я помогу тебе:
— выучить слова и фразы
— практиковать язык каждый день
— отслеживать прогресс

Начнём с короткого теста?"""
    )
    await state.set_state(OnboardingStates.onboarding_info)


# ─────────────────────────────
# Точка входа
# ─────────────────────────────

async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
