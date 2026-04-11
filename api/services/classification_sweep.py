"""
Deferred genre-classification sweep.

The bulk ingest endpoint (`POST /api/v1/trending/bulk`) tags every newly
created or refreshed entity with `metadata_json.needs_classification = true`
instead of running the classifier inline. This sweep walks the queue,
classifies entities in batches, and clears the flag.

Why deferred:
  - The genre classifier does 6+ DB queries per entity (audit AUD-002).
  - Doing that inline in an async POST handler exhausts the Neon connection
    pool and times out backfills at any scale.
  - The sweep can run on a small thread pool with bounded batches.

Idempotency:
  - Each pass picks at most `batch_size` entities and processes them in a
    single transaction. If the process dies mid-batch, the rollback leaves
    `needs_classification = true` for the unprocessed rows so the next pass
    re-claims them.
  - Entities that fail classification N times in a row get marked
    `needs_classification = "skipped"` (string sentinel, not boolean) so we
    stop retrying them. They're still queryable for a manual reclassification
    run via `force_reclassify=True`.

Safety:
  - Each entity is wrapped in its own try/except so one bad row doesn't fail
    the whole batch.
  - Failures are LOGGED with the entity id and the exception (no silent
    swallowing — that was AUD-001).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.artist import Artist
from api.models.track import Track
from api.services.genre_classifier import GenreClassifier

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500
MAX_RETRIES_BEFORE_SKIP = 3


async def sweep_unclassified_entities(
    db: AsyncSession,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force_reclassify: bool = False,
) -> dict[str, int]:
    """
    Process up to `batch_size` entities pending genre classification.

    Args:
        db: async DB session (committed at the end of the sweep)
        batch_size: max entities to process per call
        force_reclassify: if True, also re-process entities that were
            previously marked `needs_classification = "skipped"`

    Returns:
        Stats dict: {tracks_processed, tracks_classified, tracks_failed,
                     artists_processed, artists_classified, artists_failed,
                     elapsed_ms}
    """
    started = datetime.now(timezone.utc)

    classifier = GenreClassifier(db)

    tracks_stats = await _sweep_one_table(
        db, classifier, Track, batch_size, force_reclassify
    )
    artists_stats = await _sweep_one_table(
        db, classifier, Artist, batch_size, force_reclassify
    )

    await db.commit()

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    result = {
        "tracks_processed": tracks_stats["processed"],
        "tracks_classified": tracks_stats["classified"],
        "tracks_failed": tracks_stats["failed"],
        "tracks_skipped": tracks_stats["skipped"],
        "artists_processed": artists_stats["processed"],
        "artists_classified": artists_stats["classified"],
        "artists_failed": artists_stats["failed"],
        "artists_skipped": artists_stats["skipped"],
        "elapsed_ms": elapsed_ms,
    }
    logger.info("[classification-sweep] %s", result)
    return result


async def _sweep_one_table(
    db: AsyncSession,
    classifier: GenreClassifier,
    model: Any,
    batch_size: int,
    force_reclassify: bool,
) -> dict[str, int]:
    """Process one entity table (Track or Artist)."""
    table_name = model.__tablename__

    # Find candidates: rows with `metadata_json.needs_classification == true`,
    # OR (if force_reclassify) the "skipped" sentinel.
    if force_reclassify:
        where_clause = text(
            "metadata_json->>'needs_classification' IN ('true', 'skipped')"
        )
    else:
        where_clause = text("metadata_json->>'needs_classification' = 'true'")

    stmt = (
        select(model)
        .where(where_clause)
        .order_by(model.updated_at.asc().nullsfirst())
        .limit(batch_size)
    )
    result = await db.execute(stmt)
    candidates = result.scalars().all()

    stats = {"processed": 0, "classified": 0, "failed": 0, "skipped": 0}

    for entity in candidates:
        stats["processed"] += 1
        try:
            classification = await classifier.classify_and_save(entity)
            entity.metadata_json = {
                **(entity.metadata_json or {}),
                "needs_classification": False,
                "classification_quality": classification.classification_quality,
                "classification_attempts": (entity.metadata_json or {}).get(
                    "classification_attempts", 0
                ) + 1,
                "classified_at": datetime.now(timezone.utc).isoformat(),
            }
            if classification.primary_genres:
                stats["classified"] += 1
            else:
                # Classifier ran but produced no genres — count as a soft skip,
                # not a failure. Still clear the flag so we don't retry.
                stats["skipped"] += 1
        except Exception as exc:
            stats["failed"] += 1
            attempts = (entity.metadata_json or {}).get("classification_attempts", 0) + 1
            logger.warning(
                "[classification-sweep] %s id=%s attempt %d failed: %s",
                table_name, entity.id, attempts, exc,
            )
            if attempts >= MAX_RETRIES_BEFORE_SKIP:
                entity.metadata_json = {
                    **(entity.metadata_json or {}),
                    "needs_classification": "skipped",
                    "classification_attempts": attempts,
                    "classification_failed_at": datetime.now(timezone.utc).isoformat(),
                    "classification_last_error": str(exc)[:500],
                }
                logger.warning(
                    "[classification-sweep] %s id=%s permanently skipped after %d attempts",
                    table_name, entity.id, attempts,
                )
            else:
                entity.metadata_json = {
                    **(entity.metadata_json or {}),
                    "needs_classification": True,  # leave flag so we retry
                    "classification_attempts": attempts,
                    "classification_last_error": str(exc)[:500],
                }

    return stats


async def count_pending_classification(db: AsyncSession) -> dict[str, int]:
    """Quick status check: how many entities are waiting?"""
    track_count = (await db.execute(
        text("SELECT COUNT(*) FROM tracks WHERE metadata_json->>'needs_classification' = 'true'")
    )).scalar() or 0
    artist_count = (await db.execute(
        text("SELECT COUNT(*) FROM artists WHERE metadata_json->>'needs_classification' = 'true'")
    )).scalar() or 0
    track_skipped = (await db.execute(
        text("SELECT COUNT(*) FROM tracks WHERE metadata_json->>'needs_classification' = 'skipped'")
    )).scalar() or 0
    artist_skipped = (await db.execute(
        text("SELECT COUNT(*) FROM artists WHERE metadata_json->>'needs_classification' = 'skipped'")
    )).scalar() or 0
    return {
        "tracks_pending": int(track_count),
        "artists_pending": int(artist_count),
        "tracks_permanently_skipped": int(track_skipped),
        "artists_permanently_skipped": int(artist_skipped),
    }
