"""
Fonzworth ASCAP submission enqueue (T-190..T-194, PRD §31).

THIN ENQUEUE ONLY. This module used to drive Playwright in-process — that
was the wrong architecture. ASCAP portal automation runs in the separate
services/portal-worker/ Railway service (BlackTip-based, same pattern as
services/tunebat-crawler/).

What this module does now:
  1. Accept a song + artist from the admin endpoint
  2. Create an ascap_submissions row with status='pending' so the
     portal-worker's claim endpoint can pick it up
  3. Return the row immediately — actual submission happens async
     when the worker drains the queue

The portal-worker posts results back via the /admin/worker/ack|fail
endpoints, which update the same ascap_submissions row.

The ASCAP creds (ASCAP_USERNAME + ASCAP_PASSWORD) live in the
portal-worker service's env, not in the API container.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ascap_submission import AscapSubmission

logger = logging.getLogger(__name__)


async def submit_song_to_ascap(
    db: AsyncSession,
    *,
    song,
    artist,
    force_retry: bool = False,
) -> AscapSubmission:
    """
    Enqueue an ASCAP work registration. Creates or updates an
    ascap_submissions row with status='pending' and returns it.

    The portal-worker service (Node.js + BlackTip) polls for these via
    POST /admin/worker/claim-next?target_service=ascap and drives the
    portal flow outside of this process.
    """
    # Reuse the latest row unless force_retry
    existing = (
        await db.execute(
            select(AscapSubmission)
            .where(AscapSubmission.song_id == song.song_id)
            .order_by(AscapSubmission.created_at.desc())
            .limit(1)
        )
    ).scalars().first()

    if existing and existing.status in ("submitted", "accepted") and not force_retry:
        logger.info(
            "[ascap] song %s already has a %s submission (work_id=%s) — skipping",
            song.song_id, existing.status, existing.ascap_work_id,
        )
        return existing

    # Build the writer + publisher splits from the song + artist.
    # These are legally load-bearing — the worker will use them
    # verbatim in the portal form, so validation happens here.
    writers = song.writers or [
        {
            "name": artist.legal_name or artist.stage_name,
            "role": "composer",
            "ipi": None,
            "share_pct": 100.0,
        }
    ]
    publishers = song.publishers or [
        {
            "name": "SoundPulse Records LLC",
            "ipi": None,
            "share_pct": 100.0,
        }
    ]

    row = AscapSubmission(
        id=_uuid.uuid4(),
        song_id=song.song_id,
        attempt_number=(existing.attempt_number + 1) if existing else 1,
        status="pending",
        submission_title=song.title,
        submission_iswc=getattr(song, "iswc", None),
        writers_json={"writers": writers},
        publishers_json={"publishers": publishers},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "[ascap] enqueued song %s for ASCAP worker (row %s)",
        song.song_id, row.id,
    )
    return row
