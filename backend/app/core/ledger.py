"""Append-only Credit Ledger Service

Handles atomic reservation, settlement, refunds, and grants with complete auditability.
"""
import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.credit_ledger import CreditLedger


class CreditLedgerService:
    @staticmethod
    async def get_balance(db: AsyncSession, org_id: uuid.UUID) -> int:
        """Fetch the latest credit balance for an organization."""
        query = (
            select(CreditLedger.balance_after)
            .where(CreditLedger.org_id == org_id)
            .order_by(desc(CreditLedger.created_at))
            .limit(1)
        )
        result = await db.execute(query)
        balance = result.scalar_one_or_none()
        return balance if balance is not None else 0

    @classmethod
    async def reserve_credits(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        search_id: uuid.UUID,
        amount: int,
        idempotency_key: Optional[str] = None,
    ) -> CreditLedger:
        """Reserve credits before kicking off an asynchronous search job."""
        current_balance = await cls.get_balance(db, org_id)
        if current_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits. Required: {amount}, available: {current_balance}",
            )

        new_balance = current_balance - amount
        entry = CreditLedger(
            org_id=org_id,
            amount=-amount,
            entry_type="reserve",
            balance_after=new_balance,
            search_id=search_id,
            idempotency_key=idempotency_key,
            description=f"Pre-reservation for search {search_id}",
        )
        db.add(entry)
        await db.flush()
        return entry

    @classmethod
    async def settle_credits(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        search_id: uuid.UUID,
        actual_cost: int,
        reserved_cost: int,
    ) -> Optional[CreditLedger]:
        """Settle credits after search completion, refunding any unused reservation."""
        unused = reserved_cost - actual_cost
        if unused > 0:
            return await cls.refund_credits(
                db=db,
                org_id=org_id,
                search_id=search_id,
                amount=unused,
                reason=f"Partial refund for unused reserved credits (Reserved {reserved_cost}, Actual {actual_cost})",
            )
        return None

    @classmethod
    async def refund_credits(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        search_id: uuid.UUID,
        amount: int,
        reason: str = "Search failed or cancelled",
    ) -> CreditLedger:
        """Refund reserved credits to the organization ledger."""
        if amount <= 0:
            raise ValueError("Refund amount must be positive")

        current_balance = await cls.get_balance(db, org_id)
        new_balance = current_balance + amount

        entry = CreditLedger(
            org_id=org_id,
            amount=amount,
            entry_type="refund",
            balance_after=new_balance,
            search_id=search_id,
            description=reason,
        )
        db.add(entry)
        await db.flush()
        return entry

    @classmethod
    async def grant_credits(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        amount: int,
        description: str = "Manual or tier renewal grant",
    ) -> CreditLedger:
        """Deposit new credits into an organization ledger."""
        current_balance = await cls.get_balance(db, org_id)
        new_balance = current_balance + amount

        entry = CreditLedger(
            org_id=org_id,
            amount=amount,
            entry_type="grant",
            balance_after=new_balance,
            description=description,
        )
        db.add(entry)
        await db.flush()
        return entry
