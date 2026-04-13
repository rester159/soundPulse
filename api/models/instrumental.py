"""
Instrumentals — uploaded beats/tracks that Suno 'add-vocals' generates over.

An instrumental is an audio file (MP3/WAV/FLAC) uploaded by the CEO or an
agent that becomes the backing track for a vocal generation. The bytes
live in the instrumental_blobs sidecar table (mirrors the pattern used by
music_generation_audio + visual_asset_blobs).

Kie.ai's /api/v1/generate/add-vocals endpoint takes a public uploadUrl
rather than multipart bytes — so we serve the instrumental at an open
streaming path keyed by the UUID, and pass that URL as the uploadUrl
field in the add-vocals call.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Instrumental(Base):
    __tablename__ = "instrumentals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    tempo_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="audio/mpeg"
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Entry-point alignment (migration 025). See PRD §25.5.
    vocal_entry_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    vocal_entry_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InstrumentalBlob(Base):
    __tablename__ = "instrumental_blobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrumental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    audio_bytes: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
