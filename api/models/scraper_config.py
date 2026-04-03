from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ScraperConfig(Base):
    __tablename__ = "scraper_configs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g. "spotify"
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_hours: Mapped[float] = mapped_column(Float, default=6.0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(50))  # "success", "error", "running"
    last_error: Mapped[str | None] = mapped_column(String(2000))
    last_record_count: Mapped[int | None] = mapped_column(Integer, default=None)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
