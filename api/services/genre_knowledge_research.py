"""
Knowledge-only genre blueprint research (#29).

The smart_prompt service refuses to run when a genre has zero breakout
events in the last 30 days — that's correct for the data-driven path,
but it leaves long-tail genres (hip-hop.boom-bap.east-coast,
country.bluegrass, etc.) unable to generate a base blueprint.

This module fills the gap. Given a genre id, it asks an LLM to fill in
every blueprint field from general music knowledge alone — sonic
targets, recurring themes, vocabulary tone, audience, voice
requirements, production references. No breakout data, no recent
pop-culture references; just a faithful description of the genre.

The output is a dict matching the blueprint column shape so the caller
can persist it directly as a base blueprint (is_genre_default=true).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a veteran A&R + ethnomusicologist at SoundPulse Records. The user asks you to describe a music genre well enough that an automated music-generation pipeline can produce songs in that genre. Output ONLY a JSON object matching this exact shape:

{
  "target_themes": ["..."],            // 3-6 recurring lyrical themes for this genre
  "avoid_themes": ["..."],             // 1-3 themes that DON'T fit this genre
  "vocabulary_tone": "...",            // e.g. "conversational gen-z", "outlaw classic", "abstract poetic"
  "target_audience_tags": ["..."],     // 2-4 audience descriptors, e.g. "gen_z", "diaspora", "millennial_alt"
  "voice_requirements": {              // free-form description of the typical vocal direction
    "description": "..."
  },
  "target_tempo": 120,                 // typical BPM (integer, midpoint of the genre's range)
  "target_energy": 0.75,               // 0..1
  "target_danceability": 0.65,         // 0..1
  "target_valence": 0.55,              // 0..1, musical positivity
  "target_acousticness": 0.15,         // 0..1, 0=fully electronic, 1=acoustic
  "production_notes": "...",           // 1-2 sentences of production direction (instrumentation, mix style)
  "reference_track_descriptors": [     // 2-4 reference feels (NOT actual track titles)
    "..."
  ]
}

CRITICAL
  - Output ONLY the JSON object. No prose before or after, no markdown fences.
  - Use general music knowledge — you are NOT given recent breakout data.
  - For sub-subgenres (e.g. "hip-hop.boom-bap.east-coast"), describe THAT specific lineage. Do not generalize up to the parent.
  - Numeric fields use the Spotify audio-features convention (0..1 floats), tempo in BPM.
  - reference_track_descriptors are FEEL descriptors like "early 90s Wu-Tang sparseness with grimy sample loops", NOT actual track titles or artist names.
"""


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


async def research_genre_blueprint(
    db: AsyncSession,
    *,
    genre_id: str,
    web_context: str | None = None,
) -> dict[str, Any]:
    """LLM research for a genre. Returns a dict with the blueprint
    columns filled in, or {"error": "..."} on failure.

    `web_context`, if provided, is real article text fetched from
    Wikipedia (or BlackTip browser research) that grounds the LLM in
    accurate, current information instead of leaning on training data
    alone.

    The caller is expected to persist the output as a SongBlueprint with
    primary_genre=genre_id, is_genre_default=true.
    """
    if not genre_id or not genre_id.strip():
        return {"error": "genre_id is required"}

    grounding = ""
    if web_context and web_context.strip():
        grounding = (
            "\n\nUSE THE FOLLOWING SOURCE TEXT AS YOUR PRIMARY GROUND TRUTH "
            "for production traits, regional roots, era, and conventions. "
            "Where it conflicts with your training memory, prefer the source.\n\n"
            "--- SOURCE TEXT ---\n"
            f"{web_context.strip()[:6000]}\n"
            "--- END SOURCE ---"
        )

    user = f"""Describe the genre id "{genre_id.strip()}" as a JSON blueprint following the schema in the system prompt.{grounding}

Return only the JSON now."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]

    result = await llm_chat(
        db=db,
        # Reuse the existing slot — same model tier, same logging.
        action="smart_prompt_generation",
        messages=messages,
        caller="genre_knowledge_research.research_genre_blueprint",
        context_id=f"genre={genre_id}",
    )
    if not result.get("success"):
        return {"error": f"llm_chat failed: {result.get('error')}"}

    raw = (result.get("content") or "").strip()
    try:
        parsed = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as exc:
        logger.exception("[genre-research] JSON parse failed for genre=%s", genre_id)
        return {"error": f"LLM returned unparseable JSON: {exc}", "raw": raw[:500]}

    if not isinstance(parsed, dict):
        return {"error": "LLM response was not a JSON object", "raw": raw[:500]}

    # Coerce numerics defensively — LLMs sometimes return them as strings.
    for k in ("target_tempo",):
        v = parsed.get(k)
        if isinstance(v, str):
            try: parsed[k] = float(v)
            except ValueError: parsed[k] = None
    for k in ("target_energy", "target_danceability", "target_valence", "target_acousticness"):
        v = parsed.get(k)
        if isinstance(v, str):
            try: parsed[k] = float(v)
            except ValueError: parsed[k] = None

    return parsed
