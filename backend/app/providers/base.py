"""Base Interfaces, Error Hierarchy, and Metrics for Data Providers"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class ProviderError(Exception):
    """Base exception for all external provider failures."""
    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class QuotaExhaustedError(ProviderError):
    """Raised when a provider's daily or monthly quota is depleted."""
    pass


class RateLimitError(ProviderError):
    """Raised when a provider rejects requests due to exceeding rate limits (HTTP 429)."""
    pass


class CircuitBreakerOpenError(ProviderError):
    """Raised when calls to a provider are temporarily suspended due to consecutive failures."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call times out."""
    pass


# ==============================================================================
# Data Transfer Objects
# ==============================================================================

@dataclass
class ProviderCallMetric:
    """Telemetry captured for every provider invocation."""
    provider: str
    call_type: str
    cost: float
    latency_ms: int
    status_code: int = 200
    cached: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SearchBudget:
    """Tracks and bounds spending per search job."""
    max_cost: float = 1.00
    current_cost: float = 0.00
    max_calls: int = 20
    calls_made: int = 0
    serpapi_max_calls: int = 10
    serpapi_calls_made: int = 0

    def can_spend(self, estimated_cost: float) -> bool:
        return (self.current_cost + estimated_cost <= self.max_cost) and (self.calls_made + 1 <= self.max_calls)

    def record_spend(self, cost: float) -> None:
        self.current_cost += cost
        self.calls_made += 1


@dataclass
class SearchResultItemDTO:
    """Standardized search hit returned by any search provider."""
    title: str
    url: str
    snippet: str
    domain: str
    position: int
    engine: str = "google"
    is_ad: bool = False
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class ScrapedDocumentDTO:
    """Standardized document payload returned by fetching/scraping providers."""
    url: str
    title: Optional[str] = None
    markdown: str = ""
    text: str = ""
    status_code: int = 200
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnrichedCompanyDTO:
    """Standardized enrichment data returned by Apify or maps providers."""
    domain: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    social_links: Dict[str, str] = field(default_factory=dict)
    raw_attributes: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# Abstract Provider Interfaces
# ==============================================================================

class BaseSearchProvider(ABC):
    """Abstract interface for discovery search providers (SerpAPI, Brave, Serper)."""
    @abstractmethod
    async def search(
        self,
        query: str,
        engine: str = "google",
        location: Optional[str] = None,
        country_code: Optional[str] = None,
        language: str = "en",
        num_results: int = 10,
    ) -> List[SearchResultItemDTO]:
        """Execute a web or maps search and return standardized candidate hits."""
        pass


class BaseFetchProvider(ABC):
    """Abstract interface for page scraping and extraction (Firecrawl, HTTP client)."""
    @abstractmethod
    async def fetch(self, url: str) -> ScrapedDocumentDTO:
        """Fetch and return markdown/text representation of a URL."""
        pass

    @abstractmethod
    async def extract(self, url: str, schema: Type[T]) -> T:
        """Extract structured data matching a Pydantic schema from a URL."""
        pass


class BaseEnrichProvider(ABC):
    """Abstract interface for company enrichment (Apify)."""
    @abstractmethod
    async def enrich(self, domain: str, name: Optional[str] = None) -> EnrichedCompanyDTO:
        """Fetch public profile signals, ratings, and reviews for a company."""
        pass


class BaseLLMProvider(ABC):
    """Abstract interface for LLM completions and structured outputs."""
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, float, int]:
        """Generate structured Pydantic object, returning (parsed_object, cost_usd, latency_ms)."""
        pass


class BaseEmbeddingsProvider(ABC):
    """Abstract interface for vector embeddings."""
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate vector embedding for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a batch of texts."""
        pass
