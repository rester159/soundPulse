import logging
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from api.database import get_db
from api.dependencies import get_api_key_record, get_redis, require_admin
from api.models.api_key import ApiKey
from api.models.artist import Artist
from api.models.track import Track
from api.models.trending_snapshot import TrendingSnapshot
from api.schemas.trending import (
    TrendingIngest,
    TrendingIngestBulk,
    TrendingIngestBulkResponse,
    TrendingIngestResponse,
    TrendingResponse,
)
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
    # so the genre classifier can use them.
    # P1-012: also grab Chartmetric's raw `signals.genres` field (which is a
    # comma-separated string like "pop, dance pop, chill pop") and store it
    # under `chartmetric_genres`. The classifier's _normalize_label_list
    # handles both list and string shapes.
    signals = body.signals or {}
    metadata_updates = {}
    for key in ("spotify_genres", "apple_music_genres", "musicbrainz_tags",
                "chartmetric_genres", "tiktok_hashtags", "playlist_genres"):
        if key in signals:
            metadata_updates[key] = signals[key]
    # Chartmetric comma-string fallback — if `chartmetric_genres` wasn't set
    # explicitly, check the raw `genres` / `track_genre` fields.
    if "chartmetric_genres" not in metadata_updates:
        raw_cm_genres = signals.get("genres") or signals.get("track_genre")
        if raw_cm_genres:
            metadata_updates["chartmetric_genres"] = raw_cm_genres
    if metadata_updates:
        entity.metadata_json = {**(entity.metadata_json or {}), **metadata_updates}

    # Copy audio features to track model if provided
    if body.entity_type == "track" and "audio_features" in signals:
        entity.audio_features = signals["audio_features"]

    # Classify genre on new entities or when new platform data arrives.
    # AUD-001: previously this `except Exception: pass`-equivalent silently
    # swallowed every classifier failure, masking the bug that left ~95% of
    # tracks unclassified. We now log the exception with the entity id, type,
    # and any signals that might explain the failure.
    needs_classification = is_new or not entity.genres or bool(metadata_updates)
    if needs_classification:
        try:
            classifier = GenreClassifier(db)
            classification = await classifier.classify_and_save(entity)
            entity.metadata_json = {
                **(entity.metadata_json or {}),
                "classification_quality": classification.classification_quality,
            }
        except Exception as classifier_exc:
            logger.warning(
                "[trending-ingest] genre classifier failed for %s id=%s name=%s: %s "
                "(metadata_updates=%s, signals_keys=%s)",
                body.entity_type,
                getattr(entity, "id", None),
                getattr(entity, "title", None) or getattr(entity, "name", None),
                classifier_exc,
                list(metadata_updates.keys()),
                list((body.signals or {}).keys()),
            )
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


@router.post("/bulk", response_model=TrendingIngestBulkResponse, status_code=201)
async def ingest_trending_bulk(
    body: TrendingIngestBulk,
    db: AsyncSession = Depends(get_db),
    admin_key: ApiKey = Depends(require_admin),
    redis=Depends(get_redis),
):
    """
    Bulk trending ingest. Accepts up to 1000 items per call.

    Optimized for large-scale backfills:
      - Single DB transaction for the whole batch
      - Entity resolution runs per item but reuses the session (no per-item commit)
      - Snapshot inserts use ON CONFLICT DO NOTHING (no per-item duplicate query)
      - Genre classification and composite-score recalc are DEFERRED — entities
        are tagged in metadata_json with `needs_classification: true` and a
        background sweep handles them
      - Cache invalidation happens once at the end, not per item
      - Normalized score is left at 0.0; the deferred sweep computes it via the
        normal aggregation/normalization pipeline

    Returns counts: ingested, duplicates, errors, entities_created.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    items = body.items
    n_items = len(items)

    # Validate up front (cheap, fail fast on bad batches)
    for i, item in enumerate(items):
        if item.platform not in VALID_PLATFORMS:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "VALIDATION_ERROR",
                                  "message": f"items[{i}]: invalid platform '{item.platform}'", "details": {}}},
            )
        if item.entity_type not in VALID_ENTITY_TYPES:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "VALIDATION_ERROR",
                                  "message": f"items[{i}]: invalid entity_type '{item.entity_type}'", "details": {}}},
            )
        ident = item.entity_identifier
        if not any([ident.spotify_id, ident.apple_music_id, ident.tiktok_sound_id, ident.isrc, ident.title]):
            raise HTTPException(
                status_code=422,
                detail={"error": {"code": "UNPROCESSABLE_ENTITY",
                                  "message": f"items[{i}]: no usable identifiers", "details": {}}},
            )

    started = datetime.now(timezone.utc)
    entities_created = 0
    snapshot_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for i, item in enumerate(items):
        try:
            if item.entity_type == "track":
                entity, is_new = await resolve_track(db, item.entity_identifier)
            else:
                entity, is_new = await resolve_artist(db, item.entity_identifier)

            if is_new:
                entities_created += 1

            # Merge classification-relevant signals into metadata so the deferred
            # sweep has them available
            sig = item.signals or {}

            # Phase 2b/4 fix: when a track's signals include cm_artist_id
            # (Chartmetric's artist ID), propagate it onto the resolved
            # artist row so the artist-based scrapers can find it. Before
            # this fix, cm_artist_id lived only in signals_json and
            # artists.chartmetric_id was never populated — causing the
            # Phase 2b (per-artist tracks) and Phase 4 (artist stats)
            # scrapers to walk an empty result set.
            if item.entity_type == "track" and sig.get("cm_artist_id"):
                try:
                    # Chartmetric ships cm_artist as a list for multi-artist
                    # tracks; take the primary so we never try to int() a list.
                    cm_raw = sig["cm_artist_id"]
                    if isinstance(cm_raw, list):
                        cm_raw = cm_raw[0] if cm_raw else None
                    cm_artist_int = int(cm_raw) if cm_raw is not None else None
                    artist_id_fk = getattr(entity, "artist_id", None)
                    if artist_id_fk is not None:
                        # Load the artist and set chartmetric_id if missing
                        artist_result = await db.execute(
                            select(Artist).where(Artist.id == artist_id_fk)
                        )
                        artist_row = artist_result.scalar_one_or_none()
                        if (
                            artist_row is not None
                            and artist_row.chartmetric_id is None
                            and cm_artist_int is not None
                        ):
                            artist_row.chartmetric_id = cm_artist_int
                except (ValueError, TypeError):
                    pass
            meta_updates: dict[str, Any] = {}
            for key in ("spotify_genres", "apple_music_genres", "musicbrainz_tags",
                        "chartmetric_genres", "tiktok_hashtags", "playlist_genres", "genres"):
                if key in sig:
                    meta_updates[key] = sig[key]
            if meta_updates or is_new or not (entity.metadata_json or {}).get("classification_quality"):
                entity.metadata_json = {
                    **(entity.metadata_json or {}),
                    **meta_updates,
                    "needs_classification": True,
                }

            # Audio features get copied directly to the track row when present
            if item.entity_type == "track" and "audio_features" in sig and sig["audio_features"]:
                entity.audio_features = sig["audio_features"]

            snapshot_rows.append({
                "id": uuid_mod.uuid4(),
                "entity_type": item.entity_type,
                "entity_id": entity.id,
                "snapshot_date": item.snapshot_date,
                "platform": item.platform,
                "platform_rank": item.rank,
                "platform_score": item.raw_score,
                "normalized_score": 0.0,
                "signals_json": item.signals or {},
            })
        except Exception as exc:
            errors.append({"index": i, "error": str(exc)[:300]})

    # Flush entity changes (so snapshot FK references resolve) before bulk insert
    await db.flush()

    ingested = 0
    duplicates = 0
    if snapshot_rows:
        stmt = pg_insert(TrendingSnapshot).values(snapshot_rows)
        # ON CONFLICT against the unique (entity_type, entity_id, snapshot_date, platform) constraint
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["entity_type", "entity_id", "snapshot_date", "platform"]
        )
        result = await db.execute(stmt)
        ingested = result.rowcount or 0
        duplicates = len(snapshot_rows) - ingested

    await db.commit()

    # Single cache invalidation
    cache = CacheService(redis)
    await cache.delete_pattern("trending:*")

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    return TrendingIngestBulkResponse(
        data={
            "received": n_items,
            "ingested": ingested,
            "duplicates": duplicates,
            "errors": len(errors),
            "entities_created": entities_created,
            "elapsed_ms": elapsed_ms,
            "error_samples": errors[:5],
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

    # Anchor the time window to the most recent snapshot date in the DB,
    # not today(). This ensures historical backfill data always shows up
    # even if months/years have passed since it was ingested.
    latest_row = await db.execute(
        select(func.max(TrendingSnapshot.snapshot_date))
        .where(TrendingSnapshot.entity_type == entity_type)
    )
    latest_date = latest_row.scalar() or date.today()

    if time_range == "today":
        start_date = latest_date - timedelta(days=3)
    elif time_range == "7d":
        start_date = latest_date - timedelta(days=7)
    else:
        start_date = latest_date - timedelta(days=60)

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
