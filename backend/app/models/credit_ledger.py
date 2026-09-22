"""Credit Ledger model definition (Append-only)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class CreditLedger(Base):
    """Append-only credit transaction ledger.
    
    Tracks credit grants, reservations before search, final settlement,
    and refunds on shortfalls/cancellations.
    """
    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Positive for grants/refunds, negative for reservations/settlements"
    )
    entry_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="grant | reserve | settle | refund"
    )
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    search_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    # Relationships
    org = relationship("Org", back_populates="credit_entries")
