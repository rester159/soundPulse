import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TrackLyrics(Base):
    """Lyrics + extracted features for a single track."""
    __tablename__ = "track_lyrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id"), nullable=False, unique=True,
    )
    lyrics_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_richness: Mapped[float | None] = mapped_column(Float, nullable=True)
    section_structure: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    themes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    primary_theme: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    genius_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    genius_song_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    features_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
