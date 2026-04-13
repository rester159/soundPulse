"""
T-127-lite — LLM persona blender.

Takes a natural-language description of an artist and a target genre,
returns a complete ai_artists shape (all 6 DNAs + audience tags) via
Groq llama-3.3-70b.

This is a lightweight shortcut around the full §18-19 reference-artist
research pipeline (T-120..T-126 + BlackTip scraping). Use it to seed
new artists directly from a prompt when reference-artist enrichment
isn't available yet.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a creative director for SoundPulse Records, an AI music label.

Given a short description of an artist and a target genre, produce a complete
artist persona as a JSON object matching the schema below. Every field is
mandatory. Be specific and internally consistent — a gravelly-voiced outlaw
country singer should not have a "cute K-pop" visual direction.

Schema (return EXACTLY this shape, valid JSON, no markdown fences, no prose):

{
  "stage_name": "string — marketable, pronounceable, googleable",
  "legal_name": "string — often same as stage_name but can differ",
  "primary_genre": "string — echoes the target genre",
  "adjacent_genres": ["string", "string", "string"],
  "influences": ["string (real artist name)", "..."],
  "anti_influences": ["string (real artist name to explicitly NOT sound like)"],
  "audience_tags": ["string like gen_z | rural | female_lean | latin | ..."],
  "content_rating": "clean | mild | explicit",
  "voice_dna": {
    "timbre_core": "one-line description of vocal timbre",
    "range_estimate": "e.g. A2-E4 chest, falsetto to A4",
    "delivery_style": ["string", "string"],
    "phrasing_density": "low | medium | high",
    "accent_pronunciation": "e.g. US Midwestern, light Spanish coloration",
    "autotune_profile": "none | light | medium | heavy",
    "adlib_profile": ["string", "string"]
  },
  "visual_dna": {
    "face_description": "oval face, sharp eyebrows, ...",
    "body_presentation": "lean / tall / athletic / ...",
    "hair_signature": "dark wavy cropped cut",
    "color_palette": ["#hex", "#hex", "#hex"],
    "art_direction": "moody urban night photography",
    "fashion_style_summary": "latin urban streetwear with luxury accents"
  },
  "fashion_dna": {
    "core_garments": ["string", "string"],
    "accessories": ["string"],
    "footwear": ["string"],
    "avoid": ["string"]
  },
  "lyrical_dna": {
    "recurring_themes": ["string", "string", "string"],
    "vocab_level": "simple | conversational | poetic | abstract",
    "perspective": "first_person | narrative | omniscient",
    "motifs": ["string", "string"],
    "rhyme_density": "low | medium | high",
    "explicit_default": false,
    "language": "en"
  },
  "persona_dna": {
    "backstory": "2-3 sentence origin story",
    "personality_traits": ["string", "string"],
    "social_voice": "short description of posting style",
    "controversy_stance": "how they handle public controversy"
  },
  "social_dna": {
    "posting_cadence_per_day": 2,
    "preferred_video_length_seconds": 15,
    "hashtag_strategy": "string",
    "engagement_style": "string"
  }
}

Do NOT invent a real person. The stage_name must not match any existing
famous artist."""


def _strip_code_fences(text: str) -> str:
    """Some LLMs wrap JSON in ```json ... ``` fences. Strip them."""
    text = text.strip()
    # Remove opening fence
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


async def blend_persona(
    *,
    db: AsyncSession | None,
    description: str,
    target_genre: str,
    caller: str = "persona_blender",
) -> dict[str, Any]:
    """
    Produce a complete ai_artists-shaped dict from a short description.

    Raises ValueError if the LLM returns unparseable JSON.
    """
    user_prompt = (
        f"Target genre: {target_genre}\n\n"
        f"Description: {description}\n\n"
        f"Return the JSON persona now."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    result = await llm_chat(
        db=db,
        action="persona_blender",
        messages=messages,
        caller=caller,
        metadata={"target_genre": target_genre},
    )
    raw = result.get("content", "")
    cleaned = _strip_code_fences(raw)

    try:
        persona = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("[persona_blender] JSON parse failed: %s\n---\n%s", e, cleaned[:500])
        raise ValueError(f"LLM returned unparseable JSON: {e}")

    # Minimal validation — every field the ai_artists table requires
    for key in ("stage_name", "legal_name", "primary_genre", "voice_dna", "visual_dna"):
        if key not in persona:
            raise ValueError(f"persona missing required field: {key}")

    # Coerce lists that the LLM may return as strings
    for list_key in ("adjacent_genres", "influences", "anti_influences",
                     "audience_tags"):
        if list_key in persona and isinstance(persona[list_key], str):
            persona[list_key] = [s.strip() for s in persona[list_key].split(",") if s.strip()]

    return persona
