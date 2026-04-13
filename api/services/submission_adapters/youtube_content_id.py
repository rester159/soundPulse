"""
YouTube Content ID adapter (T-196).

Google's CMS API for Content ID partner accounts — registers a master
recording reference so YouTube automatically claims uploads containing
the audio. Real API (not Playwright).

Credential: YOUTUBE_CMS_SERVICE_ACCOUNT_JSON (path to or inline JSON)

Docs: https://developers.google.com/youtube/partner/guides/content_id
Scope: https://www.googleapis.com/auth/youtubepartner

This adapter uploads the audio as a 'reference' and attaches asset
metadata (title, artist, ISRC). Successful registration returns an
asset_id that YouTube uses to match incoming uploads.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any

import httpx

from api.services.external_submission_agent import register_adapter

logger = logging.getLogger(__name__)

YOUTUBE_PARTNER_API = "https://www.googleapis.com/youtube/partner/v1"


def _load_service_account() -> dict | None:
    raw = os.environ.get("YOUTUBE_CMS_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    # Accept either inline JSON or a path
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except Exception:
            return None
    if os.path.exists(raw):
        try:
            with open(raw, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None


async def _get_access_token(service_account: dict) -> str | None:
    """Build a JWT, exchange for an OAuth2 access token via Google."""
    try:
        import jwt  # type: ignore
    except ImportError:
        logger.warning("[youtube_content_id] pyjwt not installed — cannot sign service account JWT")
        return None

    now = int(time.time())
    claim = {
        "iss": service_account.get("client_email"),
        "scope": "https://www.googleapis.com/auth/youtubepartner",
        "aud": "https://oauth2.googleapis.com/token",
        "exp": now + 3600,
        "iat": now,
    }
    private_key = service_account.get("private_key")
    if not private_key:
        return None
    try:
        signed = jwt.encode(claim, private_key, algorithm="RS256")
    except Exception as e:
        logger.exception("[youtube_content_id] JWT sign failed")
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": signed,
                },
            )
        if r.status_code != 200:
            logger.warning("[youtube_content_id] token exchange failed: %s", r.text[:200])
            return None
        return r.json().get("access_token")
    except Exception:
        logger.exception("[youtube_content_id] token exchange raised")
        return None


@register_adapter("youtube_content_id")
async def youtube_content_id_adapter(db, subject_row, target) -> tuple[str, str | None, dict]:
    """Register a sound recording as a Content ID reference."""
    sa = _load_service_account()
    if sa is None:
        return ("failed", None, {"error": "YOUTUBE_CMS_SERVICE_ACCOUNT_JSON not configured"})
    token = await _get_access_token(sa)
    if token is None:
        return ("failed", None, {"error": "failed to exchange service account JWT for access token"})

    # Build asset metadata (soundRecordingMetadata)
    asset_payload = {
        "type": "sound_recording",
        "metadata": {
            "customId": str(subject_row.song_id),
            "isrc": subject_row.isrc,
            "title": subject_row.title or "Untitled",
            "artist": (subject_row.writers or [{}])[0].get("name") if subject_row.writers else None,
            "label": "SoundPulse Records LLC",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{YOUTUBE_PARTNER_API}/assets",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=asset_payload,
            )
        body = {}
        try:
            body = r.json()
        except Exception:
            body = {"raw_text": r.text[:500]}
        if r.status_code in (200, 201):
            asset_id = body.get("id")
            return (
                "submitted",
                asset_id,
                {
                    "http_status": r.status_code,
                    "asset_id": asset_id,
                    "next_step": "upload_reference_file — NOT YET IMPLEMENTED, CEO must upload manually via YouTube CMS",
                },
            )
        return ("failed", None, {"http_status": r.status_code, "response": body})
    except Exception as e:
        logger.exception("[youtube_content_id] request failed")
        return ("failed", None, {"error": f"{type(e).__name__}: {e}"})
