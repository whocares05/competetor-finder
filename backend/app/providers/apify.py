"""Apify Enrichment Provider Adapter (Paid Tier Only)

Implements BaseEnrichProvider for deep review and rating enrichment on final candidate shortlists.
"""
from typing import Optional
from app.config.settings import settings
from app.providers.base import (
    BaseEnrichProvider,
    EnrichedCompanyDTO,
    ProviderError,
)


class ApifyAdapter(BaseEnrichProvider):
    """Adapter for Apify actor executions."""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or settings.APIFY_TOKEN
        self.google_maps_actor = settings.APIFY_GOOGLE_MAPS_ACTOR_ID
        self.company_info_actor = settings.APIFY_COMPANY_INFO_ACTOR_ID

    async def enrich(self, domain: str, name: Optional[str] = None) -> EnrichedCompanyDTO:
        """Stage 1 interface stub. Full implementation in Stage 7."""
        if not self.api_token:
            return EnrichedCompanyDTO(domain=domain)
        raise NotImplementedError("ApifyAdapter.enrich will be implemented in Stage 7")
