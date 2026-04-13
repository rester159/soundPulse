"""
Duplicate detection — cosine similarity over MFCC-13 embeddings.

audio_qa_full.py writes an mfcc_mean_13 vector into song_qa_reports for
every qa_passed song. This service compares those vectors pairwise to
flag songs that are suspiciously similar to each other (could indicate
Suno / Udio recycling the same output, or an artist leaning too heavily
on one pocket).

For each song with an MFCC embedding:
  1. Compute cosine similarity against every other song's embedding
  2. Flag any pair above DUPLICATE_THRESHOLD as a potential duplicate
  3. Write a song_duplicates row (or similar tracking table)

This is an O(n²) comparison which is fine for catalog sizes up to ~10k
songs. Beyond that we'd swap in FAISS or pgvector for an ANN index.
For now, n²/2 at n=100 is 5000 comparisons — instant.

Thresholds:
  >= 0.95: near-identical (CEO review, likely needs rejection)
  >= 0.85: strong overlap (monitor)
  <  0.85: independent
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DUPLICATE_THRESHOLD_HARD = 0.95
DUPLICATE_THRESHOLD_SOFT = 0.85


def _cosine(a: list[float], b: list[float]) -> float:
    """Plain-Python cosine — avoid numpy dep for this service."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def _load_mfcc_embeddings(db: AsyncSession) -> list[tuple[str, str, list[float]]]:
    """Return [(song_id, title, mfcc_vector), ...] for every song with
    an MFCC-13 stored in song_qa_reports."""
    r = await db.execute(
        _text("""
            SELECT s.song_id::text, s.title,
                   (qa.features_json->>'mfcc_mean_13')::text AS mfcc_str
            FROM songs_master s
            JOIN song_qa_reports qa ON qa.song_id = s.song_id
            WHERE qa.features_json ? 'mfcc_mean_13'
              AND qa.source = 'audio_qa_full'
              AND s.status NOT IN ('draft','abandoned')
        """)
    )
    out: list[tuple[str, str, list[float]]] = []
    for row in r.fetchall():
        try:
            import json as _json
            vec = _json.loads(row[2])
            if isinstance(vec, list) and len(vec) == 13:
                out.append((row[0], row[1] or "", [float(x) for x in vec]))
        except Exception:
            continue
    return out


async def run_duplicate_sweep(db: AsyncSession) -> dict[str, Any]:
    """
    Walk all qa_passed songs with MFCC embeddings and flag pairs with
    cosine similarity >= DUPLICATE_THRESHOLD_SOFT.
    """
    embeddings = await _load_mfcc_embeddings(db)
    if len(embeddings) < 2:
        return {
            "songs_compared": len(embeddings),
            "pairs_checked": 0,
            "hard_duplicates": [],
            "soft_duplicates": [],
        }

    hard: list[dict[str, Any]] = []
    soft: list[dict[str, Any]] = []

    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = _cosine(embeddings[i][2], embeddings[j][2])
            if sim >= DUPLICATE_THRESHOLD_HARD:
                hard.append({
                    "song_a": {"id": embeddings[i][0], "title": embeddings[i][1]},
                    "song_b": {"id": embeddings[j][0], "title": embeddings[j][1]},
                    "cosine_similarity": round(sim, 4),
                })
            elif sim >= DUPLICATE_THRESHOLD_SOFT:
                soft.append({
                    "song_a": {"id": embeddings[i][0], "title": embeddings[i][1]},
                    "song_b": {"id": embeddings[j][0], "title": embeddings[j][1]},
                    "cosine_similarity": round(sim, 4),
                })

    logger.info(
        "[duplicate-sweep] compared %d songs, %d hard + %d soft duplicates",
        len(embeddings), len(hard), len(soft),
    )

    # Write duplication_risk_score back onto songs_master for each song
    # that's part of any flagged pair. Score = max cosine similarity it
    # had with any other song in the catalog.
    from collections import defaultdict
    per_song_max: dict[str, float] = defaultdict(float)
    for pair in hard + soft:
        sa = pair["song_a"]["id"]
        sb = pair["song_b"]["id"]
        sim = pair["cosine_similarity"]
        per_song_max[sa] = max(per_song_max[sa], sim)
        per_song_max[sb] = max(per_song_max[sb], sim)

    for song_id, score in per_song_max.items():
        await db.execute(
            _text("""
                UPDATE songs_master
                SET duplication_risk_score = :score
                WHERE song_id = :sid
            """),
            {"score": score, "sid": song_id},
        )
    await db.commit()

    return {
        "songs_compared": len(embeddings),
        "pairs_checked": (len(embeddings) * (len(embeddings) - 1)) // 2,
        "hard_duplicates": hard,
        "soft_duplicates": soft,
        "songs_with_risk_scored": len(per_song_max),
    }
