import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key_record, get_redis
from api.models.api_key import ApiKey
from api.models.artist import Artist
from api.models.track import Track
from api.models.trending_snapshot import TrendingSnapshot
from api.schemas.search import SearchResponse
from api.services.cache import CacheService
from shared.constants import CACHE_TTL

router = APIRouter(prefix="/api/v1/search", tags=["search"])


def _strip_special(q: str) -> str:
    import re
    return re.sub(r"[^\w\s]", "", q).strip()


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    type: str = Query("all", description="'artist', 'track', or 'all'"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_record),
    redis=Depends(get_redis),
):
    if type not in ("artist", "track", "all"):
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid type: {type}", "details": {}}},
        )

    cache = CacheService(redis)
    import hashlib
    q_hash = hashlib.md5(q.encode()).hexdigest()[:12]
    cache_key = f"search:{q_hash}:{type}:{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    clean_q = _strip_special(q)
    if not clean_q:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Search query is empty after sanitization", "details": {}}},
        )

    results = []

    # Search artists
    if type in ("artist", "all"):
        # Try tsvector first
        ts_query = select(Artist).where(
            func.to_tsvector("english", Artist.name).match(clean_q)
        ).limit(limit)
        r = await db.execute(ts_query)
        artists = list(r.scalars().all())

        # Supplement with trigram if needed
        if len(artists) < 5:
            try:
                trgm_query = (
                    select(Artist)
                    .where(func.similarity(Artist.name, clean_q) > 0.3)
                    .order_by(func.similarity(Artist.name, clean_q).desc())
                    .limit(limit)
                )
                r = await db.execute(trgm_query)
                seen_ids = {a.id for a in artists}
                for a in r.scalars().all():
                    if a.id not in seen_ids:
                        artists.append(a)
            except Exception:
                pass  # pg_trgm not available

        for a in artists[:limit]:
            # Get latest trending data
            latest = await _get_latest_scores(db, str(a.id), "artist")
            results.append({
                "entity": {
                    "id": str(a.id),
                    "type": "artist",
                    "name": a.name,
                    "genres": a.genres or [],
                    "image_url": a.image_url,
                },
                "latest_scores": latest,
                "relevance_score": 0.9,
            })

    # Search tracks
    if type in ("track", "all"):
        ts_query = select(Track).where(
            func.to_tsvector("english", Track.title).match(clean_q)
        ).limit(limit)
        r = await db.execute(ts_query)
        tracks = list(r.scalars().all())

        if len(tracks) < 5:
            try:
                trgm_query = (
                    select(Track)
                    .where(func.similarity(Track.title, clean_q) > 0.3)
                    .order_by(func.similarity(Track.title, clean_q).desc())
                    .limit(limit)
                )
                r = await db.execute(trgm_query)
                seen_ids = {t.id for t in tracks}
                for t in r.scalars().all():
                    if t.id not in seen_ids:
                        tracks.append(t)
            except Exception:
                pass

        for t in tracks[:limit]:
            latest = await _get_latest_scores(db, str(t.id), "track")
            results.append({
                "entity": {
                    "id": str(t.id),
                    "type": "track",
                    "name": t.title,
                    "artist": {"id": str(t.artist_id), "name": t.artist.name if t.artist else ""},
                    "genres": t.genres or [],
                    "image_url": None,
                },
                "latest_scores": latest,
                "relevance_score": 0.85,
            })

    response = {
        "data": results[:limit],
        "meta": {
            "request_id": f"req_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(results),
            "query": q,
            "type_filter": type,
        },
    }

    await cache.set(cache_key, response, ttl=CACHE_TTL["search"])
    return response


async def _get_latest_scores(db: AsyncSession, entity_id: str, entity_type: str) -> dict:
    """Get latest composite score and velocity for an entity."""
    result = await db.execute(
        select(TrendingSnapshot)
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
        )
        .order_by(TrendingSnapshot.snapshot_date.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return {"composite_score": None, "velocity": None, "platform_count": 0, "last_updated": None}

    # Count platforms
    count_result = await db.execute(
        select(func.count(func.distinct(TrendingSnapshot.platform)))
        .where(
            TrendingSnapshot.entity_id == entity_id,
            TrendingSnapshot.entity_type == entity_type,
            TrendingSnapshot.snapshot_date == snap.snapshot_date,
        )
    )
    platform_count = count_result.scalar() or 0

    return {
        "composite_score": snap.composite_score,
        "velocity": snap.velocity,
        "platform_count": platform_count,
        "last_updated": snap.updated_at.isoformat() if snap.updated_at else None,
    }
