"""
Gap finder — Layer 4 of the Breakout Analysis Engine.

For a given genre, identifies underserved sonic zones by:
  1. Pulling all tracks in that genre with audio features
  2. Building feature vectors (tempo/energy/danceability/valence/etc.)
  3. K-means clustering into 6-12 sonic zones
  4. For each cluster, computing breakout density vs supply density
  5. Ranking clusters by gap_score = breakout_density / supply_density

A high gap score means: breakouts happen here, but few people are
making music in this zone — exactly where a virtual label should
target new releases.

See planning/PRD/breakoutengine_prd.md Layer 4 for the design.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.breakout_event import BreakoutEvent

logger = logging.getLogger(__name__)

# Features used for clustering. We use a subset of audio features that
# are most descriptive of "sonic identity" — tempo, energy, mood,
# acoustic vs electronic, loudness.
CLUSTER_FEATURES = [
    "tempo",
    "energy",
    "danceability",
    "valence",
    "acousticness",
    "loudness",
]

MIN_TRACKS_FOR_CLUSTERING = 10


async def find_gaps(
    db: AsyncSession,
    genre_id: str,
    *,
    n_clusters: int | None = None,
) -> dict[str, Any]:
    """
    Run gap analysis for a single genre. Returns a dict with the
    cluster breakdown sorted by gap_score (highest = biggest opportunity).
    """
    # 1. Pull all tracks in the genre with audio features
    all_tracks = await _get_genre_tracks_with_features(db, genre_id)
    if len(all_tracks) < MIN_TRACKS_FOR_CLUSTERING:
        return {
            "genre": genre_id,
            "error": f"insufficient data: only {len(all_tracks)} tracks with features",
            "clusters": [],
        }

    # 2. Pull breakout track IDs for the same genre
    breakout_ids = await _get_breakout_track_ids(db, genre_id)

    # 3. Build feature matrices
    all_vectors, valid_tracks = _build_feature_matrix(all_tracks)
    if len(all_vectors) < MIN_TRACKS_FOR_CLUSTERING:
        return {
            "genre": genre_id,
            "error": f"insufficient feature coverage: {len(all_vectors)} valid vectors",
            "clusters": [],
        }

    # 4. Normalize to [0, 1] per feature
    scaler = MinMaxScaler()
    normalized = scaler.fit_transform(all_vectors)

    # 5. Choose cluster count: 6 default, capped by sample size / 5
    n = n_clusters or min(10, max(3, len(all_vectors) // 5))

    kmeans = KMeans(n_clusters=n, random_state=42, n_init=10)
    labels = kmeans.fit_predict(normalized)

    # 6. For each cluster, compute density metrics
    clusters: list[dict[str, Any]] = []
    total_tracks = len(valid_tracks)
    total_breakouts_in_cluster_set = sum(
        1 for t in valid_tracks if str(t["track_id"]) in breakout_ids
    )

    for cluster_id in range(n):
        mask = labels == cluster_id
        cluster_size = int(mask.sum())
        if cluster_size == 0:
            continue

        # Tracks in this cluster
        cluster_tracks = [valid_tracks[i] for i, m in enumerate(mask) if m]
        cluster_breakouts = sum(
            1 for t in cluster_tracks if str(t["track_id"]) in breakout_ids
        )

        # Density metrics
        breakout_density = cluster_breakouts / max(cluster_size, 1)
        supply_density = cluster_size / total_tracks
        # Gap score: how over-represented are breakouts here vs the genre baseline
        baseline_breakout_rate = total_breakouts_in_cluster_set / max(total_tracks, 1)
        gap_score = breakout_density / max(baseline_breakout_rate, 0.001)

        # Cluster center in original (un-normalized) units
        center_normalized = kmeans.cluster_centers_[cluster_id]
        center_original = scaler.inverse_transform(center_normalized.reshape(1, -1))[0]
        center_dict = dict(zip(CLUSTER_FEATURES, center_original.tolist()))

        clusters.append({
            "cluster_id": int(cluster_id),
            "gap_score": round(gap_score, 3),
            "breakout_density": round(breakout_density, 3),
            "supply_density": round(supply_density, 3),
            "total_tracks": cluster_size,
            "breakout_tracks": cluster_breakouts,
            "sonic_center": {k: round(v, 3) for k, v in center_dict.items()},
            "description": _describe_cluster(center_dict),
        })

    # Sort by gap_score, highest first
    clusters.sort(key=lambda c: c["gap_score"], reverse=True)

    return {
        "genre": genre_id,
        "total_tracks": total_tracks,
        "total_breakouts": total_breakouts_in_cluster_set,
        "n_clusters": n,
        "clusters": clusters,
    }


def _build_feature_matrix(tracks: list[dict]) -> tuple[np.ndarray, list[dict]]:
    """
    Build a (n_tracks, n_features) matrix from track audio_features.
    Drops tracks missing any of the cluster features.
    """
    valid: list[dict] = []
    rows: list[list[float]] = []
    for t in tracks:
        af = t.get("audio_features") or {}
        vec = [af.get(f) for f in CLUSTER_FEATURES]
        if all(isinstance(v, (int, float)) for v in vec):
            rows.append([float(v) for v in vec])
            valid.append(t)
    return np.array(rows), valid


def _describe_cluster(center: dict[str, float]) -> str:
    """Generate a human-readable description of a cluster's sonic profile."""
    parts = []

    tempo = center.get("tempo", 0)
    if tempo >= 140:
        parts.append(f"fast ({tempo:.0f} BPM)")
    elif tempo >= 110:
        parts.append(f"mid-tempo ({tempo:.0f} BPM)")
    elif tempo > 0:
        parts.append(f"slow ({tempo:.0f} BPM)")

    energy = center.get("energy", 0)
    if energy >= 0.7:
        parts.append("high-energy")
    elif energy >= 0.4:
        parts.append("medium-energy")
    elif energy > 0:
        parts.append("low-energy")

    valence = center.get("valence", 0)
    if valence >= 0.7:
        parts.append("euphoric")
    elif valence >= 0.5:
        parts.append("upbeat")
    elif valence >= 0.3:
        parts.append("moody")
    elif valence > 0:
        parts.append("dark")

    danceability = center.get("danceability", 0)
    if danceability >= 0.7:
        parts.append("danceable")

    acousticness = center.get("acousticness", 0)
    if acousticness >= 0.6:
        parts.append("acoustic")
    elif acousticness <= 0.2 and acousticness > 0:
        parts.append("electronic")

    return ", ".join(parts) if parts else "neutral profile"


async def _get_genre_tracks_with_features(
    db: AsyncSession, genre_id: str
) -> list[dict[str, Any]]:
    """All tracks in the given genre that have audio_features."""
    result = await db.execute(text("""
        SELECT t.id AS track_id, t.title, t.audio_features
        FROM tracks t
        WHERE :gid = ANY(t.genres)
          AND t.audio_features IS NOT NULL
          AND t.audio_features::text <> '{}'
    """), {"gid": genre_id})
    return [
        {"track_id": row[0], "title": row[1], "audio_features": row[2]}
        for row in result.fetchall()
    ]


async def _get_breakout_track_ids(db: AsyncSession, genre_id: str) -> set[str]:
    """Set of track UUIDs (as strings) that have breakout events for this genre."""
    result = await db.execute(
        select(BreakoutEvent.track_id).where(BreakoutEvent.genre_id == genre_id)
    )
    return {str(row[0]) for row in result.fetchall()}
