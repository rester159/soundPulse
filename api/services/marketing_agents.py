"""
Marketing agents (T-225+, PRD §37) — press release + social media content generation.

These are PURE LLM agents — no external credentials required to run.
They transform a qa_passed song + its metadata into ready-to-publish
content artifacts:

  press_release_agent: Writes a 300-400 word press release in AP style
    with a one-line headline, dateline, body paragraphs, and boilerplate.
    Stored in marketing_artifacts.

  social_media_agent: Generates 5-10 platform-specific captions (TikTok,
    Instagram, X, YouTube Shorts description) with hashtags + call to
    action. Each platform gets its own voice.

Both agents run via the existing llm_chat pipeline (Gemini flash, falls
back to whatever's configured). Failure modes are caught and stored as
failed marketing_artifacts rows so the CEO sees what needs manual
intervention.

For the external_submission_agent stub registry, these two register as
live adapters — unlike DistroKid / BMI / etc which stay stubbed until
credentials + adapter bodies land.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)


async def generate_press_release(
    db: AsyncSession,
    *,
    song,
    artist,
) -> dict[str, Any]:
    """
    Generate a publishable press release for a song. Returns the raw
    markdown + structured fields (headline, dateline, lede, body,
    boilerplate, quote).
    """
    system = (
        "You are a veteran music publicist writing AP-style press "
        "releases for an indie label. Every release must hit these beats: "
        "(1) attention-grabbing headline under 12 words, "
        "(2) dateline with city + date, "
        "(3) lede sentence with the WHO + WHAT + WHY NOW, "
        "(4) two body paragraphs with specific details and one quote "
        "attributed to the artist, "
        "(5) short boilerplate paragraph about SoundPulse Records. "
        "Never use generic 'emerging artist' language — be specific to "
        "this song and this persona. Return ONLY valid JSON."
    )
    themes = ", ".join((song.lyric_themes or [])[:5]) if song.lyric_themes else "unspecified"
    user = f"""Song: "{song.title}"
Artist: {artist.stage_name} ({artist.primary_genre})
Marketing hook: {song.marketing_hook or 'N/A'}
PR angle: {song.pr_angle or 'N/A'}
Audience: {', '.join((song.target_audience_tags or [])[:5])}
Themes: {themes}
Content rating: {song.content_rating}

Lyric excerpt:
{(song.lyric_text or '')[:1200]}

Return JSON:
{{
  "headline": "...",
  "dateline": "NEW YORK, {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
  "lede": "one-sentence who/what/why-now",
  "body_paragraphs": ["para 1", "para 2"],
  "artist_quote": "a one-sentence quote the artist could plausibly say",
  "boilerplate": "SoundPulse Records is an AI-native virtual label...",
  "hashtags": ["#...", "#..."],
  "call_to_action": "one line"
}}"""

    try:
        result = await llm_chat(
            db=db,
            action="smart_prompt_generation",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            caller="marketing_agents.press_release",
        )
        if not result.get("success"):
            return {"error": f"llm_chat failed: {result.get('error')}"}
        raw = (result.get("content") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
    except Exception as e:
        logger.exception("[press-release-agent] failed")
        return {"error": f"{type(e).__name__}: {e}"}

    # Compose the plain-text press release for easy copy-paste
    body = "\n\n".join(parsed.get("body_paragraphs", []))
    plain = (
        f"FOR IMMEDIATE RELEASE\n\n"
        f"{parsed.get('headline', '').upper()}\n\n"
        f"{parsed.get('dateline', '')} — {parsed.get('lede', '')}\n\n"
        f"{body}\n\n"
        f"\"{parsed.get('artist_quote', '')}\" — {artist.stage_name}\n\n"
        f"{parsed.get('boilerplate', '')}\n\n"
        f"{parsed.get('call_to_action', '')}\n"
        f"{' '.join(parsed.get('hashtags', []))}"
    )
    return {
        "structured": parsed,
        "plain_text": plain,
    }


async def generate_social_media_pack(
    db: AsyncSession,
    *,
    song,
    artist,
) -> dict[str, Any]:
    """
    Generate platform-specific captions. Returns one per platform with
    its own voice + hashtag strategy.
    """
    system = (
        "You are a social media manager for SoundPulse Records. You "
        "write captions that match each platform's native voice — TikTok "
        "is bratty and short, Instagram is aspirational with specific "
        "imagery, X (Twitter) is one-line and punchy, YouTube Shorts "
        "description is slightly longer with SEO keywords. Never generic. "
        "Return ONLY valid JSON."
    )
    user = f"""Song: "{song.title}"
Artist: {artist.stage_name} ({artist.primary_genre})
Edge profile: {getattr(artist, 'edge_profile', 'flirty_edge')}
Marketing hook: {song.marketing_hook or 'N/A'}
Audience: {', '.join((song.target_audience_tags or [])[:5])}
Mood: {', '.join((song.mood_tags or [])[:5])}

Lyric hook (first 10 lines):
{chr(10).join((song.lyric_text or '').splitlines()[:10])}

Return JSON:
{{
  "tiktok": {{"caption": "...", "hashtags": ["#...", "#..."], "dance_prompt": "optional: suggest a dance challenge"}},
  "instagram_feed": {{"caption": "...", "hashtags": ["#..."]}},
  "instagram_reel": {{"caption": "...", "hashtags": ["#..."]}},
  "x_twitter": {{"post": "< 240 chars with one hashtag"}},
  "youtube_shorts": {{"title": "< 60 chars", "description": "< 300 words", "tags": ["..."]}},
  "threads": {{"post": "casual conversational"}},
  "posting_order": ["tiktok_first", "then_instagram_reel", "then_youtube_shorts", "x_same_day"]
}}"""

    try:
        result = await llm_chat(
            db=db,
            action="smart_prompt_generation",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            caller="marketing_agents.social_pack",
        )
        if not result.get("success"):
            return {"error": f"llm_chat failed: {result.get('error')}"}
        raw = (result.get("content") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return {"pack": json.loads(raw)}
    except Exception as e:
        logger.exception("[social-media-agent] failed")
        return {"error": f"{type(e).__name__}: {e}"}


# ----------------------------------------------------------------------
# Register these agents as LIVE adapters on the external_submission_agent
# dispatcher. Unlike DistroKid/BMI/etc which stay stubbed, these two run
# for real — they produce marketing_artifacts rows with the generated
# content and flip status to 'submitted' on success.
# ----------------------------------------------------------------------

from api.services.external_submission_agent import register_adapter


@register_adapter("press_release_agent")
async def _adapter_press_release(db, subject_row, target):
    """Real adapter for the press_release_agent target — LIVE, no creds."""
    from api.models.ai_artist import AIArtist
    artist = (
        await db.execute(
            __import__("sqlalchemy").select(AIArtist).where(
                AIArtist.artist_id == subject_row.primary_artist_id
            )
        )
    ).scalar_one_or_none() if hasattr(subject_row, "primary_artist_id") else None

    if artist is None:
        return ("failed", None, {"error": "subject has no primary_artist_id"})

    result = await generate_press_release(db, song=subject_row, artist=artist)
    if "error" in result:
        return ("failed", None, result)

    # Store the artifact. Table is created lazily if missing.
    external_id = f"press_release_{subject_row.song_id}"
    return (
        "submitted",
        external_id,
        {
            "headline": result["structured"].get("headline"),
            "plain_text_length": len(result["plain_text"]),
            "full_text": result["plain_text"],
            "structured": result["structured"],
        },
    )


@register_adapter("social_media_agent")
async def _adapter_social_media(db, subject_row, target):
    """Real adapter for the social_media_agent target — LIVE, no creds."""
    from sqlalchemy import select as _select
    from api.models.ai_artist import AIArtist
    artist = (
        await db.execute(
            _select(AIArtist).where(AIArtist.artist_id == subject_row.primary_artist_id)
        )
    ).scalar_one_or_none() if hasattr(subject_row, "primary_artist_id") else None
    if artist is None:
        return ("failed", None, {"error": "subject has no primary_artist_id"})

    result = await generate_social_media_pack(db, song=subject_row, artist=artist)
    if "error" in result:
        return ("failed", None, result)

    external_id = f"social_pack_{subject_row.song_id}"
    return (
        "submitted",
        external_id,
        {"social_pack": result.get("pack", {})},
    )
