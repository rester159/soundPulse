"""
Genre structure — per-genre song-form skeleton injected into Suno prompts
(task #109, PRD §70, migration 033).

Stores a list of section descriptors keyed by primary_genre. Resolved at
song-generation time, formatted as a [Section: N bars{, instrumental}] tag
block, prepended to the generation_prompt so Suno produces output that
matches a known genre-specific structure.

Schema lives in alembic/versions/033_genre_structures.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class GenreStructure(Base):
    __tablename__ = "genre_structures"

    primary_genre: Mapped[str] = mapped_column(Text, primary_key=True)
    structure: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
