"""Tier Limits and Configuration Unit Tests"""
from app.config.tiers import PlanTier, get_tier_limits, TIER_CONFIGS


def test_free_tier_limits():
    """Verify free tier config meets requirements."""
    free_limits = get_tier_limits(PlanTier.FREE)
    assert free_limits.max_competitors == 10
    assert free_limits.serpapi_max_calls == 3
    assert free_limits.firecrawl_candidate_multiplier == 2
    assert free_limits.firecrawl_use_extract is False
    assert free_limits.apify_enabled is False
    assert free_limits.embedding_provider_mode == "local"
    assert free_limits.llm_allow_escalation is False


def test_paid_tier_limits():
    """Verify paid tier config meets requirements."""
    paid_limits = get_tier_limits(PlanTier.PAID)
    assert paid_limits.max_competitors == 50
    assert paid_limits.serpapi_max_calls == 6
    assert paid_limits.firecrawl_candidate_multiplier == 4
    assert paid_limits.firecrawl_use_extract is True
    assert paid_limits.apify_enabled is True
    assert paid_limits.embedding_provider_mode == "dynamic"
    assert paid_limits.llm_allow_escalation is True
