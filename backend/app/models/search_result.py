"""Search Result competitor item model definition"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Competitor Attributes
    competitor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    competitor_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="direct | indirect | leader"
    )
    match_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Score 0 - 100"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, comment="One-line explanation")
    source_url: Mapped[str] = mapped_column(Text, nullable=False, comment="Verified live URL")
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Ratings, reviews, signals, address, etc."
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    search = relationship("Search", back_populates="results")
    feedbacks = relationship("Feedback", back_populates="search_result", cascade="all, delete-orphan")
