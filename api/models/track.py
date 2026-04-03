import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    artist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artists.id"), nullable=False)
    isrc: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    spotify_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    apple_music_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    shazam_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    tiktok_sound_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    billboard_id: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    chartmetric_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    release_date: Mapped[date | None] = mapped_column(Date)
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    audio_features: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    artist = relationship("Artist", back_populates="tracks", lazy="selectin")

    __table_args__ = (
        Index("idx_track_title_trgm", title, postgresql_using="gist", postgresql_ops={"title": "gist_trgm_ops"}),
    )
