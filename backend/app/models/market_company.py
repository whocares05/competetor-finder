"""Market Company model definition with pgvector embeddings and HNSW indexing"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, JSON, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.db.base import Base

# Embedding dimensionality: 384 for multilingual sentence-transformers
EMBEDDING_DIM = 384


class MarketCompany(Base):
    """Global and tenant-scoped verified company market map."""
    __tablename__ = "market_companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Optional org_id: null indicates globally verified company shared across users
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Vector embedding for cosine similarity matching
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    source: Mapped[str] = mapped_column(String(100), default="serpapi")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Granular freshness per field: {"profile": "2026-09-22T...", "maps": "..."}
    last_verified: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_market_companies_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_market_companies_category_region", "category", "region"),
    )
