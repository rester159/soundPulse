import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'artist', 'track', 'genre'
    entity_id: Mapped[str] = mapped_column(String(200), nullable=False)  # UUID string or genre dot-notation
    horizon: Mapped[str] = mapped_column(String(5), nullable=False)  # '7d', '30d', '90d'
    predicted_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    features_json: Mapped[dict] = mapped_column(JSON, default=dict)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_score: Mapped[float | None] = mapped_column(Float)
    error: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_prediction_horizon", "horizon", predicted_at.desc()),
        Index("idx_prediction_entity", "entity_id", "horizon"),
    )
