import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AIArtist(Base):
    """
    An AI artist owned by SoundPulse. Not to be confused with the existing
    `artists` table which stores real-world artists scraped from Chartmetric.
    Per PRD §17 schema.
    """
    __tablename__ = "ai_artists"

    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stage_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender_presentation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ethnicity_heritage: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    early_life_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    sexual_orientation: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    primary_genre: Mapped[str] = mapped_column(Text, nullable=False)
    adjacent_genres: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    influences: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    anti_influences: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    voice_dna: Mapped[dict] = mapped_column(JSONB, nullable=False)
    visual_dna: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fashion_dna: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    lyrical_dna: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    persona_dna: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    social_dna: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    audience_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    content_rating: Mapped[str] = mapped_column(Text, default="mild")
    edge_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    roster_status: Mapped[str] = mapped_column(Text, default="active")
    song_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creation_trigger_blueprint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    ceo_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    ceo_approval_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ceo_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
