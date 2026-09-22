"""Provider Gateway and Exception Hierarchy Tests"""
import pytest
from app.config.tiers import PlanTier, get_tier_limits
from app.providers.base import (
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
    CircuitBreakerOpenError,
    SearchBudget,
    SearchResultItemDTO,
    BaseSearchProvider,
)
from app.providers.gateway import ProviderGateway, CircuitBreaker


class MockFailingSearchProvider(BaseSearchProvider):
    async def search(self, *args, **kwargs):
        raise RateLimitError("Rate limit exceeded", provider="mock", status_code=429)


class MockHealthySearchProvider(BaseSearchProvider):
    async def search(self, *args, **kwargs):
        return [
            SearchResultItemDTO(
                title="Rival Co",
                url="https://rival.com",
                snippet="Competitor product",
                domain="rival.com",
                position=1,
            )
        ]


def test_exception_hierarchy():
    """Verify provider error inheritance."""
    quota_err = QuotaExhaustedError("Quota reached", provider="serpapi")
    assert isinstance(quota_err, ProviderError)
    assert quota_err.provider == "serpapi"


def test_search_budget():
    """Verify search budget spend tracking."""
    budget = SearchBudget(max_cost=0.50, max_calls=3)
    assert budget.can_spend(0.10) is True
    budget.record_spend(0.40)
    assert budget.current_cost == 0.40
    assert budget.calls_made == 1
    assert budget.can_spend(0.20) is False  # Would exceed 0.50


@pytest.mark.asyncio
async def test_gateway_circuit_breaker_and_fallback():
    """Verify gateway fails over to fallback provider when primary fails."""
    primary_mock = MockFailingSearchProvider()
    fallback_mock = MockHealthySearchProvider()

    gateway = ProviderGateway(
        serpapi=primary_mock,
        fallback_search=fallback_mock,
    )
    tier_limits = get_tier_limits(PlanTier.FREE)
    budget = SearchBudget()

    # Primary will fail and circuit breaker records failure, fallback will answer
    results = await gateway.search(query="alternatives to test", tier_limits=tier_limits, budget=budget)
    assert len(results) == 1
    assert results[0].domain == "rival.com"
