import logging
import uuid

from Levenshtein import ratio as levenshtein_ratio
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.artist import Artist
from api.models.track import Track
from api.schemas.trending import EntityIdentifier

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize for fuzzy matching: lowercase, strip feat/remaster/punctuation."""
    import re

    name = name.lower().strip()
    name = re.sub(r"\(feat\..*?\)", "", name)
    name = re.sub(r"\(ft\..*?\)", "", name)
    name = re.sub(r"- remaster.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"- .*?remaster.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w\s]", "", name)
    return name.strip()


def _backfill_platform_ids(track: Track, identifier: EntityIdentifier) -> None:
    """Merge any missing platform IDs from the identifier onto the track.

    This ensures that when the same song is found on a new platform we
    record the new platform ID on the existing canonical entity.
    """
    _FIELDS = [
        ("spotify_id", "spotify_id"),
        ("apple_music_id", "apple_music_id"),
        ("shazam_id", "shazam_id"),
        ("tiktok_sound_id", "tiktok_sound_id"),
        ("billboard_id", "billboard_id"),
        ("chartmetric_id", "chartmetric_id"),
        ("isrc", "isrc"),
    ]
    for track_attr, id_attr in _FIELDS:
        incoming = getattr(identifier, id_attr, None)
        if incoming and not getattr(track, track_attr, None):
            setattr(track, track_attr, incoming)


async def resolve_track(
    db: AsyncSession,
    identifier: EntityIdentifier,
) -> tuple[Track, bool]:
    """Resolve a track from the identifier. Returns (track, is_new).

    Resolution order:
      1. ISRC match (international standard, highest reliability)
      2. Any platform ID match (spotify, apple_music, shazam, tiktok, billboard, chartmetric)
      3. Fuzzy title + artist match (Levenshtein ratio >= 0.85)
      4. Create new entity
    """

    # ------------------------------------------------------------------
    # 1. ISRC match — best cross-platform key
    # ------------------------------------------------------------------
    if identifier.isrc:
        result = await db.execute(
            select(Track).where(Track.isrc == identifier.isrc)
        )
        track = result.scalar_one_or_none()
        if track:
            _backfill_platform_ids(track, identifier)
            return track, False

    # ------------------------------------------------------------------
    # 2. Platform ID match — check all known platform IDs in one query
    # ------------------------------------------------------------------
    platform_conditions = []
    if identifier.spotify_id:
        platform_conditions.append(Track.spotify_id == identifier.spotify_id)
    if identifier.apple_music_id:
        platform_conditions.append(Track.apple_music_id == identifier.apple_music_id)
    if identifier.shazam_id:
        platform_conditions.append(Track.shazam_id == identifier.shazam_id)
    if identifier.tiktok_sound_id:
        platform_conditions.append(Track.tiktok_sound_id == identifier.tiktok_sound_id)
    if identifier.billboard_id:
        platform_conditions.append(Track.billboard_id == identifier.billboard_id)
    if identifier.chartmetric_id is not None:
        platform_conditions.append(Track.chartmetric_id == identifier.chartmetric_id)

    if platform_conditions:
        result = await db.execute(
            select(Track).where(or_(*platform_conditions))
        )
        track = result.scalar_one_or_none()
        if track:
            _backfill_platform_ids(track, identifier)
            return track, False

    # ------------------------------------------------------------------
    # 3. Fuzzy title + artist match
    # ------------------------------------------------------------------
    if identifier.title and identifier.artist_name:
        normalized_title = _normalize_name(identifier.title)
        normalized_artist = _normalize_name(identifier.artist_name)

        result = await db.execute(select(Track))
        tracks = result.scalars().all()

        best_match = None
        best_ratio = 0.0
        for t in tracks:
            t_title = _normalize_name(t.title)
            artist_name = ""
            if t.artist:
                artist_name = _normalize_name(t.artist.name)

            title_ratio = levenshtein_ratio(normalized_title, t_title)
            artist_ratio = levenshtein_ratio(normalized_artist, artist_name)
            combined = (title_ratio + artist_ratio) / 2

            if combined > best_ratio:
                best_ratio = combined
                best_match = t

        if best_match and best_ratio >= 0.85:
            _backfill_platform_ids(best_match, identifier)
            return best_match, False

    # ------------------------------------------------------------------
    # 4. No match — create new entity
    # ------------------------------------------------------------------
    artist = await _resolve_or_create_artist(db, identifier)

    track = Track(
        id=uuid.uuid4(),
        title=identifier.title or "Unknown",
        artist_id=artist.id,
        spotify_id=identifier.spotify_id,
        isrc=identifier.isrc,
        apple_music_id=identifier.apple_music_id,
        shazam_id=identifier.shazam_id,
        tiktok_sound_id=identifier.tiktok_sound_id,
        billboard_id=identifier.billboard_id,
        chartmetric_id=identifier.chartmetric_id,
    )
    db.add(track)
    await db.flush()
    return track, True


async def resolve_artist(
    db: AsyncSession,
    identifier: EntityIdentifier,
) -> tuple[Artist, bool]:
    """Resolve an artist from the identifier. Returns (artist, is_new)."""

    # 1. Platform ID match
    if identifier.artist_spotify_id or identifier.spotify_id:
        sid = identifier.artist_spotify_id or identifier.spotify_id
        result = await db.execute(
            select(Artist).where(Artist.spotify_id == sid)
        )
        artist = result.scalar_one_or_none()
        if artist:
            return artist, False

    # 2. Fuzzy name match
    if identifier.artist_name:
        return await _resolve_or_create_artist(db, identifier), False

    # 3. Create new
    artist = Artist(
        id=uuid.uuid4(),
        name=identifier.artist_name or "Unknown Artist",
        spotify_id=identifier.artist_spotify_id or identifier.spotify_id,
        metadata_json={"needs_classification": True},
    )
    db.add(artist)
    await db.flush()
    return artist, True


async def _resolve_or_create_artist(
    db: AsyncSession,
    identifier: EntityIdentifier,
) -> Artist:
    """Find or create an artist from identifier data."""
    spotify_id = identifier.artist_spotify_id or None

    if spotify_id:
        result = await db.execute(select(Artist).where(Artist.spotify_id == spotify_id))
        artist = result.scalar_one_or_none()
        if artist:
            return artist

    if identifier.artist_name:
        normalized = _normalize_name(identifier.artist_name)
        result = await db.execute(select(Artist))
        artists = result.scalars().all()
        for a in artists:
            if levenshtein_ratio(normalized, _normalize_name(a.name)) >= 0.90:
                return a

    artist = Artist(
        id=uuid.uuid4(),
        name=identifier.artist_name or "Unknown Artist",
        spotify_id=spotify_id,
        metadata_json={"needs_classification": True},
    )
    db.add(artist)
    await db.flush()
    return artist
