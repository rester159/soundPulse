"""
Chartmetric global token bucket — single-row table coordinating dispatch
rate across all Railway replicas (task #8, migration 035).

The acquire flow lives in chartmetric_ingest/global_bucket.py; this is
just the SQLAlchemy mapping.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ChartmetricGlobalBucket(Base):
    __tablename__ = "chartmetric_global_bucket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tokens: Mapped[float] = mapped_column(Float, nullable=False)
    last_refill_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    rate_per_sec: Mapped[float] = mapped_column(Float, nullable=False)
    burst: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
