from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from bot.db.models import User


def main_menu_keyboard(user: User | None = None, *, show_continue: bool | None = None, show_review: bool | None = None) -> ReplyKeyboardMarkup:
    rows = []
    if show_continue is True or (show_continue is None and user and _has_unfinished_progress(user)):
        rows.append([KeyboardButton(text="Продолжить обучение")])
    else:
        rows.append([KeyboardButton(text="📚 Начать обучение")])
    if show_review is True or (show_review is None and user and _has_lesson_progress(user)):
        rows.append([KeyboardButton(text="📚 Повторить ошибки")])
    rows.append([KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _has_unfinished_progress(user: User) -> bool:
    from bot.db.user_repo import has_unfinished_progress
    return has_unfinished_progress(user)


def _has_lesson_progress(user: User) -> bool:
    """Есть ли пройденные уроки (показывать кнопку «Повторить ошибки»)."""
    zero = getattr(user, "zero_progress", 0) or 0
    a1 = getattr(user, "a1_progress", 0) or 0
    a2 = getattr(user, "a2_progress", 0) or 0
    b1 = getattr(user, "b1_progress", 0) or 0
    return zero > 0 or a1 > 0 or a2 > 0 or b1 > 0
