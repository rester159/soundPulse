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
        start_date = today - timedelta(days=1)  # include yesterday if today has no data
    elif time_range == "7d":
        start_date = today - timedelta(days=7)
    else:
        start_date = today - timedelta(days=30)

    # Determine date range — use a wide window if data is sparse
    today = date.today()
    if time_range == "today":
        start_date = today - timedelta(days=3)  # include recent days if today has no data
    elif time_range == "7d":
        start_date = today - timedelta(days=7)
    else:
        start_date = today - timedelta(days=60)  # wider window for 30d to ensure data

    # Use ORM but with a SINGLE query — no N+1
    # Step 1: Get aggregated snapshot data per entity (one query)
    agg_query = (
        select(
            TrendingSnapshot.entity_id,
            func.max(TrendingSnapshot.composite_score).label("max_composite"),
            func.avg(TrendingSnapshot.velocity).label("avg_velocity"),
            func.min(TrendingSnapshot.platform_rank).label("best_rank"),
            func.count(func.distinct(TrendingSnapshot.platform)).label("platform_count"),
        )
        .where(
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date >= start_date,
        )
        .group_by(TrendingSnapshot.entity_id)
        .having(func.count(func.distinct(TrendingSnapshot.platform)) >= min_platforms)
    )

    if sort == "velocity":
        agg_query = agg_query.order_by(func.avg(TrendingSnapshot.velocity).desc().nullslast())
    elif sort == "platform_rank":
        agg_query = agg_query.order_by(func.min(TrendingSnapshot.platform_rank).asc().nullslast())
    else:
        agg_query = agg_query.order_by(func.max(TrendingSnapshot.composite_score).desc().nullslast())

    agg_query = agg_query.limit(limit).offset(offset)

    result = await db.execute(agg_query)
    agg_rows = result.all()

    if not agg_rows:
        items = []
        total = 0
    else:
        entity_ids = [str(row.entity_id) for row in agg_rows]

        # Step 2: Batch fetch entity info (one query, not N)
        entity_map = {}
        if entity_type == "track":
            track_result = await db.execute(
                select(Track.id, Track.title, Track.spotify_id, Track.isrc, Track.artist_id)
                .where(Track.id.in_(entity_ids))
            )
            for t in track_result.all():
                entity_map[str(t.id)] = {"name": t.title, "spotify_id": t.spotify_id, "isrc": t.isrc, "artist_id": str(t.artist_id) if t.artist_id else None}

            # Batch fetch artist names
            artist_ids = [v["artist_id"] for v in entity_map.values() if v.get("artist_id")]
            artist_name_map = {}
            if artist_ids:
                artist_result = await db.execute(
                    select(Artist.id, Artist.name).where(Artist.id.in_(artist_ids))
                )
                artist_name_map = {str(a.id): a.name for a in artist_result.all()}
        else:
            artist_result = await db.execute(
                select(Artist.id, Artist.name, Artist.spotify_id, Artist.image_url)
                .where(Artist.id.in_(entity_ids))
            )
            for a in artist_result.all():
                entity_map[str(a.id)] = {"name": a.name, "spotify_id": a.spotify_id, "image_url": a.image_url}
            artist_name_map = {}

        # Count total
        count_q = (
            select(func.count(func.distinct(TrendingSnapshot.entity_id)))
            .where(TrendingSnapshot.entity_type == entity_type, TrendingSnapshot.snapshot_date >= start_date)
        )
        total = (await db.execute(count_q)).scalar() or 0

        # Build response items
        items = []
        for row in agg_rows:
            eid = str(row.entity_id)
            info = entity_map.get(eid, {})

            entity_info = {
                "id": eid,
                "type": entity_type,
                "name": info.get("name", "Unknown"),
                "image_url": info.get("image_url"),
                "genres": [],
                "isrc": info.get("isrc"),
                "platform_ids": {},
            }
            if entity_type == "track":
                entity_info["artist"] = {
                    "id": info.get("artist_id", ""),
                    "name": artist_name_map.get(info.get("artist_id", ""), ""),
                }
            if info.get("spotify_id"):
                entity_info["platform_ids"]["spotify"] = info["spotify_id"]

            scores = {
                "composite_score": float(row.max_composite) if row.max_composite else 0,
                "composite_score_previous": None,
                "position_change": None,
                "velocity": float(row.avg_velocity) if row.avg_velocity else 0,
                "acceleration": None,
                "platforms": {},
                "platform_count": int(row.platform_count),
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
