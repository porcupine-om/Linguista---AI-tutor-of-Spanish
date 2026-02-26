import json
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.states import ZeroStates, OnboardingStates
from bot.db.user_repo import (
    get_user_by_telegram_id,
    is_current_level_completed,
    update_zero_progress,
    update_user_activity,
    add_xp,
    increment_words_learned,
    ZERO_LESSON_IDS,
)
from bot.db.session import async_session
from bot.keyboards.main_menu import main_menu_keyboard
from bot.services.review import add_mistake
from bot.services.achievements_service import check_achievements

router = Router()

ZERO_LESSONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "zero_lessons"

# Поздравление после прохождения всех уроков ZERO
ZERO_COMPLETE_MESSAGE = (
    "Поздравляю! 🎉 Ты завершил(а) базовый модуль испанского языка — "
    "теперь можешь представляться, описывать предметы и составлять простые фразы на испанском.\n\n"
    "Что дальше?\n\n"
    "➡️ Продолжить обучение — переходи к следующим урокам уровня A1 и учи новые слова и фразы.\n\n"
    "📊 Пройти тест уровня — определи свой текущий уровень (A1/A2/B1), "
    "чтобы получать задания подходящей сложности.\n\n"
    "Вперёд к новым достижениям! 🚀"
)

ZERO_COMPLETE_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➡️ Продолжить обучение (A1)")],
        [KeyboardButton(text="📊 Пройти тест уровня")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📊 Статистика")],
    ],
    resize_keyboard=True,
)

ZERO_WELCOME = (
    "Привет, {name}! 🇪🇸\n\n"
    "<b>Добро пожаловать на базовый уровень испанского!</b>\n\n"
    "Здесь ты выучишь все буквы и звуки испанского языка, "
    "а также начнёшь учить первые слова и фразы.\n\n"
    "Каждая карточка — это шаг к уверенному владению языком. "
    "Просто листай и запоминай — всё просто и понятно.\n\n"
    "<b>Способы ввода текста:</b>\n"
    "1. С испанской раскладкой клавиатуры — идеальный вариант для обучения,\n"
    "2. С английской раскладки — текст вводится с заменой ñ на n (nino=niño), без знаков ¿¡ и т.д.,\n"
    "3. Яндекс клавиатура, испанская раскладка — нажать и удерживать пробел, наговорить текст, отредактировать, если нужно — отправить.\n\n"
    "Готов начать? 🚀"
)


def _load_lesson(lesson_id: str) -> dict | None:
    path = ZERO_LESSONS_DIR / f"{lesson_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_current_lesson_id(progress: int) -> str | None:
    """Возвращает lesson_id для текущего урока по progress (0 = первый урок)."""
    if progress < len(ZERO_LESSON_IDS):
        return ZERO_LESSON_IDS[progress]
    return None


async def start_zero_lesson(message: Message, state: FSMContext, lesson_id: str, show_header: bool = True) -> bool:
    """
    Запускает ZERO-урок напрямую (без welcome). Используется при «Продолжить обучение».
    show_header: показывать «Урок N: title» перед первой карточкой.
    """
    lesson = _load_lesson(lesson_id)
    if not lesson or not lesson.get("cards"):
        return False
    cards = sorted(lesson["cards"], key=lambda c: c.get("order", 0))
    await state.update_data(
        lesson_id=lesson_id,
        lesson=lesson,
        cards=cards,
        card_index=0,
    )
    await state.set_state(ZeroStates.card)

    lesson_num = ZERO_LESSON_IDS.index(lesson_id) + 1
    title = lesson.get("title", f"Урок {lesson_num}")
    description = lesson.get("description", "")

    if show_header:
        header = f"📚 <b>Урок {lesson_num}</b>: {title}"
        if description:
            header += f"\n\n{description}"
        await message.answer(header)

    card = cards[0]
    await message.answer(
        _format_card(card, 0, len(cards)),
        reply_markup=_card_keyboard(),
    )
    return True


def _card_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➡️ Далее")],
            [KeyboardButton(text="Закончить")],
        ],
        resize_keyboard=True,
    )


def _format_card(card: dict, index: int, total: int) -> str:
    from bot.utils import get_transcription_for_card

    parts = [
        f"<b>{card['spanish']}</b> — {card.get('russian', card.get('translation', ''))}",
        f"<i>Пример: {card.get('example', '—')}</i>",
    ]
    transcription = get_transcription_for_card(card)
    if transcription:
        parts.insert(1, f"📢 [{transcription}]")
    if card.get("note"):
        parts.append(f"\n📌 {card['note']}")
    parts.append(f"\n\n📄 {index + 1}/{total}")
    return "\n".join(parts)


def _quiz_keyboard(options: list[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True,
    )


@router.message(
    StateFilter(ZeroStates.welcome),
    F.text == "Поехали!",
)
async def zero_start(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    if not user:
        await state.clear()
        await message.answer("Нажми /start", reply_markup=main_menu_keyboard(None))
        return

    progress = getattr(user, "zero_progress", 0) or 0
    lesson_id = _get_current_lesson_id(progress)

    if lesson_id is None:
        await state.clear()
        await message.answer(
            "Ты уже прошёл(а) ZERO. Продолжай обучение в меню.",
            reply_markup=main_menu_keyboard(user),
        )
        return

    lesson = _load_lesson(lesson_id)
    if not lesson or not lesson.get("cards"):
        await state.clear()
        await message.answer("Урок не найден.", reply_markup=main_menu_keyboard(user))
        return

    cards = sorted(lesson["cards"], key=lambda c: c.get("order", 0))
    await state.update_data(
        lesson_id=lesson_id,
        lesson=lesson,
        cards=cards,
        card_index=0,
    )
    await state.set_state(ZeroStates.card)

    card = cards[0]
    await message.answer(
        _format_card(card, 0, len(cards)),
        reply_markup=_card_keyboard(),
    )


@router.message(
    StateFilter(ZeroStates.card),
    F.text == "Закончить",
)
async def zero_finish(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    await state.clear()
    await message.answer(
        "Прогресс сохранён. Возвращайся, когда будешь готов продолжить! 👋",
        reply_markup=main_menu_keyboard(user),
    )


@router.message(
    StateFilter(ZeroStates.card),
    F.text == "➡️ Далее",
)
async def zero_next_card(message: Message, state: FSMContext):
    data = await state.get_data()
    cards = data["cards"]
    card_index = data["card_index"] + 1

    if card_index >= len(cards):
        # Переход к quiz
        lesson = data["lesson"]
        quiz = lesson.get("quiz", {})
        questions = quiz.get("questions", [])

        if not questions:
            # Нет quiz — сразу завершаем урок
            await _complete_lesson(message, state, data["lesson_id"])
            return

        await state.update_data(
            card_index=card_index,
            quiz_index=0,
            quiz_questions=questions,
        )
        await state.set_state(ZeroStates.quiz)

        q = questions[0]
        await message.answer(
            f"📝 <b>Вопрос 1/{len(questions)}</b>\n\n{q['question']}",
            reply_markup=_quiz_keyboard(q["options"]),
        )
        return

    await state.update_data(card_index=card_index)
    card = cards[card_index]
    await message.answer(
        _format_card(card, card_index, len(cards)),
        reply_markup=_card_keyboard(),
    )


@router.message(StateFilter(ZeroStates.quiz), F.text)
async def zero_quiz_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    questions = data["quiz_questions"]
    quiz_index = data.get("quiz_index", 0)

    if quiz_index >= len(questions):
        await _complete_lesson(message, state, data["lesson_id"])
        return

    q = questions[quiz_index]
    user_answer = message.text.strip()
    correct_answer = q["options"][q["correct_index"]]
    lesson_id = data.get("lesson_id", "zero")

    next_index = quiz_index + 1

    if user_answer == correct_answer:
        feedback = "✅ Верно!"
    else:
        feedback = f"❌ Неверно. Правильно: <b>{correct_answer}</b>"
        await add_mistake(
            telegram_id=message.from_user.id,
            item_id=f"{lesson_id}_quiz_{quiz_index}",
            item_type="exercise",
            content=q.get("question", ""),
            answer=correct_answer,
        )

    if next_index >= len(questions):
        await message.answer(feedback)
        await _complete_lesson(message, state, data["lesson_id"])
        return

    await state.update_data(quiz_index=next_index)
    next_q = questions[next_index]
    await message.answer(
        f"{feedback}\n\n📝 <b>Вопрос {next_index + 1}/{len(questions)}</b>\n\n{next_q['question']}",
        reply_markup=_quiz_keyboard(next_q["options"]),
    )


async def _complete_lesson(message: Message, state: FSMContext, lesson_id: str):
    lesson = _load_lesson(lesson_id)
    success_msg = lesson.get("success_message", "✅ Урок завершён!")
    progress = ZERO_LESSON_IDS.index(lesson_id) + 1
    cards_count = len(lesson.get("cards", []))

    await update_zero_progress(message.from_user.id, progress)
    if cards_count > 0:
        await increment_words_learned(message.from_user.id, cards_count)
    await update_user_activity(message.from_user.id)
    await add_xp(message.from_user.id, 10)
    await state.clear()

    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)

    new_achievements = await check_achievements(user)
    for ach in new_achievements:
        await message.answer_dice(emoji="🎲")
        await message.answer(
            f"🏆 Новое достижение!\n\n<b>{ach['title']}</b>\n{ach['desc']}"
        )

    if progress >= len(ZERO_LESSON_IDS):
        await state.set_state(ZeroStates.zero_complete)
        await message.answer(
            f"{success_msg}\n\n{ZERO_COMPLETE_MESSAGE}",
            reply_markup=ZERO_COMPLETE_KEYBOARD,
        )
    else:
        await message.answer(
            success_msg,
            reply_markup=main_menu_keyboard(user),
        )


@router.message(
    StateFilter(ZeroStates.zero_complete),
    F.text == "➡️ Продолжить обучение (A1)",
)
async def zero_complete_continue(message: Message, state: FSMContext):
    """Переход на уроки уровня A1."""
    await state.clear()
    from bot.handlers.a1 import start_a1_for_user

    if await start_a1_for_user(message, state):
        return
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    await message.answer(
        "Выбери действие:",
        reply_markup=main_menu_keyboard(user),
    )


@router.message(
    StateFilter(ZeroStates.zero_complete),
    F.text == "📊 Пройти тест уровня",
)
async def zero_complete_test(message: Message, state: FSMContext):
    """Переход к тесту определения уровня."""
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)

    # Проверка: тест доступен по времени ИЛИ по завершению уровня
    if user:
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
            await message.answer(
                f"Ты недавно проходил(а) тест уровня.\n\n"
                f"Повторный тест станет доступен:\n"
                f"• через {days_left} дн.\n"
                f"• или сразу после завершения текущего уровня",
                reply_markup=main_menu_keyboard(user),
            )
            return

    await state.set_state(OnboardingStates.ready_check)
    await message.answer(
        "📖 <b>Тест определения уровня</b>\n\n"
        "Ответь на 15 вопросов по лексике и грамматике — "
        "мы определим твой уровень (A1, A2 или B1) и подберём подходящие задания.\n\n"
        "Готов начать?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Начать")]],
            resize_keyboard=True,
        ),
    )
