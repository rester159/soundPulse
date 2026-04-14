"""Handler for `/api/track/{cm_id}/stat/{platform}` responses.

Parses the Chartmetric time-series response (list-of-[ts,value] pairs
nested under `obj.<metric_name>`) into rows for `track_stat_history`
and upserts via ON CONFLICT on the natural key.

Handler context shape:
    {
      "track_id": "<uuid string>",
      "chartmetric_track_id": 12345,
      "platform": "spotify",
    }

The set of metrics this handler persists per platform is the single
source of truth at `chartmetric_ingest.planners.track_history.
PLATFORM_SPECS`. This handler looks up the metric list from there,
so adding a metric is a one-line change that both the planner (which
decides what to request) and the handler (which decides what to
write) pick up automatically.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func as sa_func

from api.models.track_stat_history import TrackStatHistory
from chartmetric_ingest.handlers import register

logger = logging.getLogger(__name__)


def _normalize_date(ts: Any) -> str | None:
    """Accept ISO string or unix seconds/millis; return 'YYYY-MM-DD'."""
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts[:10]
    if isinstance(ts, (int, float)):
        try:
            secs = float(ts)
            if secs > 1e12:
                secs /= 1000.0
            return datetime.fromtimestamp(secs, tz=timezone.utc).date().isoformat()
        except Exception:
            return None
    return None


def _point_to_row(
    *,
    point: Any,
    track_id: str,
    chartmetric_track_id: int | None,
    platform: str,
    metric: str,
) -> dict[str, Any] | None:
    """Normalize a single Chartmetric time-series point to a row dict."""
    value: int | None = None
    value_float: float | None = None

    if isinstance(point, list) and len(point) >= 2:
        ts, raw = point[0], point[1]
    elif isinstance(point, dict):
        ts = point.get("timestamp") or point.get("ts") or point.get("date")
        raw = point.get("value") or point.get("v")
    else:
        return None

    snapshot_date = _normalize_date(ts)
    if snapshot_date is None:
        return None

    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, float):
        if raw.is_integer():
            value = int(raw)
        else:
            value_float = raw
    else:
        return None

    return {
        "track_id": track_id,
        "chartmetric_track_id": chartmetric_track_id,
        "platform": platform,
        "metric": metric,
        "snapshot_date": snapshot_date,
        "value": value,
        "value_float": value_float,
    }


def extract_rows(
    body: dict,
    *,
    track_id: str,
    chartmetric_track_id: int | None,
    platform: str,
    metrics: list[str],
    max_points_per_series: int = 120,
) -> list[dict[str, Any]]:
    """Walk `obj.<metric>` arrays in the response and yield row dicts.

    Kept as a pure function separate from the handler body so unit
    tests can exercise it directly against fixture JSON without
    needing a DB.
    """
    out: list[dict[str, Any]] = []
    obj = body.get("obj") if isinstance(body, dict) else None
    if not isinstance(obj, dict):
        return out
    for metric in metrics:
        series = obj.get(metric)
        if not isinstance(series, list):
            continue
        for point in series[-max_points_per_series:]:
            row = _point_to_row(
                point=point,
                track_id=track_id,
                chartmetric_track_id=chartmetric_track_id,
                platform=platform,
                metric=metric,
            )
            if row is not None:
                out.append(row)
    return out


@register("track_history")
async def handle_track_history(
    body: dict,
    ctx: dict,
    db: AsyncSession,
) -> None:
    """Upsert parsed rows into `track_stat_history`."""
    # Import here so `chartmetric_ingest.handlers` can be imported
    # without dragging the planner module into circular-import
    # territory at package init time.
    from chartmetric_ingest.planners.track_history import PLATFORM_SPECS

    track_id = ctx.get("track_id")
    chartmetric_track_id = ctx.get("chartmetric_track_id")
    platform = ctx.get("platform")
    if not (track_id and platform):
        logger.warning("[cm-handler-track-history] missing ctx fields: %s", ctx)
        return

    spec = next((s for s in PLATFORM_SPECS if s["platform"] == platform), None)
    if spec is None:
        logger.warning("[cm-handler-track-history] unknown platform %r", platform)
        return

    rows = extract_rows(
        body,
        track_id=track_id,
        chartmetric_track_id=chartmetric_track_id,
        platform=platform,
        metrics=spec["metrics"],
    )
    if not rows:
        return

    stmt = pg_insert(TrackStatHistory).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_track_stat_history_natural",
        set_={
            "value": stmt.excluded.value,
            "value_float": stmt.excluded.value_float,
            "chartmetric_track_id": stmt.excluded.chartmetric_track_id,
            "pulled_at": sa_func.now(),
        },
    )
    await db.execute(stmt)
    await db.commit()
