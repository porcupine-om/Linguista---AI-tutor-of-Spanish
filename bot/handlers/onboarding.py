from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.states import OnboardingStates, ZeroStates
from bot.handlers.zero import ZERO_WELCOME
from bot.utils import get_display_name
from bot.db.user_repo import (
    update_user_level,
    get_or_create_user,
    get_user_by_telegram_id,
    is_current_level_completed,
    ZERO_LESSON_IDS,
)
from bot.db.session import async_session
from bot.keyboards.main_menu import main_menu_keyboard

router = Router()


def path_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆕 Никогда не учил(а)")],
            [KeyboardButton(text="📊 Да! Проверить мой уровень")],
        ],
        resize_keyboard=True,
    )


def intro_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать тест уровня")]],
        resize_keyboard=True,
    )


def start_test_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать")]],
        resize_keyboard=True,
    )


@router.message(
    lambda msg: msg.text == "📚 Начать обучение",
)
async def onboarding_entry(message: Message, state: FSMContext):
    await get_or_create_user(message.from_user.id)
    await state.set_state(OnboardingStates.path_choice)
    await message.answer(
        "Ты уже учил(а) испанский раньше?",
        reply_markup=path_choice_keyboard(),
    )


@router.message(
    StateFilter(OnboardingStates.path_choice),
    lambda msg: msg.text == "🆕 Никогда не учил(а)",
)
async def path_zero(message: Message, state: FSMContext):
    await update_user_level(message.from_user.id, "A1")
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    progress = getattr(user, "zero_progress", 0) or 0
    # zero_progress = кол-во завершённых уроков; все уроки = ZERO завершён
    if progress >= len(ZERO_LESSON_IDS):
        await state.clear()
        await message.answer(
            "Ты уже прошёл(а) базовый уровень. Продолжай обучение в меню.",
            reply_markup=main_menu_keyboard(user),
        )
        return
    await state.set_state(ZeroStates.welcome)
    await message.answer(
        ZERO_WELCOME.format(name=get_display_name(message.from_user)),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Поехали!")]],
            resize_keyboard=True,
        ),
    )


@router.message(
    StateFilter(OnboardingStates.path_choice),
    F.text.in_({"📊 Проверить мой уровень", "📊 Да! Проверить мой уровень"}),
)
async def path_test(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)

    if not user:
        await get_or_create_user(message.from_user.id)
        await state.set_state(OnboardingStates.intro)
        await message.answer(
            "📖 <b>Как проходит обучение</b>\n\n"
            "Ты будешь учить слова по карточкам, проходить уроки с теорией и упражнениями "
            "и повторять материал. Сначала определим твой уровень — "
            "пройди короткий тест.",
            reply_markup=intro_keyboard(),
        )
        return

    now = datetime.utcnow()
    can_by_time = (
        not user.last_level_test_at
        or now - user.last_level_test_at >= timedelta(days=30)
    )
    can_by_progress = await is_current_level_completed(user)

    if not (can_by_time or can_by_progress):
        last = user.last_level_test_at
        if getattr(last, "tzinfo", None) is not None:
            last = last.replace(tzinfo=None)
        days_left = max(0, 30 - (now - last).days) if last else 0
        async with async_session() as session:
            u = await get_user_by_telegram_id(message.from_user.id, session)
        await message.answer(
            f"Ты недавно проходил(а) тест уровня.\n\n"
            f"Повторный тест станет доступен:\n"
            f"• через {days_left} дн.\n"
            f"• или сразу после завершения текущего уровня",
            reply_markup=main_menu_keyboard(u),
        )
        return

    await state.set_state(OnboardingStates.intro)
    await message.answer(
        "📖 <b>Как проходит обучение</b>\n\n"
        "Ты будешь учить слова по карточкам, проходить уроки с теорией и упражнениями "
        "и повторять материал. Сначала определим твой уровень — "
        "пройди короткий тест.",
        reply_markup=intro_keyboard(),
    )


@router.message(
    StateFilter(OnboardingStates.intro),
    lambda msg: msg.text == "Начать тест уровня",
)
async def intro_to_ready_check(message: Message, state: FSMContext):
    await state.set_state(OnboardingStates.ready_check)
    await message.answer(
        "Отлично! Проверка готовности.",
        reply_markup=start_test_keyboard(),
    )


