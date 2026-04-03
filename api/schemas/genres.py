from typing import Any

from pydantic import BaseModel


class GenreNode(BaseModel):
    id: str
    name: str
    depth: int
    status: str
    genre_count: int = 0
    children: list["GenreNode"] = []

    model_config = {"from_attributes": True}


class GenreDetail(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    root_category: str
    depth: int
    status: str
    platform_mappings: dict[str, list[str]] = {}
    audio_profile: dict[str, Any] | None = None
    adjacent_genres: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    trending_stats: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class GenreTreeResponse(BaseModel):
    data: dict[str, Any]
    meta: dict[str, Any] = {}


class GenreDetailResponse(BaseModel):
    data: GenreDetail
    meta: dict[str, Any] = {}
