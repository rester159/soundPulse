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

    # Update status in DB. Wrapped in try/except so a commit failure
    # surfaces in the logs instead of silently leaving last_status='running'.
    # Previously a Neon connection blip here would leave rows stuck and
    # only the reaper (1.5h grace) could clear them.
    try:
        async with _get_session_factory()() as db:
            result = await db.execute(select(ScraperConfig).where(ScraperConfig.id == scraper_id))
            config = result.scalar_one_or_none()
            if config:
                config.last_status = "error" if error_msg else "success"
                config.last_error = error_msg
                config.last_run_at = datetime.now(timezone.utc)
                config.last_record_count = stats.get("total", 0) if stats else None
                await db.commit()
    except Exception:
        logger.exception(
            "[scheduler] CRITICAL: failed to persist status for %s — "
            "row will stay at 'running' until the reaper catches it",
            scraper_id,
        )

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
    # Chartmetric quota budget: 172,800 calls/day. Previous cadences used
    # ~4% of it. New cadences (below) total ~10% — still well inside the
    # envelope while delivering 2-3.5x fresher data on every scraper.
    # NOTE: DEFAULT_CONFIGS only seeds new rows. Live-DB intervals must be
    # updated with a direct UPDATE (see commit notes for the SQL).
    DEFAULT_CONFIGS = {
        "spotify": {"interval_hours": 6, "enabled": True},
        "chartmetric": {"interval_hours": 4, "enabled": True},
        # Comprehensive US pass — ~281 API calls fanning out across the
        # ENDPOINT_MATRIX. 3h cadence → ~2.2k/day. Captures intraday
        # rank changes on every confirmed platform × chart × genre combo.
        "chartmetric_deep_us": {"interval_hours": 3, "enabled": True},
        # Long-tail playlist crawler. ~15k calls per full run, 72h cadence
        # → ~5k/day amortized.
        "chartmetric_playlist_crawler": {"interval_hours": 72, "enabled": True},
        # Per-artist track catalog enrichment. Iterates every artist with
        # a chartmetric_id and calls /api/artist/{id}/tracks. ~2.5k calls
        # per full run × twice-weekly (48h) → ~1.25k/day.
        "chartmetric_artist_tracks": {"interval_hours": 48, "enabled": True},
        # Per-city US Apple Music top tracks. Top 20 cities × 7 genres =
        # 140 calls per run × 12h cadence → ~280/day. Captures regionally-
        # popular tracks the national charts miss.
        "chartmetric_us_cities": {"interval_hours": 12, "enabled": True},
        # Per-artist platform stats enrichment. ~2.5k artists × 6 platforms
        # = ~15k calls per full run × 48h cadence → ~7.5k/day. Merges
        # latest follower/listener/stream counts into artists.metadata_json.
        "chartmetric_artist_stats": {"interval_hours": 48, "enabled": True},
        # Shazam: disabled. Public API endpoints (shazam.com/services/*,
        # amp-api.shazam.com, cdn.shazam.com) are all dead (404/204/DNS
        # failure as of 2026-04-12). RapidAPI shazam-core free tier was
        # too rate-limited before that. Shazam data already flows via
        # chartmetric_deep_us pipeline (8,952 rows from /api/charts/shazam).
        "shazam": {"interval_hours": 24, "enabled": False},
        # Apple Music (developer API) needs team_id + key_id + private key
        # path — complex setup, leave disabled until creds are configured.
        "apple_music": {"interval_hours": 6, "enabled": False},
        # MusicBrainz: free public API, no credentials. Enriches tracks
        # with ISRCs + musicbrainz tags that feed platform_labels.
        "musicbrainz": {"interval_hours": 12, "enabled": True},
        # Radio airplay: scrapes public charts, no credentials. Contributes
        # airplay signal to the composite score.
        "radio": {"interval_hours": 24, "enabled": True},
        # Kworb: scrapes free public charts from kworb.net, no credentials.
        # Provides redundant cross-platform rank signals for free.
        "kworb": {"interval_hours": 24, "enabled": True},
        "chartmetric_artists": {"interval_hours": 12, "enabled": True},
        # spotify_audio: kept for history, permanently disabled. Spotify's
        # /v1/audio-features endpoint returns 403 for any app created
        # after 2024-11-27 (ours qualifies). Replaced by
        # chartmetric_audio_features which pulls the same Spotify
        # audio feature values from Chartmetric's paid API.
        "spotify_audio": {"interval_hours": 24, "enabled": False},
        # chartmetric_audio_features: pulls tempo + duration_ms from
        # /api/track/{cm_track_id} on Chartmetric. Full audio features
        # are NOT exposed to API subscribers (the sub-endpoints return
        # 401 "internal API endpoint"), so we accept 2/13 features.
        # Runs every 6h, processes up to MAX_TRACKS_PER_RUN=1000 per
        # pass at 2.5s per call (0.4 req/s), so each run takes ~42 min
        # and the full ~5.2k-track backlog drains in ~32 hours.
        "chartmetric_audio_features": {"interval_hours": 6, "enabled": True},
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

    # Breakout detection sweep — Layer 1 of the Breakout Analysis Engine.
    # Runs every 6 hours. Scans genres for tracks that outperform their
    # genre peers (2× median composite/velocity) and writes breakout_events.
    # Also resolves old events after 30 days with outcome labels.
    _scheduler.add_job(
        _run_breakout_detection_job,
        trigger=IntervalTrigger(hours=6),
        id="sweep_breakout_detection",
        replace_existing=True,
        name="breakout detection sweep",
    )

    # Feature delta analysis — Layer 2. Runs daily after breakout detection.
    # Compares each genre's breakout audio features vs the genre baseline
    # using Welch's t-test, caching the deltas and significance scores.
    _scheduler.add_job(
        _run_feature_delta_analysis_job,
        trigger=IntervalTrigger(hours=24),
        id="sweep_feature_delta_analysis",
        replace_existing=True,
        name="feature delta analysis",
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


async def _run_breakout_detection_job():
    """APScheduler entry point for the breakout detection sweep."""
    from api.services.breakout_detection import sweep_breakout_detection

    factory = _get_session_factory()
    try:
        async with factory() as db:
            stats = await sweep_breakout_detection(db)
        logger.info("[scheduler] breakout detection: %s", stats)
    except Exception:
        logger.exception("[scheduler] breakout detection sweep failed")


async def _run_feature_delta_analysis_job():
    """APScheduler entry point for the feature delta analysis sweep."""
    from api.services.feature_delta_analysis import compute_all_feature_deltas

    factory = _get_session_factory()
    try:
        async with factory() as db:
            stats = await compute_all_feature_deltas(db)
        logger.info("[scheduler] feature delta analysis: %s", stats)
    except Exception:
        logger.exception("[scheduler] feature delta analysis failed")


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
