"""Pipeline Stage 04: Market Map Lookup (Cache / Pre-verified company check)"""
import logging
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.market_company import MarketCompany
from app.schemas.llm import CompactCandidateCard

logger = logging.getLogger("pipeline.stage_04")


async def run_stage_04_market_map_lookup(
    db: AsyncSession,
    category: str,
    region: str,
    required_count: int,
    excluded_domain: Optional[str] = None,
) -> List[CompactCandidateCard]:
    """Look up recently verified competitors from market map cache."""
    try:
        freshness_cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        query = (
            select(MarketCompany)
            .where(
                MarketCompany.category.ilike(f"%{category[:20]}%"),
                MarketCompany.updated_at >= freshness_cutoff,
            )
            .limit(required_count)
        )
        result = await db.execute(query)
        cached_items = result.scalars().all()
        
        candidates = []
        for item in cached_items:
            if excluded_domain and (item.domain == excluded_domain or excluded_domain in item.domain):
                continue
            candidates.append(
                CompactCandidateCard(
                    name=item.name,
                    domain=item.domain,
                    description=item.description,
                    source_url=item.source_url,
                )
            )
        return candidates
    except Exception as e:
        logger.warning(f"Market map cache lookup skipped: {e}")
        return []
