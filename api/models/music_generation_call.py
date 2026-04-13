import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class MusicGenerationCall(Base):
    """
    Append-only log of every music-gen provider call the system makes.

    Paired to the provider abstraction in api/services/music_providers/.
    Every /admin/music/generate submission writes a row here; every poll
    that sees a new state updates it. History drives the SongLab "recent
    generations" strip and is the raw material for future cost dashboards
    and generation-quality analytics.
    """
    __tablename__ = "music_generation_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    task_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    params_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_variant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds_requested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genre_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)

    breakout_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    song_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
