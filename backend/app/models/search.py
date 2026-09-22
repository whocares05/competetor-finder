"""Search Job and History model definition"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Inputs
    query: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    num_competitors: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    scope_override: Mapped[str | None] = mapped_column(
        String(50), default="auto", nullable=True, comment="auto | local | national | global"
    )
    competitor_types: Mapped[dict | list | None] = mapped_column(
        JSON, default=list, nullable=True, comment="['direct', 'indirect', 'leader']"
    )

    # Execution State
    status: Mapped[str] = mapped_column(
        String(50), default="queued", nullable=False, index=True,
        comment="queued | running | completed | failed | clarification_needed"
    )
    tier: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    
    # Economics & Telemetry
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    shortfall: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shortfall_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarifying_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Output metadata
    providers_used: Mapped[dict | list | None] = mapped_column(JSON, default=list, nullable=True)
    profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    org = relationship("Org", back_populates="searches", lazy="selectin")
    results = relationship("SearchResult", back_populates="search", cascade="all, delete-orphan", lazy="selectin")
    feedbacks = relationship("Feedback", back_populates="search", cascade="all, delete-orphan", lazy="selectin")
    provider_usages = relationship("ProviderUsage", back_populates="search", cascade="all, delete-orphan", lazy="selectin")
