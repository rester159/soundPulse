"""
External submission agent dispatcher (T-200..T-229, PRD §28-§37).

Single entry point every downstream submission goes through. Resolves
the target_service → adapter function, creates/updates an
external_submissions row, records payload + response, retries on
transient failure, and escalates to the CEO decision gate on permanent
failure.

Adapters live in api/services/submission_adapters/*.py. Each one is a
tiny module that:
  - Checks required env credentials
  - Builds the service-specific payload from the song/release/artist row
  - Calls the portal (either via httpx for API-backed services, or
    Playwright for browser-driven ones)
  - Returns (status, external_id, response_dict) or raises

The CEO never has to know about individual services — they just watch
the Submissions page and approve/reject escalations.
"""
from __future__ import annotations

import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.external_submission import ExternalSubmission, SubmissionTarget

logger = logging.getLogger(__name__)


# Adapter registry — filled at import time below. Each adapter is an
# async function taking (db, subject_row, target_row) and returning
# (status: str, external_id: str | None, response: dict).
AdapterFn = Callable[
    [AsyncSession, Any, SubmissionTarget],
    Awaitable[tuple[str, str | None, dict[str, Any]]],
]
_ADAPTERS: dict[str, AdapterFn] = {}


def register_adapter(target_service: str):
    def wrap(fn: AdapterFn) -> AdapterFn:
        _ADAPTERS[target_service] = fn
        return fn
    return wrap


def _missing_creds(target: SubmissionTarget) -> str | None:
    """Return a human-readable error if any required env key is missing,
    else None."""
    missing = [k for k in (target.credential_env_keys or []) if not os.environ.get(k, "").strip()]
    if missing:
        return f"missing env credentials: {', '.join(missing)}"
    return None


async def _get_target(db: AsyncSession, target_service: str) -> SubmissionTarget:
    t = (
        await db.execute(
            select(SubmissionTarget).where(SubmissionTarget.target_service == target_service)
        )
    ).scalar_one_or_none()
    if t is None:
        raise KeyError(f"submission_target '{target_service}' not seeded")
    return t


async def submit_subject(
    db: AsyncSession,
    *,
    target_service: str,
    submission_subject_type: str,
    subject_id: _uuid.UUID,
    force_retry: bool = False,
) -> ExternalSubmission:
    """
    End-to-end submit a subject to a target service.

    Creates a queued row (or reuses an existing pending one), runs the
    matching adapter, records the result. On any failure the row is
    flipped to 'failed' with last_error_message set — no exceptions
    escape the function.

    If the target isn't seeded, or no adapter is registered, or
    credentials are missing, the row is still created but marked failed
    with an explanatory error — this gives the admin UI something to
    show (and retry against) even when the integration is stubbed.
    """
    # Reuse existing latest row unless force_retry
    existing = (
        await db.execute(
            select(ExternalSubmission)
            .where(
                ExternalSubmission.target_service == target_service,
                ExternalSubmission.subject_id == subject_id,
            )
            .order_by(ExternalSubmission.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if existing and existing.status in ("submitted", "accepted") and not force_retry:
        return existing

    try:
        target = await _get_target(db, target_service)
    except KeyError as e:
        # Still write a row so the error is observable
        row = ExternalSubmission(
            id=_uuid.uuid4(),
            target_service=target_service,
            target_type="unknown",
            submission_subject_type=submission_subject_type,
            subject_id=subject_id,
            status="failed",
            last_error_message=str(e),
        )
        db.add(row)
        await db.commit()
        return row

    row = ExternalSubmission(
        id=_uuid.uuid4(),
        target_service=target_service,
        target_type=target.target_type,
        submission_subject_type=submission_subject_type,
        subject_id=subject_id,
        attempt_number=(existing.attempt_number + 1) if existing else 1,
        status="queued",
    )
    db.add(row)
    await db.flush()

    # Credential check
    cred_err = _missing_creds(target)
    if cred_err:
        row.status = "failed"
        row.last_error_message = cred_err
        await db.commit()
        logger.warning(
            "[external-submit] %s skipped — %s", target_service, cred_err
        )
        return row

    adapter = _ADAPTERS.get(target_service)
    if adapter is None:
        row.status = "failed"
        row.last_error_message = f"no adapter registered for '{target_service}' — stub mode"
        await db.commit()
        return row

    # Load the subject row
    subject_row = await _load_subject(db, submission_subject_type, subject_id)
    if subject_row is None:
        row.status = "failed"
        row.last_error_message = f"subject {submission_subject_type}/{subject_id} not found"
        await db.commit()
        return row

    # Run the adapter
    row.status = "in_progress"
    await db.flush()
    try:
        status, external_id, response = await adapter(db, subject_row, target)
        row.status = status
        row.external_id = external_id
        row.response_json = response
        if status == "submitted":
            row.submitted_at = datetime.now(timezone.utc)
        elif status == "accepted":
            row.accepted_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(
            "[external-submit] %s → %s (external_id=%s)",
            target_service, status, external_id,
        )
    except Exception as e:
        row.status = "failed"
        row.retry_count = (row.retry_count or 0) + 1
        row.last_error_message = f"{type(e).__name__}: {e}"
        await db.commit()
        logger.exception("[external-submit] %s adapter raised", target_service)

    return row


async def _load_subject(db: AsyncSession, subject_type: str, subject_id: _uuid.UUID):
    """Fetch the subject row by its type + id."""
    if subject_type in ("song", "track"):
        from api.models.songs_master import SongMaster
        return (
            await db.execute(select(SongMaster).where(SongMaster.song_id == subject_id))
        ).scalar_one_or_none()
    if subject_type == "release":
        from api.models.releases import Release
        return (
            await db.execute(select(Release).where(Release.release_id == subject_id))
        ).scalar_one_or_none()
    if subject_type == "artist":
        from api.models.ai_artist import AIArtist
        return (
            await db.execute(select(AIArtist).where(AIArtist.artist_id == subject_id))
        ).scalar_one_or_none()
    return None


# ----------------------------------------------------------------------
# STUB ADAPTERS — one per target service
#
# These all start as minimum-viable-registered stubs that fail cleanly
# with 'requires live integration' until actual adapter code is written.
# Registering them here means the dispatcher can queue work against
# every target; flipping one on is just replacing the function body.
#
# The structure is copy-paste identical so adding a real integration is
# a small diff.
# ----------------------------------------------------------------------

async def _stub_adapter(db, subject_row, target: SubmissionTarget) -> tuple[str, str | None, dict]:
    """Shared fallback body used by every not-yet-live adapter."""
    return (
        "failed",
        None,
        {
            "stub": True,
            "reason": "integration not live — credentials configured but adapter body not yet implemented",
            "target_service": target.target_service,
            "integration_status": target.integration_status,
            "next_step": (
                "Flip integration_status='partial' and implement the real body "
                "in api/services/submission_adapters/{target_service}.py"
            ),
        },
    )


_STUB_SERVICES = [
    "distrokid", "tunecore", "cd-baby", "amuse", "unitedmasters",
    "bmi", "mlc", "soundexchange", "youtube_content_id",
    "musicbed", "marmoset", "artlist", "submithub",
    "groover", "playlistpush",
    "spotify_editorial", "apple_music_for_artists",
    "press_release_agent", "social_media_agent", "tiktok_upload",
]
for _svc in _STUB_SERVICES:
    register_adapter(_svc)(_stub_adapter)
