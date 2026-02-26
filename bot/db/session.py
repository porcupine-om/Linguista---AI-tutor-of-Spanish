from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.db.base import Base

DATABASE_URL = "sqlite+aiosqlite:///bot.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)
async_session = async_session_maker


async def init_db() -> None:
    from sqlalchemy import text

    from bot.db import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for col, col_type in [
            ("content", "TEXT DEFAULT ''"),
            ("answer", "TEXT DEFAULT ''"),
            ("interval", "INTEGER DEFAULT 1"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE review_items ADD COLUMN {col} {col_type}"))
            except Exception:
                pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_level_test_at DATETIME"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN zero_progress INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN a1_progress INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN streak INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_activity_date DATE"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))
        except Exception:
            pass
        try:
            await conn.execute(
                text("UPDATE users SET created_at = datetime('now') WHERE created_at IS NULL")
            )
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN level_test_count INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN a2_progress INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN b1_progress INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN words_learned INTEGER DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN voice_practice_count INTEGER DEFAULT 0"))
        except Exception:
            pass