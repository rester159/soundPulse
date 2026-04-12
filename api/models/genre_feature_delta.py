import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text

from api.database import Base


class GenreFeatureDelta(Base):
    """
    Per-genre cached comparison of breakout tracks vs baseline tracks.
    For each audio feature, stores the mean delta and statistical
    significance (p-value from Welch's t-test).
    """
    __tablename__ = "genre_feature_deltas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    genre_id: Mapped[str] = mapped_column(String(100), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    breakout_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_count: Mapped[int] = mapped_column(Integer, nullable=False)
    deltas_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    significance_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    top_differentiators: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
