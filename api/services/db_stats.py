"""
Database stats service.

Powers `GET /api/v1/admin/db-stats` (current totals + sub-counts) and
`GET /api/v1/admin/db-stats/history?days=N` (daily new-row counts derived
from each table's `created_at` column). PRD §22.2 has the full spec.

Used as the verification dashboard for the deep US Chartmetric pull —
without this, "did the backfill land?" requires shelling into Neon.

Implementation notes:
  - Sub-counts use `COUNT(... ) FILTER (WHERE ...)` for one-pass aggregation
    on each row scan. PostgreSQL only.
  - The history endpoint groups by `DATE(created_at)`. Capped at 365 days.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_stats(db: AsyncSession) -> dict[str, Any]:
    """Return current totals + key sub-counts for every operational table."""
    tracks_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE audio_features IS NOT NULL AND audio_features::text <> '{}'::text) AS with_audio_features,
            COUNT(*) FILTER (WHERE genres IS NOT NULL AND array_length(genres, 1) > 0) AS with_genres,
            COUNT(*) FILTER (WHERE isrc IS NOT NULL) AS with_isrc,
            COUNT(*) FILTER (WHERE chartmetric_id IS NOT NULL) AS with_chartmetric_id,
            COUNT(*) FILTER (WHERE metadata_json->>'needs_classification' = 'true') AS pending_classification,
            COUNT(*) FILTER (WHERE metadata_json->>'needs_classification' = 'skipped') AS classification_skipped
        FROM tracks
    """))).mappings().one()

    artists_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE genres IS NOT NULL AND array_length(genres, 1) > 0) AS with_genres,
            COUNT(*) FILTER (WHERE spotify_id IS NOT NULL) AS with_spotify_id,
            COUNT(*) FILTER (WHERE chartmetric_id IS NOT NULL) AS with_chartmetric_id,
            COUNT(*) FILTER (WHERE metadata_json->>'needs_classification' = 'true') AS pending_classification,
            COUNT(*) FILTER (WHERE metadata_json->>'needs_classification' = 'skipped') AS classification_skipped
        FROM artists
    """))).mappings().one()

    snapshots_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(DISTINCT snapshot_date) AS distinct_dates,
            COUNT(DISTINCT platform) AS distinct_platforms,
            MIN(snapshot_date) AS earliest_date,
            MAX(snapshot_date) AS latest_date,
            COUNT(*) FILTER (WHERE normalized_score = 0
                             AND (signals_json->>'normalized_at') IS NULL
                             AND (platform_score IS NOT NULL OR platform_rank IS NOT NULL)) AS pending_normalization,
            COUNT(*) FILTER (WHERE composite_score IS NOT NULL) AS with_composite
        FROM trending_snapshots
    """))).mappings().one()

    snapshots_per_platform = [
        dict(r) for r in (await db.execute(text("""
            SELECT platform, COUNT(*) AS total
            FROM trending_snapshots
            GROUP BY platform
            ORDER BY total DESC
        """))).mappings().all()
    ]

    snapshots_per_source = [
        dict(r) for r in (await db.execute(text("""
            SELECT
                signals_json->>'source_platform' AS source_platform,
                COUNT(*) AS total
            FROM trending_snapshots
            WHERE signals_json->>'source_platform' IS NOT NULL
            GROUP BY signals_json->>'source_platform'
            ORDER BY total DESC
        """))).mappings().all()
    ]

    genres_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'active') AS active,
            COUNT(*) FILTER (WHERE audio_profile IS NOT NULL) AS with_audio_profile
        FROM genres
    """))).mappings().one()

    predictions_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE horizon = '7d') AS h_7d,
            COUNT(*) FILTER (WHERE horizon = '30d') AS h_30d,
            COUNT(*) FILTER (WHERE horizon = '90d') AS h_90d,
            COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) AS resolved
        FROM predictions
    """))).mappings().one()

    backtest_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_runs,
            COUNT(*) FILTER (WHERE status = 'running') AS running_runs,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_runs
        FROM backtest_results
    """))).mappings().one()

    scraper_row = (await db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE enabled = true) AS enabled,
            COUNT(*) FILTER (WHERE last_status = 'success') AS last_success,
            COUNT(*) FILTER (WHERE last_status = 'error') AS last_error
        FROM scraper_configs
    """))).mappings().one()

    api_keys_row = (await db.execute(text("""
        SELECT COUNT(*) AS total FROM api_keys
    """))).mappings().one()

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "tables": {
            "tracks": dict(tracks_row),
            "artists": dict(artists_row),
            "trending_snapshots": dict(snapshots_row),
            "trending_snapshots_per_platform": snapshots_per_platform,
            "trending_snapshots_per_source": snapshots_per_source,
            "genres": dict(genres_row),
            "predictions": dict(predictions_row),
            "backtest_results": dict(backtest_row),
            "scraper_configs": dict(scraper_row),
            "api_keys": dict(api_keys_row),
        },
    }


async def get_history(db: AsyncSession, days: int = 90) -> dict[str, Any]:
    """
    Return daily new-row counts per table for the last N days.

    Each table's series is keyed by date and contains the count of rows
    added on that day (derived from `created_at`). The cumulative running
    total is also returned to support the line-chart view.
    """
    days = max(1, min(days, 365))
    start_date = date.today() - timedelta(days=days - 1)

    # Tables that have a `created_at` column we can group by
    tables = [
        ("tracks", "tracks_added"),
        ("artists", "artists_added"),
        ("trending_snapshots", "snapshots_added"),
        ("predictions", "predictions_added"),
        ("backtest_results", "backtest_added"),
    ]

    # Build one big result keyed by date
    series_by_date: dict[date, dict[str, Any]] = {}
    for d in range(days):
        cur = start_date + timedelta(days=d)
        series_by_date[cur] = {"date": cur.isoformat()}
        for _, label in tables:
            series_by_date[cur][label] = 0

    for table_name, label in tables:
        rows = (await db.execute(text(f"""
            SELECT DATE(created_at) AS day, COUNT(*) AS n
            FROM {table_name}
            WHERE created_at >= :start
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """), {"start": start_date})).all()
        for row in rows:
            day, n = row[0], row[1]
            if day in series_by_date:
                series_by_date[day][label] = int(n)

    # Compute cumulative totals (running sum from the start date)
    # For accuracy we also need the pre-period total per table
    pre_period_totals: dict[str, int] = {}
    for table_name, label in tables:
        total_before = (await db.execute(text(f"""
            SELECT COUNT(*) FROM {table_name} WHERE created_at < :start
        """), {"start": start_date})).scalar() or 0
        pre_period_totals[label.replace("_added", "_total_before")] = int(total_before)

    series = sorted(series_by_date.values(), key=lambda r: r["date"])

    # Add running cumulative totals to each row
    cumulative: dict[str, int] = {
        label.replace("_added", "_total"): pre_period_totals[label.replace("_added", "_total_before")]
        for _, label in tables
    }
    for row in series:
        for _, label in tables:
            total_label = label.replace("_added", "_total")
            cumulative[total_label] += row[label]
            row[total_label] = cumulative[total_label]

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "start_date": start_date.isoformat(),
        "end_date": (start_date + timedelta(days=days - 1)).isoformat(),
        "pre_period_totals": pre_period_totals,
        "series": series,
    }
