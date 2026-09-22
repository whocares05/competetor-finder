"""Pipeline Stage 10: Enrich (Scrape landing page text for thin candidate snippets)"""
import asyncio
import logging
from typing import List
from app.config.tiers import TierLimits
from app.providers.gateway import ProviderGateway
from app.schemas.llm import CompactCandidateCard

logger = logging.getLogger("pipeline.stage_10")


async def enrich_single_candidate(cand: CompactCandidateCard, gateway: ProviderGateway) -> None:
    """Fetch website landing page text if description is too brief."""
    if len(cand.description) > 150:
        return
    try:
        doc = await gateway.fetch(f"https://{cand.domain}")
        if doc.status_code == 200 and doc.text:
            # Take clean summary text from scraped page
            clean_text = " ".join(doc.text.split())[:300]
            if len(clean_text) > len(cand.description):
                cand.description = clean_text
    except Exception as e:
        logger.debug(f"Enrichment fetch failed for {cand.domain}: {e}")


async def run_stage_10_enrich(
    candidates: List[CompactCandidateCard],
    gateway: ProviderGateway,
    tier_limits: TierLimits,
    max_to_enrich: int = 5,
) -> List[CompactCandidateCard]:
    """Enrich finalists with deeper landing page content via Firecrawl or web scraping."""
    # Only enrich top candidates with brief descriptions
    needs_enrichment = [c for c in candidates if len(c.description) < 120][:max_to_enrich]
    if not needs_enrichment:
        return candidates

    tasks = [enrich_single_candidate(c, gateway) for c in needs_enrichment]
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=8.0)
    except asyncio.TimeoutError:
        logger.info("Stage 10 enrichment timed out gracefully, proceeding with existing snippets.")
    except Exception as e:
        logger.warning(f"Stage 10 enrichment exception: {e}")

    return candidates
