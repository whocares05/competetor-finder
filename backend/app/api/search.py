"""Search API Endpoints"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import asyncio
from app.db.session import get_db
from app.models.user import User
from app.models.org import Org
from app.models.search import Search
from app.schemas.search import SearchCreate, SearchRead
from app.config.tiers import get_tier_limits, PlanTier
from app.core.auth import get_current_user, get_current_org
from app.core.ledger import CreditLedgerService
from app.pipeline.stage_12_stream import sse_event_generator
from app.pipeline.runner import run_search_pipeline

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.post("", response_model=SearchRead, status_code=status.HTTP_202_ACCEPTED)
async def create_search(
    payload: SearchCreate,
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Initiate an asynchronous competitor search job."""
    # 1. Tier & input validation
    try:
        tier_enum = PlanTier(current_org.plan_tier)
    except ValueError:
        tier_enum = PlanTier.FREE

    limits = get_tier_limits(tier_enum)
    if payload.num_competitors > limits.max_competitors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested {payload.num_competitors} competitors exceeds {limits.tier.value} tier limit ({limits.max_competitors})",
        )

    # 2. Search record creation
    search = Search(
        org_id=current_org.id,
        user_id=current_user.id,
        query=payload.query.strip(),
        location=payload.location.strip() if payload.location else None,
        num_competitors=payload.num_competitors,
        scope_override=payload.scope_override,
        competitor_types=payload.competitor_types,
        status="queued",
        tier=limits.tier.value,
        idempotency_key=payload.idempotency_key,
        estimated_cost=float(limits.credit_cost_per_search),
    )
    db.add(search)
    await db.flush()

    # 3. Reserve credits in append-only ledger
    await CreditLedgerService.reserve_credits(
        db=db,
        org_id=current_org.id,
        search_id=search.id,
        amount=limits.credit_cost_per_search,
        idempotency_key=payload.idempotency_key,
    )

    await db.commit()
    await db.refresh(search)
    search.results = []

    # 4. Trigger asynchronous pipeline execution across all stages
    asyncio.create_task(run_search_pipeline(search.id))

    return SearchRead.model_validate(search)


@router.get("/{search_id}", response_model=SearchRead)
async def get_search(
    search_id: uuid.UUID,
    current_org: Org = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve search status and verified competitor results."""
    query = (
        select(Search)
        .where(Search.id == search_id, Search.org_id == current_org.id)
        .options(selectinload(Search.results))
    )
    result = await db.execute(query)
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return SearchRead.model_validate(search)


@router.get("/{search_id}/events")
async def stream_search_events(
    search_id: uuid.UUID,
    current_org: Org = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events (SSE) stream for real-time progress and verified results."""
    query = select(Search).where(Search.id == search_id, Search.org_id == current_org.id)
    result = await db.execute(query)
    search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")

    return StreamingResponse(
        sse_event_generator(str(search_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
