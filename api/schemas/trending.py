from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class EntityIdentifier(BaseModel):
    spotify_id: str | None = None
    apple_music_id: str | None = None
    tiktok_sound_id: str | None = None
    shazam_id: str | None = None
    billboard_id: str | None = None
    chartmetric_id: int | None = None
    isrc: str | None = None
    title: str | None = None
    artist_name: str | None = None
    artist_spotify_id: str | None = None


class TrendingIngest(BaseModel):
    platform: str
    entity_type: str
    entity_identifier: EntityIdentifier
    raw_score: float | None = None
    rank: int | None = None
    signals: dict[str, Any] = {}
    snapshot_date: date


class TrendingIngestResponse(BaseModel):
    data: dict[str, Any]


class EntityInfo(BaseModel):
    id: str
    type: str
    name: str
    artist: dict[str, str] | None = None
    image_url: str | None = None
    genres: list[str] = []
    isrc: str | None = None
    platform_ids: dict[str, str] = {}


class PlatformScore(BaseModel):
    normalized_score: float
    raw_score: float | None = None
    rank: int | None = None
    signals: dict[str, Any] = {}
    last_updated: datetime | None = None


class TrendingScores(BaseModel):
    composite_score: float = 0.0
    composite_score_previous: float | None = None
    position_change: int | None = None
    velocity: float | None = None
    acceleration: float | None = None
    platforms: dict[str, PlatformScore] = {}
    platform_count: int = 0


class TrendingItem(BaseModel):
    entity: EntityInfo
    scores: TrendingScores
    sparkline_7d: list[float | None] = []


class TrendingResponse(BaseModel):
    data: list[TrendingItem]
    meta: dict[str, Any] = {}
