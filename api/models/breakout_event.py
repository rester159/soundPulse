import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class BreakoutEvent(Base):
    __tablename__ = "breakout_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tracks.id"), nullable=False)
    genre_id: Mapped[str] = mapped_column(String(100), nullable=False)

    detection_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)

    peak_composite: Mapped[float] = mapped_column(Float, nullable=False)
    peak_velocity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_rank: Mapped[float | None] = mapped_column(Float, nullable=True)
    platform_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    genre_median_composite: Mapped[float] = mapped_column(Float, nullable=False)
    genre_median_velocity: Mapped[float] = mapped_column(Float, nullable=False)
    genre_track_count: Mapped[int] = mapped_column(Integer, nullable=False)

    composite_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    velocity_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    breakout_score: Mapped[float] = mapped_column(Float, nullable=False)

    audio_features: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_label: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
