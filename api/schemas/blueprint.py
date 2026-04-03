"""Schemas for blueprint generation endpoints."""

from __future__ import annotations
from pydantic import BaseModel, Field


class BlueprintRequest(BaseModel):
    genre: str = Field(description="Genre ID (e.g., 'electronic.house')")
    model: str = Field(default="suno", pattern="^(suno|udio|soundraw|musicgen)$")


class GenreOpportunity(BaseModel):
    genre: str
    genre_name: str
    opportunity_score: float
    confidence: float
    track_count: int
    avg_composite: float
    avg_velocity: float
    momentum: str
