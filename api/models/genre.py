from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

GENRE_STATUS = SAEnum("active", "deprecated", "proposed", name="genre_status", create_type=True)


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(200), ForeignKey("genres.id"))
    root_category: Mapped[str] = mapped_column(String(50), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spotify_genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    apple_music_genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    musicbrainz_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    chartmetric_genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    audio_profile: Mapped[dict | None] = mapped_column(JSON)
    adjacent_genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[str] = mapped_column(GENRE_STATUS, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    children = relationship("Genre", back_populates="parent", lazy="selectin")
    parent = relationship("Genre", back_populates="children", remote_side=[id], lazy="selectin")

    __table_args__ = (
        Index("idx_genre_parent", "parent_id"),
        Index("idx_genre_root", "root_category"),
    )
