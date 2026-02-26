from datetime import date
from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.db.session import async_session
from bot.db.user_repo import get_user_by_telegram_id, get_user_stats, has_unfinished_progress, ZERO_LESSON_IDS
from bot.config.achievements_config import ACHIEVEMENTS
from bot.db.achievement_repo import get_user_achievements
from bot.handlers.zero import start_zero_lesson, _get_current_lesson_id
from bot.handlers.a1 import start_a1_for_user
from bot.handlers.a2 import start_a2_for_user
from bot.handlers.b1 import start_b1_for_user
from bot.handlers.review import start_review
from bot.services.review import get_due_review_items
from bot.keyboards.main_menu import main_menu_keyboard
from bot.utils import format_date, get_test_availability_text, progress_bar, get_display_name

router = Router()

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ZERO_LESSONS_DIR = DATA_DIR / "zero_lessons"
A1_LESSONS_DIR = DATA_DIR / "a1_lessons"
A2_LESSONS_DIR = DATA_DIR / "a2_lessons"
B1_LESSONS_DIR = DATA_DIR / "b1_lessons"


def _get_zero_lesson_count() -> int:
    """Количество уроков ZERO (zero_*.json)."""
    if not ZERO_LESSONS_DIR.exists():
        return 0
    return len(list(ZERO_LESSONS_DIR.glob("zero_*.json")))


def _get_a1_lesson_count() -> int:
    """Количество уроков A1 (a1_*.json / а1_*.json)."""
    if not A1_LESSONS_DIR.exists():
        return 0
    count = len(list(A1_LESSONS_DIR.glob("a1_*.json")))
    if count == 0:
        count = len(list(A1_LESSONS_DIR.glob("а1_*.json")))
    return count


def _get_lesson_count(lesson_dir: Path, pattern: str) -> int:
    if not lesson_dir.exists():
        return 0
    return len(list(lesson_dir.glob(pattern)))


@router.message(F.text == "Продолжить обучение")
async def resume(message: Message, state: FSMContext, from_review_complete: bool = False):
    """from_review_complete: True если вызван после завершения повторений (не показывать «Сегодня повторений нет»)."""
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    if not user or not has_unfinished_progress(user):
        await message.answer(
            "Нечего продолжать. Выбери «📚 Начать обучение».",
            reply_markup=main_menu_keyboard(user),
        )
        return

    # Сначала повторение ошибок перед уроком
    due_items = await get_due_review_items(message.from_user.id)
    count = len(due_items)
    zero_progress = getattr(user, "zero_progress", 0) or 0
    a1_progress = getattr(user, "a1_progress", 0) or 0
    has_any_lesson_progress = zero_progress > 0 or a1_progress > 0

    if count > 0:
        await message.answer(f"📚 Сегодня к повторению: {count}. Сначала повторим прошлые ошибки")
        if await start_review(message, state, continue_after_lesson=True):
            return
    elif not from_review_complete and has_any_lesson_progress:
        # Не показывать после теста / при первом входе — пользователь ещё не проходил уроки
        await message.answer("📚 Сегодня повторений нет — можно идти дальше!")

    # ZERO (A1 без теста, ZERO не завершён)
    if user.level == "A1" and user.last_level_test_at is None and zero_progress < len(ZERO_LESSON_IDS):
        lesson_id = _get_current_lesson_id(zero_progress)
        if lesson_id and await start_zero_lesson(message, state, lesson_id, show_header=True):
            return

    # level=A1 → A1-урок (ZERO завершён или пользователь с тестом)
    if user.level == "A1":
        if await start_a1_for_user(message, state, already_shown_count=True):
            return

    # level=A2 → A2-урок
    if user.level == "A2":
        if await start_a2_for_user(message, state, already_shown_count=True):
            return

    # level=B1 → B1-урок
    if user.level == "B1":
        if await start_b1_for_user(message, state, already_shown_count=True):
            return

    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard(user))




@router.message(lambda msg: msg.text == "👤 Мой профиль")
async def profile(message: Message):
    name = get_display_name(message.from_user)
    stats = await get_user_stats(message.from_user.id, name=name)

    if stats is None:
        await message.answer("Сначала нажми /start")
        return

    created_at = stats["created_at"]
    created_date = created_at.date() if hasattr(created_at, "date") else created_at
    today = date.today()
    days_with_bot = (today - created_date).days + 1

    level = stats["level"] or "Базовый"
    level_test_count = stats.get("level_test_count", 0) or 0
    last_level_test_at = stats.get("last_level_test_at")

    zero_total = _get_zero_lesson_count()
    a1_total = _get_a1_lesson_count()
    a2_total = _get_lesson_count(A2_LESSONS_DIR, "a2_*.json") or _get_lesson_count(A2_LESSONS_DIR, "а2_*.json")
    b1_total = _get_lesson_count(B1_LESSONS_DIR, "b1_*.json") or _get_lesson_count(B1_LESSONS_DIR, "б1_*.json")

    z, a1, a2, b1 = stats["zero_progress"], stats["a1_progress"], stats.get("a2_progress", 0), stats.get("b1_progress", 0)
    level_lines = []
    if zero_total:
        level_lines.append(f"Базовый {progress_bar(z, zero_total)} {z}/{zero_total}")
    if a1_total:
        level_lines.append(f"A1      {progress_bar(a1, a1_total)} {a1}/{a1_total}")
    if a2_total:
        level_lines.append(f"A2      {progress_bar(a2, a2_total)} {a2}/{a2_total}")
    if b1_total:
        level_lines.append(f"B1      {progress_bar(b1, b1_total)} {b1}/{b1_total}")

    lines = [
        f"👤 <b>{stats['name']}</b>",
        "",
        f"🇪🇸 Уровень: {level}",
        f"📅 Начало обучения: {format_date(created_at)}",
        f"🔥 Дней подряд: {stats['streak']}",
        f"⭐ Баллы обучения: {stats['xp']}",
        "",
        "📚 <b>Прогресс по уровням:</b>",
        *level_lines,
        "",
        f"📖 Слов выучено: {stats.get('words_learned', 0)}",
        f"🧠 Карточек на повторении: {stats['count_due_reviews']}",
        f"🗓 Всего дней с Lingüista ES: {days_with_bot}",
        "",
    ]

    if level_test_count == 0:
        lines.extend([
            "🧪 Тест уровня: ещё не проходил(а)",
            "▶️ Тест доступен: по окончании уровня",
        ])
    else:
        test_availability = get_test_availability_text(last_level_test_at)
        lines.extend([
            f"🧪 Тест уровня: {level_test_count} раз(а)",
            f"📅 Последний тест: {format_date(last_level_test_at)}",
            f"▶️ Повторный тест: {test_availability}",
        ])
        if test_availability != "доступен сейчас":
            lines.append("Заверши текущий уровень, чтобы открыть тест раньше 30 дней")

    text = "\n".join(lines)

    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)
    await message.answer(text, reply_markup=main_menu_keyboard(user))



@router.message(lambda msg: msg.text == "📊 Статистика")
async def stats(message: Message):
    async with async_session() as session:
        user = await get_user_by_telegram_id(message.from_user.id, session)

    if user is None:
        await message.answer("Сначала нажми /start")
        return

    # Синхронизация: начислить достижения, которые могли быть пропущены (напр. при переходе через 200 баллов)
    from bot.services.achievements_service import check_achievements
    await check_achievements(user)

    zero_total = _get_zero_lesson_count()
    a1_total = _get_a1_lesson_count()
    a2_total = _get_lesson_count(A2_LESSONS_DIR, "a2_*.json")
    if a2_total == 0:
        a2_total = _get_lesson_count(A2_LESSONS_DIR, "а2_*.json")
    b1_total = _get_lesson_count(B1_LESSONS_DIR, "b1_*.json")
    if b1_total == 0:
        b1_total = _get_lesson_count(B1_LESSONS_DIR, "б1_*.json")

    zero_progress = getattr(user, "zero_progress", 0) or 0
    a1_progress = getattr(user, "a1_progress", 0) or 0
    a2_progress = getattr(user, "a2_progress", 0) or 0
    b1_progress = getattr(user, "b1_progress", 0) or 0

    review_items = await get_due_review_items(message.from_user.id)
    review_count = len(review_items)

    level = user.level or "определяется"

    xp = getattr(user, "xp", 0) or 0
    streak = getattr(user, "streak", 0) or 0
    achievements_list = await get_user_achievements(message.from_user.id)
    achievements_count = len(achievements_list)
    achievement_titles = [
        ACHIEVEMENTS.get(code, {}).get("title", code) for code in achievements_list
    ]
    lines = [
        "📊 <b>Твоя статистика</b>",
        "",
        f"Текущий уровень: <b>{level}</b>",
        f"⭐ Баллы обучения: {xp}",
        f"🔥 Дней подряд: {streak}",
        f"🏆 Достижения: {achievements_count}",
    ]
    for title in achievement_titles:
        lines.append(f" - {title}")
    lines.extend([
        "",
        "Пройдено уроков (пройдено / всего):",
        "",
        f"Базовый уровень: {zero_progress} / {zero_total}",
        f"A1: {a1_progress} / {a1_total}",
    ])
    if a2_total > 0:
        lines.append(f"A2: {a2_progress} / {a2_total}")
    if b1_total > 0:
        lines.append(f"B1: {b1_progress} / {b1_total}")

    lines.extend(["", f"Карточек на повторении: {review_count}"])
    if review_count == 0:
        lines.append("Отлично! Все карточки повторены ✅")

    await message.answer("\n".join(lines))


