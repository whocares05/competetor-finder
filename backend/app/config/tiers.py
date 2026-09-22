"""Central Tier Configuration and Feature Flag Limits

This module defines all capabilities, quotas, and behavioral switches for the
FREE and PAID plan tiers. No pipeline stage or provider adapter may hardcode
tier limits; all limits must be queried dynamically through this interface.
"""
from enum import Enum
from typing import Dict
from pydantic import BaseModel, Field
from app.config.settings import settings


class PlanTier(str, Enum):
    FREE = "free"
    PAID = "paid"


class TierLimits(BaseModel):
    """Encapsulates runtime boundaries and capabilities for a specific plan tier."""
    tier: PlanTier
    max_competitors: int = Field(..., description="Maximum allowed competitor count in search query")
    default_competitors: int = Field(default=10, description="Default competitor count")
    
    # SerpAPI Provider Limits
    serpapi_max_calls: int = Field(..., description="Hard budget of SerpAPI calls per search")
    
    # Firecrawl Provider Limits
    firecrawl_candidate_multiplier: int = Field(..., description="Verification candidate limit multiplier (e.g. N * 2)")
    firecrawl_use_extract: bool = Field(..., description="Whether to use structured extract endpoint vs scrape only")
    
    # Apify Provider Limits
    apify_enabled: bool = Field(..., description="Whether Apify enrichment is enabled for final shortlist")
    
    # Embeddings
    embedding_provider_mode: str = Field(..., description="'local' or 'dynamic' (configured via EMBEDDING_PROVIDER)")
    
    # LLM Settings
    llm_default_model: str = Field(..., description="Model ID for standard tasks (parsing, extraction, judging)")
    llm_escalation_model: str = Field(..., description="Model ID for escalation when judge confidence is low")
    llm_allow_escalation: bool = Field(..., description="Whether model escalation on low confidence is allowed")
    
    # Cost & Credits
    credit_cost_per_search: int = Field(..., description="Base credits reserved per search")


TIER_CONFIGS: Dict[PlanTier, TierLimits] = {
    PlanTier.FREE: TierLimits(
        tier=PlanTier.FREE,
        max_competitors=10,
        default_competitors=10,
        serpapi_max_calls=3,
        firecrawl_candidate_multiplier=2,
        firecrawl_use_extract=False,  # scrape only
        apify_enabled=False,           # Apify disabled in free tier
        embedding_provider_mode="local",
        llm_default_model="claude-3-5-haiku-latest",
        llm_escalation_model="claude-3-5-haiku-latest",  # No escalation to expensive model
        llm_allow_escalation=False,
        credit_cost_per_search=1,
    ),
    PlanTier.PAID: TierLimits(
        tier=PlanTier.PAID,
        max_competitors=50,
        default_competitors=20,
        serpapi_max_calls=6,
        firecrawl_candidate_multiplier=4,
        firecrawl_use_extract=True,   # Structured extract endpoint enabled
        apify_enabled=True,            # Enabled for final shortlist
        embedding_provider_mode="dynamic",  # Reads EMBEDDING_PROVIDER env
        llm_default_model="claude-3-5-haiku-latest",
        llm_escalation_model="claude-3-7-sonnet-latest",
        llm_allow_escalation=True,
        credit_cost_per_search=5,
    ),
}


def _resolve_llm_models(limits: TierLimits) -> TierLimits:
    """Dynamically sets model names based on active LLM_PROVIDER (Groq vs Anthropic)."""
    is_groq = (settings.LLM_PROVIDER or "").lower() == "groq"
    default_model = settings.GROQ_DEFAULT_MODEL if is_groq else settings.ANTHROPIC_DEFAULT_MODEL
    escalation_model = settings.GROQ_ESCALATION_MODEL if is_groq else (
        settings.ANTHROPIC_ESCALATION_MODEL if limits.tier == PlanTier.PAID else settings.ANTHROPIC_DEFAULT_MODEL
    )
    # Return copy with updated models
    return limits.model_copy(update={
        "llm_default_model": default_model,
        "llm_escalation_model": escalation_model,
    })


def get_current_plan_tier() -> PlanTier:
    """Read the active runtime tier from settings, defaulting to FREE if invalid."""
    normalized = (settings.PLAN_TIER or "").strip().lower()
    try:
        return PlanTier(normalized)
    except ValueError:
        return PlanTier.FREE


def get_tier_limits(tier: PlanTier | None = None) -> TierLimits:
    """Retrieve the limits object for a given tier or the current runtime tier."""
    active_tier = tier or get_current_plan_tier()
    base_limits = TIER_CONFIGS.get(active_tier, TIER_CONFIGS[PlanTier.FREE])
    return _resolve_llm_models(base_limits)
