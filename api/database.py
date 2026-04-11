from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    # L008: SQLAlchemy defaults to pool_size=5 + max_overflow=10 = 15 total
    # connections. That's not enough under concurrent load — the deep US
    # Chartmetric backfill bulk-ingests while the classification sweep,
    # composite sweep, DB Stats polling, user requests, and scheduler
    # queries all compete. Saturated the pool within 10 minutes of the
    # first backfill and returned 500 errors. Neon supports far more
    # connections than this — bump to 20 base + 40 overflow = 60 total.
    pool_size=20,
    max_overflow=40,
    # Recycle connections after 30 minutes to avoid stale ones that asyncpg
    # closes server-side (the "connection is closed" errors in the logs).
    pool_recycle=1800,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
