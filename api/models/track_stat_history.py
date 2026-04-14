import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TrackStatHistory(Base):
    __tablename__ = "track_stat_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    chartmetric_track_id: Mapped[int | None] = mapped_column(Integer, index=True)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[int | None] = mapped_column(BigInteger)
    value_float: Mapped[float | None] = mapped_column(Float)
    pulled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "track_id", "platform", "metric", "snapshot_date",
            name="uq_track_stat_history_natural",
        ),
        Index(
            "idx_track_stat_history_lookup",
            "track_id", "platform", "snapshot_date",
        ),
        Index(
            "idx_track_stat_history_metric_date",
            "metric", "snapshot_date",
        ),
    )
