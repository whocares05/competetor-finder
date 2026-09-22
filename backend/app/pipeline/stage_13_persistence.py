"""Pipeline Stage 13: Persistence (Upsert to Market Map, write results, and log telemetry)"""
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.search import Search
from app.models.search_result import SearchResult
from app.models.market_company import MarketCompany
from app.schemas.llm import JudgeCompetitorItem
from app.core.ledger import CreditLedgerService

logger = logging.getLogger("pipeline.stage_13")


async def run_stage_13_persistence(
    db: AsyncSession,
    search: Search,
    competitors: List[JudgeCompetitorItem],
    providers_used: List[str],
    actual_cost: float,
    category: Optional[str] = None,
    region: Optional[str] = None,
) -> None:
    """Save finalized competitors, update search job state, and cache to market map."""
    now = datetime.now(timezone.utc)
    
    # 1. Save Search Results
    for comp in competitors:
        result_item = SearchResult(
            search_id=search.id,
            org_id=search.org_id,
            competitor_name=comp.name,
            domain=comp.domain,
            competitor_type=comp.type,
            match_score=comp.match_score,
            reason=comp.reason,
            source_url=comp.source_url,
            verified_at=now,
        )
        db.add(result_item)

        # 2. Upsert into MarketCompany cache
        try:
            query = select(MarketCompany).where(MarketCompany.domain == comp.domain).limit(1)
            res = await db.execute(query)
            existing = res.scalar_one_or_none()
            if existing:
                existing.last_verified = {"verified_at": now.isoformat(), "source": "serpapi"}
                existing.updated_at = now
            else:
                new_mc = MarketCompany(
                    org_id=None,  # Shared across ecosystem
                    name=comp.name,
                    domain=comp.domain,
                    category=category or "Business Services",
                    region=region or "global",
                    description=comp.reason,
                    source="serpapi",
                    source_url=comp.source_url,
                    last_verified={"verified_at": now.isoformat()},
                )
                db.add(new_mc)
        except Exception as e:
            logger.debug(f"Market map upsert notice for {comp.domain}: {e}")

    # 3. Update Search Record
    search.status = "completed"
    search.actual_cost = actual_cost
    search.providers_used = providers_used
    search.completed_at = now

    # 4. Settle reserved credits
    try:
        reserved_cost = int(search.estimated_cost or 1)
        actual_int_cost = int(actual_cost) if actual_cost > 0 else 1
        await CreditLedgerService.settle_credits(
            db=db,
            org_id=search.org_id,
            search_id=search.id,
            actual_cost=actual_int_cost,
            reserved_cost=reserved_cost,
        )
    except Exception as e:
        logger.warning(f"Credit settlement warning: {e}")

    await db.commit()
    logger.info(f"Persistence complete: {len(competitors)} results saved for search {search.id}.")
