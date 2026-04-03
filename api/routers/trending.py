import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key_record, get_redis, require_admin
from api.models.api_key import ApiKey
from api.models.artist import Artist
from api.models.track import Track
from api.models.trending_snapshot import TrendingSnapshot
from api.schemas.trending import TrendingIngest, TrendingIngestResponse, TrendingResponse
from api.services.aggregation import recalculate_composite_for_entity
from api.services.cache import CacheService
from api.services.entity_resolution import resolve_artist, resolve_track
from api.services.genre_classifier import GenreClassifier
from api.services.normalization import calculate_velocity, normalize_score
from shared.constants import CACHE_TTL, VALID_ENTITY_TYPES, VALID_PLATFORMS, VALID_TIME_RANGES, VALID_TRENDING_SORT

router = APIRouter(prefix="/api/v1/trending", tags=["trending"])


@router.post("", response_model=TrendingIngestResponse, status_code=201)
async def ingest_trending(
    body: TrendingIngest,
    db: AsyncSession = Depends(get_db),
    admin_key: ApiKey = Depends(require_admin),
    redis=Depends(get_redis),
):
    # Validate platform
    if body.platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid platform: {body.platform}", "details": {}}},
        )
    if body.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid entity_type: {body.entity_type}", "details": {}}},
        )

    ident = body.entity_identifier
    has_any = any([ident.spotify_id, ident.apple_music_id, ident.tiktok_sound_id, ident.isrc, ident.title])
    if not has_any:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "UNPROCESSABLE_ENTITY", "message": "No usable identifiers provided", "details": {}}},
        )

    # Entity resolution
    if body.entity_type == "track":
        entity, is_new = await resolve_track(db, ident)
        entity_name = entity.title
        matched_by = "new" if is_new else "resolved"
    else:
        entity, is_new = await resolve_artist(db, ident)
        entity_name = entity.name
        matched_by = "new" if is_new else "resolved"

    # Merge genre-relevant signals from the ingest payload into entity metadata
    # so the genre classifier can use them
    signals = body.signals or {}
    metadata_updates = {}
    for key in ("spotify_genres", "apple_music_genres", "musicbrainz_tags",
                "chartmetric_genres", "tiktok_hashtags", "playlist_genres"):
        if key in signals:
            metadata_updates[key] = signals[key]
    if metadata_updates:
        entity.metadata_json = {**(entity.metadata_json or {}), **metadata_updates}

    # Copy audio features to track model if provided
    if body.entity_type == "track" and "audio_features" in signals:
        entity.audio_features = signals["audio_features"]

    # Classify genre on new entities or when new platform data arrives
    needs_classification = is_new or not entity.genres or bool(metadata_updates)
    if needs_classification:
        try:
            classifier = GenreClassifier(db)
            classification = await classifier.classify_and_save(entity)
            entity.metadata_json = {
                **(entity.metadata_json or {}),
                "classification_quality": classification.classification_quality,
            }
        except Exception:
            # Classification failure must not corrupt the DB session
            await db.rollback()
            # Re-fetch the entity after rollback
            if body.entity_type == "track":
                from sqlalchemy import select as sa_select
                result = await db.execute(sa_select(Track).where(Track.id == entity.id))
                entity = result.scalar_one_or_none()
                if not entity:
                    entity, _ = await resolve_track(db, ident)
            else:
                from sqlalchemy import select as sa_select
                result = await db.execute(sa_select(Artist).where(Artist.id == entity.id))
                entity = result.scalar_one_or_none()
                if not entity:
                    entity, _ = await resolve_artist(db, ident)

    # Check for duplicate snapshot
    existing = await db.execute(
        select(TrendingSnapshot).where(
            TrendingSnapshot.entity_type == body.entity_type,
            TrendingSnapshot.entity_id == entity.id,
            TrendingSnapshot.snapshot_date == body.snapshot_date,
            TrendingSnapshot.platform == body.platform,
        )
    )
    dup = existing.scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "Duplicate snapshot already exists",
                    "details": {"snapshot_id": str(dup.id)},
                }
            },
        )

    # Normalize score
    norm_score = await normalize_score(db, body.platform, body.entity_type, body.raw_score, body.rank)

    # Create snapshot
    snapshot = TrendingSnapshot(
        id=uuid_mod.uuid4(),
        entity_type=body.entity_type,
        entity_id=entity.id,
        snapshot_date=body.snapshot_date,
        platform=body.platform,
        platform_rank=body.rank,
        platform_score=body.raw_score,
        normalized_score=norm_score,
        signals_json=body.signals,
    )
    db.add(snapshot)
    await db.flush()

    # Recalculate composite
    composite = await recalculate_composite_for_entity(
        db, str(entity.id), body.entity_type, body.snapshot_date
    )

    # Invalidate cache
    cache = CacheService(redis)
    await cache.delete_pattern("trending:*")

    return TrendingIngestResponse(
        data={
            "entity_id": str(entity.id),
            "entity_type": body.entity_type,
            "entity_name": entity_name,
            "matched_by": matched_by,
            "is_new_entity": is_new,
            "normalized_score": norm_score,
            "snapshot_id": str(snapshot.id),
        }
    )


@router.get("", response_model=TrendingResponse)
async def get_trending(
    entity_type: str = Query(..., description="'artist' or 'track'"),
    genre: str | None = Query(None),
    platform: str | None = Query(None),
    time_range: str = Query("today"),
    limit: int = Query(50, ge=10, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("composite_score"),
    min_platforms: int = Query(1, ge=1, le=6),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_record),
    redis=Depends(get_redis),
):
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid entity_type: {entity_type}", "details": {}}},
        )
    if time_range not in VALID_TIME_RANGES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid time_range: {time_range}", "details": {}}},
        )
    if sort not in VALID_TRENDING_SORT:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid sort: {sort}", "details": {}}},
        )

    # Check cache
    cache = CacheService(redis)
    cache_key = f"trending:{entity_type}:{genre}:{platform}:{time_range}:{sort}:{limit}:{offset}:{min_platforms}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Determine date range
    today = date.today()
    if time_range == "today":
        start_date = today
    elif time_range == "7d":
        start_date = today - timedelta(days=7)
    else:
        start_date = today - timedelta(days=30)

    # Build query — get latest snapshot per entity per platform
    subq = (
        select(
            TrendingSnapshot.entity_id,
            TrendingSnapshot.platform,
            func.max(TrendingSnapshot.snapshot_date).label("latest_date"),
        )
        .where(
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date >= start_date,
        )
        .group_by(TrendingSnapshot.entity_id, TrendingSnapshot.platform)
        .subquery()
    )

    # Get the actual snapshot rows
    snap_query = (
        select(TrendingSnapshot)
        .join(
            subq,
            and_(
                TrendingSnapshot.entity_id == subq.c.entity_id,
                TrendingSnapshot.platform == subq.c.platform,
                TrendingSnapshot.snapshot_date == subq.c.latest_date,
            ),
        )
        .where(TrendingSnapshot.entity_type == entity_type)
    )

    if platform:
        snap_query = snap_query.where(TrendingSnapshot.platform == platform)

    result = await db.execute(snap_query)
    snapshots = result.scalars().all()

    # Group by entity
    entity_data: dict[str, dict[str, Any]] = {}
    for snap in snapshots:
        eid = str(snap.entity_id)
        if eid not in entity_data:
            entity_data[eid] = {"snapshots": {}, "composite": snap.composite_score or 0.0}
        entity_data[eid]["snapshots"][snap.platform] = snap
        if snap.composite_score is not None:
            entity_data[eid]["composite"] = max(entity_data[eid]["composite"], snap.composite_score)

    # Filter by min_platforms
    entity_data = {eid: d for eid, d in entity_data.items() if len(d["snapshots"]) >= min_platforms}

    # Filter by genre
    if genre:
        filtered = {}
        for eid, d in entity_data.items():
            if entity_type == "track":
                r = await db.execute(select(Track).where(Track.id == eid))
                entity_obj = r.scalar_one_or_none()
                if entity_obj and any(g.startswith(genre) for g in (entity_obj.genres or [])):
                    filtered[eid] = d
            else:
                r = await db.execute(select(Artist).where(Artist.id == eid))
                entity_obj = r.scalar_one_or_none()
                if entity_obj and any(g.startswith(genre) for g in (entity_obj.genres or [])):
                    filtered[eid] = d
        entity_data = filtered

    # Sort
    def sort_key(item):
        eid, d = item
        if sort == "composite_score":
            return d["composite"]
        elif sort == "velocity":
            snaps = list(d["snapshots"].values())
            return snaps[0].velocity or 0.0 if snaps else 0.0
        else:  # platform_rank
            snaps = list(d["snapshots"].values())
            return -(snaps[0].platform_rank or 999) if snaps else -999

    sorted_entities = sorted(entity_data.items(), key=sort_key, reverse=True)
    total = len(sorted_entities)
    page = sorted_entities[offset : offset + limit]

    # Build response
    items = []
    for eid, d in page:
        if entity_type == "track":
            r = await db.execute(select(Track).where(Track.id == eid))
            entity_obj = r.scalar_one_or_none()
            if not entity_obj:
                continue
            entity_info = {
                "id": str(entity_obj.id),
                "type": "track",
                "name": entity_obj.title,
                "artist": {"id": str(entity_obj.artist_id), "name": entity_obj.artist.name if entity_obj.artist else ""},
                "image_url": None,
                "genres": entity_obj.genres or [],
                "isrc": entity_obj.isrc,
                "platform_ids": {},
            }
            if entity_obj.spotify_id:
                entity_info["platform_ids"]["spotify"] = entity_obj.spotify_id
        else:
            r = await db.execute(select(Artist).where(Artist.id == eid))
            entity_obj = r.scalar_one_or_none()
            if not entity_obj:
                continue
            entity_info = {
                "id": str(entity_obj.id),
                "type": "artist",
                "name": entity_obj.name,
                "image_url": entity_obj.image_url,
                "genres": entity_obj.genres or [],
                "platform_ids": {},
            }
            if entity_obj.spotify_id:
                entity_info["platform_ids"]["spotify"] = entity_obj.spotify_id

        platforms_data = {}
        for p, snap in d["snapshots"].items():
            platforms_data[p] = {
                "normalized_score": snap.normalized_score,
                "raw_score": snap.platform_score,
                "rank": snap.platform_rank,
                "signals": snap.signals_json or {},
                "last_updated": snap.updated_at.isoformat() if snap.updated_at else None,
            }

        scores = {
            "composite_score": d["composite"],
            "composite_score_previous": None,
            "position_change": None,
            "velocity": list(d["snapshots"].values())[0].velocity if d["snapshots"] else None,
            "acceleration": None,
            "platforms": platforms_data,
            "platform_count": len(d["snapshots"]),
        }

        items.append({"entity": entity_info, "scores": scores, "sparkline_7d": []})

    ttl_key = f"trending_{time_range}"
    response = {
        "data": items,
        "meta": {
            "request_id": f"req_{uuid_mod.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data_freshness": datetime.now(timezone.utc).isoformat(),
            "total": total,
            "limit": limit,
            "offset": offset,
            "time_range": time_range,
            "entity_type": entity_type,
            "filters_applied": {"genre": genre, "platform": platform, "min_platforms": min_platforms},
        },
    }

    await cache.set(cache_key, response, ttl=CACHE_TTL.get(ttl_key, 900))
    return response
