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
    For breakout_events detected before `cutoff` that haven't been
    resolved yet, check the track's current composite_score and assign
    an outcome label.
    """
    result = await db.execute(
        select(BreakoutEvent)
        .where(
            BreakoutEvent.resolved_at.is_(None),
            BreakoutEvent.detection_date <= cutoff,
        )
        .limit(500)
    )
    events = result.scalars().all()
    resolved = 0

    for event in events:
        # Get the track's latest composite score
        latest = await db.execute(
            select(func.max(TrendingSnapshot.composite_score))
            .where(
                TrendingSnapshot.entity_id == event.track_id,
                TrendingSnapshot.entity_type == "track",
            )
        )
        current_composite = latest.scalar() or 0

        # Compare against the genre median at detection time
        if current_composite > 2 * event.genre_median_composite:
            label = "hit"
        elif current_composite > event.genre_median_composite:
            label = "moderate"
        else:
            label = "fizzle"

        event.resolved_at = datetime.now(timezone.utc)
        event.outcome_score = current_composite
        event.outcome_label = label
        resolved += 1

    return resolved
