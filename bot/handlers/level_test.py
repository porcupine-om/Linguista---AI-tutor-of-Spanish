from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from datetime import datetime

from data.level_test.questions import QUESTIONS
from data.level_test.scoring import calculate_level
from bot.states import OnboardingStates, LevelTestStates
from bot.db.user_repo import update_user_level, get_user_by_telegram_id
from bot.db.session import async_session
from bot.keyboards.main_menu import main_menu_keyboard

router = Router()

MOTIVATION_5 = "Отличный темп! Продолжай в том же духе 💪"
MOTIVATION_10 = "Почти готово! Осталось совсем чуть-чуть 🎯"


def _question_inline_keyboard(question: dict) -> InlineKeyboardMarkup:
    buttons = []
    for i, opt in enumerate(question["options"]):
        buttons.append([
            InlineKeyboardButton(
                text=opt,
                callback_data=f"lt:{question['id']}:{i}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _send_question(
    event: Message | CallbackQuery,
    state: FSMContext,
    index: int,
    as_new_message: bool = False,
) -> None:
    question = QUESTIONS[index]
    text = f"<b>Вопрос {index + 1}/{len(QUESTIONS)}</b>\n\n{question['question']}"
    kb = _question_inline_keyboard(question)

    if isinstance(event, CallbackQuery):
        if as_new_message:
            await event.message.answer(text, reply_markup=kb)
        else:
            await event.message.edit_text(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)

    await state.update_data(current_index=index)
    await state.set_state(LevelTestStates.question)


async def run_level_test(message: Message, state: FSMContext) -> None:
    """Запускает тест уровня. Можно вызывать из хендлеров завершения A1/A2."""
    await message.answer("Поехали!", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LevelTestStates.question)
    await state.update_data(current_index=0, answers={})
    await _send_question(message, state, 0)


@router.message(
    StateFilter(OnboardingStates.ready_check),
    F.text == "Начать",
)
async def start_level_test(message: Message, state: FSMContext):
    await run_level_test(message, state)


@router.callback_query(F.data.startswith("lt:"), StateFilter(LevelTestStates.question))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return

    q_id = int(parts[1])
    selected_idx = int(parts[2])

    data = await state.get_data()
    answers: dict = data.get("answers", {})
    if q_id in answers:
        await callback.answer()
        return

    question = next((q for q in QUESTIONS if q["id"] == q_id), None)
    if not question:
        await callback.answer()
        return

    is_correct = selected_idx == question["correct"]
    answers[q_id] = is_correct
    current_index = data.get("current_index", 0)

    await state.update_data(answers=answers)
    await callback.answer()

    next_index = current_index + 1

    if next_index >= len(QUESTIONS):
        level = calculate_level(answers)
        await update_user_level(
            callback.from_user.id,
            level,
            last_level_test_at=datetime.utcnow(),
            increment_test_count=True,
        )
        await state.clear()
        await callback.message.edit_text(
            f"✅ Тест завершён!\n\n<b>Твой уровень: {level}</b>",
        )
        async with async_session() as session:
            u = await get_user_by_telegram_id(callback.from_user.id, session)
        await callback.message.answer(
            "Выбери, с чего начнём:",
            reply_markup=main_menu_keyboard(u, show_review=False),
        )
        return

    show_motivation = next_index in (5, 10)
    if show_motivation:
        await callback.message.edit_text("✓")
        if next_index == 5:
            await callback.message.answer(MOTIVATION_5)
        else:
            await callback.message.answer(MOTIVATION_10)
        await _send_question(callback, state, next_index, as_new_message=True)
    else:
        await _send_question(callback, state, next_index, as_new_message=False)
