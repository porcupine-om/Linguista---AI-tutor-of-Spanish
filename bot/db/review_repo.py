"""Репозиторий для повторения ошибок (review_items)."""
from datetime import datetime, timedelta

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import ReviewItem
from bot.db.session import async_session_maker


async def add_review_item(
    telegram_id: int,
    item_id: str,
    item_type: str,
    content: str,
    answer: str,
    interval: int = 1,
) -> None:
    """Создаёт запись. next_review_at = now + interval дней (0 = сегодня)."""
    next_review_at = datetime.utcnow() + timedelta(days=max(interval, 0))
    async with async_session_maker() as session:
        item = ReviewItem(
            telegram_id=telegram_id,
            item_id=item_id,
            item_type=item_type,
            content=content,
            answer=answer,
            interval=interval,
            next_review_at=next_review_at,
        )
        session.add(item)
        await session.commit()


async def get_due_reviews(telegram_id: int, limit: int | None = None) -> list[ReviewItem]:
    """Возвращает ReviewItem, где next_review_at <= now. limit — макс. количество."""
    now = datetime.utcnow()
    async with async_session_maker() as session:
        q = (
            select(ReviewItem)
            .where(
                and_(
                    ReviewItem.telegram_id == telegram_id,
                    ReviewItem.next_review_at <= now,
                )
            )
            .order_by(ReviewItem.next_review_at.asc())
        )
        if limit is not None:
            q = q.limit(limit)
        result = await session.execute(q)
        return list(result.scalars().all())


async def remove_review_item(item_id: int) -> None:
    """Удаляет запись по id."""
    async with async_session_maker() as session:
        await session.execute(delete(ReviewItem).where(ReviewItem.id == item_id))
        await session.commit()


async def update_review_interval(item_id: int, new_interval: int) -> None:
    """Обновляет interval и next_review_at."""
    now = datetime.utcnow()
    next_review_at = now + timedelta(days=new_interval)
    async with async_session_maker() as session:
        result = await session.execute(select(ReviewItem).where(ReviewItem.id == item_id))
        item = result.scalar_one_or_none()
        if item:
            item.interval = new_interval
            item.next_review_at = next_review_at
            await session.commit()


async def get_review_item_by_id(item_id: int) -> ReviewItem | None:
    """Возвращает ReviewItem по id."""
    async with async_session_maker() as session:
        result = await session.execute(select(ReviewItem).where(ReviewItem.id == item_id))
        return result.scalar_one_or_none()
