"""
Обработчик A2-уроков.
Поток: welcome (первый раз) → title → theory → cards → exercises → success.
"""
import json
from pathlib import Path

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.states import A2States
from bot.db.user_repo import get_user_by_telegram_id, update_a2_progress, update_user_activity, add_xp, increment_words_learned
from bot.db.session import async_session
from bot.keyboards.main_menu import main_menu_keyboard
from bot.services.llm import check_fill_text, evaluate_dialogue
from bot.services.review import add_mistake, get_due_review_items
from bot.services.achievements_service import check_achievements

router = Router()

A2_LESSONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "a2_lessons"

A2_WELCOME = (
    "Привет, {name}! 🇪🇸\n\n"
    "<b>Добро пожаловать на уровень A2!</b>\n\n"
    "<b>Здесь на начнешь:</b>\n"
    "• <b>Строить предложения</b> — не отдельные слова, а целые фразы\n"
    "• <b>Использовать времена глаголов</b> — прошедшее, настоящее, будущее\n"
    "• <b>Работать с микроситуациями</b> — реальные сценарии общения (в магазине, в кафе, о планах)\n"
    "• <b>Строить диалог</b> — отвечать на вопросы, поддерживать беседу\n"
    "• <b>Голосовые упражнения</b> — в каждом уроке одно задание нужно выполнить голосом: записывай голосовое сообщение и чётко произноси ответ. В текстовых упражнениях голос можно использовать по желанию — вместо печати.\n\n"
    "⚠️ <b>Голосовые сообщения:</b> записи твоего голоса обрабатываются только для обучения (распознавание речи и оценка произношения). Данные используются исключительно в целях обучения и не передаются третьим лицам.\n\n"
    "<b>Структура уроков:</b>\n"
    "Теория, карточки и упражнения — как на A1, но задания сложнее.\n\n"
    "Готов перейти на новый уровень? 🚀"
)

A2_WELCOME_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Поехали!")]],
    resize_keyboard=True,
)

A2_COMPLETE_MESSAGE = (
    "🎉 Поздравляю! Ты завершил(а) уровень A2.\n\n"
    "Ты освоил(а) времена глаголов и научился строить диалоги.\n"
    "Что хочешь сделать?"
)


def _a2_complete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Начать уровень B1", callback_data="a2_complete:b1")],
        [InlineKeyboardButton(text="🧪 Пройти тест", callback_data="a2_complete:test")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="a2_complete:menu")],
    ])


def _get_lesson_path(lesson_num: int) -> Path | None:
    for prefix in ("a2", "а2"):
        path = A2_LESSONS_DIR / f"{prefix}_{lesson_num:02d}.json"
        if path.exists():
            return path
    return None


def _load_lesson(lesson_num: int) -> dict | None:
    path = _get_lesson_path(lesson_num)
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _normalize_spanish_for_match(s: str) -> str:
    if not s:
        return ""
    t = s.lower().strip()
    for ch in "¿¡?!.,;:":
        t = t.replace(ch, "")
    return t


def _find_russian_for_spanish(spanish: str, cards: list[dict]) -> str | None:
    norm = _normalize_spanish_for_match(spanish)
    for c in cards:
        if _normalize_spanish_for_match(c.get("spanish", "")) == norm:
            return c.get("russian", "")
    return None


def _extract_russian_from_question(question: str) -> str | None:
    import re
    m = re.search(r"[\(\（]([^\)\）]+)[\)\）]", question)
    if m:
        return m.group(1).strip()
    m = re.search(r"«([^»]+)»", question)
    if m:
        return m.group(1).strip()
    return None


def _has_a2_lesson(progress: int) -> bool:
    return _get_lesson_path(progress + 1) is not None


def _get_total_a2_lessons() -> int:
    if not A2_LESSONS_DIR.exists():
        return 0
    count = 0
    for f in A2_LESSONS_DIR.iterdir():
        if f.suffix == ".json":
            stem = f.stem
            if stem.startswith("a2_") or stem.startswith("а2_"):
                try:
                    int(stem.split("_")[-1])
                    count += 1
                except (ValueError, IndexError):
                    pass
    return count


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
        f"<b>{card['spanish']}</b> — {card['russian']}",
        f"<i>Пример: {card.get('example', '—')}</i>",
    ]
    transcription = get_transcription_for_card(card)
    if transcription:
        parts.insert(1, f"📢 [{transcription}]")
    if card.get("note"):
        parts.append(f"<i>{card['note']}</i>")
    parts.append(f"\n\n📄 {index + 1}/{total}")
    return "\n".join(parts)


def _theory_to_cards_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➡️ К карточкам")]],
        resize_keyboard=True,
    )


def _exercise_choice_keyboard(options: list[str], exercise_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"a2ex:{exercise_idx}:{i}")]
            for i, opt in enumerate(options)
        ]
    )


def _next_lesson_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➡️ Следующий урок")],
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True,
    )


async def _start_a2_lesson(message: Message, state: FSMContext, lesson_num: int) -> bool:
    lesson = _load_lesson(lesson_num)
    if not lesson:
        return False

    cards = lesson.get("cards", [])
    exercises = lesson.get("exercises", [])

    await state.update_data(
        lesson_num=lesson_num,
        lesson=lesson,
        cards=cards,
        card_index=0,
        exercises=exercises,
        exercise_index=0,
        lesson_level="A2",
    )

    title = lesson.get("title", f"Урок A2-{lesson_num}")
    await message.answer(f"📚 <b>Урок A2-{lesson_num}</b>: {title}")

    theory = lesson.get("theory")
    if theory:
        await state.set_state(A2States.theory)
        await message.answer(
            f"📖 <b>Теория</b>\n\n{theory}",
            reply_markup=_theory_to_cards_keyboard(),
        )
    elif cards:
        await state.set_state(A2States.card)
        await message.answer(
            _format_card(cards[0], 0, len(cards)),
            reply_markup=_card_keyboard(),
        )
    else:
        await _go_to_exercises_or_complete(message, state)
    return True


async def _go_to_exercises_or_complete(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data.get("exercises", [])
    if exercises:
        await _start_exercises(message, state)
    else:
        await _complete_a2_lesson(message, state)


async def _start_exercises(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data.get("exercises", [])
    if not exercises:
        await _complete_a2_lesson(message, state)
        return

    await state.update_data(exercise_index=0)
    await _show_exercise(message, state, exercises[0], 0)


def _exercise_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Пропустить")]], resize_keyboard=True)


async def _show_exercise(message: Message, state: FSMContext, ex: dict, idx: int):
    total = len((await state.get_data()).get("exercises", []))
    await state.set_state(A2States.exercise)
    question = ex.get("question") or ex.get("prompt", "")

    if ex.get("type") == "choice":
        options = ex.get("options", [])
        kb = _exercise_choice_keyboard(options, idx)
        await message.answer(f"✏️ Упражнение {idx + 1}/{total}\n\n{question}", reply_markup=kb)
    elif ex.get("type") == "voice":
        task_ru = ex.get("task_ru", ex.get("question", ex.get("prompt", "")))
        await message.answer(
            f"🎙 <b>Голосовое задание</b>\n\n{task_ru}\n\nЗапиши голосовое сообщение.",
            reply_markup=_exercise_reply_keyboard(),
        )
        await state.update_data(
            lesson_voice_expected=ex["expected"],
            waiting_for_voice=True,
            lesson_level="A2",
        )
    else:
        await message.answer(
            f"✏️ Упражнение {idx + 1}/{total}\n\n{question}\n\nНапиши свой ответ сообщением:",
            reply_markup=_exercise_reply_keyboard(),
        )


async def _complete_a2_lesson(message: Message, state: FSMContext):
    data = await state.get_data()
    lesson_num = data.get("lesson_num", 1)
    lesson = data.get("lesson", {})
    success_msg = lesson.get("success_message", "✅ Урок завершён!")
    cards_count = len(lesson.get("cards", []))

    await update_a2_progress(message.from_user.id, lesson_num)
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

    if _has_a2_lesson(lesson_num):
        await message.answer(
            success_msg,
            reply_markup=_next_lesson_keyboard(),
        )
    else:
        await message.answer(success_msg)
        await message.answer(A2_COMPLETE_MESSAGE, reply_markup=_a2_complete_keyboard())


async def start_a2_for_user(event: Message | CallbackQuery, state: FSMContext, already_shown_count: bool = False) -> bool:
    if isinstance(event, CallbackQuery):
        msg = event.message
        user_id = event.from_user.id
    else:
        msg = event
        user_id = event.from_user.id

    async with async_session() as session:
        user = await get_user_by_telegram_id(user_id, session)
    if not user or user.level != "A2":
        return False

    due_items = await get_due_review_items(user_id)
    count = len(due_items)
    if count > 0:
        from bot.handlers.review import start_review
        await msg.answer(f"📚 Сначала повторим прошлые ошибки. Сегодня к повторению: {count}. ")
        if await start_review(msg, state, continue_after_lesson=True):
            return True
    elif not already_shown_count:
        await msg.answer("📚 Сегодня повторений нет — можно идти дальше!")

    a2_progress = getattr(user, "a2_progress", 0)
    total_lessons = _get_total_a2_lessons()
    if total_lessons > 0 and a2_progress >= total_lessons:
        await state.clear()
        await msg.answer(A2_COMPLETE_MESSAGE, reply_markup=_a2_complete_keyboard())
        return True

    lesson_num = a2_progress + 1
    lesson = _load_lesson(lesson_num)
    if not lesson:
        await state.clear()
        await msg.answer(
            "Все уроки A2 завершены.",
            reply_markup=main_menu_keyboard(user),
        )
        return True

    if a2_progress == 0:
        await state.set_state(A2States.welcome)
        from bot.utils import get_display_name
        user_obj = event.from_user if isinstance(event, CallbackQuery) else msg.from_user
        await msg.answer(A2_WELCOME.format(name=get_display_name(user_obj)), reply_markup=A2_WELCOME_KEYBOARD)
        return True

    await _start_a2_lesson(msg, state, lesson_num)
    return True


# ─── Обработчики ───

@router.message(A2States.welcome, F.text == "Поехали!")
async def a2_welcome_start(message: Message, state: FSMContext):
    due_items = await get_due_review_items(message.from_user.id)
    count = len(due_items)
    if count > 0:
        from bot.handlers.review import start_review
        await message.answer(f"📚 Сегодня к повторению: {count}. Сначала повторим прошлые ошибки")
        if await start_review(message, state, continue_after_lesson=True):
            return
    else:
        async with async_session() as session:
            user = await get_user_by_telegram_id(message.from_user.id, session)
        a2_p = getattr(user, "a2_progress", 0) or 0
        if a2_p > 0:
            await message.answer("📚 Сегодня повторений нет — можно идти дальше!")
    await _start_a2_lesson(message, state, lesson_num=1)


@router.message(A2States.card, F.text == "Закончить")
async def a2_finish(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    await state.clear()
    await message.answer(
        "Прогресс сохранён. Возвращайся, когда будешь готов продолжить! 👋",
        reply_markup=main_menu_keyboard(user),
    )


@router.message(A2States.card, F.text == "➡️ Далее")
async def a2_next_card(message: Message, state: FSMContext):
    data = await state.get_data()
    cards = data["cards"]
    card_index = data["card_index"] + 1

    if card_index >= len(cards):
        await _go_to_exercises_or_complete(message, state)
        return

    await state.update_data(card_index=card_index)
    await message.answer(
        _format_card(cards[card_index], card_index, len(cards)),
        reply_markup=_card_keyboard(),
    )


@router.message(A2States.theory, F.text == "➡️ К карточкам")
async def a2_theory_to_cards(message: Message, state: FSMContext):
    data = await state.get_data()
    cards = data.get("cards", [])
    if cards:
        await state.update_data(card_index=0)
        await state.set_state(A2States.card)
        await message.answer(
            _format_card(cards[0], 0, len(cards)),
            reply_markup=_card_keyboard(),
        )
    else:
        await _go_to_exercises_or_complete(message, state)


@router.callback_query(F.data.startswith("a2ex:"), StateFilter(A2States.exercise))
async def a2_exercise_choice(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer()
        return
    ex_idx = int(parts[1])
    chosen_idx = int(parts[2])

    data = await state.get_data()
    exercises = data["exercises"]
    lesson_num = data.get("lesson_num", 1)
    ex = exercises[ex_idx]
    correct = chosen_idx == ex["correct_index"]
    correct_opt = ex["options"][ex["correct_index"]]

    if not correct:
        lesson = data.get("lesson", {})
        cards = lesson.get("cards", [])
        question = ex.get("question", "")
        answer_ru = _find_russian_for_spanish(correct_opt, cards) or _extract_russian_from_question(question) or correct_opt
        await add_mistake(
            telegram_id=callback.from_user.id,
            item_id=f"a2_{lesson_num}_choice_{ex_idx}",
            item_type="exercise",
            content=correct_opt,
            answer=answer_ru,
        )

    feedback = "✅ Верно!" if correct else f"❌ Неверно. Правильно: <b>{correct_opt}</b>"
    await callback.message.edit_text(
        callback.message.text + f"\n\n{feedback}",
    )
    await callback.answer()

    ex_idx += 1
    if ex_idx >= len(exercises):
        await _complete_a2_lesson(callback.message, state)
        return

    await state.update_data(exercise_index=ex_idx)
    await _show_exercise(callback.message, state, exercises[ex_idx], ex_idx)


@router.message(A2States.exercise, F.text == "Пропустить")
async def a2_exercise_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data["exercises"]
    ex_idx = data.get("exercise_index", 0) + 1

    await message.answer("⏭ Пропущено.")

    if ex_idx >= len(exercises):
        await _complete_a2_lesson(message, state)
        return

    await state.update_data(exercise_index=ex_idx)
    await _show_exercise(message, state, exercises[ex_idx], ex_idx)


@router.message(A2States.exercise, F.text)
async def a2_exercise_text(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data["exercises"]
    lesson_num = data.get("lesson_num", 1)
    ex_idx = data.get("exercise_index", 0)
    ex = exercises[ex_idx]

    if ex["type"] == "fill_text":
        await message.answer("Проверяю твой ответ…")
        correct, feedback = await check_fill_text(message.text, ex.get("answer", ""))
        await message.answer(feedback)
        if not correct:
            expected = ex.get("answer", "")
            question = ex.get("question", "")
            if "___" in question:
                content = question.replace("___", expected).replace("«", "").replace("»", "").strip()
            else:
                content = expected
            answer_ru = _extract_russian_from_question(question) or expected
            await add_mistake(
                telegram_id=message.from_user.id,
                item_id=f"a2_{lesson_num}_fill_{ex_idx}",
                item_type="exercise",
                content=content if content else expected,
                answer=answer_ru,
            )
    elif ex["type"] == "dialogue":
        await message.answer("Проверяю твой ответ…")
        lesson = data.get("lesson", {})
        theory = lesson.get("theory", "")
        feedback = await evaluate_dialogue(message.text, ex.get("prompt", ""), theory=theory)
        await message.answer(feedback)
        if feedback.strip().startswith("❌"):
            content = ex.get("review_content", "")
            answer_ru = ex.get("review_answer", "")
            if not content or not answer_ru:
                content = ex.get("prompt", "")
                answer_ru = ex.get("prompt", "")
            await add_mistake(
                telegram_id=message.from_user.id,
                item_id=f"a2_{lesson_num}_dialogue_{ex_idx}",
                item_type="exercise",
                content=content,
                answer=answer_ru,
            )
    else:
        await message.answer("Нажми на кнопку варианта.")
        return

    ex_idx += 1
    if ex_idx >= len(exercises):
        await _complete_a2_lesson(message, state)
        return

    await state.update_data(exercise_index=ex_idx)
    await _show_exercise(message, state, exercises[ex_idx], ex_idx)


@router.message(F.text == "➡️ Следующий урок")
async def next_lesson(message: Message, state: FSMContext):
    from bot.handlers.b1 import start_b1_for_user
    if await start_b1_for_user(message, state):
        return
    if await start_a2_for_user(message, state):
        return
    from bot.handlers.a1 import start_a1_for_user
    await start_a1_for_user(message, state)


@router.callback_query(F.data.startswith("a2_complete:"))
async def a2_complete_callback(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[-1]
    await callback.answer()

    async with async_session() as session:
        user = await get_user_by_telegram_id(callback.from_user.id, session)

    if action == "b1":
        from bot.db.user_repo import update_user_level
        await update_user_level(callback.from_user.id, "B1")
        from bot.handlers.b1 import start_b1_for_user
        if await start_b1_for_user(callback, state):
            return
        if user:
            await callback.message.answer("Выбери действие:", reply_markup=main_menu_keyboard(user))
    elif action == "test":
        from bot.handlers.level_test import run_level_test
        await run_level_test(callback.message, state)
    elif action == "menu":
        await state.clear()
        if user:
            await callback.message.answer("Выбери действие:", reply_markup=main_menu_keyboard(user))
