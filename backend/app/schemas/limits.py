"""Limits and Quota Response Pydantic Schemas"""
from typing import Dict, Any
from pydantic import BaseModel
from app.config.tiers import PlanTier, TierLimits


class LimitsResponse(BaseModel):
    tier: PlanTier
    max_competitors: int
    default_competitors: int
    serpapi_max_calls: int
    firecrawl_candidate_multiplier: int
    firecrawl_use_extract: bool
    apify_enabled: bool
    embedding_provider: str
    llm_default_model: str
    llm_allow_escalation: bool
    credits_balance: int
    daily_quota_remaining: Dict[str, Any]
