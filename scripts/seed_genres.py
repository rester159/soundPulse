"""
Seed the genres table from the canonical genre taxonomy.

Usage:
    python -m scripts.seed_genres

Env vars:
    DATABASE_URL_SYNC  (default: postgresql://soundpulse:soundpulse_dev@localhost:5432/soundpulse)
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from shared.genre_taxonomy import GENRE_TAXONOMY

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://soundpulse:soundpulse_dev@localhost:5432/soundpulse",
)

UPSERT_SQL = text("""
    INSERT INTO genres (
        id, name, parent_id, root_category, depth,
        spotify_genres, apple_music_genres, musicbrainz_tags,
        chartmetric_genres, audio_profile, adjacent_genres, status
    ) VALUES (
        :id, :name, :parent_id, :root_category, :depth,
        :spotify_genres, :apple_music_genres, :musicbrainz_tags,
        :chartmetric_genres, CAST(:audio_profile AS jsonb), :adjacent_genres, :status
    )
    ON CONFLICT (id) DO UPDATE SET
        name              = EXCLUDED.name,
        parent_id         = EXCLUDED.parent_id,
        root_category     = EXCLUDED.root_category,
        depth             = EXCLUDED.depth,
        spotify_genres    = EXCLUDED.spotify_genres,
        apple_music_genres = EXCLUDED.apple_music_genres,
        musicbrainz_tags  = EXCLUDED.musicbrainz_tags,
        chartmetric_genres = EXCLUDED.chartmetric_genres,
        audio_profile     = EXCLUDED.audio_profile,
        adjacent_genres   = EXCLUDED.adjacent_genres,
        status            = EXCLUDED.status,
        updated_at        = now()
""")


def seed_genres() -> int:
    """Insert or update every genre from the taxonomy. Returns count of rows upserted."""
    import json

    engine = create_engine(DATABASE_URL_SYNC, echo=False)

    count = 0
    with Session(engine) as session:
        for genre in GENRE_TAXONOMY:
            session.execute(
                UPSERT_SQL,
                {
                    "id": genre["id"],
                    "name": genre["name"],
                    "parent_id": genre.get("parent_id"),
                    "root_category": genre["root_category"],
                    "depth": genre["depth"],
                    "spotify_genres": genre.get("spotify_genres", []),
                    "apple_music_genres": genre.get("apple_music_genres", []),
                    "musicbrainz_tags": genre.get("musicbrainz_tags", []),
                    "chartmetric_genres": genre.get("chartmetric_genres", []),
                    "audio_profile": json.dumps(genre.get("audio_profile")),
                    "adjacent_genres": genre.get("adjacent_genres", []),
                    "status": genre.get("status", "active"),
                },
            )
            count += 1
        session.commit()

    engine.dispose()
    return count


if __name__ == "__main__":
    total = seed_genres()
    print(f"Seeded {total} genres into the database.")
