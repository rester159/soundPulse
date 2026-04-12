import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class AgentRegistry(Base):
    """
    Catalog of all agents in the SoundPulse virtual label. 14 entries
    seeded from marketing spec §12 + the new Submissions Agent.
    """
    __tablename__ = "agent_registry"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code_letter: Mapped[str | None] = mapped_column(String(2), nullable=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    actions: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    interdependencies: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )


class ToolsRegistry(Base):
    """
    Catalog of all external tools/APIs the system uses, with credential
    env-var names. Source-of-truth for the Settings → Tools view.
    """
    __tablename__ = "tools_registry"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    auth_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    credential_env_vars: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    documentation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cost_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    automation_class: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    capabilities: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )


class AgentToolGrant(Base):
    """
    Many-to-many: which agent has access to which tool.
    """
    __tablename__ = "agent_tool_grants"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="agent_tool_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False,
    )
    tool_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("tools_registry.id", ondelete="CASCADE"), nullable=False,
    )
    scope: Mapped[str | None] = mapped_column(String(200), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    granted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
