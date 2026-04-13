"""
Pop-culture reference harvester — Part 3 of the edgy-themes pipeline.

Maintains a rolling `pop_culture_references` table of things the lyric
writer can drop into songs: TikTok sounds, viral phrases, named brands,
memes, show references, celeb moments. Every reference expires — nothing
ages worse than a stale meme.

Why LLM-powered (MVP) instead of individual scrapers:
  Building 5 separate scrapers (TikTok, Twitter, Know Your Meme,
  Billboard, Reddit) is a multi-week project with fragile selectors and
  legal questions. gpt-4o-mini has a 2024-cutoff training knowledge plus
  we can prompt it to 'imagine this is a cultural analyst writing a
  weekly briefing for songwriters'. It produces surprisingly good output
  because the model has seen millions of TikTok captions and lyrics.

  This is the same 'LLM as data extractor' pattern used in
  persona_blender and smart_prompt. We call it weekly (manual or cron),
  harvest ~20 references per run, persist them, let them decay.

  Later: swap in real scrapers for TikTok Creative Center + X trending
  as Part 3.1. The injection code won't change — same table.

Flow:
  1. POST /admin/pop-culture/refresh  (or scheduled weekly)
  2. call_llm → structured JSON of references with type, text, context,
     genres, edge_tiers, decay_weeks
  3. INSERT INTO pop_culture_references (with expires_at = NOW + decay)
  4. smart_prompt.py later SELECT-s the top-N by recency + genre match

Each reference lifecycle:
  first_seen_at → expires_at (default 90d, scraper can override)
  usage_count increments when smart_prompt picks it up
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)


SCRAPER_SYSTEM = """You are a cultural analyst writing a weekly briefing for pop songwriters at a virtual record label. Your job is to surface SPECIFIC, REFERENCEABLE pop-culture moments a lyric writer can actually name-drop in a chorus or verse this week.

Good reference = named, specific, currently-viral, edgy enough to feel of-the-moment.
Bad reference = vague category ("social media"), generic ("parties"), or stale (>18 months old).

REFERENCE TYPES (use exactly these values):
  tiktok_sound     — a song or audio clip currently going viral on TikTok
  tiktok_dance     — a named dance trend (e.g. "the Stanley Cup dance")
  tiktok_phrase    — a catchphrase from a viral creator (e.g. "I'm in my flop era")
  viral_meme       — an image/video meme format (e.g. "girl dinner", "moo deng")
  show_reference   — a current show/movie moment (e.g. "Rehearsal season 2")
  brand            — a specific brand with cultural weight RIGHT NOW (e.g. "Stanley cup", "Erewhon smoothie")
  app              — an app or feature (e.g. "Duolingo streak", "BeReal notification", "AirPods case")
  gaming           — gaming reference (e.g. "Helldivers 2", "Fortnite OG")
  celeb_moment     — a named celeb event (e.g. "Selena's CFDA dress")
  news_event       — a non-political cultural moment with broad recognition
  lyric_phrase     — a phrase from a current hit someone else's song made famous
  slang            — a word/phrase with specific gen-z/alpha currency

EDGE TIERS — tag each reference with the ones it fits:
  clean_edge     — safe for Disney/Taylor/Olivia Rodrigo — no sex, no drugs, no profanity
  flirty_edge    — Sabrina/Doja/Charli XCX zone — innuendo, flirty, bratty, sex-positive but not explicit
  savage_edge    — Doechii/Ice Spice/Central Cee — explicit allowed, named targets allowed, drugs/sex direct

GENRES — tag each reference with the genres it works in (leave empty for universal):
  pop, hip-hop, country, reggae, k-pop, r&b, indie, dance, rock, latin, afrobeats

Return ONLY valid JSON in this exact shape (no markdown fences):

{
  "references": [
    {
      "reference_type": "tiktok_phrase",
      "text": "in my villain era",
      "context": "Used to mean 'doing what's best for me even if it looks selfish'. Peaked Q4 2025, still in rotation.",
      "source": "TikTok / Twitter",
      "genres": ["pop", "hip-hop", "r&b"],
      "edge_tiers": ["flirty_edge", "savage_edge"],
      "decay_weeks": 20
    }
  ]
}

Write about 20 references per response. Mix types. Be specific — "TikTok" alone is worthless; "the corn kid autotune edit" is gold. If a reference only works in one genre, limit the genres array. If it's universal, include 3-4 genres. Decay_weeks should be 8 for fast-moving memes, 26 for brand references, 52 for genuine cultural moments."""


SCRAPER_USER_PROMPT = """Generate this week's pop-culture reference briefing. Focus on things that are:

  1. Currently viral (as of early 2026 / your knowledge cutoff extended with reasoning about momentum)
  2. Specific enough to name in a lyric without explanation
  3. Edgy enough to feel modern — skip stuff your parents would recognize
  4. Spread across at least 6 different reference_types

Write exactly 20 references. Return the JSON now."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


async def refresh_pop_culture_references(
    db: AsyncSession,
    *,
    caller: str = "pop_culture_scraper.refresh",
) -> dict[str, Any]:
    """
    Call the LLM to harvest ~20 fresh pop-culture references and insert
    them into pop_culture_references. Returns a summary of what was
    persisted.

    This is the MVP version — single LLM call with an extended context.
    When we later build dedicated scrapers for TikTok Creative Center +
    X trending + Know Your Meme, they'll feed the same table and this
    function becomes one of several data sources.
    """
    result = await llm_chat(
        db=db,
        action="pop_culture_scraper",
        messages=[
            {"role": "system", "content": SCRAPER_SYSTEM},
            {"role": "user", "content": SCRAPER_USER_PROMPT},
        ],
        caller=caller,
    )
    if not result.get("success"):
        return {
            "inserted": 0,
            "error": f"LLM call failed: {result.get('error')}",
        }

    raw = result.get("content", "")
    try:
        parsed = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as e:
        logger.error("[pop-culture] JSON parse failed: %s\n---\n%s", e, raw[:500])
        return {"inserted": 0, "error": f"LLM returned unparseable JSON: {e}"}

    refs = parsed.get("references") or []
    if not isinstance(refs, list):
        return {"inserted": 0, "error": "LLM output missing 'references' array"}

    inserted = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for ref in refs:
        if not isinstance(ref, dict):
            skipped += 1
            continue
        rtype = (ref.get("reference_type") or "").strip()
        text_val = (ref.get("text") or "").strip()
        if not rtype or not text_val:
            skipped += 1
            continue
        decay_weeks = int(ref.get("decay_weeks") or 13)
        expires_at = now + timedelta(weeks=decay_weeks)
        genres = ref.get("genres") or []
        if not isinstance(genres, list):
            genres = []
        edge_tiers = ref.get("edge_tiers") or ["flirty_edge", "savage_edge"]
        if not isinstance(edge_tiers, list) or not edge_tiers:
            edge_tiers = ["flirty_edge", "savage_edge"]

        try:
            await db.execute(
                _text("""
                    INSERT INTO pop_culture_references
                      (reference_type, text, context, source, source_url,
                       genres, edge_tiers, expires_at)
                    VALUES (:rtype, :text_val, :context, :source, :source_url,
                            :genres, :edge_tiers, :expires_at)
                """),
                {
                    "rtype": rtype,
                    "text_val": text_val,
                    "context": ref.get("context") or None,
                    "source": ref.get("source") or None,
                    "source_url": ref.get("source_url") or None,
                    "genres": genres,
                    "edge_tiers": edge_tiers,
                    "expires_at": expires_at,
                },
            )
            inserted += 1
        except Exception:
            await db.rollback()
            logger.exception("[pop-culture] insert failed for ref: %s", text_val[:60])
            skipped += 1
            continue

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("[pop-culture] commit failed")
        return {"inserted": 0, "error": "commit failed"}

    logger.info("[pop-culture] refresh complete: inserted=%d skipped=%d", inserted, skipped)
    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_offered": len(refs),
    }


async def fetch_references_for_prompt(
    db: AsyncSession,
    *,
    genre: str | None,
    edge_profile: str | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """
    Fetch a random sample of live (un-expired) references that match the
    target genre and edge profile. Used by smart_prompt.py to inject
    fresh pop-culture hooks into the lyric brief.

    - Prefers references explicitly tagged with the genre, but falls back
      to universal-tagged ones (genres = '{}') if the genre-specific pool
      is thin.
    - Filters by edge_profile if provided — a clean_edge artist never
      sees a savage_edge reference.
    - Random sample so consecutive songs don't all reuse the same hooks.
    """
    # Build filters permissively — we'd rather inject 3 broad references
    # than none.
    params: dict[str, Any] = {"limit": limit}
    where = ["expires_at > NOW()"]

    if genre:
        where.append("(:genre = ANY(genres) OR genres = '{}' OR array_length(genres, 1) IS NULL)")
        params["genre"] = genre

    if edge_profile:
        where.append(":edge = ANY(edge_tiers)")
        params["edge"] = edge_profile

    sql = f"""
        SELECT id, reference_type, text, context, genres, edge_tiers,
               usage_count, first_seen_at
        FROM pop_culture_references
        WHERE {' AND '.join(where)}
        ORDER BY RANDOM()
        LIMIT :limit
    """
    result = await db.execute(_text(sql), params)
    rows = result.fetchall()
    return [
        {
            "id": str(row[0]),
            "type": row[1],
            "text": row[2],
            "context": row[3],
            "genres": row[4] or [],
            "edge_tiers": row[5] or [],
            "usage_count": row[6] or 0,
        }
        for row in rows
    ]


async def mark_references_used(
    db: AsyncSession, reference_ids: list[str]
) -> None:
    """Bump usage_count + last_used_at on references that actually ended
    up in the smart prompt. Not strictly necessary yet but useful later
    for retiring stale references or surfacing 'most-used this month'."""
    if not reference_ids:
        return
    try:
        await db.execute(
            _text("""
                UPDATE pop_culture_references
                SET usage_count = usage_count + 1,
                    last_used_at = NOW()
                WHERE id = ANY(:ids::uuid[])
            """),
            {"ids": reference_ids},
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("[pop-culture] usage bump failed")


def format_references_block(
    refs: list[dict[str, Any]],
    edge_profile: str | None,
) -> str:
    """Turn a reference list into a compact block the lyric LLM can cite."""
    if not refs:
        return "POP_CULTURE_HOOKS (none available — use your own edge)\n"
    lines = [
        "POP_CULTURE_HOOKS — live references from our weekly culture briefing.",
        "Use 1-2 of these where they fit naturally. Do NOT force-fit. Do NOT",
        "explain them in the lyric — if a reference needs explanation it's",
        "already dead. Specific > clever > generic.",
        "",
    ]
    for i, ref in enumerate(refs, 1):
        ctx = f" — {ref.get('context')}" if ref.get("context") else ""
        lines.append(
            f"  {i}. [{ref.get('type')}] \"{ref.get('text')}\"{ctx}"
        )
    if edge_profile:
        lines.append("")
        lines.append(f"Edge profile: {edge_profile} — match the tone accordingly.")
    return "\n".join(lines)
