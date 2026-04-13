"""
MLC DDEX adapter (T-193).

The Mechanical Licensing Collective registers mechanical royalties on
the publisher side. Unlike DistroKid/BMI, MLC has a REAL API
(DDEX CWR + JSON) — no browser automation required.

Docs: https://www.themlc.com/member-portal
Credential env vars: MLC_CLIENT_ID + MLC_CLIENT_SECRET → OAuth2 token
Endpoints: https://api.themlc.com/v1/works

This adapter:
  1. Fetches an OAuth2 bearer token from /v1/oauth/token
  2. Builds a DDEX-style work registration JSON from songs_master +
     writers/publishers fields (set by metadata_projection.py)
  3. POSTs to /v1/works
  4. Returns the mlc_work_id on success

This is a 'partial' integration — the real MLC API schema has more
nuance (contributor splits, ISRC linking, rights-owner codes) than
we fill in at MVP. For the first production run we submit the minimum
payload and let the CEO fill in any rejected fields via the MLC portal
manually. The adapter stores the raw response so rejection reasons
are visible in the Submissions UI.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)

MLC_OAUTH_URL = os.environ.get("MLC_OAUTH_URL", "https://api.themlc.com/v1/oauth/token")
MLC_WORKS_URL = os.environ.get("MLC_WORKS_URL", "https://api.themlc.com/v1/works")


async def _get_oauth_token() -> str | None:
    client_id = os.environ.get("MLC_CLIENT_ID", "").strip()
    client_secret = os.environ.get("MLC_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                MLC_OAUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
        if r.status_code != 200:
            logger.warning("[mlc] OAuth failed %s: %s", r.status_code, r.text[:200])
            return None
        return r.json().get("access_token")
    except Exception:
        logger.exception("[mlc] OAuth request raised")
        return None


def _build_work_payload(song, artist) -> dict[str, Any]:
    """Build the minimum-viable MLC work-registration payload."""
    writers = song.writers or [{"name": artist.legal_name or artist.stage_name, "share_pct": 100.0}]
    publishers = song.publishers or [{"name": "SoundPulse Records LLC", "share_pct": 100.0}]
    return {
        "title": song.title or "Untitled",
        "iswc": song.iswc,
        "isrc_list": [song.isrc] if song.isrc else [],
        "first_release_date": (
            song.actual_release_date.isoformat()
            if song.actual_release_date else None
        ),
        "language": song.language or "en",
        "writers": [
            {
                "name": w.get("name"),
                "role": w.get("role", "composer"),
                "ipi": w.get("ipi"),
                "share_pct": w.get("share_pct", 0),
            }
            for w in writers
        ],
        "publishers": [
            {
                "name": p.get("name"),
                "ipi": p.get("ipi"),
                "share_pct": p.get("share_pct", 0),
            }
            for p in publishers
        ],
        "rights_territory": song.territory_rights or ["WW"],
    }


@register_adapter("mlc")
async def mlc_adapter(db, subject_row, target) -> tuple[str, str | None, dict]:
    """Live-mode MLC DDEX work registration adapter."""
    token = await _get_oauth_token()
    if not token:
        return ("failed", None, {"error": "MLC OAuth token unavailable — check MLC_CLIENT_ID/SECRET"})

    from api.models.ai_artist import AIArtist
    artist = (
        await db.execute(
            select(AIArtist).where(AIArtist.artist_id == subject_row.primary_artist_id)
        )
    ).scalar_one_or_none()
    if artist is None:
        return ("failed", None, {"error": "primary artist missing"})

    payload = _build_work_payload(subject_row, artist)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                MLC_WORKS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        body: dict[str, Any] = {}
        try:
            body = r.json()
        except Exception:
            body = {"raw_text": r.text[:500]}
        if r.status_code in (200, 201, 202):
            work_id = body.get("work_id") or body.get("mlc_work_id") or body.get("id")
            return ("submitted", work_id, {"http_status": r.status_code, "response": body, "payload": payload})
        return ("failed", None, {"http_status": r.status_code, "response": body, "payload": payload})
    except Exception as e:
        logger.exception("[mlc] request failed")
        return ("failed", None, {"error": f"{type(e).__name__}: {e}"})
