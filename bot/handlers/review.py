"""
Показ повторений ошибок (spaced repetition lite).
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.states import ReviewStates
from bot.db.session import async_session
from bot.db.user_repo import get_user_by_telegram_id, update_user_activity, add_xp
from bot.services.achievements_service import check_achievements
from bot.services.review import (
    get_due_review_items,
    process_review_answer,
    is_answer_correct,
    is_translation_semantically_correct,
)

REVIEW_LIMIT = 7
from bot.keyboards.main_menu import main_menu_keyboard

router = Router()


def _item_to_dict(r) -> dict:
    return {
        "id": r.id,
        "item_id": r.item_id,
        "content": getattr(r, "content", "") or r.item_id,
        "answer": getattr(r, "answer", "") or "",
    }


def _content_label(content: str) -> str:
    """Подпись: «Слово:» или «Фраза:» в зависимости от наличия пробела."""
    return "Фраза:" if " " in content else "Слово:"


async def start_review(message: Message, state: FSMContext, continue_after_lesson: bool = False) -> bool:
    """
    Запускает сессию повторений. Возвращает True, если есть элементы.
    continue_after_lesson: после завершения запустить урок.
    """
    reviews = await get_due_review_items(message.from_user.id, limit=REVIEW_LIMIT)
    if not reviews:
        return False

    total = len(reviews)
    await state.update_data(
        review_items=[_item_to_dict(r) for r in reviews],
        review_index=0,
        review_total=total,
        review_continue_lesson=continue_after_lesson,
    )
    await state.set_state(ReviewStates.item)

    item = reviews[0]
    content = getattr(item, "content", None) or item.item_id
    num = 1
    header = f"📚 Повторение {num}/{total}\n\n" if total > 1 else ""
    label = _content_label(content)
    await message.answer(
        f"{header}{label}\n\n🇪🇸 <b>{content}</b>\n\nНапиши перевод:",
    )
    return True


@router.message(F.text == "📚 Повторить ошибки")
async def review_entry(message: Message, state: FSMContext):
    """Вход по кнопке «Повторить ошибки»."""
    due_items = await get_due_review_items(message.from_user.id)
    count = len(due_items)
    if count == 0:
        async with async_session() as session:
            user = await get_user_by_telegram_id(message.from_user.id, session)
        await message.answer(
            "📚 Сегодня повторений нет — можно идти дальше!",
            reply_markup=main_menu_keyboard(user),
        )
        return

    await message.answer(f"📚 Сначала повторим прошлые ошибки. Сегодня к повторению: {count}. ")
    await start_review(message, state, continue_after_lesson=False)


@router.message(ReviewStates.item, F.text == "Закончить")
async def review_finish(message: Message, state: FSMContext):
    """Выход из повторения."""
    data = await state.get_data()
    continue_lesson = data.get("review_continue_lesson", False)
    await state.clear()

    if continue_lesson:
        from bot.handlers.menu import resume
        await resume(message, state)
        return

    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    await message.answer(
        "Повторения прерваны. Возвращайся, когда будешь готов! 📚",
        reply_markup=main_menu_keyboard(user),
    )


async def _finish_review_and_continue(message: Message, state: FSMContext):
    """Завершение повторений и переход к уроку или меню."""
    data = await state.get_data()
    continue_lesson = data.get("review_continue_lesson", False)
    reviews_count = data.get("review_total", len(data.get("review_items", [])))
    await update_user_activity(message.from_user.id)
    await add_xp(message.from_user.id, reviews_count * 5)
    await state.clear()

    remaining = await get_due_review_items(message.from_user.id)
    if len(remaining) > REVIEW_LIMIT:
        await message.answer(
            "📚 Сегодня повторим только часть карточек (7), чтобы не перегружать тебя.\n"
            "Остальные повторим позже 🙂"
        )

    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    new_achievements = await check_achievements(user)
    for ach in new_achievements:
        await message.answer_dice(emoji="🎲")
        await message.answer(
            f"🏆 Новое достижение!\n\n<b>{ach['title']}</b>\n{ach['desc']}"
        )

    if continue_lesson:
        await message.answer("🎉 Повторения завершены!\nПродолжаем обучение.")
        from bot.handlers.menu import resume
        await resume(message, state, from_review_complete=True)
    else:
        await message.answer(
            "🎉 Повторения завершены!",
            reply_markup=main_menu_keyboard(user),
        )


@router.message(ReviewStates.item, F.text)
async def review_answer(message: Message, state: FSMContext):
    """Проверка ответа, process_review_answer, показ следующей карточки."""
    data = await state.get_data()
    items = data.get("review_items", [])
    index = data.get("review_index", 0)
    total = data.get("review_total", len(items))

    if not items or index >= len(items):
        await state.clear()
        return

    current = items[index]
    user_answer = message.text or ""
    expected = current.get("answer", "")
    content_es = current.get("content", "")

    correct = is_answer_correct(user_answer, expected) if expected else True
    if not correct and expected and content_es:
        await message.answer("Проверяю ответ…")
        correct = await is_translation_semantically_correct(user_answer, expected, content_es)

    if correct:
        feedback = "✅ Верно!"
    else:
        feedback = f"❌ Неверно\nПравильный ответ: <b>{expected}</b>"

    await message.answer(feedback)

    from bot.db.review_repo import get_review_item_by_id
    review_item = await get_review_item_by_id(current["id"])
    if review_item:
        await process_review_answer(review_item, correct)

    index += 1
    if index >= len(items):
        await _finish_review_and_continue(message, state)
        return

    await state.update_data(review_index=index)
    next_item = items[index]
    content = next_item.get("content", next_item.get("item_id", ""))
    num = index + 1
    header = f"📚 Повторение {num}/{total}\n\n" if total > 1 else ""
    label = _content_label(content)
    await message.answer(
        f"{header}{label}\n\n🇪🇸 <b>{content}</b>\n\nНапиши перевод:",
    )
