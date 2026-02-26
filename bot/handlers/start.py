from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from bot.db.user_repo import get_or_create_user
from bot.keyboards.main_menu import main_menu_keyboard
from bot.utils import get_display_name

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    user = await get_or_create_user(message.from_user.id)
    name = get_display_name(message.from_user)
    await message.answer(
        f"Привет, {name}! 👋\n"
        "Я твой персональный AI-тренер по испанскому 🇪🇸\n\n"
        "Выбери, с чего начнём:",
        reply_markup=main_menu_keyboard(user),
    )

