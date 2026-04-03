import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TrendingSnapshot(Base):
    __tablename__ = "trending_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'artist' or 'track'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    platform_rank: Mapped[int | None] = mapped_column(Integer)
    platform_score: Mapped[float | None] = mapped_column(Float)
    normalized_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    velocity: Mapped[float | None] = mapped_column(Float)
    signals_json: Mapped[dict] = mapped_column(JSON, default=dict)
    composite_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "snapshot_date", "platform", name="uq_snapshot"),
        Index("idx_trending_entity_date", "entity_id", snapshot_date.desc()),
        Index("idx_trending_platform_date", "platform", snapshot_date.desc()),
        Index(
            "idx_trending_composite",
            composite_score.desc(),
            postgresql_where=(composite_score.isnot(None)),
        ),
    )
