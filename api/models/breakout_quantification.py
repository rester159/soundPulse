import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class BreakoutQuantification(Base):
    """
    Cached per-genre per-window quantification of expected streams +
    $ revenue + confidence for the breakout opportunity in that genre.

    See planning/PRD/opportunity_quantification_spec.md for the model.
    """
    __tablename__ = "breakout_quantifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    genre_id: Mapped[str] = mapped_column(String(100), nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    quantification: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    total_revenue_median_usd: Mapped[float] = mapped_column(Float, nullable=False)
    n_breakouts_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
