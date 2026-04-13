"""
Song stem pipeline — job queue + output artifacts.

See migration 024. Two tables:

  SongStemJob     — claim-driven work queue. One row per
                    (song_id, generation) that needs stem extraction.
                    Stem-extractor microservice polls via SELECT FOR
                    UPDATE SKIP LOCKED.

  SongStem        — one row per stem (suno_original / vocals_only /
                    final_mixed / drums / bass / other) per song.
                    Audio bytes stored inline BYTEA.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SongStemJob(Base):
    __tablename__ = "song_stem_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    song_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    music_generation_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    source_instrumental_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    source_audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    # 'full' (download→tempo-lock→Demucs→entry-lock→mix) or 'remix_only'
    # (reuse cached vocals_only, re-trim + re-mix only). See migration 025.
    job_type: Mapped[str] = mapped_column(Text, nullable=False, default="full")
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    params_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SongStem(Base):
    __tablename__ = "song_stems"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    song_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    stem_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="audio/mpeg"
    )
    audio_bytes: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    loudness_lufs: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
