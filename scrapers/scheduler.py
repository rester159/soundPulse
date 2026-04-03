"""
Scraper scheduler using APScheduler.
Runs inside the FastAPI process, reads config from DB.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

logger = logging.getLogger(__name__)

# Will be set by init_scheduler
_scheduler: AsyncIOScheduler | None = None
_session_factory: async_sessionmaker | None = None


def _get_session_factory():
    """Return the session factory, creating one if needed."""
    global _session_factory
    if _session_factory is None:
        import os
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://soundpulse:soundpulse_dev@localhost:5432/soundpulse",
        )
        engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def _run_scraper_job(scraper_id: str):
    """Execute a single scraper run and update its config in DB."""
    from api.models.scraper_config import ScraperConfig

    factory = _get_session_factory()
    async with factory() as db:
        result = await db.execute(select(ScraperConfig).where(ScraperConfig.id == scraper_id))
        config = result.scalar_one_or_none()
        if not config or not config.enabled:
            return

        config.last_status = "running"
        config.last_run_at = datetime.now(timezone.utc)
        await db.commit()

    # Import and run the appropriate scraper
    stats = {}
    error_msg = None
    api_url = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
    admin_key = os.environ.get("API_ADMIN_KEY", "")
    scraper = None
    try:
        if scraper_id == "spotify":
            from scrapers.spotify import SpotifyScraper
            scraper = SpotifyScraper(
                credentials={
                    "client_id": os.environ.get("SPOTIFY_CLIENT_ID", ""),
                    "client_secret": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "chartmetric":
            from scrapers.chartmetric import ChartmetricScraper
            scraper = ChartmetricScraper(
                credentials={
                    "api_key": os.environ.get("CHARTMETRIC_API_KEY", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "shazam":
            from scrapers.shazam import ShazamScraper
            scraper = ShazamScraper(
                credentials={
                    "rapidapi_key": os.environ.get("SHAZAM_RAPIDAPI_KEY", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "apple_music":
            from scrapers.apple_music import AppleMusicScraper
            scraper = AppleMusicScraper(
                credentials={
                    "team_id": os.environ.get("APPLE_MUSIC_TEAM_ID", ""),
                    "key_id": os.environ.get("APPLE_MUSIC_KEY_ID", ""),
                    "private_key_path": os.environ.get("APPLE_MUSIC_PRIVATE_KEY_PATH", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "musicbrainz":
            from scrapers.musicbrainz import MusicBrainzEnricher
            scraper = MusicBrainzEnricher(
                credentials={},
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "radio":
            from scrapers.radio import RadioScraper
            scraper = RadioScraper(
                credentials={},
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "kworb":
            from scrapers.kworb import KworbScraper
            scraper = KworbScraper(
                credentials={},
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "chartmetric_artists":
            from scrapers.chartmetric_artists import ChartmetricArtistsScraper
            scraper = ChartmetricArtistsScraper(
                credentials={
                    "api_key": os.environ.get("CHARTMETRIC_API_KEY", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "spotify_audio":
            from scrapers.spotify_audio import SpotifyAudioScraper
            scraper = SpotifyAudioScraper(
                credentials={
                    "client_id": os.environ.get("SPOTIFY_CLIENT_ID", ""),
                    "client_secret": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        elif scraper_id == "genius_lyrics":
            from scrapers.genius_lyrics import GeniusLyricsScraper
            scraper = GeniusLyricsScraper(
                credentials={
                    "api_key": os.environ.get("GENIUS_API_KEY", ""),
                },
                api_base_url=api_url, admin_key=admin_key,
            )
        else:
            logger.warning("Unknown scraper: %s", scraper_id)
            return

        try:
            stats = await scraper.run()
        finally:
            await scraper.close()
    except Exception as e:
        error_msg = str(e)[:2000]
        logger.exception("Scraper %s failed", scraper_id)

    # Update status in DB
    async with _get_session_factory()() as db:
        result = await db.execute(select(ScraperConfig).where(ScraperConfig.id == scraper_id))
        config = result.scalar_one_or_none()
        if config:
            config.last_status = "error" if error_msg else "success"
            config.last_error = error_msg
            config.last_run_at = datetime.now(timezone.utc)
            config.last_record_count = stats.get("total", 0) if stats else None
            await db.commit()

    logger.info("Scraper %s finished: status=%s stats=%s", scraper_id, "error" if error_msg else "success", stats)


async def init_scheduler(database_url: str):
    """Initialize the scheduler and load jobs from DB."""
    global _scheduler, _session_factory

    engine = create_async_engine(database_url, echo=False)
    _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    _scheduler = AsyncIOScheduler()

    # Default scraper configs to seed if missing
    DEFAULT_CONFIGS = {
        "spotify": {"interval_hours": 6, "enabled": True},
        "chartmetric": {"interval_hours": 4, "enabled": True},
        "shazam": {"interval_hours": 4, "enabled": True},
        "apple_music": {"interval_hours": 6, "enabled": False},
        "musicbrainz": {"interval_hours": 12, "enabled": False},
        "radio": {"interval_hours": 24, "enabled": False},
        "kworb": {"interval_hours": 24, "enabled": False},
        "chartmetric_artists": {"interval_hours": 12, "enabled": True},
        "spotify_audio": {"interval_hours": 24, "enabled": True},
        "genius_lyrics": {"interval_hours": 24, "enabled": False},
        "spotify_audio": {"interval_hours": 24, "enabled": True},
    }

    # Seed default configs for scrapers that don't exist in DB yet
    async with _session_factory() as db:
        from api.models.scraper_config import ScraperConfig

        for scraper_id, defaults in DEFAULT_CONFIGS.items():
            result = await db.execute(
                select(ScraperConfig).where(ScraperConfig.id == scraper_id)
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                new_config = ScraperConfig(
                    id=scraper_id,
                    interval_hours=defaults["interval_hours"],
                    enabled=defaults["enabled"],
                )
                db.add(new_config)
                logger.info("Seeded default config for scraper '%s'", scraper_id)

        await db.commit()

    # Load configs from DB and schedule enabled scrapers
    async with _session_factory() as db:
        result = await db.execute(select(ScraperConfig).where(ScraperConfig.enabled == True))
        configs = result.scalars().all()

        for config in configs:
            _scheduler.add_job(
                _run_scraper_job,
                trigger=IntervalTrigger(hours=config.interval_hours),
                id=f"scraper_{config.id}",
                args=[config.id],
                replace_existing=True,
                name=f"{config.id} scraper",
            )
            logger.info("Scheduled scraper '%s' every %.1f hours", config.id, config.interval_hours)

    _scheduler.start()
    logger.info("Scraper scheduler started with %d jobs", len(_scheduler.get_jobs()))


def update_job(scraper_id: str, interval_hours: float, enabled: bool):
    """Update or remove a scheduled job. Called when admin changes config."""
    if _scheduler is None:
        return

    job_id = f"scraper_{scraper_id}"

    if not enabled:
        try:
            _scheduler.remove_job(job_id)
            logger.info("Removed job %s", job_id)
        except Exception:
            pass
        return

    _scheduler.add_job(
        _run_scraper_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id=job_id,
        args=[scraper_id],
        replace_existing=True,
        name=f"{scraper_id} scraper",
    )
    logger.info("Updated job %s: every %.1f hours", job_id, interval_hours)


async def trigger_now(scraper_id: str):
    """Trigger an immediate run of a scraper."""
    await _run_scraper_job(scraper_id)


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    if _scheduler:
        _scheduler.shutdown(wait=False)
