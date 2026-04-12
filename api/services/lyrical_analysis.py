"""
LLM-powered lyrical analysis — Layer 6 of the Breakout Analysis Engine.

For each genre with breakout events, gathers the lyrics of breakout
tracks (Set A) and baseline tracks (Set B), then asks an LLM to compare:
  - What themes dominate breakouts vs baseline?
  - Which themes are underserved (in breakouts but rare in baseline)?
  - Which are overserved (saturated in baseline, absent from breakouts)?
  - Structural patterns (verse/chorus repetition, tone)
  - One actionable insight

Output cached in genre_lyrical_analysis. Runs weekly to keep LLM costs
low (~$0.02/week at our scale per the PRD §4 cost analysis).

See planning/PRD/breakoutengine_prd.md Layer 3 for the full design.
"""
from __future__ import annotations

import json
import logging
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.breakout_event import BreakoutEvent
from api.models.genre_lyrical_analysis import GenreLyricalAnalysis
from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
MIN_BREAKOUT_LYRICS = 5
MIN_BASELINE_LYRICS = 10
MAX_BREAKOUT_LYRICS = 10
MAX_BASELINE_LYRICS = 20
MAX_LYRICS_CHARS = 2000  # truncate each lyric to keep prompt small


LYRICAL_ANALYSIS_SYSTEM = """You are a music industry A&R analyst. Your job is to compare two sets of song lyrics from the same genre and identify what makes the breakout hits different from the baseline. Return ONLY valid JSON, no markdown."""

LYRICAL_ANALYSIS_PROMPT_TEMPLATE = """GENRE: {genre}

SET A — BREAKOUT HITS ({breakout_count} tracks that significantly outperformed their peers):
{breakout_lyrics}

SET B — BASELINE ({baseline_count} typical tracks in this genre that did not break out):
{baseline_lyrics}

Compare the two sets and return ONLY this JSON structure (no markdown fences, no commentary):
{{
  "breakout_themes": ["theme1", "theme2", "theme3"],
  "baseline_themes": ["theme1", "theme2", "theme3"],
  "underserved_themes": ["themes present in breakouts but RARE in baseline"],
  "overserved_themes": ["themes saturated in baseline but ABSENT from breakouts"],
  "structural_patterns": {{
    "avg_verse_lines": 4,
    "chorus_repetition": "high|medium|low",
    "talk_singing": false,
    "narrative_vs_abstract": "narrative|abstract|mixed"
  }},
  "vocabulary_tone": "raw|polished|conversational|poetic",
  "key_insight": "one sentence: the single most actionable lyrical difference for songwriters"
}}"""


async def analyze_all_genres(
    db: AsyncSession,
    *,
    only_genre: str | None = None,
) -> dict[str, int]:
    """
    Sweep all genres with sufficient breakout + baseline lyrics, run
    LLM analysis on each, and cache results in genre_lyrical_analysis.
    """
    today = date.today()
    window_start = today - timedelta(days=WINDOW_DAYS)

    stats = {
        "genres_processed": 0,
        "analyses_completed": 0,
        "skipped_low_data": 0,
        "errors": 0,
        "elapsed_ms": 0,
    }
    started = datetime.now(timezone.utc)

    # Get genres with breakout events in window
    if only_genre:
        genre_ids = [only_genre]
    else:
        result = await db.execute(
            select(BreakoutEvent.genre_id)
            .where(BreakoutEvent.detection_date >= window_start)
            .distinct()
        )
        genre_ids = [row[0] for row in result.fetchall()]

    for genre_id in genre_ids:
        stats["genres_processed"] += 1

        breakout_lyrics = await _get_breakout_lyrics(db, genre_id, window_start)
        baseline_lyrics = await _get_baseline_lyrics(db, genre_id, breakout_lyrics)

        if len(breakout_lyrics) < MIN_BREAKOUT_LYRICS or len(baseline_lyrics) < MIN_BASELINE_LYRICS:
            stats["skipped_low_data"] += 1
            continue

        # Truncate and format
        breakout_text = _format_lyrics_set(breakout_lyrics[:MAX_BREAKOUT_LYRICS])
        baseline_text = _format_lyrics_set(baseline_lyrics[:MAX_BASELINE_LYRICS])

        prompt = LYRICAL_ANALYSIS_PROMPT_TEMPLATE.format(
            genre=genre_id,
            breakout_count=len(breakout_lyrics),
            baseline_count=len(baseline_lyrics),
            breakout_lyrics=breakout_text,
            baseline_lyrics=baseline_text,
        )

        # Call LLM via the shared provider abstraction
        result = await llm_chat(
            db=db,
            action="lyrical_analysis",
            messages=[
                {"role": "system", "content": LYRICAL_ANALYSIS_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            caller="lyrical_analysis.analyze_all_genres",
            context_id=f"genre={genre_id}",
            override_max_tokens=1500,
        )

        if not result["success"]:
            logger.warning(
                "[lyrical-analysis] LLM failed for genre=%s: %s",
                genre_id, result.get("error"),
            )
            stats["errors"] += 1
            continue

        # Parse the JSON response
        try:
            analysis_json = _parse_llm_json(result["content"])
        except Exception as exc:
            logger.warning(
                "[lyrical-analysis] could not parse JSON for genre=%s: %s",
                genre_id, exc,
            )
            stats["errors"] += 1
            continue

        # Upsert: delete existing for this genre+window_end, then insert
        await db.execute(
            text("""
                DELETE FROM genre_lyrical_analysis
                WHERE genre_id = :gid AND window_end = :wend
            """),
            {"gid": genre_id, "wend": today},
        )
        row = GenreLyricalAnalysis(
            id=uuid_mod.uuid4(),
            genre_id=genre_id,
            window_end=today,
            breakout_count=len(breakout_lyrics),
            baseline_count=len(baseline_lyrics),
            analysis_json=analysis_json,
        )
        db.add(row)
        stats["analyses_completed"] += 1

    await db.commit()
    stats["elapsed_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info("[lyrical-analysis] %s", stats)
    return stats


def _format_lyrics_set(lyrics_rows: list[dict[str, str]]) -> str:
    """Format a list of lyrics for inclusion in the LLM prompt."""
    blocks = []
    for i, row in enumerate(lyrics_rows, 1):
        title = row.get("title") or "Unknown"
        artist = row.get("artist_name") or "Unknown"
        text = (row.get("lyrics_text") or "")[:MAX_LYRICS_CHARS]
        blocks.append(f"[{i}] {artist} — {title}\n{text}")
    return "\n\n---\n\n".join(blocks)


def _parse_llm_json(content: str) -> dict[str, Any]:
    """
    Strip any markdown fences and parse JSON from the LLM response.
    Tolerates models that wrap JSON in ```json fences despite our
    explicit "no markdown" instruction.
    """
    s = content.strip()
    if s.startswith("```"):
        # remove first fence line and trailing fence
        lines = s.split("\n")
        s = "\n".join(line for line in lines if not line.strip().startswith("```"))
    return json.loads(s.strip())


async def _get_breakout_lyrics(
    db: AsyncSession, genre_id: str, since: date
) -> list[dict[str, str]]:
    """Lyrics for breakout tracks in this genre (highest-scoring first)."""
    result = await db.execute(text("""
        SELECT t.title, a.name AS artist_name, tl.lyrics_text
        FROM breakout_events be
        JOIN tracks t ON t.id = be.track_id
        LEFT JOIN artists a ON a.id = t.artist_id
        JOIN track_lyrics tl ON tl.track_id = t.id
        WHERE be.genre_id = :gid
          AND be.detection_date >= :since
        ORDER BY be.breakout_score DESC
        LIMIT :lim
    """), {"gid": genre_id, "since": since, "lim": MAX_BREAKOUT_LYRICS})
    return [
        {"title": row[0], "artist_name": row[1], "lyrics_text": row[2]}
        for row in result.fetchall()
    ]


async def _get_baseline_lyrics(
    db: AsyncSession, genre_id: str, breakout_lyrics: list[dict]
) -> list[dict[str, str]]:
    """Lyrics for non-breakout tracks in this genre (random sample)."""
    # Build a set of titles to exclude (rough dedupe by title)
    exclude_titles = {r.get("title") for r in breakout_lyrics if r.get("title")}

    result = await db.execute(text("""
        SELECT t.title, a.name AS artist_name, tl.lyrics_text
        FROM tracks t
        LEFT JOIN artists a ON a.id = t.artist_id
        JOIN track_lyrics tl ON tl.track_id = t.id
        WHERE :gid = ANY(t.genres)
          AND NOT EXISTS (
              SELECT 1 FROM breakout_events be
              WHERE be.track_id = t.id AND be.genre_id = :gid
          )
        ORDER BY random()
        LIMIT :lim
    """), {"gid": genre_id, "lim": MAX_BASELINE_LYRICS})

    return [
        {"title": row[0], "artist_name": row[1], "lyrics_text": row[2]}
        for row in result.fetchall()
        if row[0] not in exclude_titles
    ]
