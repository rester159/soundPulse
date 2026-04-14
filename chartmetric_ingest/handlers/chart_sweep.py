"""Handler for Chartmetric chart endpoints — `/api/charts/<platform>/...`.

Chart endpoints return a list of ranked items (tracks, artists,
videos) that Chartmetric re-computes on its own schedule. They are
the backbone of the "what's trending right now?" feed that
`trending_snapshots` captures, and they produce new data on every
fetch regardless of our catalog size.

This handler parses the response into a minimal `trending_snapshots`-
compatible payload and POSTs it to the existing
`/api/v1/trending/bulk` endpoint via an in-process service call.
That's the same sink every existing chart-shaped scraper writes to,
so we get entity resolution + classification + composite recalc for
free via the shared pipeline.

Handler context shape:
    {
      "endpoint_key": "chart_sweep_spotify_viral_us",
      "platform": "spotify",
      "chart_type": "viral",
      "country": "us",
      "entity_type": "track",
    }

Generality note
---------------
The list of chart endpoints lives in the planner
(`planners/chart_sweep.py`) as the single source of truth. This
handler is **endpoint-shape-agnostic** — it walks a handful of
common response shapes (top-level list, `obj` wrapper, `obj.data`,
`obj.<platform>`) and extracts (rank, name, artist, cm_id, ids)
from whichever shape matches. New chart endpoints can be added to
the planner list without touching this handler unless Chartmetric
invents a brand new response envelope.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from chartmetric_ingest import fetch_log as cmq_fetch_log
from chartmetric_ingest.handlers import register

logger = logging.getLogger(__name__)


def _api_base_url() -> str:
    return os.environ.get("SOUNDPULSE_API_URL", "http://localhost:8000")


def _admin_key() -> str:
    return os.environ.get("API_ADMIN_KEY", "")


def _extract_items(body: Any) -> list[dict[str, Any]]:
    """Walk common Chartmetric chart-response shapes and yield item dicts.

    Handles the four shapes deep_us observed during the 2026-04-11
    probe: (1) top-level list, (2) `{obj: [...]}`, (3) `{obj: {data: [...]}}`,
    (4) `{obj: {<platform>: [...]}}`.
    """
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if not isinstance(body, dict):
        return []
    obj = body.get("obj")
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("data", "tracks", "items"):
            seq = obj.get(key)
            if isinstance(seq, list):
                return [x for x in seq if isinstance(x, dict)]
        # Platform-nested: obj.spotify, obj.applemusic, etc.
        for value in obj.values():
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _build_trending_records(
    items: list[dict[str, Any]],
    *,
    platform: str,
    chart_type: str,
    country: str | None,
    entity_type: str,
    snapshot: date,
) -> list[dict[str, Any]]:
    """Map raw chart items to the TrendingIngest-shaped records bulk expects."""
    records: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        name = (
            item.get("name")
            or item.get("track_name")
            or item.get("title")
            or (item.get("track") or {}).get("name")
        )
        artist_name = (
            item.get("artist_name")
            or item.get("artist")
            or (item.get("artists") or [{}])[0].get("name")
            if isinstance(item.get("artists"), list) and item.get("artists")
            else item.get("artist_name") or item.get("artist")
        )
        if not name:
            continue
        entity_identifier: dict[str, Any] = {"title": name}
        if artist_name:
            entity_identifier["artist_name"] = artist_name
        for src_key, dst_key in (
            ("spotify_track_id", "spotify_id"),
            ("spotify_id", "spotify_id"),
            ("apple_music_id", "apple_music_id"),
            ("itunes_track_id", "apple_music_id"),
            ("isrc", "isrc"),
        ):
            if item.get(src_key):
                entity_identifier[dst_key] = str(item[src_key])
        cm_id = item.get("cm_track") or item.get("cm_track_id") or item.get("id")
        if cm_id:
            entity_identifier["chartmetric_id"] = cm_id

        records.append({
            "platform": "chartmetric",
            "entity_type": entity_type,
            "entity_identifier": entity_identifier,
            "raw_score": None,
            "rank": item.get("rank", idx + 1),
            "snapshot_date": snapshot.isoformat(),
            "signals": {
                "source_platform": platform,
                "chart_type": chart_type,
                "country": country,
                "cm_track_id": cm_id,
            },
        })
    return records


@register("chart_sweep")
async def handle_chart_sweep(
    body: dict,
    ctx: dict,
    db: AsyncSession,
) -> None:
    """Parse a chart response into trending_snapshots-shaped records and bulk-ingest."""
    platform = ctx.get("platform", "unknown")
    chart_type = ctx.get("chart_type", "unknown")
    country = ctx.get("country")
    entity_type = ctx.get("entity_type", "track")
    endpoint_key = ctx.get("endpoint_key")

    items = _extract_items(body)
    if not items:
        return

    records = _build_trending_records(
        items,
        platform=platform,
        chart_type=chart_type,
        country=country,
        entity_type=entity_type,
        snapshot=date.today(),
    )
    if not records:
        return

    # Reuse the existing `/api/v1/trending/bulk` pipeline (entity
    # resolution + dedup + deferred classification + composite recalc).
    # The fetcher runs in-process with the API so this is a localhost
    # round-trip — ~5 ms overhead, far cleaner than re-implementing
    # the ingest path here.
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{_api_base_url()}/api/v1/trending/bulk",
                json={"items": records},
                headers={"X-API-Key": _admin_key()},
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "[cm-handler-chart-sweep] bulk HTTP %d for %s: %s",
                    resp.status_code, endpoint_key, resp.text[:200],
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "[cm-handler-chart-sweep] bulk transport error for %s: %s",
                endpoint_key, exc,
            )
            raise

    # Stamp the fetch log so the planner's freshness query sees this
    # endpoint as recently refreshed. The endpoint_key IS the entity
    # here (chart endpoints are not per-entity), so we use a sentinel
    # UUID derived from the endpoint_key.
    import uuid as _uuid
    sentinel = _uuid.uuid5(_uuid.NAMESPACE_URL, f"chart_endpoint:{endpoint_key}")
    await cmq_fetch_log.mark_fetched(
        db,
        entity_type="chart_endpoint",
        entity_id=sentinel,
        endpoint_key=endpoint_key or "chart_sweep_unknown",
        status=200,
    )
    await db.commit()
