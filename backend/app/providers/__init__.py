"""Providers package"""
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
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
    CircuitBreakerOpenError,
    ProviderTimeoutError,
)
from app.providers.serpapi import SerpAPIAdapter
from app.providers.fallback_search import FallbackSearchAdapter
from app.providers.firecrawl import FirecrawlAdapter
from app.providers.llm import AnthropicLLMAdapter, GroqLLMAdapter, create_llm_adapter
from app.providers.embeddings import EmbeddingsAdapter
from app.providers.gateway import ProviderGateway, provider_gateway

__all__ = [
    "BaseSearchProvider",
    "BaseFetchProvider",
    "BaseEnrichProvider",
    "BaseLLMProvider",
    "BaseEmbeddingsProvider",
    "SearchResultItemDTO",
    "ScrapedDocumentDTO",
    "EnrichedCompanyDTO",
    "SearchBudget",
    "ProviderCallMetric",
    "ProviderError",
    "QuotaExhaustedError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "ProviderTimeoutError",
    "SerpAPIAdapter",
    "FallbackSearchAdapter",
    "FirecrawlAdapter",
    "ApifyAdapter",
    "AnthropicLLMAdapter",
    "GroqLLMAdapter",
    "create_llm_adapter",
    "EmbeddingsAdapter",
    "ProviderGateway",
    "provider_gateway",
]
