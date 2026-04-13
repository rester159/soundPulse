"""
Freeform lyrics writer (called from _generate_song_with_instrumental_core).

The smart_prompt pipeline is built around breakout data — it refuses to
run when a genre has no breakout_events rows. That's correct behavior
for the data-driven path, but it leaves us without lyrics when the CEO
picks an instrumental + artist and there's no blueprint to draw from.

This service fills that gap. It takes an artist + optional instrumental
and calls a lightweight Gemini flash LLM action that:

  - Respects voice_dna.vocal_mode (rapped / sung / spoken / chanted /
    mixed) — rapped artists get bars + flows, sung artists get
    verse/chorus/bridge structure
  - Respects artist.edge_profile (clean / flirty / savage)
  - Respects artist.content_rating (clean / mild / explicit)
  - Pulls persona_dna.backstory + lyrical_dna.recurring_themes + motifs
    so the output feels authentic to the persona
  - Honors the same EDGE RULES + EARWORM RULE + HOOK ISOLATION RULE
    from smart_prompt — they're system-prompt-embedded so every
    lyric generation produces edgy, hook-isolated, pop-culture-aware
    content regardless of which entry point called it
  - Locks to the instrumental's tempo/key/genre if provided

Returns a fully-formed STYLE + LYRICS block the orchestrator passes to
Suno. The Kie.ai add-vocals endpoint sees real verse/bars content
instead of the style-only synthesis that was producing nonsense.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)


FREEFORM_SYSTEM = """You are a veteran songwriter and A&R at SoundPulse Records writing REAL LYRICS for an AI artist based on their persona. Your output goes directly to Suno Kie.ai's add-vocals endpoint — whatever you write IS what Suno sings.

CRITICAL RULES

1. Honor vocal_mode. This is the single most important directive.
   - "rapped"   → Write BARS, not verses. 16-bar verse structure.
                  No sung melody. No verse/chorus alternation unless
                  the hook is obviously chanted/rap-hook style.
                  Use internal rhymes, multisyllabic rhymes, flow
                  shifts, punchlines. Think: Jay-Z, Kendrick, Nas,
                  J. Cole, Rakim. The chorus (if any) is a rap-hook
                  not a sung melody — "Rollin' / rollin' / rollin'"
                  style, not melismatic.
   - "sung"     → Write verse/pre-chorus/chorus/bridge/chorus
                  structure with clear melodic hook. Sabrina
                  Carpenter / NewJeans / Olivia Rodrigo style.
   - "spoken"   → Spoken-word delivery, no rhythm lock. Think
                  poetry interludes.
   - "chanted"  → Group chant hook with sung verses around it.
                  Think protest music or tribal choruses.
   - "mixed"    → Rapped verses with a sung chorus. Drake,
                  Post Malone, Travis Scott style.

2. EDGE RULES — every chorus/hook MUST contain at least TWO of:
   (a) chorus-level double entendre
   (b) named pop-culture reference <18 months old (Stanley cup,
       Duolingo streak, Erewhon, delulu, BeReal, Air Force 1s,
       Labubu, girl dinner, mother is mothering, villain era)
   (c) opinionated named-target take (would offend 15-25% of listeners)
   (d) concrete visual/sensory hook (named brand, object, specific place)
   (e) structural surprise

   Banned tropes — rewrite if caught:
     "finally finding myself", "dancing in the rain", "chasing dreams",
     "through the darkness to the light", "you're the one", "meant to be"

3. EARWORM RULE — the chorus hook must satisfy ≥5 of:
   1. Hook length 4-7 syllables, max 2 bars
   2. Repetition with variation (4+ reps, final lands different)
   3. V-shape melodic contour (up then down)
   4. Downbeat vowel stress on open vowels (ah/eh/oh/ay)
   5. One unexpected interval
   6. A cappella singability (can hum after one listen)
   7. Concrete noun in the hook (not abstract emotion)

4. HOOK ISOLATION RULE — for SUNG or MIXED vocal_mode only.
   The chorus MUST contain a 2-5 word phrase that appears as its OWN
   STANDALONE LINE, VERBATIM, at least 4 TIMES per chorus. Rapped
   choruses can bend this rule — rap hooks often use ad-lib call-
   and-response instead.

5. CONTENT RATING
   - "clean"    → no profanity, no sex, no drugs
   - "mild"     → mild language OK, no slurs, no explicit sex
   - "explicit" → explicit allowed, named targets allowed, drugs/sex
                  direct

6. STYLE ADHERENCE
   - Use the artist's lyrical_dna.recurring_themes as the starting
     theme palette. Pick ONE or TWO, don't cram them all in.
   - Reference the artist's persona_dna.backstory to ground the voice
     in their world (Brooklyn hustler, K-pop idol, Kingston luxe, etc).
   - Lock to the instrumental's tempo/key if provided — a 72 BPM B
     minor beat wants a laid-back introspective bar, not a 160 BPM
     drill pocket.

OUTPUT FORMAT — return ONLY valid JSON matching this exact shape:

{
  "title": "short working title, 1-5 words",
  "style_directive": "one-sentence sonic guidance for Suno — include vocal_mode explicitly, e.g. 'laid-back 72 BPM East Coast hip-hop with RAPPED vocals over a B minor loop, Brooklyn boom-bap swagger'",
  "lyrics": "full lyrics block with [Verse 1] / [Chorus] / [Verse 2] / [Bridge] section tags — for RAPPED vocal_mode use [Verse 1] 16-bar / [Hook] 4-bar / [Verse 2] 16-bar / [Hook] / [Bridge] 8-bar / [Hook] structure",
  "rationale": {
    "vocal_mode_applied": "rapped | sung | spoken | chanted | mixed",
    "edge_devices_used": ["list the 2+ edge devices you put in the chorus/hook"],
    "earworm_score": "X of 7 properties satisfied, name them",
    "hook_phrase": "the 2-5 word hook if sung, or 'n/a' if rapped",
    "themes_used": ["which lyrical_dna themes you leaned into"]
  }
}

Return ONLY the JSON, no markdown fences, no prose."""


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*\n?", "", t)
    t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


async def generate_freeform_lyrics(
    db: AsyncSession,
    *,
    artist,
    instrumental=None,
    blueprint=None,
) -> dict[str, Any]:
    """
    Call Gemini flash to produce a full STYLE + LYRICS block for an
    artist + (optional) instrumental + (optional) blueprint context.
    Returns a dict matching the FREEFORM_SYSTEM output JSON, or
    {"error": "..."} on failure.
    """
    voice_dna = artist.voice_dna or {}
    lyrical_dna = artist.lyrical_dna or {}
    persona_dna = artist.persona_dna or {}

    vocal_mode = voice_dna.get("vocal_mode") or "sung"
    timbre = voice_dna.get("timbre_core") or "distinctive vocal"
    delivery = voice_dna.get("delivery_style") or []
    if isinstance(delivery, list):
        delivery = ", ".join(delivery)
    accent = voice_dna.get("accent_pronunciation") or "neutral"

    themes = lyrical_dna.get("recurring_themes") or []
    if isinstance(themes, str):
        themes = [themes]
    motifs = lyrical_dna.get("motifs") or []
    if isinstance(motifs, str):
        motifs = [motifs]
    vocab = lyrical_dna.get("vocab_level") or "conversational"
    backstory = persona_dna.get("backstory") or ""

    instr_bits: list[str] = []
    if instrumental is not None:
        if getattr(instrumental, "tempo_bpm", None):
            instr_bits.append(f"{instrumental.tempo_bpm} BPM")
        if getattr(instrumental, "key_hint", None):
            instr_bits.append(str(instrumental.key_hint))
        if getattr(instrumental, "genre_hint", None):
            instr_bits.append(f"genre hint: {instrumental.genre_hint}")
    instr_str = ", ".join(instr_bits) if instr_bits else "no backing track specified"

    bp_theme = ""
    if blueprint is not None and getattr(blueprint, "target_themes", None):
        targets = blueprint.target_themes
        if isinstance(targets, list) and targets:
            bp_theme = f"\nBlueprint target themes (prefer these): {', '.join(targets[:3])}"

    user = f"""ARTIST: {artist.stage_name}
  primary_genre: {artist.primary_genre}
  edge_profile: {getattr(artist, 'edge_profile', 'flirty_edge')}
  content_rating: {artist.content_rating or 'mild'}
  gender_presentation: {artist.gender_presentation or 'unspecified'}
  ethnicity_heritage: {artist.ethnicity_heritage or 'unspecified'}

VOICE
  vocal_mode: {vocal_mode}
  timbre: {timbre}
  delivery_style: {delivery}
  accent: {accent}

PERSONA BACKSTORY
  {backstory}

LYRICAL DNA
  recurring_themes: {', '.join(themes) if themes else '(none specified — pick from the backstory)'}
  motifs: {', '.join(motifs) if motifs else '(none)'}
  vocab_level: {vocab}

INSTRUMENTAL / BACKING TRACK
  {instr_str}{bp_theme}

Write a full song — title + style_directive + lyrics + rationale — as
JSON matching the exact schema in the system prompt. Lock to the
vocal_mode ({vocal_mode}) rigorously. If vocal_mode=rapped, do NOT
write sung verse/chorus alternation — write 16-bar rap verses with
a rap-hook. If vocal_mode=sung, write verse/pre-chorus/chorus/bridge/
chorus with a repeating isolated hook.

Return the JSON now."""

    messages = [
        {"role": "system", "content": FREEFORM_SYSTEM},
        {"role": "user", "content": user},
    ]

    result = await llm_chat(
        db=db,
        action="smart_prompt_generation",  # reuse the existing action slot
        messages=messages,
        caller="freeform_lyrics.generate",
        context_id=f"artist={artist.stage_name} mode={vocal_mode}",
    )
    if not result.get("success"):
        return {"error": f"llm_chat failed: {result.get('error')}"}

    raw = (result.get("content") or "").strip()
    try:
        parsed = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as e:
        logger.exception("[freeform-lyrics] JSON parse failed")
        return {"error": f"LLM returned unparseable JSON: {e}", "raw": raw[:500]}

    # Validate minimum shape
    if not isinstance(parsed, dict) or not parsed.get("lyrics"):
        return {"error": "LLM response missing 'lyrics' field", "raw": raw[:500]}

    # Compose the STYLE + LYRICS block the orchestrator expects in
    # smart_prompt_text shape. This goes through assemble_generation_prompt
    # and then gets stripped down to the lyric content by suno_kie.
    style_directive = parsed.get("style_directive") or ""
    lyrics_block = parsed["lyrics"]
    title = parsed.get("title") or ""

    composed = f"STYLE: {style_directive}\n\nLYRICS:\n{lyrics_block}"

    return {
        "prompt": composed,
        "title": title,
        "lyrics": lyrics_block,
        "style_directive": style_directive,
        "rationale": parsed.get("rationale") or {},
        "vocal_mode": vocal_mode,
    }
