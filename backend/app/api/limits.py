"""Limits and Quotas API Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.org import Org
from app.config.tiers import get_tier_limits, PlanTier
from app.schemas.limits import LimitsResponse
from app.core.auth import get_current_org
from app.core.ledger import CreditLedgerService

router = APIRouter(prefix="/api/limits", tags=["Limits"])


@router.get("", response_model=LimitsResponse)
async def get_limits(
    current_org: Org = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve runtime tier limits, quotas, and available credit balance."""
    try:
        tier_enum = PlanTier(current_org.plan_tier)
    except ValueError:
        tier_enum = PlanTier.FREE

    limits = get_tier_limits(tier_enum)
    balance = await CreditLedgerService.get_balance(db, current_org.id)

    return LimitsResponse(
        tier=limits.tier,
        max_competitors=limits.max_competitors,
        default_competitors=limits.default_competitors,
        serpapi_max_calls=limits.serpapi_max_calls,
        firecrawl_candidate_multiplier=limits.firecrawl_candidate_multiplier,
        firecrawl_use_extract=limits.firecrawl_use_extract,
        apify_enabled=limits.apify_enabled,
        embedding_provider=limits.embedding_provider_mode,
        llm_default_model=limits.llm_default_model,
        llm_allow_escalation=limits.llm_allow_escalation,
        credits_balance=balance,
        daily_quota_remaining={
            "serpapi_calls_remaining": 100,
            "firecrawl_scrapes_remaining": 500,
            "apify_runs_remaining": 50 if limits.apify_enabled else 0,
        },
    )
