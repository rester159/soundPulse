"""
Rights holder — canonical publisher / writer / composer entity (migration 036).

Polymorphic single-table design (kind ∈ {publisher, writer, composer}) — these
three rights-related parties share ~90% of their fields (IPI, PRO affiliation,
contact, tax info, split %), so one table + a `kind` discriminator beats three
near-duplicate tables.

CRUD lives in api/routers/admin_rights_holders.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class RightsHolder(Base):
    __tablename__ = "rights_holders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # publisher | writer | composer
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    stage_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipi_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    isni: Mapped[str | None] = mapped_column(Text, nullable=True)
    pro_affiliation: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher_company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_split_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
