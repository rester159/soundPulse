"""Handler for `/api/artist/{cm_id}/stat/{platform}?latest=true`.

Chartmetric returns a `{obj: {metric_name: scalar_or_timeseries}}`
shape. We pull the latest value for each metric named in the
platform spec, merge into `artists.metadata_json.chartmetric_stats.
<platform>` as `{metric: value, ..., updated_at: <iso>}`, and stamp
the fetch_log so the planner sees the refresh.

`handler_context` shape:
    {
      "artist_id": "<uuid>",           # our DB id
      "chartmetric_artist_id": 12345,  # upstream id (kept for logs)
      "platform": "spotify",
    }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.artist import Artist
from chartmetric_ingest import fetch_log as cmq_fetch_log
from chartmetric_ingest.handlers import register

logger = logging.getLogger(__name__)


def _extract_latest(obj: dict[str, Any], metric_keys: list[str]) -> dict[str, Any]:
    """Pull the last-known value for each metric from the response body.

    Chartmetric returns each metric either as a scalar (with
    ?latest=true) or as a [[ts, value], ...] array. For arrays we
    take the last entry's value.
    """
    out: dict[str, Any] = {}
    for key in metric_keys:
        val = obj.get(key)
        if isinstance(val, list) and val:
            last = val[-1]
            if isinstance(last, list) and len(last) >= 2:
                out[key] = last[1]
            elif isinstance(last, dict):
                out[key] = last.get("value") or last.get("v")
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            out[key] = val
        elif isinstance(val, dict):
            out[key] = val.get("value")
    return out


@register("artist_stats")
async def handle_artist_stats(
    body: dict,
    ctx: dict,
    db: AsyncSession,
) -> None:
    from chartmetric_ingest.planners.artist_stats import PLATFORM_SPECS

    artist_id = ctx.get("artist_id")
    platform = ctx.get("platform")
    if not (artist_id and platform):
        logger.warning("[cm-handler-artist-stats] missing ctx: %s", ctx)
        return

    spec = next((s for s in PLATFORM_SPECS if s["platform"] == platform), None)
    if spec is None:
        logger.warning("[cm-handler-artist-stats] unknown platform %r", platform)
        return

    obj = body.get("obj") if isinstance(body, dict) else None
    if not isinstance(obj, dict):
        # Still stamp the fetch_log so we don't re-request a known-empty
        # artist next cycle.
        await cmq_fetch_log.mark_fetched(
            db,
            entity_type="artist",
            entity_id=artist_id,
            endpoint_key=spec["endpoint_key"],
            status=200,
        )
        await db.commit()
        return

    latest = _extract_latest(obj, spec["metrics"])
    now_iso = datetime.now(timezone.utc).isoformat()

    # Read-merge-write the metadata_json blob. artists.metadata_json
    # is a JSON column (not JSONB) on the current model, so we merge
    # in-memory rather than with jsonb_set.
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()
    if artist is None:
        logger.warning("[cm-handler-artist-stats] unknown artist id %s", artist_id)
        return

    metadata = dict(artist.metadata_json or {})
    cm_stats = dict(metadata.get("chartmetric_stats") or {})
    platform_stats = dict(cm_stats.get(platform) or {})
    platform_stats.update(latest)
    platform_stats["updated_at"] = now_iso
    cm_stats[platform] = platform_stats
    metadata["chartmetric_stats"] = cm_stats
    metadata["chartmetric_stats_updated_at"] = now_iso
    artist.metadata_json = metadata

    await cmq_fetch_log.mark_fetched(
        db,
        entity_type="artist",
        entity_id=artist_id,
        endpoint_key=spec["endpoint_key"],
        status=200,
    )
    await db.commit()
