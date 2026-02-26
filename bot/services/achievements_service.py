from bot.config.achievements_config import ACHIEVEMENTS
from bot.db.achievement_repo import add_achievement, has_achievement


async def check_achievements(user) -> list[dict]:
    """
    Проверяет достижения пользователя. Возвращает список новых достижений
    (каждое — dict с ключами code, title, desc).
    """
    if not user:
        return []

    total_lessons = (
        (getattr(user, "zero_progress", 0) or 0)
        + (getattr(user, "a1_progress", 0) or 0)
        + (getattr(user, "a2_progress", 0) or 0)
        + (getattr(user, "b1_progress", 0) or 0)
    )
    streak = getattr(user, "streak", 0) or 0
    xp = getattr(user, "xp", 0) or 0
    words_learned = getattr(user, "words_learned", 0) or 0
    voice_practice_count = getattr(user, "voice_practice_count", 0) or 0

    checks = [
        (total_lessons >= 1, "first_lesson"),
        (total_lessons >= 5, "five_lessons"),
        (streak >= 3, "streak3"),
        (streak >= 7, "streak7"),
        (words_learned >= 20, "words20"),
        (voice_practice_count >= 1, "first_voice"),
        (xp >= 50, "xp50"),
        (xp >= 200, "xp200"),
    ]

    new_achievements: list[dict] = []
    telegram_id = user.telegram_id

    for condition, code in checks:
        if not condition:
            continue
        if await has_achievement(telegram_id, code):
            continue
        cfg = ACHIEVEMENTS.get(code, {})
        await add_achievement(telegram_id, code)
        new_achievements.append({
            "code": code,
            "title": cfg.get("title", code),
            "desc": cfg.get("desc", ""),
        })

    return new_achievements
