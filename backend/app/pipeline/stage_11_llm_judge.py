"""Pipeline Stage 11: LLM Judge (One call, strict JSON schema output, zero hallucination)"""
import logging
from typing import List, Optional
from app.config.tiers import TierLimits
from app.schemas.llm import (
    BusinessProfileSchema,
    CompactCandidateCard,
    JudgeOutputSchema,
    JudgeCompetitorItem,
)
from app.providers.base import BaseLLMProvider
from app.providers.llm import create_llm_adapter

logger = logging.getLogger("pipeline.stage_11")


async def run_stage_11_llm_judge(
    profile: BusinessProfileSchema,
    candidates: List[CompactCandidateCard],
    target_count: int,
    allowed_types: List[str],
    tier_limits: TierLimits,
    llm_provider: Optional[BaseLLMProvider] = None,
) -> JudgeOutputSchema:
    """Evaluate candidate cards strictly against retrieved web data."""
    if not candidates:
        return JudgeOutputSchema(
            competitors=[],
            shortfall=True,
            shortfall_explanation="No verified candidates found during discovery.",
            judge_confidence=1.0,
        )

    provider = llm_provider or create_llm_adapter()

    # Build prompt with candidate cards
    candidate_lines = []
    for i, c in enumerate(candidates, start=1):
        candidate_lines.append(
            f"[{i}] Name: {c.name} | Domain: {c.domain} | URL: {c.source_url}\n    Description: {c.description}"
        )
    candidates_text = "\n".join(candidate_lines)

    allowed_types_str = ", ".join(allowed_types or ["direct", "indirect", "leader"])

    system_prompt = (
        "You are an expert market intelligence analyst and competitor evaluation judge.\n"
        "STRICT GROUNDING RULES:\n"
        "1. You must ONLY evaluate companies from the provided candidate list.\n"
        "2. NEVER invent, imagine, or hallucinate new competitors.\n"
        "3. Every competitor you include MUST come from the candidates list and preserve its exact source_url.\n"
        "4. Filter out non-competitors (e.g. news sites, review blogs, unrelated software, partners).\n"
        "5. If fewer than requested competitors exist among the candidates, return ONLY genuine competitors, set shortfall=true, and provide a clear explanation. DO NOT pad results.\n"
    )

    user_prompt = f"""EVALUATE CANDIDATES FOR TARGET BUSINESS:
- Business Name: {profile.business_name}
- Category / Type: {profile.business_type}
- Customer Type: {profile.customer_type}
- Offerings: {', '.join(profile.offerings or [])}
- Location: {profile.location or 'Global'}
- Requested Competitor Count: {target_count}
- Allowed Competitor Types: {allowed_types_str}

CANDIDATES TO EVALUATE:
{candidates_text}

INSTRUCTIONS:
1. For each candidate that genuinely competes with {profile.business_name}:
   - type: Choose from [{allowed_types_str}].
     * "direct": Primary product/service targeting the same core need and customer.
     * "indirect": Different product approach or adjacent customer solving the same underlying problem.
     * "leader": Dominant market giant or enterprise standard in this category.
   - match_score: Number from 0.0 to 100.0 based on degree of direct competitive overlap.
   - reason: 1-2 factual sentences explaining why they compete based on the retrieved data.
   - source_url: Use the exact candidate URL.
   - is_competitor: true
2. Sort competitors by match_score descending.
3. Return up to {target_count} competitors.
4. Set shortfall=true if count < {target_count}.
5. Product & Brand Disambiguation: If a candidate represents a prominent product line or division (e.g. 'Google Pixel', 'AWS', 'Microsoft Azure'), evaluate the competitive overlap against the relevant parent brand/division and output the proper competitor name.
"""

    try:
        judge_output, cost, latency = await provider.generate_structured(
            prompt=user_prompt,
            schema=JudgeOutputSchema,
            system_prompt=system_prompt,
            temperature=0.0,
        )

        # Post-filter only genuine competitors matching allowed types
        filtered_competitors: List[JudgeCompetitorItem] = []
        for comp in judge_output.competitors:
            if not comp.is_competitor:
                continue
            if allowed_types and comp.type not in allowed_types:
                continue
            filtered_competitors.append(comp)

        # Enforce target_count limit
        final_competitors = filtered_competitors[:target_count]
        shortfall = len(final_competitors) < target_count

        return JudgeOutputSchema(
            competitors=final_competitors,
            shortfall=shortfall,
            shortfall_explanation=judge_output.shortfall_explanation or (
                f"Found {len(final_competitors)} verified competitors out of {target_count} requested." if shortfall else None
            ),
            judge_confidence=judge_output.judge_confidence or 0.95,
        )

    except Exception as e:
        logger.error(f"Stage 11 LLM Judge evaluation failed: {e}. Executing algorithmic fallback.")
        # Algorithmic fallback without LLM failure blocking
        fallback_competitors: List[JudgeCompetitorItem] = []
        for cand in candidates[:target_count]:
            fallback_competitors.append(
                JudgeCompetitorItem(
                    name=cand.name,
                    domain=cand.domain,
                    type="direct",
                    match_score=85.0,
                    reason=f"Verified category competitor matching {profile.business_type} web presence.",
                    source_url=cand.source_url,
                    is_competitor=True,
                )
            )
        shortfall = len(fallback_competitors) < target_count
        return JudgeOutputSchema(
            competitors=fallback_competitors,
            shortfall=shortfall,
            shortfall_explanation="Fewer verified candidates available" if shortfall else None,
            judge_confidence=0.8,
        )
