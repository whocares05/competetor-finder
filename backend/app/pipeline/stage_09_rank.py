"""Pipeline Stage 09: Cheap Pre-Ranking (Consensus score + heuristic relevance signals)"""
from typing import List, Dict
from app.schemas.llm import CompactCandidateCard


async def run_stage_09_rank_cheaply(
    candidates: List[CompactCandidateCard],
    consensus_scores: Dict[str, int],
    target_count: int,
    business_type: str = "",
) -> List[CompactCandidateCard]:
    """Sort candidates by multi-signal heuristics and keep up to target_count * 2 finalists."""
    def score_card(card: CompactCandidateCard) -> float:
        base_score = float(consensus_scores.get(card.domain, 1))
        # Direct competitor extractions from Google web snippets get strong priority
        if "market competitor" in card.description.lower():
            base_score += 3.0
        # Keyword bonus in description or name
        if business_type:
            keywords = business_type.lower().split()
            desc_lower = card.description.lower()
            for kw in keywords:
                if len(kw) > 3 and kw in desc_lower:
                    base_score += 0.5
        return base_score

    sorted_candidates = sorted(
        candidates,
        key=score_card,
        reverse=True,
    )
    # Allow the AI Judge to evaluate up to 30 verified candidates without premature truncation
    max_to_keep = max(target_count * 5, 30)
    return sorted_candidates[:max_to_keep]
