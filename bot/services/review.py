"""Сервис повторения ошибок (spaced repetition lite)."""
import re

from bot.db.review_repo import (
    add_review_item,
    get_due_reviews,
    remove_review_item,
    update_review_interval,
)

# Прогрессия интервалов: 1 -> 3 -> 7 -> 14 -> удалить
INTERVALS = [1, 3, 7, 14]


async def add_mistake(
    telegram_id: int,
    item_id: str,
    item_type: str,
    content: str,
    answer: str,
    interval: int = 0,
) -> None:
    """Добавляет ошибку в очередь повторений. interval=0 — сразу на сегодня (для теста)."""
    await add_review_item(
        telegram_id=telegram_id,
        item_id=item_id,
        item_type=item_type,
        content=content,
        answer=answer,
        interval=interval,
    )


async def get_today_reviews(telegram_id: int) -> list:
    """Возвращает элементы для повторения на сегодня."""
    return await get_due_reviews(telegram_id)


async def get_due_review_items(telegram_id: int, limit: int | None = None) -> list:
    """Возвращает элементы для повторения (все или с лимитом)."""
    return await get_due_reviews(telegram_id, limit=limit)


def _normalize_answer(text: str) -> str:
    """Нормализация для сравнения: lower, strip, убрать пунктуацию, тире."""
    if not text:
        return ""
    t = text.lower().strip()
    for ch in ".,;:!?—–-":
        t = t.replace(ch, " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_answer_correct(user_answer: str, expected_answer: str) -> bool:
    """Сравнение ответов с нормализацией."""
    return _normalize_answer(user_answer) == _normalize_answer(expected_answer)


async def is_translation_semantically_correct(
    user_answer: str,
    expected_answer: str,
    spanish_content: str,
) -> bool:
    """
    Проверка перевода по смыслу через LLM.
    Вызывать, когда is_answer_correct вернул False — для учёта синонимов,
    опущения местоимений (Живем = Мы живём) и т.п.
    """
    from bot.services.llm import check_translation_equivalent
    return await check_translation_equivalent(user_answer, expected_answer, spanish_content)


async def process_review_answer(review_item, is_correct: bool) -> bool:
    """
    Обрабатывает ответ пользователя.
    Возвращает True если карточку удалили (достигли 14 дней), False иначе.
    """
    interval = getattr(review_item, "interval", 1) or 1
    if is_correct:
        idx = INTERVALS.index(interval) if interval in INTERVALS else 0
        next_idx = idx + 1
        if next_idx >= len(INTERVALS):
            await remove_review_item(review_item.id)
            from bot.db.user_repo import increment_words_learned
            await increment_words_learned(getattr(review_item, "telegram_id", 0))
            return True
        await update_review_interval(review_item.id, INTERVALS[next_idx])
    else:
        await update_review_interval(review_item.id, 1)
    return False
