"""Chart sweep planner — matrix-driven, entity-count-independent.

This is the saturation floor. Every other planner emits per-entity
jobs whose volume scales with catalog size. `chart_sweep` enumerates
a fixed list of chart endpoints (spotify regional/viral, apple top,
shazam, amazon, soundcloud, tiktok, deezer, ...) and re-emits the
stalest ones every cadence. Chartmetric re-charts these on its own
schedule, so they are *always* generating new data regardless of
how many tracks we have in our DB.

Without this planner the queue can run dry on small catalogs and
the fetcher idles below 90% utilization. With it, there's always a
backlog of chart endpoints to refresh — the fetcher sustains its
1.8 req/s drain rate.

Every row in `CHART_ENDPOINTS` maps to:
  1. A chartmetric_endpoint_config row (endpoint_key prefix
     `chart_sweep_`, seeded in endpoints.py)
  2. A handler dispatch key (always `chart_sweep` — the handler is
     shape-agnostic)

Adding a new chart surface is three edits:
  1. Append to CHART_ENDPOINTS here
  2. Append to endpoints.py DEFAULT_ENDPOINT_CONFIGS
  3. Ship — no handler change needed.

Generality check: the matrix *is* the source of truth for "which
chart surfaces are we sweeping." Every entry is a tuple of
(endpoint_key, path, params, chart_type). Nothing in this file
references a specific country, genre, or entity — those are all
just elements of the matrix. Adding Brazilian Apple Music Top Songs
is one line here plus one endpoint_config row.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Any

from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.chartmetric_queue import ChartmetricEndpointConfig
from chartmetric_ingest import queue as cmq_queue
from chartmetric_ingest.planners import register
from chartmetric_ingest.priority import freshness_score, priority_from_scores

logger = logging.getLogger(__name__)


API_BASE = "https://api.chartmetric.com"
HANDLER_NAME = "chart_sweep"
PRODUCER_NAME = "planner_chart_sweep"
PLANNER_INTERVAL_SECONDS = 120.0  # 2 minutes
BATCH_SIZE = 100
JOB_EXPIRES_IN_HOURS = 2.0


# Each entry specifies the (endpoint_key, path, params) needed for one
# chart sweep call. Param shapes were cross-referenced against
# `scrapers/chartmetric_deep_us.py` ENDPOINT_MATRIX, which was probed
# against the live Chartmetric API on 2026-04-11 and has been running
# in production without 400s. Key param rules we rediscovered the
# hard way:
#   - Most chart endpoints want `country_code` (lowercase value).
#     Amazon is the one exception — it wants `code2` (uppercase value).
#   - Spotify /artists is a GLOBAL chart. No country param at all.
#   - Shazam /charts/shazam wants country_code=us (the "global" chart
#     also needs a specific country).
#   - TikTok charts are GLOBAL — no country param.
#   - Deezer's path ends with a trailing slash: `/api/charts/deezer/`.
#
# Endpoints that REQUIRE a genre fan-out (Apple Music tracks, iTunes,
# SoundCloud, Beatport, Amazon) are OMITTED from chart_sweep for now
# — they'd require a per-genre loop that bloats the matrix, and the
# primary saturation sources are track_history + artist_stats anyway.
# chart_sweep is the "always has work" floor, not the volume driver.
CHART_ENDPOINTS: list[dict[str, Any]] = [
    # ---------- Spotify tracks: regional (daily) across top markets ----------
    {"endpoint_key": "chart_sweep_spotify_regional_us",
     "path": "/api/charts/spotify",
     "params": {"type": "regional", "interval": "daily", "country_code": "us"},
     "platform": "spotify", "chart_type": "regional", "country": "us"},
    {"endpoint_key": "chart_sweep_spotify_regional_gb",
     "path": "/api/charts/spotify",
     "params": {"type": "regional", "interval": "daily", "country_code": "gb"},
     "platform": "spotify", "chart_type": "regional", "country": "gb"},
    {"endpoint_key": "chart_sweep_spotify_regional_de",
     "path": "/api/charts/spotify",
     "params": {"type": "regional", "interval": "daily", "country_code": "de"},
     "platform": "spotify", "chart_type": "regional", "country": "de"},
    {"endpoint_key": "chart_sweep_spotify_regional_fr",
     "path": "/api/charts/spotify",
     "params": {"type": "regional", "interval": "daily", "country_code": "fr"},
     "platform": "spotify", "chart_type": "regional", "country": "fr"},
    {"endpoint_key": "chart_sweep_spotify_regional_br",
     "path": "/api/charts/spotify",
     "params": {"type": "regional", "interval": "daily", "country_code": "br"},
     "platform": "spotify", "chart_type": "regional", "country": "br"},
    {"endpoint_key": "chart_sweep_spotify_regional_mx",
     "path": "/api/charts/spotify",
     "params": {"type": "regional", "interval": "daily", "country_code": "mx"},
     "platform": "spotify", "chart_type": "regional", "country": "mx"},

    # ---------- Spotify tracks: viral (daily) across top markets ----------
    {"endpoint_key": "chart_sweep_spotify_viral_us",
     "path": "/api/charts/spotify",
     "params": {"type": "viral", "interval": "daily", "country_code": "us"},
     "platform": "spotify", "chart_type": "viral", "country": "us"},
    {"endpoint_key": "chart_sweep_spotify_viral_gb",
     "path": "/api/charts/spotify",
     "params": {"type": "viral", "interval": "daily", "country_code": "gb"},
     "platform": "spotify", "chart_type": "viral", "country": "gb"},
    {"endpoint_key": "chart_sweep_spotify_viral_de",
     "path": "/api/charts/spotify",
     "params": {"type": "viral", "interval": "daily", "country_code": "de"},
     "platform": "spotify", "chart_type": "viral", "country": "de"},
    {"endpoint_key": "chart_sweep_spotify_viral_br",
     "path": "/api/charts/spotify",
     "params": {"type": "viral", "interval": "daily", "country_code": "br"},
     "platform": "spotify", "chart_type": "viral", "country": "br"},

    # ---------- Spotify /artists (GLOBAL, no country param) ----------
    # 5 type variants: monthly_listeners / popularity / followers /
    # playlist_count / playlist_reach. Interval is weekly.
    {"endpoint_key": "chart_sweep_spotify_artists_monthly_listeners",
     "path": "/api/charts/spotify/artists",
     "params": {"type": "monthly_listeners", "interval": "weekly"},
     "platform": "spotify", "chart_type": "artists_monthly_listeners", "country": None,
     "entity_type": "artist"},
    {"endpoint_key": "chart_sweep_spotify_artists_popularity",
     "path": "/api/charts/spotify/artists",
     "params": {"type": "popularity", "interval": "weekly"},
     "platform": "spotify", "chart_type": "artists_popularity", "country": None,
     "entity_type": "artist"},
    {"endpoint_key": "chart_sweep_spotify_artists_followers",
     "path": "/api/charts/spotify/artists",
     "params": {"type": "followers", "interval": "weekly"},
     "platform": "spotify", "chart_type": "artists_followers", "country": None,
     "entity_type": "artist"},
    {"endpoint_key": "chart_sweep_spotify_artists_playlist_reach",
     "path": "/api/charts/spotify/artists",
     "params": {"type": "playlist_reach", "interval": "weekly"},
     "platform": "spotify", "chart_type": "artists_playlist_reach", "country": None,
     "entity_type": "artist"},

    # ---------- Shazam (country_code required) ----------
    {"endpoint_key": "chart_sweep_shazam_us",
     "path": "/api/charts/shazam",
     "params": {"country_code": "us"},
     "platform": "shazam", "chart_type": "top", "country": "us"},

    # ---------- TikTok (GLOBAL, no country, no interval) ----------
    # The `interval=weekly` param works with an explicit `date=...`,
    # but conflicts with `latest=true` which we merge at enqueue time
    # ('interval' is not allowed when latest=true). Drop interval and
    # let latest=true pick the current week on its own.
    {"endpoint_key": "chart_sweep_tiktok_tracks",
     "path": "/api/charts/tiktok/tracks",
     "params": {},
     "platform": "tiktok", "chart_type": "tracks_weekly", "country": None},
    {"endpoint_key": "chart_sweep_tiktok_videos",
     "path": "/api/charts/tiktok/videos",
     "params": {},
     "platform": "tiktok", "chart_type": "videos_weekly", "country": None},

    # ---------- Deezer (trailing slash in path, country_code required) ----------
    {"endpoint_key": "chart_sweep_deezer_us",
     "path": "/api/charts/deezer/",
     "params": {"country_code": "us"},
     "platform": "deezer", "chart_type": "top", "country": "us"},

    # ---------- Apple Music videos (global, no genre) ----------
    {"endpoint_key": "chart_sweep_apple_videos",
     "path": "/api/charts/applemusic/videos",
     "params": {},
     "platform": "apple_music", "chart_type": "videos", "country": None},
]


@register("chart_sweep", interval_seconds=PLANNER_INTERVAL_SECONDS)
async def plan_chart_sweep(db: AsyncSession) -> int:
    """Emit fetch jobs for the stalest chart endpoints.

    Unlike entity-based planners, chart_sweep has a fixed matrix of
    endpoints — staleness is tracked in chartmetric_entity_fetch_log
    via sentinel UUIDs derived from the endpoint_key, so the
    freshness query returns {endpoint_key -> last_fetched_at} for
    every known sweep endpoint.
    """
    enabled = await _enabled_configs(db)
    if not enabled:
        return 0

    fetch_log = await _fetch_log_by_endpoint(db, [c.endpoint_key for c in enabled])

    candidates: list[tuple[dict[str, Any], ChartmetricEndpointConfig, Any]] = []
    for cfg in enabled:
        spec = next((s for s in CHART_ENDPOINTS if s["endpoint_key"] == cfg.endpoint_key), None)
        if spec is None:
            continue
        candidates.append((spec, cfg, fetch_log.get(cfg.endpoint_key)))

    # Sort stalest first; freshness_score == 0 means never-fetched or
    # past 2*target_interval.
    def sort_key(item):
        spec, cfg, last_fetched = item
        f = freshness_score(last_fetched, cfg.target_interval_hours)
        return (f, spec["endpoint_key"])

    candidates.sort(key=sort_key)

    enqueued = 0
    for spec, cfg, last_fetched in candidates[:BATCH_SIZE]:
        url = f"{API_BASE}{spec['path']}"
        # Chartmetric's chart endpoints require a `date` param or an
        # explicit `latest=true` to return the most recent chart.
        # Without either they respond 400 "No date was given". We want
        # the newest chart every poll, so latest=true is the simplest
        # shape — merged with the per-endpoint static params.
        params = {**spec["params"], "latest": "true"}
        freshness = freshness_score(last_fetched, cfg.target_interval_hours)
        priority = priority_from_scores(
            freshness=freshness,
            importance=75.0,  # chart endpoints are higher-value than long-tail entity stats
            endpoint_weight=cfg.priority_weight,
        )
        job_id = await cmq_queue.enqueue(
            db,
            url=url,
            params=params,
            producer=PRODUCER_NAME,
            handler=HANDLER_NAME,
            priority=priority,
            handler_context={
                "endpoint_key": spec["endpoint_key"],
                "platform": spec["platform"],
                "chart_type": spec["chart_type"],
                "country": spec.get("country"),
                "entity_type": "track",
            },
            expires_in_hours=JOB_EXPIRES_IN_HOURS,
        )
        if job_id is not None:
            enqueued += 1
    await db.commit()
    if enqueued:
        logger.info("[cm-planner-chart-sweep] enqueued %d chart jobs", enqueued)
    return enqueued


async def _enabled_configs(db: AsyncSession) -> list[ChartmetricEndpointConfig]:
    keys = [s["endpoint_key"] for s in CHART_ENDPOINTS]
    result = await db.execute(
        select(ChartmetricEndpointConfig).where(
            ChartmetricEndpointConfig.endpoint_key.in_(keys),
            ChartmetricEndpointConfig.enabled.is_(True),
        )
    )
    return list(result.scalars())


async def _fetch_log_by_endpoint(
    db: AsyncSession, endpoint_keys: list[str]
) -> dict[str, Any]:
    """Return {endpoint_key -> last_fetched_at} for the given chart sweep keys.

    Uses the sentinel UUID scheme the handler writes with.
    """
    if not endpoint_keys:
        return {}
    sentinels = {
        key: _uuid.uuid5(_uuid.NAMESPACE_URL, f"chart_endpoint:{key}")
        for key in endpoint_keys
    }
    placeholders = ", ".join([f":id{i}" for i in range(len(endpoint_keys))])
    sql = sa_text(f"""
        SELECT endpoint_key, last_fetched_at
        FROM chartmetric_entity_fetch_log
        WHERE entity_type = 'chart_endpoint'
          AND entity_id IN ({placeholders})
    """)
    params = {f"id{i}": str(u) for i, u in enumerate(sentinels.values())}
    result = await db.execute(sql, params)
    return {row.endpoint_key: row.last_fetched_at for row in result.fetchall()}
