from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PredictionSignal(BaseModel):
    feature: str
    value: float
    impact: str
    description: str = ""


class PredictionEntity(BaseModel):
    id: str
    type: str
    name: str
    genres: list[str] = []
    image_url: str | None = None


class PredictionItem(BaseModel):
    prediction_id: str
    entity: PredictionEntity
    horizon: str
    current_score: float | None = None
    predicted_score: float
    predicted_change_pct: float | None = None
    predicted_change_abs: float | None = None
    confidence: float
    confidence_interval: dict[str, float] = {}
    top_signals: list[PredictionSignal] = []
    model_version: str
    predicted_at: datetime
    horizon_ends_at: datetime | None = None


class PredictionResponse(BaseModel):
    data: list[PredictionItem]
    meta: dict[str, Any] = {}


class FeedbackRequest(BaseModel):
    prediction_id: str
    actual_score: float = Field(ge=0, le=100)
    notes: str = ""


class FeedbackResponse(BaseModel):
    data: dict[str, Any]
