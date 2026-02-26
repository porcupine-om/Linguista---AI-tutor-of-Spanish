from datetime import date, datetime

from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class ReviewItem(Base):
    """Элемент для повторения ошибок (spaced repetition lite)."""
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    item_id: Mapped[str] = mapped_column()
    item_type: Mapped[str] = mapped_column()  # "word" | "phrase" | "exercise"
    content: Mapped[str] = mapped_column()  # текст на испанском
    answer: Mapped[str] = mapped_column()  # правильный перевод
    interval: Mapped[int] = mapped_column(default=1)  # дни до следующего повторения
    next_review_at: Mapped[datetime] = mapped_column(index=True)


class Achievement(Base):
    """Достижение пользователя."""
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("telegram_id", "code", name="uq_achievement_user_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    code: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    level: Mapped[str | None] = mapped_column(nullable=True)
    last_level_test_at: Mapped[datetime | None] = mapped_column(nullable=True)
    level_test_count: Mapped[int] = mapped_column(default=0)
    zero_progress: Mapped[int] = mapped_column(default=0)
    a1_progress: Mapped[int] = mapped_column(default=0)
    a2_progress: Mapped[int] = mapped_column(default=0)
    b1_progress: Mapped[int] = mapped_column(default=0)
    streak: Mapped[int] = mapped_column(default=0)
    last_activity_date: Mapped[date | None] = mapped_column(nullable=True)
    xp: Mapped[int] = mapped_column(default=0)
    words_learned: Mapped[int] = mapped_column(default=0)
    voice_practice_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
    )
