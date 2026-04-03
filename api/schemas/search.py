from typing import Any

from pydantic import BaseModel


class SearchEntityInfo(BaseModel):
    id: str
    type: str
    name: str
    artist: dict[str, str] | None = None
    genres: list[str] = []
    image_url: str | None = None


class LatestScores(BaseModel):
    composite_score: float | None = None
    velocity: float | None = None
    platform_count: int = 0
    last_updated: str | None = None


class SearchResult(BaseModel):
    entity: SearchEntityInfo
    latest_scores: LatestScores
    relevance_score: float = 0.0


class SearchResponse(BaseModel):
    data: list[SearchResult]
    meta: dict[str, Any] = {}
