import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class GenreLyricalAnalysis(Base):
    """
    LLM-powered lyrical theme analysis per genre. Stores the JSON
    output of comparing breakout-track lyrics vs baseline lyrics.
    Created weekly by the breakout engine.
    """
    __tablename__ = "genre_lyrical_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    genre_id: Mapped[str] = mapped_column(String(100), nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    breakout_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_count: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
