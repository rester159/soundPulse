import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key_record, get_redis
from api.models.api_key import ApiKey
from api.models.genre import Genre
from api.schemas.genres import GenreDetail, GenreDetailResponse, GenreNode, GenreTreeResponse
from api.services.cache import CacheService
from shared.constants import CACHE_TTL, ROOT_CATEGORIES

router = APIRouter(prefix="/api/v1/genres", tags=["genres"])


def _build_tree(genres: list[Genre], max_depth: int | None = None) -> list[dict]:
    """Build nested tree from flat genre list."""
    by_id = {g.id: g for g in genres}
    roots = []

    for g in genres:
        if max_depth is not None and g.depth > max_depth:
            continue
        node = {
            "id": g.id,
            "name": g.name,
            "depth": g.depth,
            "status": g.status,
            "genre_count": 0,
            "children": [],
        }
        by_id[g.id] = node  # type: ignore

    # Rebuild as dict nodes
    nodes = {}
    for g in genres:
        if max_depth is not None and g.depth > max_depth:
            continue
        nodes[g.id] = {
            "id": g.id,
            "name": g.name,
            "depth": g.depth,
            "status": g.status,
            "genre_count": 0,
            "children": [],
        }

    for g in genres:
        if max_depth is not None and g.depth > max_depth:
            continue
        if g.parent_id and g.parent_id in nodes:
            nodes[g.parent_id]["children"].append(nodes[g.id])
        elif g.parent_id is None or g.parent_id not in nodes:
            roots.append(nodes[g.id])

    # Count descendants
    def _count(node: dict) -> int:
        total = len(node["children"])
        for child in node["children"]:
            total += _count(child)
        node["genre_count"] = total
        return total

    for r in roots:
        _count(r)

    return roots


@router.get("", response_model=GenreTreeResponse)
async def get_genres(
    root: str | None = Query(None, description="Filter by root category"),
    depth: int | None = Query(None, description="Max depth to return"),
    status: str = Query("active", description="Genre status filter"),
    flat: bool = Query(False, description="Return flat list instead of tree"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_record),
    redis=Depends(get_redis),
):
    cache = CacheService(redis)
    cache_key = f"genres:{root}:{depth}:{status}:{flat}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    query = select(Genre)
    if root:
        query = query.where(Genre.root_category == root)
    if status != "all":
        query = query.where(Genre.status == status)

    result = await db.execute(query.order_by(Genre.id))
    genres = result.scalars().all()

    if flat:
        genre_list = [
            {"id": g.id, "name": g.name, "depth": g.depth, "status": g.status, "parent_id": g.parent_id}
            for g in genres
            if depth is None or g.depth <= depth
        ]
        response = {
            "data": {"genres": genre_list, "root_categories": ROOT_CATEGORIES, "total_genres": len(genre_list)},
            "meta": {"request_id": f"req_{uuid.uuid4().hex[:12]}", "timestamp": datetime.now(timezone.utc).isoformat()},
        }
    else:
        tree = _build_tree(list(genres), max_depth=depth)
        response = {
            "data": {"genres": tree, "root_categories": ROOT_CATEGORIES, "total_genres": len(genres)},
            "meta": {"request_id": f"req_{uuid.uuid4().hex[:12]}", "timestamp": datetime.now(timezone.utc).isoformat()},
        }

    await cache.set(cache_key, response, ttl=CACHE_TTL["genres"])
    return response


@router.get("/{genre_id}", response_model=GenreDetailResponse)
async def get_genre(
    genre_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_record),
    redis=Depends(get_redis),
):
    cache = CacheService(redis)
    cache_key = f"genre:{genre_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await db.execute(select(Genre).where(Genre.id == genre_id))
    genre = result.scalar_one_or_none()

    if genre is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": f"Genre '{genre_id}' not found", "details": {}}},
        )

    # Get children
    child_result = await db.execute(select(Genre).where(Genre.parent_id == genre_id))
    children = child_result.scalars().all()

    # Build adjacent genre details
    adjacent = []
    if genre.adjacent_genres:
        for adj_id in genre.adjacent_genres:
            adj_result = await db.execute(select(Genre).where(Genre.id == adj_id))
            adj = adj_result.scalar_one_or_none()
            if adj:
                relationship = "sibling" if adj.parent_id == genre.parent_id else "cross-branch"
                adjacent.append({"id": adj.id, "name": adj.name, "relationship": relationship, "affinity": 0.7})

    detail = GenreDetail(
        id=genre.id,
        name=genre.name,
        parent_id=genre.parent_id,
        root_category=genre.root_category,
        depth=genre.depth,
        status=genre.status,
        platform_mappings={
            "spotify": genre.spotify_genres or [],
            "apple_music": genre.apple_music_genres or [],
            "musicbrainz": genre.musicbrainz_tags or [],
            "chartmetric": genre.chartmetric_genres or [],
        },
        audio_profile=genre.audio_profile,
        adjacent_genres=adjacent,
        children=[{"id": c.id, "name": c.name, "status": c.status} for c in children],
        trending_stats={},
    )

    response = {
        "data": detail.model_dump(),
        "meta": {"request_id": f"req_{uuid.uuid4().hex[:12]}", "timestamp": datetime.now(timezone.utc).isoformat()},
    }
    await cache.set(cache_key, response, ttl=CACHE_TTL["genres"])
    return response
