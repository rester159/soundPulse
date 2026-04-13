"""
Lightweight audio QA sweep (T-162-lite, §25).

Minimal checks that need no DSP library — durations, sizes, and
metadata. Enough to unblock the autonomous flow while the full
Essentia/Librosa QA service (T-162-full) lands later. Every check that
can't run yet (tempo match, key match, silence, clipping, loudness,
duplication) writes NULL into song_qa_reports so the real service can
fill them in on a re-run.

Thresholds are deliberately lenient so MusicGen output (instrumental,
sometimes short) doesn't get unfairly rejected.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import bindparam, text as _text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Thresholds — tune once real DSP lands
MIN_DURATION_SECONDS = 5
MAX_DURATION_SECONDS = 600  # 10 min upper bound
MIN_AUDIO_BYTES = 1_000     # 1 KB — anything smaller is broken


async def sweep_audio_qa(db: AsyncSession, *, limit: int = 100) -> dict[str, Any]:
    """
    Scan songs_master WHERE status='qa_pending' and check each against
    the lightweight thresholds. Returns stats dict for the caller.

    Safe to run from cron OR on-demand from an admin endpoint.
    """
    stats = {
        "scanned": 0,
        "passed": 0,
        "failed": 0,
        "skipped_no_audio": 0,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    # Pull candidate songs + their master audio asset + bytes size
    result = await db.execute(
        _text("""
            SELECT
                s.song_id,
                s.title,
                s.duration_seconds AS song_duration,
                aa.asset_id,
                aa.duration_seconds AS asset_duration,
                aa.storage_url,
                COALESCE(mga.size_bytes, 0) AS size_bytes,
                mgc.id AS call_id
            FROM songs_master s
            LEFT JOIN audio_assets aa ON aa.song_id = s.song_id AND aa.is_master_candidate
            LEFT JOIN music_generation_calls mgc ON mgc.id = aa.music_generation_call_id
            LEFT JOIN music_generation_audio mga ON mga.music_generation_call_id = mgc.id
            WHERE s.status = 'qa_pending'
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()

    for row in rows:
        stats["scanned"] += 1
        song_id = row[0]
        title = row[1]
        asset_id = row[3]
        asset_duration = row[4]
        size_bytes = row[6]

        if asset_id is None:
            stats["skipped_no_audio"] += 1
            logger.info("[audio-qa-lite] %s skip — no master audio asset", title)
            continue

        failure_reasons: list[str] = []
        duration_ok = None

        if asset_duration is None or asset_duration <= 0:
            failure_reasons.append("duration unknown or zero")
            duration_ok = False
        elif asset_duration < MIN_DURATION_SECONDS:
            failure_reasons.append(f"duration {asset_duration:.1f}s below min {MIN_DURATION_SECONDS}s")
            duration_ok = False
        elif asset_duration > MAX_DURATION_SECONDS:
            failure_reasons.append(f"duration {asset_duration:.1f}s above max {MAX_DURATION_SECONDS}s")
            duration_ok = False
        else:
            duration_ok = True

        if size_bytes < MIN_AUDIO_BYTES:
            failure_reasons.append(f"audio bytes {size_bytes} below min {MIN_AUDIO_BYTES}")

        pass_fail = len(failure_reasons) == 0

        report = {
            "engine": "audio_qa_lite_v1",
            "asset_duration_seconds": float(asset_duration) if asset_duration else None,
            "size_bytes": int(size_bytes),
            "notes": "Lightweight checks only. DSP metrics (tempo, key, "
                     "silence, clipping, loudness, duplication) deferred to T-162-full.",
        }
        # asyncpg needs JSONB columns bound via a typed parameter — plain
        # dicts sent through a raw text query hit DataError.
        insert_stmt = _text("""
            INSERT INTO song_qa_reports (
                song_id, asset_id, duration_ok, pass_fail, failure_reasons, report_json
            ) VALUES (
                :song_id, :asset_id, :duration_ok, :pass_fail, :reasons, CAST(:report AS jsonb)
            )
        """)
        await db.execute(
            insert_stmt,
            {
                "song_id": song_id,
                "asset_id": asset_id,
                "duration_ok": duration_ok,
                "pass_fail": pass_fail,
                "reasons": failure_reasons if failure_reasons else None,
                "report": json.dumps(report),
            },
        )

        new_status = "qa_passed" if pass_fail else "qa_failed"
        await db.execute(
            _text("""
                UPDATE songs_master
                SET status = :status,
                    qa_pass = :pass_fail,
                    updated_at = NOW()
                WHERE song_id = :song_id
            """),
            {"status": new_status, "pass_fail": pass_fail, "song_id": song_id},
        )

        if pass_fail:
            stats["passed"] += 1
            logger.info("[audio-qa-lite] PASS %s (%.1fs, %d bytes)", title, asset_duration, size_bytes)
        else:
            stats["failed"] += 1
            logger.warning("[audio-qa-lite] FAIL %s — %s", title, ", ".join(failure_reasons))

    await db.commit()
    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[audio-qa-lite] sweep %s", stats)
    return stats
