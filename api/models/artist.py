import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    spotify_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    apple_music_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    tiktok_handle: Mapped[str | None] = mapped_column(String(200))
    chartmetric_id: Mapped[int | None] = mapped_column()
    musicbrainz_id: Mapped[str | None] = mapped_column(String(100))
    image_url: Mapped[str | None] = mapped_column(String(1000))
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    canonical: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tracks = relationship("Track", back_populates="artist", lazy="selectin")

    __table_args__ = (
        Index("idx_artist_name_trgm", name, postgresql_using="gist", postgresql_ops={"name": "gist_trgm_ops"}),
    )
