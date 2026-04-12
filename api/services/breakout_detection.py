"""
Breakout detection sweep — Layer 1 of the Breakout Analysis Engine.

Runs every 6 hours. For each genre with ≥5 tracks in the last 14 days,
identifies tracks whose peak composite_score OR velocity exceeds 2× the
genre median. Writes one breakout_events row per detection.

Also resolves old breakout events: after 30 days, checks if the track
sustained (hit), faded (moderate), or died (fizzle) by comparing its
current composite_score against the genre median at resolution time.

See planning/PRD/breakoutengine_prd.md for the full design.
"""
from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any

from sqlalchemy import select, text, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.breakout_event import BreakoutEvent
from api.models.trending_snapshot import TrendingSnapshot
from api.models.track import Track

logger = logging.getLogger(__name__)

WINDOW_DAYS = 14
MIN_GENRE_TRACKS = 5
BREAKOUT_THRESHOLD = 2.0
BREAKOUT_SCORE_THRESHOLD = 0.4
RESOLUTION_DAYS = 30


async def sweep_breakout_detection(
    db: AsyncSession,
    *,
    as_of: date | None = None,
) -> dict[str, int]:
    """
    Main entry point. Scans all genres for breakout tracks and writes
    breakout_events rows. Also resolves old unresolved events.

    Returns stats dict.
    """
    today = as_of or date.today()
    window_start = today - timedelta(days=WINDOW_DAYS)

    stats = {
        "genres_scanned": 0,
        "breakouts_detected": 0,
        "already_detected": 0,
        "events_resolved": 0,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    # ---- Step 1: Get per-genre track performance in the window ----
    genre_tracks = await _get_genre_track_performance(db, window_start, today)

    # ---- Step 2: For each genre, detect breakouts ----
    for genre_id, tracks in genre_tracks.items():
        if len(tracks) < MIN_GENRE_TRACKS:
            continue
        stats["genres_scanned"] += 1

        composites = [t["peak_composite"] for t in tracks if t["peak_composite"] is not None]
        velocities = [t["peak_velocity"] for t in tracks if t["peak_velocity"] is not None]

        if not composites or not velocities:
            continue

        med_composite = median(composites)
        med_velocity = median(velocities) if velocities else 0.0

        for t in tracks:
            pc = t["peak_composite"] or 0
            pv = t["peak_velocity"] or 0

            composite_ratio = pc / med_composite if med_composite > 0 else 0
            velocity_ratio = pv / max(med_velocity, 0.1)
            platform_bonus = 0.1 * max(0, (t["platform_count"] or 1) - 1)

            breakout_score = (
                0.5 * min(composite_ratio / 3.0, 1.0) +
                0.3 * min(velocity_ratio / 5.0, 1.0) +
                0.2 * platform_bonus
            )

            if (composite_ratio >= BREAKOUT_THRESHOLD or velocity_ratio >= BREAKOUT_THRESHOLD) \
                    and breakout_score >= BREAKOUT_SCORE_THRESHOLD:
                # Check if we already detected this track+genre+window
                existing = await db.execute(
                    select(BreakoutEvent.id).where(
                        BreakoutEvent.track_id == t["track_id"],
                        BreakoutEvent.genre_id == genre_id,
                        BreakoutEvent.window_end == today,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    stats["already_detected"] += 1
                    continue

                # Fetch the track's audio features
                track_row = await db.execute(
                    select(Track.audio_features).where(Track.id == t["track_id"])
                )
                af = track_row.scalar_one_or_none()

                event = BreakoutEvent(
                    id=uuid_mod.uuid4(),
                    track_id=t["track_id"],
                    genre_id=genre_id,
                    detection_date=today,
                    window_start=window_start,
                    window_end=today,
                    peak_composite=pc,
                    peak_velocity=pv,
                    avg_rank=t.get("avg_rank"),
                    platform_count=t.get("platform_count"),
                    genre_median_composite=med_composite,
                    genre_median_velocity=med_velocity,
                    genre_track_count=len(tracks),
                    composite_ratio=round(composite_ratio, 3),
                    velocity_ratio=round(velocity_ratio, 3),
                    breakout_score=round(breakout_score, 4),
                    audio_features=af if isinstance(af, dict) else None,
                )
                db.add(event)
                stats["breakouts_detected"] += 1

    # ---- Step 3: Resolve old events ----
    resolution_cutoff = today - timedelta(days=RESOLUTION_DAYS)
    stats["events_resolved"] = await _resolve_old_events(db, resolution_cutoff)

    await db.commit()

    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[breakout-detection] %s", stats)
    return stats


async def _get_genre_track_performance(
    db: AsyncSession, window_start: date, window_end: date
) -> dict[str, list[dict[str, Any]]]:
    """
    For each genre, get each track's peak composite, peak velocity,
    platform count, and avg rank within the window.

    Genre comes from the track's genres array (classified genres, not
    signals_json). This ensures consistency with the taxonomy.
    """
    result = await db.execute(text("""
        SELECT
            t.id AS track_id,
            UNNEST(t.genres) AS genre_id,
            MAX(ts.composite_score) AS peak_composite,
            MAX(ts.velocity) AS peak_velocity,
            AVG(ts.platform_rank) AS avg_rank,
            COUNT(DISTINCT ts.platform) AS platform_count
        FROM trending_snapshots ts
        JOIN tracks t ON t.id = ts.entity_id
        WHERE ts.entity_type = 'track'
          AND ts.snapshot_date >= :window_start
          AND ts.snapshot_date <= :window_end
          AND t.genres IS NOT NULL
          AND array_length(t.genres, 1) > 0
          AND ts.composite_score IS NOT NULL
        GROUP BY t.id, genre_id
    """), {"window_start": window_start, "window_end": window_end})

    genre_tracks: dict[str, list[dict[str, Any]]] = {}
    for row in result.fetchall():
        genre_id = row[1]
        if genre_id not in genre_tracks:
            genre_tracks[genre_id] = []
        genre_tracks[genre_id].append({
            "track_id": row[0],
            "peak_composite": row[2],
            "peak_velocity": row[3],
            "avg_rank": row[4],
            "platform_count": row[5],
        })

    return genre_tracks


async def _resolve_old_events(db: AsyncSession, cutoff: date) -> int:
    """
    Resolve breakout events that are old enough to have outcome data.

    For each unresolved event with detection_date <= cutoff, look up the
    track's MAX composite_score in a ±5-day window centered on
    detection_date + 30 days. That value is the actual outcome — what
    the track became 30 days after we flagged it.

    Outcome labels:
      hit       — outcome > 2x genre_median_composite at detection time
      moderate  — outcome > 1x genre_median_composite
      fizzle    — outcome <= 1x genre_median_composite

    This works for both real-time resolution (30+ day old events) AND
    historical backfill (events detected with as_of in the past), because
    the lookup is bounded to a date window relative to detection_date,
    not "all time."
    """
    result = await db.execute(
        select(BreakoutEvent)
        .where(
            BreakoutEvent.resolved_at.is_(None),
            BreakoutEvent.detection_date <= cutoff,
        )
        .limit(2000)
    )
    events = result.scalars().all()
    resolved = 0

    for event in events:
        target_date = event.detection_date + timedelta(days=RESOLUTION_DAYS)
        window_start = target_date - timedelta(days=5)
        window_end = target_date + timedelta(days=5)

        latest = await db.execute(
            select(func.max(TrendingSnapshot.composite_score))
            .where(
                TrendingSnapshot.entity_id == event.track_id,
                TrendingSnapshot.entity_type == "track",
                TrendingSnapshot.snapshot_date >= window_start,
                TrendingSnapshot.snapshot_date <= window_end,
            )
        )
        outcome_composite = latest.scalar()

        if outcome_composite is None:
            # No snapshots in the resolution window — track went quiet.
            # That's a fizzle (track disappeared), but mark with a 0.
            outcome_composite = 0

        # Compare against the genre median at detection time
        if outcome_composite > 2 * event.genre_median_composite:
            label = "hit"
        elif outcome_composite > event.genre_median_composite:
            label = "moderate"
        else:
            label = "fizzle"

        event.resolved_at = datetime.now(timezone.utc)
        event.outcome_score = float(outcome_composite)
        event.outcome_label = label
        resolved += 1

    return resolved


async def backfill_historical_breakouts(
    db: AsyncSession,
    *,
    weeks_back: int = 78,  # ~18 months of weekly steps
    step_days: int = 7,
) -> dict[str, int]:
    """
    Walk backward through historical reference dates and detect breakouts
    AS IF each date were "today." This populates breakout_events with
    historical data we can resolve immediately, since the ground-truth
    outcome (composite_score 30 days later) is already in the DB.

    The newest reference date is `today - 30 days` (we need at least 30
    days of forward data for resolution to be meaningful). The oldest
    reference date is `today - (30 + weeks_back * 7) days`, capped by
    the earliest snapshot we have.

    After all detections are written, runs a full resolution sweep to
    label every event whose forward window has data.

    This is the bootstrap that lets the ML hit predictor train on real
    historical outcomes instead of waiting 30 days from launch.
    """
    today = date.today()

    # Find the actual data range we have to work with
    range_result = await db.execute(text("""
        SELECT MIN(snapshot_date) AS earliest, MAX(snapshot_date) AS latest
        FROM trending_snapshots
        WHERE entity_type = 'track' AND composite_score IS NOT NULL
    """))
    range_row = range_result.fetchone()
    if not range_row or not range_row[0]:
        return {"error": "no historical snapshots available"}

    earliest_data = range_row[0]
    latest_data = range_row[1]

    # Newest reference: leave 30 days of forward window for resolution
    newest_ref = min(today, latest_data) - timedelta(days=RESOLUTION_DAYS)
    # Oldest reference: walk back weeks_back weeks, but not before our data
    requested_oldest = newest_ref - timedelta(days=weeks_back * 7)
    # Need at least 14 days of LOOKBACK data before the reference date too
    oldest_ref = max(requested_oldest, earliest_data + timedelta(days=WINDOW_DAYS))

    if oldest_ref >= newest_ref:
        return {
            "error": "insufficient historical range",
            "oldest_ref": oldest_ref.isoformat(),
            "newest_ref": newest_ref.isoformat(),
        }

    stats = {
        "reference_dates_scanned": 0,
        "total_breakouts_detected": 0,
        "total_already_existed": 0,
        "events_resolved": 0,
        "earliest_ref": oldest_ref.isoformat(),
        "newest_ref": newest_ref.isoformat(),
        "step_days": step_days,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    # Walk forward from oldest to newest
    ref_date = oldest_ref
    while ref_date <= newest_ref:
        sweep_stats = await sweep_breakout_detection(db, as_of=ref_date)
        stats["reference_dates_scanned"] += 1
        stats["total_breakouts_detected"] += sweep_stats.get("breakouts_detected", 0)
        stats["total_already_existed"] += sweep_stats.get("already_detected", 0)
        stats["events_resolved"] += sweep_stats.get("events_resolved", 0)
        ref_date += timedelta(days=step_days)

    # Final resolution pass for anything that fell through
    final_resolved = await _resolve_old_events(db, today - timedelta(days=RESOLUTION_DAYS))
    stats["events_resolved"] += final_resolved
    await db.commit()

    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[breakout-backfill] %s", stats)
    return stats
