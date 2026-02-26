from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Achievement
from bot.db.session import async_session_maker


async def add_achievement(telegram_id: int, code: str) -> None:
    async with async_session_maker() as session:
        achievement = Achievement(telegram_id=telegram_id, code=code)
        session.add(achievement)
        await session.commit()


async def has_achievement(telegram_id: int, code: str) -> bool:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Achievement).where(
                Achievement.telegram_id == telegram_id,
                Achievement.code == code,
            )
        )
        return result.scalar_one_or_none() is not None


async def get_user_achievements(telegram_id: int) -> list[str]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Achievement.code).where(Achievement.telegram_id == telegram_id)
        )
        return [row[0] for row in result.fetchall()]
