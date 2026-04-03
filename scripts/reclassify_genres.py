"""
Weekly genre re-classification for low-quality entities.

Usage:
    python -m scripts.reclassify_genres [--dry-run] [--limit 500]

Re-classifies entities that have:
- Empty genres array
- classification_quality == "low" in metadata_json
- Never been classified (no classification_quality key)
"""

import argparse
import asyncio
import logging
import os

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://soundpulse:soundpulse_dev@localhost:5432/soundpulse",
)


async def reclassify(dry_run: bool = False, limit: int = 500):
    from api.models.artist import Artist
    from api.models.track import Track
    from api.services.genre_classifier import GenreClassifier

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"artists_processed": 0, "tracks_processed": 0, "upgraded": 0, "skipped": 0}

    async with async_session() as db:
        classifier = GenreClassifier(db)

        # Find artists needing classification
        result = await db.execute(
            select(Artist).where(
                or_(
                    Artist.genres == [],  # empty genres
                    Artist.genres.is_(None),
                    text("metadata_json->>'classification_quality' = 'low'"),
                    text("metadata_json->>'classification_quality' IS NULL"),
                )
            ).limit(limit)
        )
        artists = result.scalars().all()
        logger.info(f"Found {len(artists)} artists needing re-classification")

        for artist in artists:
            try:
                result = await classifier.classify(artist)
                old_genres = list(artist.genres or [])
                old_quality = (artist.metadata_json or {}).get("classification_quality", "none")

                if not dry_run and result.primary_genres:
                    artist.genres = result.primary_genres
                    artist.metadata_json = {
                        **(artist.metadata_json or {}),
                        "classification_quality": result.classification_quality,
                    }

                stats["artists_processed"] += 1
                if result.classification_quality != "low" and old_quality in ("low", "none", None):
                    stats["upgraded"] += 1

                logger.info(
                    f"Artist '{artist.name}': {old_genres} -> {result.primary_genres} "
                    f"(quality: {old_quality} -> {result.classification_quality})"
                )
            except Exception:
                logger.exception(f"Failed to classify artist {artist.id}")
                stats["skipped"] += 1

        # Find tracks needing classification
        result = await db.execute(
            select(Track).where(
                or_(
                    Track.genres == [],
                    Track.genres.is_(None),
                    text("metadata_json->>'classification_quality' = 'low'"),
                    text("metadata_json->>'classification_quality' IS NULL"),
                )
            ).limit(limit)
        )
        tracks = result.scalars().all()
        logger.info(f"Found {len(tracks)} tracks needing re-classification")

        for track in tracks:
            try:
                result = await classifier.classify(track)
                old_genres = list(track.genres or [])
                old_quality = (track.metadata_json or {}).get("classification_quality", "none")

                if not dry_run and result.primary_genres:
                    track.genres = result.primary_genres
                    track.metadata_json = {
                        **(track.metadata_json or {}),
                        "classification_quality": result.classification_quality,
                    }

                stats["tracks_processed"] += 1
                if result.classification_quality != "low" and old_quality in ("low", "none", None):
                    stats["upgraded"] += 1

                logger.info(
                    f"Track '{track.title}': {old_genres} -> {result.primary_genres} "
                    f"(quality: {old_quality} -> {result.classification_quality})"
                )
            except Exception:
                logger.exception(f"Failed to classify track {track.id}")
                stats["skipped"] += 1

        if not dry_run:
            await db.commit()
            logger.info("Changes committed to database")
        else:
            logger.info("DRY RUN — no changes committed")

    await engine.dispose()
    logger.info(f"Done. Stats: {stats}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-classify entities with low/missing genres")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    parser.add_argument("--limit", type=int, default=500, help="Max entities to process")
    args = parser.parse_args()
    asyncio.run(reclassify(dry_run=args.dry_run, limit=args.limit))
