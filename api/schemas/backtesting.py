"""Schemas for backtesting endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    months: int = Field(default=24, ge=1, le=60, description="Number of months to backtest")
    horizon: str = Field(default="7d", pattern="^(7d|14d|30d|90d)$")
    entity_type: str | None = Field(default=None, description="Filter by entity type (track/artist)")
    genre: str | None = Field(default=None, description="Filter by genre (e.g., 'electronic.house')")
    top_n: int = Field(default=50, ge=10, le=200, description="Top N chart threshold for breakout")


class BacktestTimelinePoint(BaseModel):
    evaluation_date: str
    mae: float | None
    rmse: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    sample_count: int
    positive_count: int
    predicted_avg: float | None
    actual_rate: float | None
    model_version: str | None


class BacktestRunSummary(BaseModel):
    run_id: str
    status: str
    created_at: str
    entity_type: str | None
    genre: str | None
    horizon: str
    period_count: int
    overall_mae: float | None


class BacktestGenreRow(BaseModel):
    genre: str
    mae: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    sample_count: int
