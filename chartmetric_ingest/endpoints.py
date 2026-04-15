"""Default endpoint config — seeded on every boot, idempotent.

These are the `chartmetric_endpoint_config` rows the planners expect
to exist. On startup the runner calls `seed_endpoint_configs` which
does INSERT ... ON CONFLICT DO NOTHING so operator edits to
`target_interval_hours` / `priority_weight` / `enabled` are never
clobbered — only new keys are added.

Adding a new endpoint type is a three-step edit:
  1. Append a row here
  2. Write a planner (chartmetric_ingest/planners/<name>.py)
  3. Write a handler (chartmetric_ingest/handlers/<name>.py)

No schema migration. No scheduler wiring. The runner picks up the
new planner automatically via the PLANNER_REGISTRY bootstrap.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.chartmetric_queue import ChartmetricEndpointConfig

logger = logging.getLogger(__name__)


DEFAULT_ENDPOINT_CONFIGS: list[dict[str, Any]] = [
    # ---------------------------------------------------------------
    # Target intervals are set aggressively (1-6h). Rationale:
    #
    # The fetcher's global token bucket runs at 1.8 req/s = 155,520
    # req/day = 90% of the Chartmetric daily quota. That's the drain
    # rate. For the queue to stay non-empty — and therefore for the
    # fetcher to actually hit 90% rather than stalling on an empty
    # queue — the sum of (entity_count × 24h/target_interval) across
    # every planner must exceed 155,520 / day.
    #
    # At 1h target, every (entity, endpoint) pair generates 24 jobs/day,
    # so we need ~6,500 total (entity, endpoint) pairs to saturate.
    # Current combined reach (tracks × 3 platforms + artists × 6
    # platforms) clears that by a wide margin, so 1-2h targets on the
    # high-frequency endpoints guarantee the queue is always warm.
    #
    # If Chartmetric reports unchanged values on rapid re-fetches we
    # spend quota without new data — but the alternative is wasting
    # quota on idle time, which is worse. The token bucket caps us
    # at 90% regardless; tightening the target interval just controls
    # how much of that budget is active vs idle.
    #
    # Every value below is operator-tunable via the admin API at
    # runtime — none of this is a hardcode in the hot path.
    # ---------------------------------------------------------------

    # Per-track daily time-series from /api/track/{cm_id}/stat/{platform}.
    {
        "endpoint_key": "track_stat_spotify",
        "target_interval_hours": 2.0,
        "priority_weight": 1.0,
        "notes": "Per-track Spotify streams/popularity/playlist_reach",
    },
    {
        "endpoint_key": "track_stat_tiktok",
        "target_interval_hours": 2.0,
        "priority_weight": 1.0,
        "notes": "Per-track TikTok video_count/view_count",
    },
    {
        "endpoint_key": "track_stat_shazam",
        "target_interval_hours": 6.0,
        "priority_weight": 0.8,
        "notes": "Per-track Shazam count (lower weight, slower cadence)",
    },

    # Per-artist latest stats across 6 platforms.
    {
        "endpoint_key": "artist_stat_spotify",
        "target_interval_hours": 6.0,
        "priority_weight": 1.0,
        "notes": "Per-artist Spotify followers/monthly_listeners/popularity",
    },
    {
        "endpoint_key": "artist_stat_instagram",
        "target_interval_hours": 12.0,
        "priority_weight": 0.9,
        "notes": "Per-artist Instagram followers",
    },
    {
        "endpoint_key": "artist_stat_tiktok",
        "target_interval_hours": 6.0,
        "priority_weight": 1.0,
        "notes": "Per-artist TikTok followers/likes",
    },
    {
        "endpoint_key": "artist_stat_youtube",
        "target_interval_hours": 12.0,
        "priority_weight": 1.0,
        "notes": "Per-artist YouTube subscribers/views",
    },
    {
        "endpoint_key": "artist_stat_twitter",
        "target_interval_hours": 24.0,
        "priority_weight": 0.6,
        "notes": "Per-artist Twitter followers (slow-moving, lower weight)",
    },
    # NOTE: artist_stat_shazam was removed after 2026-04-14 — Chartmetric's
    # /api/artist/{id}/stat/{source} endpoint does not accept "shazam" as
    # a source (400 'source must be one of [...]'). Wire to a dedicated
    # shazam endpoint in a follow-up task if per-artist shazam stats
    # become important again.

    # ---------------------------------------------------------------
    # Chart sweep — confirmed-working matrix, no genre-required
    # endpoints. Keys must match CHART_ENDPOINTS in
    # chartmetric_ingest/planners/chart_sweep.py.
    # ---------------------------------------------------------------
    # Spotify regional (daily) across 6 markets
    {"endpoint_key": "chart_sweep_spotify_regional_us", "target_interval_hours": 0.5, "priority_weight": 1.2,
     "notes": "Spotify regional chart US"},
    {"endpoint_key": "chart_sweep_spotify_regional_gb", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify regional chart GB"},
    {"endpoint_key": "chart_sweep_spotify_regional_de", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify regional chart DE"},
    {"endpoint_key": "chart_sweep_spotify_regional_fr", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify regional chart FR"},
    {"endpoint_key": "chart_sweep_spotify_regional_br", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify regional chart BR"},
    {"endpoint_key": "chart_sweep_spotify_regional_mx", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify regional chart MX"},

    # Spotify viral (daily) across 4 markets
    {"endpoint_key": "chart_sweep_spotify_viral_us", "target_interval_hours": 0.5, "priority_weight": 1.2,
     "notes": "Spotify viral chart US"},
    {"endpoint_key": "chart_sweep_spotify_viral_gb", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify viral chart GB"},
    {"endpoint_key": "chart_sweep_spotify_viral_de", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify viral chart DE"},
    {"endpoint_key": "chart_sweep_spotify_viral_br", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Spotify viral chart BR"},

    # Spotify /artists (GLOBAL, no country) — 4 confirmed-working type variants
    {"endpoint_key": "chart_sweep_spotify_artists_monthly_listeners", "target_interval_hours": 6.0, "priority_weight": 1.0,
     "notes": "Spotify artists ranked by monthly listeners"},
    {"endpoint_key": "chart_sweep_spotify_artists_popularity", "target_interval_hours": 6.0, "priority_weight": 1.0,
     "notes": "Spotify artists ranked by popularity"},
    {"endpoint_key": "chart_sweep_spotify_artists_followers", "target_interval_hours": 6.0, "priority_weight": 1.0,
     "notes": "Spotify artists ranked by follower count"},
    {"endpoint_key": "chart_sweep_spotify_artists_playlist_reach", "target_interval_hours": 6.0, "priority_weight": 1.0,
     "notes": "Spotify artists ranked by playlist reach"},

    # Shazam top US (country_code=us)
    {"endpoint_key": "chart_sweep_shazam_us", "target_interval_hours": 1.0, "priority_weight": 1.0,
     "notes": "Shazam top chart US"},

    # TikTok tracks + videos, weekly (GLOBAL, no country)
    {"endpoint_key": "chart_sweep_tiktok_tracks", "target_interval_hours": 6.0, "priority_weight": 1.1,
     "notes": "TikTok tracks weekly (global)"},
    {"endpoint_key": "chart_sweep_tiktok_videos", "target_interval_hours": 6.0, "priority_weight": 1.1,
     "notes": "TikTok videos weekly (global)"},

    # Deezer top (trailing-slash path, country_code=us)
    {"endpoint_key": "chart_sweep_deezer_us", "target_interval_hours": 6.0, "priority_weight": 0.7,
     "notes": "Deezer top US"},

    # Apple Music videos (global, no genre)
    {"endpoint_key": "chart_sweep_apple_videos", "target_interval_hours": 12.0, "priority_weight": 0.6,
     "notes": "Apple Music videos (global)"},
]


async def seed_endpoint_configs(db: AsyncSession) -> int:
    """Upsert defaults; existing rows keep operator overrides.

    Returns the count of rows newly inserted.
    """
    if not DEFAULT_ENDPOINT_CONFIGS:
        return 0

    existing = await db.execute(select(ChartmetricEndpointConfig.endpoint_key))
    existing_keys = {row[0] for row in existing.all()}
    to_insert = [c for c in DEFAULT_ENDPOINT_CONFIGS if c["endpoint_key"] not in existing_keys]
    if not to_insert:
        return 0

    stmt = (
        pg_insert(ChartmetricEndpointConfig)
        .values(to_insert)
        .on_conflict_do_nothing(index_elements=["endpoint_key"])
    )
    await db.execute(stmt)
    await db.commit()
    logger.info(
        "[cm-endpoints] seeded %d new endpoint configs: %s",
        len(to_insert),
        [c["endpoint_key"] for c in to_insert],
    )
    return len(to_insert)
