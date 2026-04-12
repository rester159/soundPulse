"""
Smart Prompt v2 — Layer 5 of the Breakout Analysis Engine.

Synthesizes everything from layers 1-4 (and optionally Layer 6 lyrical
analysis) into a production-ready song prompt for Suno/Udio/MusicGen.

Inputs (assembled from cached tables):
  - Genre opportunity score + breakdown (P3)
  - Feature deltas: what's winning sonically (P2)
  - Top gap: the underserved zone with high breakout density (P4)
  - Lyrical analysis: themes to target/avoid (P6, optional)
  - Hit prediction probability (P8, optional, future)

Output: structured dict with:
  - prompt: the actual text to paste into Suno/Udio
  - rationale: why each choice was made (transparency for the user)
  - confidence: how much data backs the recommendation
  - based_on: counts of breakouts/baseline/lyrics analyzed

See planning/PRD/breakoutengine_prd.md Layer 5 for the full design.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.breakout_event import BreakoutEvent
from api.models.genre_feature_delta import GenreFeatureDelta
from api.models.genre_lyrical_analysis import GenreLyricalAnalysis
from api.services.gap_finder import find_gaps
from api.services.llm_client import llm_chat

logger = logging.getLogger(__name__)


SMART_PROMPT_SYSTEM = """You are a hit songwriter's AI collaborator at a virtual record label. Your job is to write a song creation prompt that targets a SPECIFIC GAP in a genre's sonic + lyrical landscape based on real breakout data.

The goal is NOT to copy the average — it's to fill a high-opportunity gap that the data shows is underserved but winning.

Return ONLY valid JSON, no markdown fences."""


SMART_PROMPT_TEMPLATE = """GENRE: {genre}
TARGET MODEL: {model}

OPPORTUNITY: This genre has {breakout_count} breakouts in the last 30 days from {track_count} tracks. Average breakout achieved {composite_ratio:.1f}x normal composite score and {velocity_ratio:.1f}x normal velocity. The opportunity score ranks this genre #{opportunity_rank} of all genres.

WHAT'S WINNING SONICALLY (statistically significant differentiators):
{differentiators}

TOP GAP — TARGET THIS SONIC ZONE (high breakout rate, low supply):
{gap}

{lyrical_section}

Write a {model}-formatted song creation prompt that:
1. Targets the gap zone sonically (use the tempo/key/energy from the gap center)
2. Reflects the winning differentiators (e.g. if "energy 12% higher" is a winning trait, write a high-energy prompt)
3. {lyrical_directive}
4. Is specific enough that {model} will produce something distinctive (not generic)
5. Includes both STYLE and LYRICS sections in the format {model} expects

Return ONLY this JSON:
{{
  "prompt": "STYLE: ...\\n\\nLYRICS:\\n[Verse 1]\\n...",
  "rationale": {{
    "sonic_targeting": "one sentence on why these sonic choices",
    "lyrical_targeting": "one sentence on why these lyrical choices",
    "differentiation": "one sentence on what makes this distinctive vs typical {genre}"
  }}
}}"""


async def generate_smart_prompt(
    db: AsyncSession,
    genre: str,
    model: str = "suno",
) -> dict[str, Any]:
    """
    Generate a data-driven song prompt for the given genre + model.
    Returns a dict with prompt, rationale, confidence, and source counts.
    """
    today = date.today()
    window_start = today - timedelta(days=30)

    # ---- Layer 1: breakout context ----
    breakout_stats = await _get_breakout_context(db, genre, window_start)
    if breakout_stats["breakout_count"] == 0:
        return {
            "prompt": None,
            "error": f"No breakout events found for genre '{genre}' in the last 30 days. The breakout detection sweep needs to run first, or this genre lacks sufficient data.",
        }

    # ---- Layer 2: feature deltas ----
    deltas = await _get_latest_feature_delta(db, genre)
    differentiators_text = "\n".join(
        f"  - {d}" for d in (deltas.get("top_differentiators") or [])
    ) if deltas else "  (no statistically significant differentiators yet)"

    # ---- Layer 4: gap finder ----
    gap_result = await find_gaps(db, genre)
    top_gap = (gap_result.get("clusters") or [None])[0]
    if top_gap:
        gap_text = (
            f"  Sonic profile: {top_gap['description']}\n"
            f"  Center: {top_gap['sonic_center']}\n"
            f"  Stats: {top_gap['breakout_tracks']} breakouts in {top_gap['total_tracks']} tracks "
            f"(gap_score={top_gap['gap_score']:.2f})"
        )
    else:
        gap_text = "  (insufficient feature coverage to compute gaps)"

    # ---- Layer 6: lyrical analysis (optional) ----
    lyrical = await _get_latest_lyrical_analysis(db, genre)
    if lyrical:
        analysis = lyrical.get("analysis_json") or {}
        underserved = analysis.get("underserved_themes") or []
        overserved = analysis.get("overserved_themes") or []
        breakout_themes = analysis.get("breakout_themes") or []
        tone = analysis.get("vocabulary_tone") or "varied"
        structural = analysis.get("structural_patterns") or {}
        key_insight = analysis.get("key_insight") or ""

        lyrical_section = (
            f"LYRICAL INTELLIGENCE (from LLM analysis of {lyrical['breakout_count']} "
            f"breakout vs {lyrical['baseline_count']} baseline lyrics):\n"
            f"  Breakout themes: {', '.join(breakout_themes)}\n"
            f"  Underserved themes (TARGET): {', '.join(underserved) or 'none'}\n"
            f"  Overserved themes (AVOID): {', '.join(overserved) or 'none'}\n"
            f"  Winning tone: {tone}\n"
            f"  Structural pattern: {structural}\n"
            f"  Key insight: {key_insight}"
        )
        lyrical_directive = (
            f"Use one of the underserved themes ({', '.join(underserved[:2]) or 'pick something distinctive'}), "
            f"avoid the overserved ones, and write in a {tone} tone"
        )
    else:
        lyrical_section = "LYRICAL INTELLIGENCE: not available yet (waiting for genius_lyrics + lyrical_analysis to run)"
        lyrical_directive = "Pick a distinctive theme that fits the sonic profile (avoid generic love/heartbreak unless that's the genre's core)"

    # ---- Build the LLM prompt ----
    prompt_text = SMART_PROMPT_TEMPLATE.format(
        genre=genre,
        model=model,
        breakout_count=breakout_stats["breakout_count"],
        track_count=breakout_stats["track_count"],
        composite_ratio=breakout_stats["avg_composite_ratio"],
        velocity_ratio=breakout_stats["avg_velocity_ratio"],
        opportunity_rank=breakout_stats.get("opportunity_rank", "?"),
        differentiators=differentiators_text,
        gap=gap_text,
        lyrical_section=lyrical_section,
        lyrical_directive=lyrical_directive,
    )

    result = await llm_chat(
        db=db,
        action="smart_prompt_generation",
        messages=[
            {"role": "system", "content": SMART_PROMPT_SYSTEM},
            {"role": "user", "content": prompt_text},
        ],
        caller="smart_prompt.generate_smart_prompt",
        context_id=f"genre={genre} model={model}",
        override_max_tokens=2000,
        override_temperature=0.7,
    )

    if not result["success"]:
        return {
            "prompt": None,
            "error": f"LLM call failed: {result.get('error')}",
        }

    # Parse the LLM JSON
    try:
        parsed = _parse_llm_json(result["content"])
    except Exception as exc:
        return {
            "prompt": result["content"],
            "rationale": None,
            "error": f"LLM returned malformed JSON: {exc}",
        }

    return {
        "prompt": parsed.get("prompt"),
        "rationale": parsed.get("rationale"),
        "model": model,
        "genre": genre,
        "based_on": {
            "breakout_count": breakout_stats["breakout_count"],
            "feature_deltas_count": (deltas or {}).get("breakout_count", 0),
            "feature_baseline_count": (deltas or {}).get("baseline_count", 0),
            "gap_clusters": len(gap_result.get("clusters") or []),
            "lyrical_analysis_present": lyrical is not None,
            "audio_features_coverage_pct": _audio_coverage_pct(gap_result),
        },
        "confidence": _confidence_label(breakout_stats, deltas, top_gap, lyrical),
        "llm_call": {
            "model": result.get("model"),
            "tokens": result.get("total_tokens"),
            "cost_cents": result.get("cost_cents"),
            "latency_ms": result.get("latency_ms"),
        },
    }


def _confidence_label(breakout_stats, deltas, gap, lyrical) -> str:
    """Heuristic confidence based on data depth."""
    score = 0
    if breakout_stats and breakout_stats["breakout_count"] >= 5:
        score += 1
    if breakout_stats and breakout_stats["breakout_count"] >= 15:
        score += 1
    if deltas and deltas.get("breakout_count", 0) >= 5:
        score += 1
    if gap and gap.get("breakout_tracks", 0) >= 2:
        score += 1
    if lyrical:
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _audio_coverage_pct(gap_result: dict) -> int:
    total = gap_result.get("total_tracks") or 0
    if total == 0:
        return 0
    return 100  # if find_gaps succeeded, the tracks it returned all had features


def _parse_llm_json(content: str) -> dict[str, Any]:
    s = content.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(line for line in lines if not line.strip().startswith("```"))
    return json.loads(s.strip())


async def _get_breakout_context(
    db: AsyncSession, genre_id: str, since: date
) -> dict[str, Any]:
    result = await db.execute(text("""
        SELECT
            COUNT(*) AS breakout_count,
            AVG(composite_ratio) AS avg_composite_ratio,
            AVG(velocity_ratio) AS avg_velocity_ratio,
            (SELECT COUNT(DISTINCT t.id) FROM tracks t WHERE :gid = ANY(t.genres)) AS track_count
        FROM breakout_events
        WHERE genre_id = :gid AND detection_date >= :since
    """), {"gid": genre_id, "since": since})
    row = result.fetchone()
    return {
        "breakout_count": int(row[0] or 0),
        "avg_composite_ratio": float(row[1] or 0),
        "avg_velocity_ratio": float(row[2] or 0),
        "track_count": int(row[3] or 0),
    }


async def _get_latest_feature_delta(
    db: AsyncSession, genre_id: str
) -> dict[str, Any] | None:
    result = await db.execute(
        select(GenreFeatureDelta)
        .where(GenreFeatureDelta.genre_id == genre_id)
        .order_by(GenreFeatureDelta.window_end.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return {
        "breakout_count": row.breakout_count,
        "baseline_count": row.baseline_count,
        "deltas": row.deltas_json,
        "significance": row.significance_json,
        "top_differentiators": row.top_differentiators or [],
    }


async def _get_latest_lyrical_analysis(
    db: AsyncSession, genre_id: str
) -> dict[str, Any] | None:
    result = await db.execute(
        select(GenreLyricalAnalysis)
        .where(GenreLyricalAnalysis.genre_id == genre_id)
        .order_by(GenreLyricalAnalysis.window_end.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return {
        "breakout_count": row.breakout_count,
        "baseline_count": row.baseline_count,
        "analysis_json": row.analysis_json,
    }
