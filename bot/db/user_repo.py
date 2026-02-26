import json
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.db.session import async_session_maker
from bot.services.review import get_due_review_items

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ZERO_LESSONS_DIR = DATA_DIR / "zero_lessons"
A1_LESSONS_DIR = DATA_DIR / "a1_lessons"
A2_LESSONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "a2_lessons"
B1_LESSONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "b1_lessons"


def _has_b1_lesson_file(progress: int) -> bool:
    """Проверяет, есть ли файл урока b1_{progress+1:02d}.json."""
    lesson_num = progress + 1
    for prefix in ("b1", "б1"):
        if (B1_LESSONS_DIR / f"{prefix}_{lesson_num:02d}.json").exists():
            return True
    return False


def _has_a2_lesson_file(progress: int) -> bool:
    """Проверяет, есть ли файл урока a2_{progress+1:02d}.json."""
    lesson_num = progress + 1
    for prefix in ("a2", "а2"):
        if (A2_LESSONS_DIR / f"{prefix}_{lesson_num:02d}.json").exists():
            return True
    return False


def _has_a1_lesson_file(progress: int) -> bool:
    """Проверяет, есть ли файл урока a1_{progress+1:02d}.json."""
    lesson_num = progress + 1
    for prefix in ("a1", "а1"):
        if (A1_LESSONS_DIR / f"{prefix}_{lesson_num:02d}.json").exists():
            return True
    return False


async def get_user_by_telegram_id(telegram_id: int, session: AsyncSession) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def update_user_level(
    telegram_id: int,
    level: str,
    last_level_test_at: datetime | None = None,
    increment_test_count: bool = False,
) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.level = level
            if last_level_test_at is not None:
                user.last_level_test_at = last_level_test_at
            if increment_test_count:
                user.level_test_count = (getattr(user, "level_test_count", 0) or 0) + 1
            await session.commit()


async def update_zero_progress(telegram_id: int, progress: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.zero_progress = progress
            await session.commit()


async def update_a1_progress(telegram_id: int, progress: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.a1_progress = progress
            await session.commit()


async def update_a2_progress(telegram_id: int, progress: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.a2_progress = progress
            await session.commit()


async def update_b1_progress(telegram_id: int, progress: int) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.b1_progress = progress
            await session.commit()


async def add_xp(telegram_id: int, amount: int) -> None:
    """Начисляет XP пользователю."""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.xp = (getattr(user, "xp", 0) or 0) + amount
            await session.commit()


async def increment_words_learned(telegram_id: int, amount: int = 1) -> None:
    """Увеличивает счётчик выученных слов (при завершении урока или освоении карточки в повторениях)."""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.words_learned = (getattr(user, "words_learned", 0) or 0) + amount
            await session.commit()


async def increment_voice_practice(telegram_id: int) -> None:
    """Увеличивает счётчик голосовых практик."""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.voice_practice_count = (getattr(user, "voice_practice_count", 0) or 0) + 1
            await session.commit()


async def update_user_activity(telegram_id: int) -> None:
    """Обновляет streak (дни подряд) и last_activity_date после активности."""
    today = date.today()
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return
        last = getattr(user, "last_activity_date", None)
        if last is not None:
            last = last.date() if hasattr(last, "date") else last
        if last == today:
            return
        if last == today - timedelta(days=1):
            user.streak = (getattr(user, "streak", 0) or 0) + 1
        else:
            user.streak = 1
        user.last_activity_date = today
        await session.commit()


def _load_zero_lesson_ids() -> list[str]:
    """Динамически загружает список lesson_id из папки zero_lessons (zero_01, zero_02, ...)."""
    if not ZERO_LESSONS_DIR.exists():
        return []
    files = sorted(ZERO_LESSONS_DIR.glob("zero_*.json"))
    return [f.stem for f in files]


# Номера ZERO-уроков (zero_progress = кол-во завершённых). Загружается из файлов при старте.
ZERO_LESSON_IDS = _load_zero_lesson_ids()


async def is_current_level_completed(user) -> bool:
    """
    Проверяет, завершён ли текущий уровень обучения.
    Позволяет открыть тест раньше 30 дней при завершении уровня.
    """
    if not user:
        return False
    zero_progress = getattr(user, "zero_progress", 0) or 0
    a1_progress = getattr(user, "a1_progress", 0) or 0

    # Путь ZERO: A1 без теста, проходим ZERO
    if user.level == "A1" and user.last_level_test_at is None:
        return zero_progress >= len(ZERO_LESSON_IDS)

    # Путь A1: ZERO завершён или тест пройден
    if user.level == "A1":
        return not _has_a1_lesson_file(a1_progress)

    a2_progress = getattr(user, "a2_progress", 0) or 0
    if user.level == "A2":
        return not _has_a2_lesson_file(a2_progress)

    b1_progress = getattr(user, "b1_progress", 0) or 0
    if user.level == "B1":
        return not _has_b1_lesson_file(b1_progress)

    return False


def has_unfinished_progress(user: User | None) -> bool:
    """Проверяет, есть ли незавершённый прогресс на любом уровне."""
    if not user:
        return False
    zero_progress = getattr(user, "zero_progress", 0) or 0
    a1_progress = getattr(user, "a1_progress", 0) or 0

    if user.level == "A1":
        if user.last_level_test_at is None:
            if zero_progress < len(ZERO_LESSON_IDS):
                return True
        if _has_a1_lesson_file(a1_progress):
            return True
    a2_progress = getattr(user, "a2_progress", 0) or 0
    if user.level == "A2":
        if _has_a2_lesson_file(a2_progress):
            return True
    b1_progress = getattr(user, "b1_progress", 0) or 0
    if user.level == "B1":
        if _has_b1_lesson_file(b1_progress):
            return True
    return False


def _estimate_words_from_progress(zero: int, a1: int, a2: int, b1: int) -> int:
    """Оценивает кол-во выученных слов по прогрессу (для backfill)."""
    total = 0
    for i in range(1, zero + 1):
        path = ZERO_LESSONS_DIR / f"zero_{i:02d}.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                total += len(data.get("cards", []))
            except Exception:
                pass
    for i in range(1, a1 + 1):
        for prefix in ("a1", "а1"):
            path = A1_LESSONS_DIR / f"{prefix}_{i:02d}.json"
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    total += len(data.get("cards", []))
                except Exception:
                    pass
                break
    for i in range(1, a2 + 1):
        for prefix in ("a2", "а2"):
            path = A2_LESSONS_DIR / f"{prefix}_{i:02d}.json"
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    total += len(data.get("cards", []))
                except Exception:
                    pass
                break
    for i in range(1, b1 + 1):
        for prefix in ("b1", "б1"):
            path = B1_LESSONS_DIR / f"{prefix}_{i:02d}.json"
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    total += len(data.get("cards", []))
                except Exception:
                    pass
                break
    return total


async def get_user_stats(
    telegram_id: int,
    name: str | None = None,
) -> dict | None:
    """
    Возвращает статистику пользователя для отображения в профиле.
    name — имя из Telegram (передаётся вызывающим).
    """
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
    if not user:
        return None

    created_at = getattr(user, "created_at", None)
    if created_at is None:
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            u = result.scalar_one_or_none()
            if u:
                u.created_at = datetime.utcnow()
                await session.commit()
        created_at = datetime.utcnow()

    due_items = await get_due_review_items(telegram_id)
    count_due_reviews = len(due_items)

    words_learned = getattr(user, "words_learned", 0) or 0
    zero_p = getattr(user, "zero_progress", 0) or 0
    a1_p = getattr(user, "a1_progress", 0) or 0
    a2_p = getattr(user, "a2_progress", 0) or 0
    b1_p = getattr(user, "b1_progress", 0) or 0
    # Backfill для пользователей, прошедших уроки до добавления учёта слов
    if words_learned == 0 and (zero_p > 0 or a1_p > 0 or a2_p > 0 or b1_p > 0):
        estimated = _estimate_words_from_progress(zero_p, a1_p, a2_p, b1_p)
        if estimated > 0:
            async with async_session_maker() as s:
                r = await s.execute(select(User).where(User.telegram_id == telegram_id))
                u = r.scalar_one_or_none()
                if u:
                    u.words_learned = estimated
                    await s.commit()
            words_learned = estimated

    return {
        "name": name or "Ученик",
        "level": getattr(user, "level", None),
        "xp": getattr(user, "xp", 0) or 0,
        "streak": getattr(user, "streak", 0) or 0,
        "created_at": created_at,
        "zero_progress": getattr(user, "zero_progress", 0) or 0,
        "a1_progress": getattr(user, "a1_progress", 0) or 0,
        "a2_progress": getattr(user, "a2_progress", 0) or 0,
        "b1_progress": getattr(user, "b1_progress", 0) or 0,
        "count_due_reviews": count_due_reviews,
        "words_learned": words_learned,
        "level_test_count": getattr(user, "level_test_count", 0) or 0,
        "last_level_test_at": getattr(user, "last_level_test_at", None),
    }


async def get_or_create_user(telegram_id: int) -> User:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user
