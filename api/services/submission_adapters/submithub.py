"""
SubmitHub adapter (T-213).

SubmitHub has a real REST API — no Playwright needed. Takes a song URL
(we pass our self-hosted streaming URL via PUBLIC_BASE_URL), matches it
to curator inboxes based on genre, and gets responses back.

Credential: SUBMITHUB_API_KEY env var

Docs: https://www.submithub.com/api
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)

SUBMITHUB_BASE = os.environ.get("SUBMITHUB_BASE_URL", "https://www.submithub.com/api/v1")


@register_adapter("submithub")
async def submithub_adapter(db, subject_row, target) -> tuple[str, str | None, dict]:
    """Submit a song to SubmitHub curators."""
    api_key = os.environ.get("SUBMITHUB_API_KEY", "").strip()
    if not api_key:
        return ("failed", None, {"error": "SUBMITHUB_API_KEY not set"})

    public_base = os.environ.get(
        "PUBLIC_BASE_URL",
        "https://soundpulse-production-5266.up.railway.app",
    )

    # SubmitHub wants a playable URL. We use our self-hosted audio stream.
    # Resolve the music_generation_call so we know which provider/task
    # the audio URL points at.
    from sqlalchemy import text as _text
    r = await db.execute(
        _text("""
            SELECT mgc.provider, mgc.task_id
            FROM music_generation_calls mgc
            WHERE mgc.song_id = :sid
            ORDER BY mgc.completed_at DESC NULLS LAST, mgc.created_at DESC
            LIMIT 1
        """),
        {"sid": subject_row.song_id},
    )
    row = r.fetchone()
    if row is None:
        return ("failed", None, {"error": "no music_generation_call for song"})
    provider, task_id = row[0], row[1]
    audio_url = f"{public_base}/api/v1/admin/music/audio/{provider}/{task_id}.mp3"

    # Build the SubmitHub payload
    payload = {
        "song_url": audio_url,
        "title": subject_row.title or "Untitled",
        "genre": (subject_row.primary_genre or "").split(".")[0] or "pop",
        "description": subject_row.marketing_hook or "",
        "mood_tags": (subject_row.mood_tags or [])[:5],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{SUBMITHUB_BASE}/submissions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        body: dict[str, Any] = {}
        try:
            body = r.json()
        except Exception:
            body = {"raw_text": r.text[:500]}
        if r.status_code in (200, 201, 202):
            sub_id = body.get("submission_id") or body.get("id")
            return ("submitted", sub_id, {"http_status": r.status_code, "response": body})
        return ("failed", None, {"http_status": r.status_code, "response": body})
    except Exception as e:
        logger.exception("[submithub] request failed")
        return ("failed", None, {"error": f"{type(e).__name__}: {e}"})
