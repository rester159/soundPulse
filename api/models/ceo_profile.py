from datetime import datetime, time

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class CeoProfile(Base):
    """
    Single-row CEO contact + escalation preferences. Used by the
    CEO Action Agent (marketing spec §12.M) to reach the CEO when
    a critical decision needs approval (artist creation, paid spend,
    brand pivots, etc.). The CHECK (id = 1) constraint enforces
    that there is exactly one CEO.
    """
    __tablename__ = "ceo_profile"
    __table_args__ = (
        CheckConstraint("id = 1", name="ceo_profile_singleton"),
        CheckConstraint(
            "preferred_channel IN ('email','phone','telegram','slack')",
            name="ceo_profile_channel_valid",
        ),
        CheckConstraint(
            "escalation_severity_threshold IN ('low','medium','high','critical')",
            name="ceo_profile_severity_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telegram_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slack_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_channel: Mapped[str | None] = mapped_column(String(20), default="email")
    escalation_severity_threshold: Mapped[str | None] = mapped_column(String(20), default="medium")
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), default="UTC")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
