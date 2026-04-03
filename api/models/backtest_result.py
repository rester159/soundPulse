"""Database model for storing backtesting results."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    evaluation_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    genre_filter: Mapped[str | None] = mapped_column(String(200), nullable=True)
    horizon: Mapped[str] = mapped_column(String(5), nullable=False, default="7d")

    # Aggregate metrics for this evaluation period
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    auc_roc: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Counts
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_count: Mapped[int] = mapped_column(Integer, default=0)

    # Average predicted probability and actual breakout rate for charting
    predicted_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    model_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")

    # Per-entity details: [{entity_id, predicted_prob, actual_outcome, error}]
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_backtest_run_date", "run_id", "evaluation_date"),
        Index("idx_backtest_genre_date", "genre_filter", "evaluation_date"),
    )
