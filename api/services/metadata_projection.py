"""
Metadata projection service (T-167, PRD §27).

Projects the metadata fields on songs_master that aren't filled by the
generation orchestrator — ISRC, UPC, ISWC, writers, publishers, marketing
hook, target audience tags, playlist fit, PR angle, copyright year,
release strategy, scheduled_release_date. These are the fields a
distributor / PRO / playlist service expects to see.

Two sources feed projection:
  1. Deterministic rules — ISRC format, UPC minting, copyright year =
     current year, master_owner = 'SoundPulse Records LLC', territory_rights
     = ['WW'], writers = [artist.legal_name @ 100%], publishers =
     ['SoundPulse Records LLC' @ 100%].
  2. LLM-backed enrichment — marketing_hook, pr_angle, playlist_fit,
     target_audience_tags, release_strategy. These are judgment calls
     so they go through generate_smart_prompt-style JSON calls against
     Gemini flash.

Called after qa_passed, before release assembly. Writes directly to the
songs_master columns so downstream submission agents can read them.

ISRC Generation
---------------
SoundPulse registrant code = 'QZHZS' (placeholder; real code comes from
the ISRC Agency when the user registers). Format: CC-XXX-YY-NNNNN
  CC = country (US)
  XXX = registrant (QZH for SoundPulse)
  YY = 2-digit year
  NNNNN = sequential song number (derived from songs_master count)

UPC Generation
---------------
Until a real UPC block is registered, we use 'SP' + zero-padded release
id as a placeholder. Real UPCs come from the distributor on upload.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select, text as _text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


ISRC_COUNTRY_CODE = "US"
ISRC_REGISTRANT = os.environ.get("SOUNDPULSE_ISRC_REGISTRANT", "QZH")
CANONICAL_MASTER_OWNER = "SoundPulse Records LLC"
CANONICAL_PUBLISHER = "SoundPulse Records LLC"
CANONICAL_TERRITORY = ["WW"]


async def _next_isrc_sequence(db: AsyncSession) -> int:
    """Return the next sequential number for ISRC minting."""
    result = await db.execute(
        _text("SELECT COUNT(*) FROM songs_master WHERE isrc IS NOT NULL")
    )
    return int(result.scalar() or 0) + 1


def _build_isrc(sequence: int) -> str:
    """Format: US-QZH-25-00001  (omitting dashes → USQZH2500001)"""
    yy = datetime.now(timezone.utc).strftime("%y")
    nnnnn = f"{sequence:05d}"
    return f"{ISRC_COUNTRY_CODE}{ISRC_REGISTRANT}{yy}{nnnnn}"


def _build_copyright_year() -> int:
    return datetime.now(timezone.utc).year


async def _llm_marketing_enrichment(
    db: AsyncSession,
    *,
    song_title: str,
    primary_genre: str,
    artist_stage_name: str,
    lyric_text: str | None,
    edge_profile: str | None,
) -> dict[str, Any]:
    """
    Generate marketing_hook, pr_angle, playlist_fit, target_audience_tags,
    release_strategy via a single Gemini flash call. Returns {} on
    failure (caller falls back to defaults).
    """
    from api.services.llm_client import llm_chat

    excerpt = (lyric_text or "")[:1500]
    system = (
        "You are a music marketing strategist at SoundPulse Records. "
        "Produce JSON marketing metadata for a new song. Be SPECIFIC — "
        "no generic 'chill vibes' or 'summer anthem'. Reference concrete "
        "moments in the lyric if provided. Return ONLY valid JSON."
    )
    user = f"""Title: {song_title}
Primary genre: {primary_genre}
Artist: {artist_stage_name}
Edge profile: {edge_profile or 'flirty_edge'}

Lyric excerpt:
{excerpt}

Return JSON with these exact keys:
{{
  "marketing_hook": "one-sentence pitch — what's the angle?",
  "pr_angle": "one-sentence PR headline — why a journalist should care",
  "playlist_fit": ["specific Spotify playlist names this fits, not genres"],
  "target_audience_tags": ["concrete audience segments like gen_z_coastal, tiktok_dating_discourse, reggaeton_twitter"],
  "release_strategy": "solo_single | feature_single | ep_track | album_track",
  "mood_tags": ["3-5 mood descriptors, specific not generic"]
}}"""

    try:
        result = await llm_chat(
            db=db,
            action="smart_prompt_generation",  # reuse the existing action slot
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            caller="metadata_projection.marketing",
        )
        if not result.get("success"):
            return {}
        raw = (result.get("content") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception:
        logger.exception("[metadata-projection] LLM enrichment failed")
        return {}


async def project_metadata_for_song(
    db: AsyncSession,
    *,
    song,
    artist,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Fill in all downstream metadata on a songs_master row.
    `overwrite=False` (default) only fills NULL fields so manual CEO
    overrides aren't clobbered. `overwrite=True` replaces everything.
    """
    updates: dict[str, Any] = {}

    def maybe_set(field: str, value: Any) -> None:
        if value is None:
            return
        current = getattr(song, field, None)
        if current is not None and not overwrite:
            return
        updates[field] = value

    # ---- Deterministic fields ----
    if song.isrc is None or overwrite:
        seq = await _next_isrc_sequence(db)
        updates["isrc"] = _build_isrc(seq)

    maybe_set("master_owner", CANONICAL_MASTER_OWNER)
    maybe_set("copyright_year", _build_copyright_year())
    maybe_set("territory_rights", CANONICAL_TERRITORY)
    maybe_set("writers", [
        {
            "name": artist.legal_name or artist.stage_name,
            "share_pct": 100.0,
            "role": "composer",
            "ipi": None,
        }
    ])
    maybe_set("publishers", [
        {
            "name": CANONICAL_PUBLISHER,
            "share_pct": 100.0,
        }
    ])
    maybe_set("language", "en")  # default; overridden per-genre if needed

    # Set ISWC placeholder (real one comes from MLC after registration)
    if song.iswc is None or overwrite:
        updates["iswc"] = None  # explicit — will be populated post-MLC

    # ---- LLM enrichment ----
    # Only fire if at least one marketing field is missing AND we have
    # lyric text to reason about.
    needs_enrichment = overwrite or any(
        getattr(song, f, None) is None
        for f in ("marketing_hook", "pr_angle", "playlist_fit", "target_audience_tags", "release_strategy")
    )
    if needs_enrichment:
        enrichment = await _llm_marketing_enrichment(
            db,
            song_title=song.title or "Untitled",
            primary_genre=song.primary_genre or "pop",
            artist_stage_name=artist.stage_name,
            lyric_text=song.lyric_text,
            edge_profile=getattr(artist, "edge_profile", None),
        )
        if enrichment:
            maybe_set("marketing_hook", enrichment.get("marketing_hook"))
            maybe_set("pr_angle", enrichment.get("pr_angle"))
            maybe_set("playlist_fit", enrichment.get("playlist_fit"))
            maybe_set("target_audience_tags", enrichment.get("target_audience_tags"))
            maybe_set("release_strategy", enrichment.get("release_strategy"))
            # Also update mood_tags if the generator left it empty
            if not song.mood_tags or overwrite:
                mood = enrichment.get("mood_tags")
                if isinstance(mood, list):
                    maybe_set("mood_tags", mood)

    # Apply updates
    for field, value in updates.items():
        if field in ("writers", "publishers", "playlist_fit", "target_audience_tags", "mood_tags", "territory_rights"):
            # JSONB / array fields — use SQL UPDATE so the cast happens
            # cleanly. SQLAlchemy handles list→array for Mapped[list].
            setattr(song, field, value)
        else:
            setattr(song, field, value)

    if updates:
        song.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(song)
        logger.info(
            "[metadata-projection] projected %d fields onto song %s",
            len(updates), song.song_id,
        )

    return {
        "song_id": str(song.song_id),
        "fields_projected": list(updates.keys()),
        "isrc": song.isrc,
        "master_owner": song.master_owner,
        "writers": song.writers,
        "publishers": song.publishers,
        "marketing_hook": song.marketing_hook,
        "pr_angle": song.pr_angle,
        "playlist_fit": song.playlist_fit,
        "target_audience_tags": song.target_audience_tags,
        "release_strategy": song.release_strategy,
    }
