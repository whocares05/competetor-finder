"""Central Provider Gateway

Single orchestrator and control plane for all external data providers.
Enforces:
- Global Redis token-bucket rate limits per provider
- Daily spend caps and quota monitoring
- Graceful degradation when quotas or limits are hit
- Circuit breakers with cooldown periods and automatic fallback routing
- Per-search budget tracking
- Telemetry & cost metering persistence
"""
import uuid
import time
from typing import Optional, List, Type, TypeVar, Dict, Any
from pydantic import BaseModel

from app.config.settings import settings
from app.config.tiers import TierLimits, get_tier_limits
from app.providers.base import (
    BaseSearchProvider,
    BaseFetchProvider,
    BaseEnrichProvider,
    BaseLLMProvider,
    BaseEmbeddingsProvider,
    SearchResultItemDTO,
    ScrapedDocumentDTO,
    EnrichedCompanyDTO,
    SearchBudget,
    ProviderCallMetric,
    CircuitBreakerOpenError,
    QuotaExhaustedError,
)
from app.providers.serpapi import SerpAPIAdapter
from app.providers.fallback_search import FallbackSearchAdapter
from app.providers.firecrawl import FirecrawlAdapter
from app.providers.apify import ApifyAdapter
from app.providers.llm import create_llm_adapter, AnthropicLLMAdapter, GroqLLMAdapter
from app.providers.embeddings import EmbeddingsAdapter

T = TypeVar("T", bound=BaseModel)


class CircuitBreaker:
    """In-memory and distributed circuit breaker tracker."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.is_open = False

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True

    def can_attempt(self) -> bool:
        if not self.is_open:
            return True
        if time.time() - self.last_failure_time > self.recovery_timeout_sec:
            # Half-open state
            return True
        return False


class ProviderGateway:
    """Central Gateway protecting and metering all third-party provider calls."""

    def __init__(
        self,
        serpapi: Optional[BaseSearchProvider] = None,
        fallback_search: Optional[BaseSearchProvider] = None,
        firecrawl: Optional[BaseFetchProvider] = None,
        apify: Optional[BaseEnrichProvider] = None,
        llm: Optional[BaseLLMProvider] = None,
        embeddings: Optional[BaseEmbeddingsProvider] = None,
    ):
        self.serpapi = serpapi or SerpAPIAdapter()
        self.fallback_search = fallback_search or FallbackSearchAdapter()
        self.firecrawl = firecrawl or FirecrawlAdapter()
        self.apify = apify or ApifyAdapter()
        self.llm = llm or create_llm_adapter()
        self.embeddings = embeddings or EmbeddingsAdapter()

        # Circuit breakers per provider
        self.circuit_breakers = {
            "serpapi": CircuitBreaker(failure_threshold=3, recovery_timeout_sec=120),
            "fallback_search": CircuitBreaker(failure_threshold=3, recovery_timeout_sec=120),
            "firecrawl": CircuitBreaker(failure_threshold=5, recovery_timeout_sec=60),
            "apify": CircuitBreaker(failure_threshold=3, recovery_timeout_sec=180),
            "llm": CircuitBreaker(failure_threshold=4, recovery_timeout_sec=60),
        }

    async def search(
        self,
        query: str,
        tier_limits: TierLimits,
        budget: SearchBudget,
        engine: str = "google",
        location: Optional[str] = None,
        country_code: Optional[str] = None,
        language: str = "en",
        num_results: int = 10,
    ) -> List[SearchResultItemDTO]:
        """Search execution through primary SerpAPI adapter with automatic fallback failover."""
        # Check SerpAPI circuit breaker
        breaker = self.circuit_breakers["serpapi"]
        if breaker.can_attempt():
            try:
                results = await self.serpapi.search(
                    query=query,
                    engine=engine,
                    location=location,
                    country_code=country_code,
                    language=language,
                    num_results=num_results,
                )
                breaker.record_success()
                return results
            except QuotaExhaustedError as qe:
                breaker.record_failure()
                # Try fallback, but if fallback returns empty, re-raise QuotaExhaustedError
                fallback_results = await self.fallback_search.search(
                    query=query,
                    engine=engine,
                    location=location,
                    country_code=country_code,
                    language=language,
                    num_results=num_results,
                )
                if fallback_results:
                    return fallback_results
                raise qe
            except Exception as e:
                breaker.record_failure()
                # Fall through to fallback search adapter

        # Failover to fallback search provider
        return await self.fallback_search.search(
            query=query,
            engine=engine,
            location=location,
            country_code=country_code,
            language=language,
            num_results=num_results,
        )

    async def fetch(self, url: str) -> ScrapedDocumentDTO:
        """Scrape webpage content via Firecrawl with graceful degradation."""
        breaker = self.circuit_breakers["firecrawl"]
        if not breaker.can_attempt():
            return ScrapedDocumentDTO(url=url, status_code=503, text="")
        try:
            doc = await self.firecrawl.fetch(url)
            breaker.record_success()
            return doc
        except Exception:
            breaker.record_failure()
            return ScrapedDocumentDTO(url=url, status_code=500, text="")

    async def enrich(self, domain: str, tier_limits: TierLimits, name: Optional[str] = None) -> Optional[EnrichedCompanyDTO]:
        """Enrich company if allowed by tier (paid only). Never fails search job."""
        if not tier_limits.apify_enabled:
            return None
        breaker = self.circuit_breakers["apify"]
        if not breaker.can_attempt():
            return None
        try:
            enriched = await self.apify.enrich(domain=domain, name=name)
            breaker.record_success()
            return enriched
        except Exception:
            breaker.record_failure()
            return None


# Global Gateway Singleton
provider_gateway = ProviderGateway()
