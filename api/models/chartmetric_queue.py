import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, Index, PrimaryKeyConstraint, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ChartmetricRequestQueue(Base):
    __tablename__ = "chartmetric_request_queue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    producer: Mapped[str] = mapped_column(Text, nullable=False)
    handler: Mapped[str] = mapped_column(Text, nullable=False)
    handler_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    response_status: Mapped[int | None] = mapped_column(SmallInteger)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_cmq_completed_at", "completed_at"),
    )


class ChartmetricQuotaState(Base):
    __tablename__ = "chartmetric_quota_state"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    adaptive_multiplier: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    last_429_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_cm_quota_singleton"),
    )


class ChartmetricEntityFetchLog(Base):
    __tablename__ = "chartmetric_entity_fetch_log"

    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    endpoint_key: Mapped[str] = mapped_column(Text, nullable=False)
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_status: Mapped[int | None] = mapped_column(SmallInteger)

    __table_args__ = (
        PrimaryKeyConstraint(
            "entity_type", "entity_id", "endpoint_key",
            name="pk_cm_entity_fetch_log",
        ),
        Index(
            "idx_cm_fetch_log_stale",
            "entity_type", "endpoint_key", "last_fetched_at",
        ),
    )


class ChartmetricEndpointConfig(Base):
    __tablename__ = "chartmetric_endpoint_config"

    endpoint_key: Mapped[str] = mapped_column(Text, primary_key=True)
    target_interval_hours: Mapped[float] = mapped_column(Float, nullable=False)
    priority_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
