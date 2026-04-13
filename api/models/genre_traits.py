"""
Genre traits — multi-dimensional per-genre profile (migration 020).

Read by smart_prompt.py to scale edge rules / earworm demand / meme
density / pop-culture source filtering per genre, so K-pop gets the
full meme treatment while bluegrass gets zero and outlaw country gets
named-target savagery via storytelling.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class GenreTraits(Base):
    __tablename__ = "genre_traits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    genre_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Numeric dimensions 0-100
    edginess: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    meme_density: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    earworm_demand: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    sonic_experimentation: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    lyrical_complexity: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    vocal_processing: Mapped[int] = mapped_column(Integer, nullable=False, default=40)

    # Discrete fields
    tempo_range_bpm: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    key_mood: Mapped[str] = mapped_column(Text, nullable=False, default="mixed")
    default_edge_profile: Mapped[str] = mapped_column(Text, nullable=False, default="flirty_edge")
    vocabulary_era: Mapped[str] = mapped_column(Text, nullable=False, default="timeless")
    pop_culture_sources: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    instrumentation_palette: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    structural_conventions: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
