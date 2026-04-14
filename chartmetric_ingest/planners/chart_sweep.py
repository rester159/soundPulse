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


# (endpoint_key, path, params, chart_type, country, platform)
# The endpoint_key must match a row in chartmetric_endpoint_config.
CHART_ENDPOINTS: list[dict[str, Any]] = [
    # Spotify — regional + viral across top markets
    {
        "endpoint_key": "chart_sweep_spotify_regional_us",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "code2": "US", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "regional",
        "country": "us",
    },
    {
        "endpoint_key": "chart_sweep_spotify_regional_gb",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "code2": "GB", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "regional",
        "country": "gb",
    },
    {
        "endpoint_key": "chart_sweep_spotify_regional_de",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "code2": "DE", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "regional",
        "country": "de",
    },
    {
        "endpoint_key": "chart_sweep_spotify_regional_fr",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "code2": "FR", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "regional",
        "country": "fr",
    },
    {
        "endpoint_key": "chart_sweep_spotify_regional_br",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "code2": "BR", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "regional",
        "country": "br",
    },
    {
        "endpoint_key": "chart_sweep_spotify_regional_mx",
        "path": "/api/charts/spotify",
        "params": {"type": "regional", "code2": "MX", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "regional",
        "country": "mx",
    },
    {
        "endpoint_key": "chart_sweep_spotify_viral_us",
        "path": "/api/charts/spotify",
        "params": {"type": "viral", "code2": "US", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "viral",
        "country": "us",
    },
    {
        "endpoint_key": "chart_sweep_spotify_viral_gb",
        "path": "/api/charts/spotify",
        "params": {"type": "viral", "code2": "GB", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "viral",
        "country": "gb",
    },
    {
        "endpoint_key": "chart_sweep_spotify_viral_de",
        "path": "/api/charts/spotify",
        "params": {"type": "viral", "code2": "DE", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "viral",
        "country": "de",
    },
    {
        "endpoint_key": "chart_sweep_spotify_viral_br",
        "path": "/api/charts/spotify",
        "params": {"type": "viral", "code2": "BR", "interval": "daily"},
        "platform": "spotify",
        "chart_type": "viral",
        "country": "br",
    },
    # Shazam top — single global plus US
    {
        "endpoint_key": "chart_sweep_shazam_us",
        "path": "/api/charts/shazam",
        "params": {"type": "top", "country_iso_code": "US"},
        "platform": "shazam",
        "chart_type": "top",
        "country": "us",
    },
    {
        "endpoint_key": "chart_sweep_shazam_world",
        "path": "/api/charts/shazam",
        "params": {"type": "top", "country_iso_code": "WORLD"},
        "platform": "shazam",
        "chart_type": "top",
        "country": "world",
    },
    # Apple Music top songs by region
    {
        "endpoint_key": "chart_sweep_apple_top_us",
        "path": "/api/charts/applemusic",
        "params": {"type": "top", "country_iso_code": "US"},
        "platform": "apple_music",
        "chart_type": "top",
        "country": "us",
    },
    {
        "endpoint_key": "chart_sweep_apple_top_gb",
        "path": "/api/charts/applemusic",
        "params": {"type": "top", "country_iso_code": "GB"},
        "platform": "apple_music",
        "chart_type": "top",
        "country": "gb",
    },
    {
        "endpoint_key": "chart_sweep_apple_top_de",
        "path": "/api/charts/applemusic",
        "params": {"type": "top", "country_iso_code": "DE"},
        "platform": "apple_music",
        "chart_type": "top",
        "country": "de",
    },
    # Amazon Music
    {
        "endpoint_key": "chart_sweep_amazon_us",
        "path": "/api/charts/amazon",
        "params": {"type": "top", "code2": "US"},
        "platform": "amazon",
        "chart_type": "top",
        "country": "us",
    },
    # Deezer
    {
        "endpoint_key": "chart_sweep_deezer_us",
        "path": "/api/charts/deezer",
        "params": {"type": "top", "code2": "US"},
        "platform": "deezer",
        "chart_type": "top",
        "country": "us",
    },
    # SoundCloud
    {
        "endpoint_key": "chart_sweep_soundcloud_global",
        "path": "/api/charts/soundcloud",
        "params": {"type": "top", "code2": "US"},
        "platform": "soundcloud",
        "chart_type": "top",
        "country": "us",
    },
    # YouTube
    {
        "endpoint_key": "chart_sweep_youtube_us",
        "path": "/api/charts/youtube",
        "params": {"type": "top", "code2": "US"},
        "platform": "youtube",
        "chart_type": "top",
        "country": "us",
    },
    # iTunes
    {
        "endpoint_key": "chart_sweep_itunes_us",
        "path": "/api/charts/itunes",
        "params": {"type": "top", "code2": "US"},
        "platform": "itunes",
        "chart_type": "top",
        "country": "us",
    },
    # Beatport
    {
        "endpoint_key": "chart_sweep_beatport_global",
        "path": "/api/charts/beatport",
        "params": {"type": "top"},
        "platform": "beatport",
        "chart_type": "top",
        "country": None,
    },
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
        freshness = freshness_score(last_fetched, cfg.target_interval_hours)
        priority = priority_from_scores(
            freshness=freshness,
            importance=75.0,  # chart endpoints are higher-value than long-tail entity stats
            endpoint_weight=cfg.priority_weight,
        )
        job_id = await cmq_queue.enqueue(
            db,
            url=url,
            params=spec["params"],
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
