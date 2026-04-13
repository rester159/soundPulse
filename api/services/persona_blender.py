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


SYSTEM_PROMPT = """You are a creative director for SoundPulse Records, an AI music label. You pick names like a top-tier A&R person at Columbia or XL Recordings — realistic, professional, and marketable.

Given a short description of an artist and a target genre, produce a complete
artist persona as a JSON object matching the schema below. Every field is
mandatory. Be specific and internally consistent — a gravelly-voiced outlaw
country singer should not have a "cute K-pop" visual direction.

GENRE-ACCURATE DEMOGRAPHICS — READ THIS CAREFULLY:

  The artist's ethnicity, age range, and visual presentation MUST reflect
  the genre's cultural home and the demographics of the reference artists
  listed below, UNLESS the user's description explicitly overrides it.

  Default heritage by genre (when the description doesn't specify):
    K-pop / K-R&B               → Korean, or Korean-American/Korean diaspora
    J-pop / city-pop            → Japanese, or Japanese diaspora
    C-pop / Mandopop            → Chinese, Taiwanese, or Hong Kong
    Afrobeats / Amapiano        → Nigerian, Ghanaian, South African, West African
    Reggae / dancehall          → Jamaican, Afro-Caribbean
    Reggaeton / Latin urban     → Puerto Rican, Dominican, Colombian, Mexican
    Bollywood / Desi hip-hop    → Indian, Pakistani, South Asian diaspora
    Bhangra / Punjabi pop       → Punjabi, Sikh, South Asian
    Flamenco / Latin pop        → Spanish, Latin American
    Highlife / Azonto           → Ghanaian, West African
    Arabic pop / Khaleeji       → Levantine, Gulf Arab, North African
    Country / Americana         → American, typically white rural or Black Southern
    Bluegrass / Appalachian     → White Appalachian American
    Hip-hop / trap / drill      → Black American, or matches the specific scene
                                   (UK drill → Black British; Brazilian funk → Afro-Brazilian)
    R&B / neo-soul              → predominantly Black American, mixed-heritage
    Indie / bedroom pop         → globally diverse — follow reference artists
    Electronic / techno / house → globally diverse — follow reference artists

  If reference artists are provided below, your ethnicity_heritage MUST be
  consistent with theirs. If the reference list is empty, use the defaults
  above. Never output a generic "ambiguous" or "mixed" heritage unless the
  genre demands it.

  Age range: 20-30 is typical for breakthrough AI artists. Go younger
  (18-22) for K-pop/drill/hyperpop; older (28-40) for country/reggae/jazz.
  Match the genre's typical breakthrough age.

  Gender presentation: pick "female", "male", or "non_binary" based on the
  description; if unspecified, match the majority presentation of the
  reference artists, then default to whatever creates a more distinctive
  persona in the current roster.

STAGE NAME RULES — THIS IS CRITICAL. Read carefully:

  GOOD names (use these as a quality bar):
    Pop/indie:   Clairo, Mitski, Phoebe Bridgers, Gracie Abrams, Maisie Peters,
                 Beabadoobee, Faye Webster, Men I Trust, Still Woozy
    Hip-hop:     Ken Carson, Yeat, Ice Spice, Doechii, BabyTron, NLE Choppa,
                 Destroy Lonely, Lil Tecca
    Reggae:      Koffee, Protoje, Chronixx, Lila Iké, Masicka, Popcaan,
                 Vybz Kartel, Kabaka Pyramid, Samory I
    Country:     Zach Bryan, Tyler Childers, Sierra Ferrell, Ian Noe,
                 Margo Price, Kassi Ashton
    R&B:         SZA, Summer Walker, Kehlani, Ari Lennox, Snoh Aalegra,
                 UMI, Arlo Parks

  BAD names (these are DISQUALIFYING — do NOT generate anything like these):
    ❌ "Rasta Breeze" — meme-y, literal, sounds like a beer ad
    ❌ "Beat King" — generic, on-the-nose
    ❌ "DJ SunVibes" — cliché, dated
    ❌ "MC Flow" — lazy abbreviation pattern
    ❌ "Lil Shadow" — overused "Lil" prefix
    ❌ "The Sunshine Collective" — overly wholesome group name
    ❌ "Melody Rivers" — too perfect, sounds like a soap opera
    ❌ Any name that literally describes the genre

  Rules that ALWAYS apply:
    - Sound like a real person's name OR a pronounceable made-up word
    - 1-3 words max, typically 1-2
    - Googleable — avoid collisions with famous existing artists
    - Must pass the "would this work on a Spotify editorial cover?" test
    - Reggae names often use Jamaican first names (Kofi, Jaden, Tafari,
      Marcia) with or without a short stylized surname; avoid "Rasta X"
      or "Jah X" which are parodies
    - Pop/indie names often use real-sounding lowercase or single names
      (like "clairo", "mitski")
    - Hip-hop can stylize but must not default to "Lil/Young/Big X"
    - Country names use Americana-sounding first + last names

You must return FIVE distinct stage_name_alternatives in the output. All five
must pass the quality bar above. The top-level stage_name field is the first
choice (the default); the CEO will pick one of the 5 to finalize.

Schema (return EXACTLY this shape, valid JSON, no markdown fences, no prose):

{
  "stage_name_alternatives": ["string", "string", "string", "string", "string"],
  "stage_name": "string — equals stage_name_alternatives[0], your top pick",
  "legal_name": "string — real-sounding legal name in the artist's own language/script convention (e.g. Korean-romanized for K-pop, Spanish for reggaeton, Jamaican-English for reggae)",
  "primary_genre": "string — echoes the target genre",
  "adjacent_genres": ["string", "string", "string"],
  "influences": ["string (real artist name)", "..."],
  "anti_influences": ["string (real artist name to explicitly NOT sound like)"],
  "audience_tags": ["string like gen_z | rural | female_lean | latin | ..."],
  "content_rating": "clean | mild | explicit",
  "age": 24,
  "gender_presentation": "female | male | non_binary",
  "ethnicity_heritage": "string — SPECIFIC heritage that matches the genre and reference artists (e.g. 'Korean', 'Jamaican', 'Nigerian Yoruba', 'Mexican-American', 'Punjabi', 'Black American / Southern US'). Do NOT write vague answers like 'mixed' or 'international'.",
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
    "core_garments": ["string (2-4 specific hero pieces, not generic 'pants')"],
    "fabric_inspirations": ["string (e.g. 'hanbok silk', 'Japanese denim', 'leather', 'pvc', 'lace', 'metallic mesh', 'cashmere', 'washed cotton') — at least 2"],
    "silhouette": "string — e.g. 'oversized layered streetwear', 'tailored slim cut', 'cropped y2k', 'draped avant-garde', 'utility workwear'",
    "accessories": ["string (2-4 specific items — earrings, chains, bags, hats, gloves, belts)"],
    "footwear": ["string"],
    "styling_mood": "string — one-line fashion editorial mood, e.g. 'moody cyberpunk minimalism', 'sun-bleached Americana', 'Seoul 4th-gen K-pop pastel futurism', 'Kingston dancehall luxe'",
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
    avoid_stage_names: list[str] | None = None,
    reference_artists_block: str | None = None,
    reference_artist_names: list[str] | None = None,
) -> dict[str, Any]:
    """
    Produce a complete ai_artists-shaped dict from a short description.

    Raises ValueError if the LLM returns unparseable JSON.

    `avoid_stage_names` — existing roster names the LLM must NOT reuse.
    `reference_artists_block` — pre-formatted string describing current
      top-momentum artists in the target genre. Grounds the LLM in real
      data vs pre-training confabulation.
    `reference_artist_names` — list of the actual names that were passed
      in the block; goes into the persona's `derived_from` field so we
      can trace which references drove the output.
    """
    avoid_block = ""
    if avoid_stage_names:
        sample = avoid_stage_names[:30]  # prompt budget
        avoid_block = (
            f"\n\nDO NOT use any of these stage names (they're already in our roster): "
            f"{', '.join(sample)}.\n"
            f"Pick something distinctive that has never been used before."
        )

    reference_block = ""
    if reference_artists_block:
        reference_block = f"\n\n{reference_artists_block}\n"

    user_prompt = (
        f"Target genre: {target_genre}\n\n"
        f"Description: {description}"
        f"{reference_block}"
        f"{avoid_block}\n\n"
        f"Return the JSON persona now. In the `influences` field, cite at "
        f"least 2-3 of the reference artists above (if provided) and add any "
        f"additional real artists from your knowledge that fit the direction."
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

    # Demographics: hard-require heritage so the portrait has something to
    # anchor on. Gender + age are softer — default if missing.
    if not (persona.get("ethnicity_heritage") or "").strip():
        raise ValueError(
            "persona missing ethnicity_heritage — portrait will be ungrounded. "
            "Retry the blend."
        )
    if not persona.get("gender_presentation"):
        persona["gender_presentation"] = "female"  # arbitrary but deterministic
    if not isinstance(persona.get("age"), int):
        try:
            persona["age"] = int(persona.get("age") or 25)
        except (TypeError, ValueError):
            persona["age"] = 25

    # Ensure stage_name_alternatives is present + non-empty; if the LLM
    # skipped it, synthesize from the top stage_name so downstream code
    # can still show "options" even if it's a list of 1.
    alts = persona.get("stage_name_alternatives")
    if not isinstance(alts, list) or not alts:
        persona["stage_name_alternatives"] = [persona["stage_name"]]
    else:
        # De-duplicate while preserving order + ensure stage_name is first
        seen = set()
        unique = []
        for n in [persona["stage_name"]] + list(alts):
            if n and n not in seen:
                seen.add(n)
                unique.append(n)
        persona["stage_name_alternatives"] = unique[:5]

    # Coerce lists that the LLM may return as strings
    for list_key in ("adjacent_genres", "influences", "anti_influences",
                     "audience_tags"):
        if list_key in persona and isinstance(persona[list_key], str):
            persona[list_key] = [s.strip() for s in persona[list_key].split(",") if s.strip()]

    # Tag the persona with the references used so callers can trace
    # which real-world artists drove the output
    if reference_artist_names:
        persona["derived_from"] = {
            "reference_artists": reference_artist_names,
            "method": "chartmetric_top_momentum",
            "blender_version": "lite_v2",
        }

    return persona
