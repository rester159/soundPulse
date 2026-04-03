"""
AI Assistant service — answers questions about SoundPulse data using Groq/Llama.

Queries the database for relevant context, then sends it to Groq's
chat completion API to generate a natural language answer.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.trending_snapshot import TrendingSnapshot
from api.models.track import Track
from api.models.artist import Artist

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are the SoundPulse AI assistant — the intelligence brain of a fully autonomous virtual record label.

You have access to real-time music trending data, artist social metrics, song audio features, and genre intelligence.
Answer questions concisely and with specific numbers when available. If the data doesn't contain the answer, say so.

You can help with:
- What's trending in any genre right now
- Which artists/tracks are gaining momentum
- Genre opportunity analysis (what niches are underserved)
- Song DNA insights (what sonic characteristics define a genre)
- Prediction explanations (why a track is predicted to break out)
- Blueprint suggestions (what kind of song to make for a genre)
- Artist portfolio recommendations

Always ground your answers in the data provided. Don't make up numbers."""


async def gather_context(db: AsyncSession, question: str) -> str:
    """Query the database for context relevant to the user's question."""
    context_parts = []
    lookback = date.today() - timedelta(days=30)

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
            select(Track.id, Track.title, Track.isrc, Track.genres, Track.audio_features)
            .where(Track.id.in_(track_ids))
        )
        track_map = {str(t.id): t for t in track_result.all()}

        lines = ["TOP TRENDING TRACKS (last 30 days):"]
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
        lines = ["\nGENRE DISTRIBUTION (last 30 days):"]
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

    # Get scraper status
    result = await db.execute(text("""
        SELECT id, enabled, last_status, last_run_at, last_record_count
        FROM scraper_configs ORDER BY id
    """))
    scrapers = result.all()
    lines = ["\nSCRAPER STATUS:"]
    for s in scrapers:
        lines.append(f"- {s.id}: enabled={s.enabled} status={s.last_status} records={s.last_record_count} last_run={s.last_run_at}")
    context_parts.append("\n".join(lines))

    return "\n".join(context_parts)


async def ask_assistant(
    db: AsyncSession,
    question: str,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """Ask the AI assistant a question about SoundPulse data."""
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_api_key:
        return {"answer": "Groq API key not configured. Add GROQ_API_KEY to environment variables.", "error": True}

    # Gather relevant context from the database
    context = await gather_context(db, question)

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + context}]

    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history[-6:]:  # Last 6 messages for context
            messages.append(msg)

    messages.append({"role": "user", "content": question})

    # Call Groq API
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )

            if resp.status_code != 200:
                return {"answer": f"Groq API error: {resp.status_code} — {resp.text[:200]}", "error": True}

            data = resp.json()
            answer = data["choices"][0]["message"]["content"]

            return {
                "answer": answer,
                "model": GROQ_MODEL,
                "usage": data.get("usage", {}),
                "context_length": len(context),
            }

    except Exception as e:
        logger.error("Assistant error: %s", e)
        return {"answer": f"Error: {str(e)}", "error": True}
