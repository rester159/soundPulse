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

    # Resolve the scraper via the registry (scrapers/registry.py).
    # Adding a new scraper is a one-line edit to SCRAPER_REGISTRY — the
    # scheduler stays agnostic.
    from scrapers.registry import load_scraper

    stats = {}
    error_msg = None
    api_url = os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")
    admin_key = os.environ.get("API_ADMIN_KEY", "")
    scraper = load_scraper(scraper_id, api_base_url=api_url, admin_key=admin_key)
    if scraper is None:
        logger.warning("Unknown scraper: %s", scraper_id)
        return

    try:
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

    # Default scraper configs to seed if missing.
    # AUD-004: previously had `spotify_audio` defined twice — Python silently
    # kept the second definition. Now defined exactly once.
    # P1-059: `chartmetric_deep_us` is the continuous daily comprehensive
    # pass — full ENDPOINT_MATRIX (~281 calls/day) hitting the bulk endpoint.
    # The existing `chartmetric` scraper above keeps its 4h cadence on the
    # small confirmed endpoint set for freshness; the deep one runs once a day.
    DEFAULT_CONFIGS = {
        "spotify": {"interval_hours": 6, "enabled": True},
        "chartmetric": {"interval_hours": 4, "enabled": True},
        # Phase 1 L4: 24h → 6h. 4x refresh rate. Each run is ~250 API calls
        # (expanded per-genre), 6h cadence = ~1,000 calls/day = 0.6% of the
        # 172,800/day Chartmetric quota. Captures intraday rank changes and
        # shortens the "data freshness" window on the live dashboard.
        # NOTE: seeded-only — existing DB rows must be PATCHed separately
        # (see commit instructions).
        "chartmetric_deep_us": {"interval_hours": 6, "enabled": True},
        # Phase 2a: long-tail playlist crawler. Weekly cadence. Enumerates
        # top US playlists on Spotify/AppleMusic/Deezer, then fetches each
        # playlist's tracks. ~15K calls per full run = ~2K/day amortized.
        "chartmetric_playlist_crawler": {"interval_hours": 168, "enabled": True},
        # Phase 2b: per-artist track catalog enrichment. Weekly cadence.
        # Iterates every artist in our DB with a chartmetric_id and calls
        # /api/artist/{id}/tracks to harvest deep catalog. ~2.5K calls per
        # full run = ~350/day amortized.
        "chartmetric_artist_tracks": {"interval_hours": 168, "enabled": True},
        # Phase 3: per-city US Apple Music top tracks. Daily cadence.
        # Top 20 US cities × 7 genres = 140 calls per run. Captures
        # regionally-popular tracks the national charts miss.
        "chartmetric_us_cities": {"interval_hours": 24, "enabled": True},
        # Phase 4: per-artist platform stats enrichment. Weekly cadence.
        # ~2.5K artists × 6 platforms = ~15K calls per full run = ~2.1K/day
        # amortized. Merges latest follower/listener/stream counts into
        # artists.metadata_json.chartmetric_stats for ML feature depth.
        "chartmetric_artist_stats": {"interval_hours": 168, "enabled": True},
        "shazam": {"interval_hours": 4, "enabled": True},
        "apple_music": {"interval_hours": 6, "enabled": False},
        "musicbrainz": {"interval_hours": 12, "enabled": False},
        "radio": {"interval_hours": 24, "enabled": False},
        "kworb": {"interval_hours": 24, "enabled": False},
        "chartmetric_artists": {"interval_hours": 12, "enabled": True},
        "spotify_audio": {"interval_hours": 24, "enabled": True},
        "genius_lyrics": {"interval_hours": 24, "enabled": False},
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

    # Deferred sweeps — run every 15 minutes regardless of scraper config.
    # These process the queues created by the bulk ingest endpoint
    # (`POST /api/v1/trending/bulk`):
    #   - classification sweep: clears `metadata_json.needs_classification`
    #   - composite sweep: normalizes `normalized_score=0` snapshots and
    #     recomputes composite scores
    _scheduler.add_job(
        _run_classification_sweep_job,
        trigger=IntervalTrigger(minutes=15),
        id="sweep_classification",
        replace_existing=True,
        name="classification sweep (deferred)",
    )
    _scheduler.add_job(
        _run_composite_sweep_job,
        trigger=IntervalTrigger(minutes=15),
        id="sweep_composite",
        replace_existing=True,
        name="composite sweep (deferred)",
    )

    # Stale-job reaper — clears scrapers whose last_status got stuck at
    # "running" because the process was killed mid-run (deploy, OOM, crash).
    # Without this, a scraper can sit in "running" forever until the next
    # scheduled interval fires, masking failures on the admin dashboard.
    # Runs once on startup and every 30 minutes thereafter.
    await _reap_stale_running_scrapers()
    _scheduler.add_job(
        _reap_stale_running_scrapers,
        trigger=IntervalTrigger(minutes=30),
        id="sweep_stale_scrapers",
        replace_existing=True,
        name="stale-scraper reaper",
    )

    _scheduler.start()
    logger.info("Scraper scheduler started with %d jobs", len(_scheduler.get_jobs()))


# ---------------------------------------------------------------------------
# Deferred sweep job runners (called by APScheduler)
# ---------------------------------------------------------------------------

async def _run_classification_sweep_job():
    """APScheduler entry point for the classification sweep."""
    from api.services.classification_sweep import sweep_unclassified_entities

    factory = _get_session_factory()
    try:
        async with factory() as db:
            stats = await sweep_unclassified_entities(db, batch_size=500)
        logger.info("[scheduler] classification sweep: %s", stats)
    except Exception:
        logger.exception("[scheduler] classification sweep failed")


async def _run_composite_sweep_job():
    """APScheduler entry point for the composite recalc sweep."""
    from api.services.composite_sweep import sweep_zero_normalized_snapshots

    factory = _get_session_factory()
    try:
        async with factory() as db:
            stats = await sweep_zero_normalized_snapshots(db, batch_size=1000)
        logger.info("[scheduler] composite sweep: %s", stats)
    except Exception:
        logger.exception("[scheduler] composite sweep failed")


async def _reap_stale_running_scrapers():
    """
    Mark scrapers whose last_status='running' is older than 2x their
    configured interval (or 2 hours, whichever is larger) as "error: stale".

    Why: scheduler.py's `_run_scraper_job` updates last_status inside a
    post-run transaction. If the container dies between `scraper.run()`
    finishing and that transaction committing (deploy restart, OOM), the
    row stays at "running" forever. The admin dashboard then shows a
    phantom in-flight job that masks real failures and blocks the next
    scheduled run from looking normal.

    This reaper runs on startup (once) and every 30 minutes thereafter.
    """
    from api.models.scraper_config import ScraperConfig

    factory = _get_session_factory()
    try:
        async with factory() as db:
            result = await db.execute(
                select(ScraperConfig).where(ScraperConfig.last_status == "running")
            )
            stuck = result.scalars().all()
            now = datetime.now(timezone.utc)
            reaped = 0
            for cfg in stuck:
                if cfg.last_run_at is None:
                    continue
                # Absolute 90-minute grace: no legitimate scraper takes
                # longer than this (deep_us tops out around ~15 min for
                # ~280 endpoints at 2 req/s). Previous `2x interval_hours`
                # formula was effectively infinite for 168h weekly jobs.
                grace_hours = 1.5
                last_run = cfg.last_run_at
                # Normalize naive timestamps from older rows
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                age_hours = (now - last_run).total_seconds() / 3600.0
                if age_hours >= grace_hours:
                    cfg.last_status = "error"
                    cfg.last_error = (
                        f"stale: last_status stuck at 'running' for "
                        f"{age_hours:.1f}h (grace={grace_hours:.1f}h) — "
                        f"likely killed mid-run by deploy/crash"
                    )
                    reaped += 1
            if reaped:
                await db.commit()
                logger.warning("[scheduler] reaped %d stale 'running' scraper row(s)", reaped)
    except Exception:
        logger.exception("[scheduler] stale-scraper reaper failed")


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
