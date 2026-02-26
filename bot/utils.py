"""Утилиты для форматирования."""
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram.types import User


def get_display_name(telegram_user: "User") -> str:
    """
    Имя для отображения: first_name + last_name (если есть).
    Никогда не использует username (@nick) — только имя человека.
    """
    first = (telegram_user.first_name or "").strip()
    last = (telegram_user.last_name or "").strip()
    if first and last:
        return f"{first} {last}"
    if first:
        return first
    return "Ученик"


def progress_bar(current: int, total: int, width: int = 10) -> str:
    """Возвращает строку вида [████░░░░░░] 40%."""
    if total <= 0:
        filled = 0
        pct = 0
    else:
        pct = min(100, int(100 * current / total))
        filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct}%"
from datetime import date, datetime
from pathlib import Path

_TRANSCRIPTION_CACHE: dict[str, str] | None = None


def _slug_for_lookup(s: str) -> str:
    """card_id из spanish: пробелы → подчёркивание, без спецсимволов."""
    import re
    s = re.sub(r"[/\s]+", "_", s.strip())
    return re.sub(r"[^\w\-]", "", s) or ""


def _iter_cards_with_transcription(obj) -> "list[dict]":
    """Рекурсивно обходит cards_seed (могут быть вложенные массивы) и возвращает карточки с transcription."""
    result: list = []
    if isinstance(obj, dict):
        if obj.get("transcription"):
            result.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            result.extend(_iter_cards_with_transcription(item))
    return result


def _load_transcription_lookup() -> dict[str, str]:
    """Загружает cards_seed.json и cards_zero.json, строит lookup id/spanish -> transcription."""
    global _TRANSCRIPTION_CACHE
    if _TRANSCRIPTION_CACHE is not None:
        return _TRANSCRIPTION_CACHE
    lookup: dict[str, str] = {}
    data_dir = Path(__file__).parent.parent / "data"
    for filename in ("cards_seed.json", "cards_zero.json"):
        path = data_dir / filename
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for c in _iter_cards_with_transcription(data):
                t = c["transcription"]
                if c.get("id") is not None:
                    lookup[str(c["id"])] = t
                spanish = c.get("spanish")
                if spanish:
                    lookup[spanish.lower().strip()] = t
                    lookup[_slug_for_lookup(spanish)] = t
        except Exception:
            pass
    # Дополнение: A1-слова, отсутствующие в cards_seed
    for supplement_name in ("a1_transcriptions.json", "a2_transcriptions.json"):
        supplement = data_dir / supplement_name
        if supplement.exists():
            try:
                with open(supplement, encoding="utf-8") as f:
                    extra = json.load(f)
                for spanish, t in extra.items():
                    if spanish and t:
                        lookup[spanish.lower().strip()] = t
                        lookup[_slug_for_lookup(spanish)] = t
            except Exception:
                pass
    _TRANSCRIPTION_CACHE = lookup
    return lookup


def get_transcription_for_card(card: dict) -> str | None:
    """Возвращает транскрипцию для карточки: из самой карточки или из cards_seed по card_id/spanish."""
    t = card.get("transcription")
    if t:
        return t
    lookup = _load_transcription_lookup()
    card_id = card.get("card_id") or card.get("id")
    if card_id:
        t = lookup.get(str(card_id))
        if t:
            return t
    spanish = card.get("spanish")
    if spanish:
        return lookup.get(spanish.lower().strip()) or lookup.get(spanish)
    return None

RUSSIAN_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def get_test_availability_text(last_test_at: datetime | None) -> str:
    """
    Возвращает текст о доступности повторного теста (ограничение 30 дней).
    """
    if last_test_at is None:
        return "доступен сейчас"

    now = datetime.utcnow()
    try:
        days_passed = (now - last_test_at).days
    except (TypeError, AttributeError):
        return "доступен сейчас"

    remaining = 30 - days_passed

    if remaining <= 0:
        return "доступен сейчас"
    if remaining == 1:
        return "через 1 день"
    return f"через {remaining} дней"


def format_date(dt: date | datetime | None) -> str:
    """Форматирует дату: «12 февраля 2026» (русские месяцы, без времени)."""
    if dt is None:
        return "—"
    if hasattr(dt, "date"):
        dt = dt.date()
    return f"{dt.day} {RUSSIAN_MONTHS[dt.month - 1]} {dt.year}"
