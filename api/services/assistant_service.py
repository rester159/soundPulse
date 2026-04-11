"""
AI Assistant service — answers questions about SoundPulse data and product using Groq/Llama.

Gathers live DB context AND injects relevant PRD sections based on question topic.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import httpx  # still used by gather_context — leave import
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot
from api.models.track import Track
from api.models.artist import Artist

logger = logging.getLogger(__name__)

# Generality principle: no hardcoded LLM vendor / model / URL here.
# Provider + model + pricing are loaded from config/llm.json through
# api.services.llm_client.llm_chat. To switch to OpenAI / Claude / a
# different Llama variant, edit config/llm.json — no code change needed.

# ─────────────────────────────────────────────────────────────────────────────
# PRD Knowledge Base — always present in system prompt (condensed)
# Full sections injected dynamically based on question topic
# ─────────────────────────────────────────────────────────────────────────────

PRD_SUMMARY = """
=== SOUNDPULSE PRODUCT KNOWLEDGE BASE ===

WHAT IS SOUNDPULSE:
SoundPulse is a fully autonomous virtual record label with zero human employees.
It analyzes what makes music succeed → predicts which songs will succeed → generates songs →
distributes to 150+ platforms → markets automatically → registers with PROs → collects royalties → reinvests.
The output is revenue, not a dashboard.

CURRENT STATUS (April 2026):
- Phase 1 (Data Foundation): 90% complete
- Phase 2 (Prediction + Song DNA): 40% complete
- Phase 3 (Full Autonomous Pipeline): Specified, not started

WHAT'S BUILT:
✅ Chartmetric scraper (2 req/sec, 170K/day, charts from Spotify/Shazam US)
✅ Spotify scraper (12 genres, every 6h)
✅ Spotify Audio Analysis scraper (tempo, energy, key, etc.)
✅ Entity resolution (ISRC, fuzzy matching)
✅ 959-genre taxonomy (12 root categories)
✅ Composite scoring + velocity calculation
✅ React dashboard (6 pages: Dashboard, Explore, Song Lab, Model Validation, API Tester, Assistant)
✅ FastAPI backend (16 endpoints)
✅ Railway deployment (5 services: API, UI, Celery Worker, Celery Beat, Redis)
✅ Neon PostgreSQL database (14,189 snapshots, 2,065 tracks)
✅ Blueprint generation (Song DNA → Suno/Udio/SOUNDRAW/MusicGen prompts)
✅ Backtesting / Model Validation system
✅ AI Assistant (this chat, powered by Groq/Llama 3.3 70B)

WHAT'S NEXT (Phase 2 remaining):
- LightGBM prediction model producing useful predictions (needs 60+ days stable data)
- Audio features populated for top tracks (scraper running)
- Lyrics themes populated (Genius scraper ready)
- Genre classifier producing good results

WHAT'S PLANNED (Phase 3):
- Suno API integration for song generation
- Artist creation system (persona + visuals + social accounts)
- Revelator/LabelGrid distribution API
- TikTok/Instagram/YouTube marketing automation
- PRO registration via TuneRegistry
- Revenue tracking and reinvestment

THE COMPLETE PIPELINE:
1. Analyze → 2. Predict → 3. Create → 4. Distribute → 5. Market → 6. Register → 7. Collect → loop

UNIT ECONOMICS:
- Song generation: ~$0.015/song (Suno Premier $30/mo = ~2K songs)
- Song generation via API: ~$0.11-0.14/song (EvoLink or CometAPI wrappers)
- Cover art (DALL-E 3): ~$0.04/image
- Distribution (LabelGrid): ~$0.12/song
- Per-song total (gen + distribution): ~$0.17-0.30
- Typical promo spend per song: ~$300-500 (Playlist Push + Meta Ads)
- Revenue per stream: ~$0.004 average across platforms
- Break-even: ~500 songs in catalog, 100 getting traction at 8K avg streams/month (~$1K/mo profit)

DATA STRATEGY:
- Chartmetric = primary backbone ($350/mo, 170K req/day)
- Covers Spotify, Apple Music, TikTok, YouTube, Shazam, Instagram, Twitter
- Historical backfill: 2 years of daily chart data

PREDICTION MODEL:
- LightGBM → Ensemble (Phase 3)
- ~70 features: platform momentum, cross-platform, temporal, genre, entity history, Song DNA
- Targets: spotify_top_50_us (7d), shazam_top_200_us (7d), billboard_hot_100 (14d), cross_platform_breakout (14d)
- Platform weights: Chartmetric 40%, Spotify 30%, Shazam 20%, Other 10%

DISTRIBUTION OPTIONS:
- Revelator: top pick (full REST API, distribution + rights + royalties)
- LabelGrid: budget pick ($1,428/yr, transparent docs)
- NOT suitable: DistroKid, Amuse, UnitedMasters (no API)

PRO REGISTRATION:
- TuneRegistry: winner ($35-95/mo flat, handles ASCAP/BMI/SESAC/HFA/SoundExchange/MLC)
- Timeline to first royalty: 9-18 months (industry standard)

MUSIC GENERATION APIS (April 2026):
- Suno Premier: $30/mo (~2K songs), no official API, best for vocals
- EvoLink (Suno wrapper): $0.111/song, REST API
- CometAPI (Suno wrapper): $0.144/song, REST API
- Udio Pro: $30/mo (~2.4K songs), no official API, good for style transfer
- SOUNDRAW: $500/mo, official REST API, royalty-free instrumentals
- MusicGen (Replicate): $0.064/run, open source, instrumental only

ARTIST STRATEGY:
- Each AI artist has persistent DNA: identity, voice, visual, genre, persona, lyrical style
- Artist Decision Model: assign to existing artist (genre match >80%) or create new
- 6-angle reference portrait for visual consistency across all generated images
- Platform accounts (Instagram, TikTok, YouTube): created manually once (~15 min), then fully automated

0→3K STREAMS PLAYBOOK (~$500/song):
- Playlist Push: $300/campaign, ~25 streams/$
- Meta Ads → Smart Link: $0.15-0.40/stream
- Short-form video (TikTok/Reels/Shorts): viral potential
- SubmitHub: ~$8-12/placement, AI detection risk (98.5% detection rate — must disclose)
- Spotify trigger thresholds: ~2,500 streams + 375 saves in 14 days for Discover Weekly

INFRASTRUCTURE (current):
- Railway: API ($10/mo), UI ($5/mo), Celery Worker ($10/mo), Celery Beat ($5/mo), Redis ($5/mo) = ~$35/mo
- Neon: Free tier → $19/mo (after 3GB)
- Chartmetric: $350/mo
- Total monthly ops: ~$830/mo
"""

# ─────────────────────────────────────────────────────────────────────────────
# Topic → PRD section mapping for deep-dive questions
# ─────────────────────────────────────────────────────────────────────────────

PRD_SECTIONS = {
    "vision": ["virtual label", "vision", "what is soundpulse", "what does it do", "pipeline", "autonomous", "end to end"],
    "revenue": ["revenue", "money", "royalt", "stream", "earn", "unit economics", "break-even", "breakeven", "cost", "profit"],
    "distribution": ["distribut", "release", "platform", "revelator", "labelgrid", "distrokid", "udi", "dsp", "streaming platform"],
    "marketing": ["market", "tiktok", "instagram", "social", "promotion", "playlist push", "submithub", "groover", "viral", "0 to 3k", "0→3k"],
    "generation": ["generat", "suno", "udio", "soundraw", "musicgen", "song creat", "make a song", "music api"],
    "artist": ["artist", "persona", "dna", "creator", "ai artist", "visual", "portrait", "identity"],
    "prediction": ["predict", "model", "lightgbm", "breakout", "confidence", "accuracy", "ml", "machine learning"],
    "blueprint": ["blueprint", "song lab", "song dna", "tempo", "key", "energy", "valence", "bpm"],
    "legal": ["legal", "copyright", "pro", "ascap", "bmi", "royalt", "tuneregistry", "isrc", "register"],
    "phase": ["phase", "roadmap", "status", "built", "what's next", "plan", "timeline", "week"],
}

PRD_SECTION_DETAILS = {
    "vision": """
VISION DETAIL:
The complete pipeline (end to end, no human intervention):
1. Analyze — What sonic + cultural characteristics are driving success in micro-genres right now?
2. Predict — Which artist persona + song combination has highest probability of success?
3. Create — Generate artist (if new) and song with consistent identity
4. Distribute — Upload to every streaming platform via distribution API
5. Market — Post TikTok teasers, Instagram, YouTube visualizers automatically
6. Register — Register with PROs for royalty collection
7. Optimize — Monitor performance, adjust future blueprints
8. Collect — Royalties flow back automatically
9. Reinvest — Revenue funds the next generation cycle

Example flow: SoundPulse detects melodic trap accelerating in C# minor at 140-150 BPM.
Assigns to existing artist "VOIDBOY". Blueprint: 145 BPM, C# minor, energy 0.72, heartbreak themes.
Song generated via Suno. Distributed via LabelGrid to 150+ platforms. TikTok teaser 3 days before.
Day 7: 2,400 streams. Day 30: 18,000 streams. $72 revenue. Results fed back to model.
""",
    "revenue": """
REVENUE DETAIL:
Per-stream payouts: Spotify $0.003-0.005, Apple Music $0.007-0.01, YouTube $0.002-0.004, avg ~$0.004

Conservative model (20% of songs get traction):
- 50 songs: 10 with traction, $120/mo revenue, $830/mo infra = -$710/mo
- 200 songs: 40 traction, $800/mo, $1,400/mo infra = -$600/mo
- 500 songs: 100 traction at 8K streams, $3,200/mo, $2,200/mo infra = +$1,000/mo
- 1,000 songs: 200 traction at 10K streams, $8,000/mo = +$4,000/mo

Break-even: ~500 songs, ~12-18 months cumulative investment
Key lever: prediction model pushing hit rate from 20% toward 40%+ = faster break-even

Per-song economics:
- Generation (Suno Premier): ~$0.015 ($30/mo = 2K songs)
- Distribution (LabelGrid): ~$0.12/song
- Promo per song: ~$300-500
- Total with promo: ~$300.30/song
""",
    "marketing": """
MARKETING DETAIL (0→3K Streams Playbook, ~$500/song):

Week 0 (pre-release): Pre-save via Hypeddit. Spotify editorial pitch. Prepare 10-15 short videos.
Week 1: Playlist Push $300 (best ROI, ~25 streams/$). Meta Ads $100. Daily TikTok/Reels/Shorts.
Week 1-2: SubmitHub $40 (50 credits) — WARNING: 98.5% AI detection rate, disclosure required.
Week 2-3: Groover campaign $55 (25 curators, 10-21% acceptance). Discord posts.
Total: ~$500 → ~3,000-6,000 streams

Spotify trigger thresholds for algorithmic pickup:
- ~2,500 streams + 375 saves in 14 days → Discover Weekly consideration
- High listen-through (>50%) → Autoplay/Radio
- 30+ followers → Release Radar
- 100+ pre-saves → Day-1 signal boost

TikTok hook extraction: 5 sec before chorus + first 10 sec of chorus = 15-sec clip
Video: Google Veo + 6-angle artist portrait as face seed
""",
    "generation": """
MUSIC GENERATION DETAIL (April 2026 pricing):
- Suno Premier: $30/mo, ~2K songs, no official API, best for vocals + lyrics, license (not ownership)
- EvoLink (Suno wrapper): $0.111/song, REST API, same quality as Suno
- CometAPI (Suno wrapper): $0.144/song, REST API
- Udio Pro: $30/mo, ~2.4K songs, style transfer, downloads broken as of 4/2026
- SOUNDRAW: $500/mo, official REST API, royalty-free instrumentals, structured params
- MusicGen (Replicate): $0.064/run, open source, instrumental only, MIT license

Recommendation: Start Suno Premier ($30/mo) for testing.
Move to EvoLink/CometAPI wrapper for API automation.

Quality check after generation: tempo ±10%, energy ±0.15 of blueprint. Max 3 retries.
Pipeline: Blueprint + Artist DNA → prompt → Suno/Udio API → audio → QA → pass/fail
""",
    "legal": """
LEGAL & PRO REGISTRATION DETAIL:
Winner: TuneRegistry ($35-95/mo flat, handles ASCAP/BMI/SESAC/HFA/SoundExchange/MLC)
NOT recommended: Songtrust (15-20% commission)

Registration flow: Distribute → ISRC assigned → TuneRegistry CSV upload → auto-delivered to all orgs
Required per song: title, writer legal name, writer IPI number, publisher name, IPI, ownership %, ISRC

AI music + PROs: ASCAP/BMI accept AI-assisted works with "meaningful human creative contribution."
Fully AI works NOT eligible. Gray area — needs legal counsel.
SoundPulse model: human selects genre + approves blueprint = "meaningful human contribution."

Timeline to first royalty: 9-18 months (industry standard, unavoidable).

Copyright: US Copyright Office does not recognize raw AI-generated audio as copyrightable.
Post Warner Music deal (late 2025), Suno grants perpetual commercial license but retains authorship.
""",
}


def _detect_topics(question: str) -> list[str]:
    """Detect which PRD sections are relevant to the question."""
    q = question.lower()
    matched = []
    for topic, keywords in PRD_SECTIONS.items():
        if any(kw in q for kw in keywords):
            matched.append(topic)
    return matched


async def gather_context(db: AsyncSession, question: str) -> str:
    """Query the database for context relevant to the user's question."""
    context_parts = []

    # Anchor to most recent data (backfill data may be from 2024-2025)
    latest_row = await db.execute(
        select(func.max(TrendingSnapshot.snapshot_date))
        .where(TrendingSnapshot.entity_type == "track")
    )
    latest_date = latest_row.scalar() or date.today()
    lookback = latest_date - timedelta(days=30)

    # Get top trending tracks
    result = await db.execute(
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.composite_score,
            TrendingSnapshot.velocity,
            TrendingSnapshot.platform,
            TrendingSnapshot.platform_rank,
            TrendingSnapshot.signals_json,
        )
        .where(TrendingSnapshot.entity_type == "track")
        .where(TrendingSnapshot.snapshot_date >= lookback)
        .order_by(TrendingSnapshot.composite_score.desc().nullslast())
        .limit(20)
    )
    top_tracks = result.all()

    if top_tracks:
        track_ids = [str(t.entity_id) for t in top_tracks]
        track_result = await db.execute(
            select(Track.id, Track.title, Track.genres, Track.audio_features)
            .where(Track.id.in_(track_ids))
        )
        track_map = {str(t.id): t for t in track_result.all()}

        lines = [f"TOP TRENDING TRACKS (as of {latest_date}):"]
        for snap in top_tracks[:15]:
            track = track_map.get(str(snap.entity_id))
            if not track:
                continue
            signals = snap.signals_json or {}
            genres = signals.get("genres") or signals.get("track_genre") or ""
            artist = signals.get("artist_name") or ""
            lines.append(
                f"- {track.title} by {artist} | score={snap.composite_score:.0f} "
                f"velocity={snap.velocity or 0:.1f} platform={snap.platform} "
                f"rank={snap.platform_rank} genres=[{genres}]"
            )
        context_parts.append("\n".join(lines))

    # Get genre distribution
    result = await db.execute(
        text("""
            SELECT signals_json->>'genres' as genres, COUNT(*) as cnt,
                   AVG(composite_score) as avg_score
            FROM trending_snapshots
            WHERE snapshot_date >= :lookback
              AND signals_json->>'genres' IS NOT NULL
              AND signals_json->>'genres' != ''
            GROUP BY signals_json->>'genres'
            ORDER BY cnt DESC
            LIMIT 15
        """),
        {"lookback": lookback},
    )
    genre_rows = result.all()
    if genre_rows:
        lines = ["\nGENRE DISTRIBUTION (last 30 days from latest data):"]
        for row in genre_rows:
            lines.append(f"- {row.genres}: {row.cnt} snapshots, avg_score={row.avg_score:.1f}")
        context_parts.append("\n".join(lines))

    # Get database stats
    result = await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM tracks) as total_tracks,
            (SELECT COUNT(*) FROM artists) as total_artists,
            (SELECT COUNT(*) FROM trending_snapshots) as total_snapshots,
            (SELECT COUNT(DISTINCT snapshot_date) FROM trending_snapshots) as distinct_dates,
            (SELECT MIN(snapshot_date) FROM trending_snapshots) as earliest,
            (SELECT MAX(snapshot_date) FROM trending_snapshots) as latest
    """))
    stats = result.one()
    context_parts.append(
        f"\nDATABASE STATS: {stats.total_tracks} tracks, {stats.total_artists} artists, "
        f"{stats.total_snapshots} snapshots across {stats.distinct_dates} dates "
        f"({stats.earliest} to {stats.latest})"
    )

    # Scraper status
    try:
        result = await db.execute(text("""
            SELECT id, enabled, last_status, last_run_at, last_record_count
            FROM scraper_configs ORDER BY id
        """))
        scrapers = result.all()
        lines = ["\nSCRAPER STATUS:"]
        for s in scrapers:
            lines.append(f"- {s.id}: enabled={s.enabled} status={s.last_status} records={s.last_record_count} last_run={s.last_run_at}")
        context_parts.append("\n".join(lines))
    except Exception:
        pass

    return "\n".join(context_parts)


async def ask_assistant(
    db: AsyncSession,
    question: str,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Ask the AI assistant a question about SoundPulse data and product.

    Routes through api.services.llm_client.llm_chat which:
      - Resolves provider/model/API URL from config/llm.json (action="assistant_chat")
      - Makes the HTTP call in the right format (OpenAI-compat, Anthropic, etc)
      - Logs one row to `llm_calls` with tokens + cost + latency
    """
    from api.services.llm_client import llm_chat

    # Gather live DB context
    db_context = await gather_context(db, question)

    # Detect relevant PRD sections and inject them
    topics = _detect_topics(question)
    prd_context = ""
    for topic in topics:
        if topic in PRD_SECTION_DETAILS:
            prd_context += PRD_SECTION_DETAILS[topic] + "\n"

    # Build system prompt: always include PRD summary + dynamic section details
    system_content = (
        "You are the SoundPulse AI assistant — the intelligence brain of a fully autonomous virtual record label.\n\n"
        "You have access to: (1) real-time music trending data from the database, and (2) full knowledge of "
        "the SoundPulse product, vision, roadmap, economics, and strategy from the PRD.\n\n"
        "Answer questions concisely with specific numbers when available. "
        "For product/strategy questions, draw on the PRD knowledge. "
        "For data questions (trending, genres, predictions), use the live database context. "
        "If you don't know something, say so.\n\n"
        + PRD_SUMMARY
        + "\n\n=== LIVE DATABASE CONTEXT ===\n"
        + db_context
    )

    if prd_context:
        system_content += "\n\n=== RELEVANT PRD DETAIL FOR THIS QUESTION ===\n" + prd_context

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append(msg)

    messages.append({"role": "user", "content": question})

    result = await llm_chat(
        db=db,
        action="assistant_chat",
        messages=messages,
        caller="assistant_service.ask_assistant",
        metadata={
            "question_length": len(question),
            "history_length": len(conversation_history or []),
            "prd_topics_injected": topics,
        },
    )

    if not result.get("success"):
        return {
            "answer": f"Assistant error: {result.get('error') or 'unknown'}",
            "error": True,
            "model": result.get("model", ""),
            "provider": result.get("provider", ""),
        }

    return {
        "answer": result["content"],
        "model": result["model"],
        "provider": result["provider"],
        "usage": {
            "prompt_tokens": result["input_tokens"],
            "completion_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
        },
        "cost_cents": result["cost_cents"],
        "latency_ms": result["latency_ms"],
        "context_length": len(system_content),
        "prd_topics_injected": topics,
    }
