"""
Shared pytest fixtures for SoundPulse tests.
"""

import os
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.database import Base, get_db
from api.dependencies import get_redis
from api.main import app
from api.models.artist import Artist
from api.models.track import Track

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://soundpulse:soundpulse_dev@localhost:5432/soundpulse",
)

ADMIN_API_KEY = "sp_admin_0000000000000000000000000000dead"

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session():
    """Yield a transactional async DB session that rolls back after each test."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Redis mock
# ---------------------------------------------------------------------------


def _fake_redis():
    """Return an AsyncMock that behaves enough like aioredis.Redis for tests."""
    mock = AsyncMock()
    mock.get.return_value = None  # cache miss by default
    mock.set.return_value = True
    mock.delete.return_value = True
    mock.scan_iter.return_value = AsyncMock(return_value=[])
    mock.scan_iter.__aiter__ = AsyncMock(return_value=iter([]))
    return mock


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Async httpx test client with DB and Redis overrides."""
    fake_redis = _fake_redis()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = lambda: fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_headers():
    """Headers dict containing a valid admin API key."""
    return {"X-API-Key": ADMIN_API_KEY}


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sample_artist(db_session: AsyncSession) -> Artist:
    """Insert and return a sample Artist row."""
    artist = Artist(
        id=uuid.uuid4(),
        name="Test Artist",
        spotify_id=f"sp_{uuid.uuid4().hex[:22]}",
        genres=["pop"],
    )
    db_session.add(artist)
    await db_session.flush()
    return artist


@pytest_asyncio.fixture
async def sample_track(db_session: AsyncSession, sample_artist: Artist) -> Track:
    """Insert and return a sample Track row linked to sample_artist."""
    track = Track(
        id=uuid.uuid4(),
        title="Test Track",
        artist_id=sample_artist.id,
        spotify_id=f"sp_{uuid.uuid4().hex[:22]}",
        isrc="USRC12345678",
        genres=["pop"],
    )
    db_session.add(track)
    await db_session.flush()
    return track
