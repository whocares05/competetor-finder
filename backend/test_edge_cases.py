"""Interactive Edge-Case Tester for Competitor Finder Pipeline"""
import asyncio
import sys

# Configure UTF-8 for Windows PowerShell terminal
sys.stdout.reconfigure(encoding="utf-8")

from app.config.tiers import TIER_CONFIGS, PlanTier
from app.providers.base import SearchBudget
from app.providers.gateway import ProviderGateway
from app.pipeline.stage_01_understand import run_stage_01_understand_input
from app.pipeline.stage_02_entity_resolution import run_stage_02_entity_resolution
from app.pipeline.stage_03_scope_detection import run_stage_03_scope_detection
from app.pipeline.stage_05_discovery import run_stage_05_discovery
from app.pipeline.stage_06_consensus_scoring import run_stage_06_consensus_scoring
from app.pipeline.stage_07_extract_candidates import run_stage_07_extract_candidates
from app.pipeline.stage_08_verify import run_stage_08_verify
from app.pipeline.stage_09_rank import run_stage_09_rank_cheaply
from app.pipeline.stage_11_llm_judge import run_stage_11_llm_judge


async def execute_edge_case(query: str, location: str | None, count: int = 5):
    print(f"\n{'='*60}")
    print(f"RUNNING EDGE CASE: Query='{query}' | Location='{location or 'None'}'")
    print(f"{'='*60}")

    gateway = ProviderGateway()
    tier = TIER_CONFIGS[PlanTier.FREE]
    budget = SearchBudget()

    # Stage 01
    print("\n[Stage 01] Understanding Input & Web Grounding...")
    profile = await run_stage_01_understand_input(query, location=location, gateway=gateway, tier_limits=tier, budget=budget)
    print(f" -> Business Name: {profile.business_name}")
    print(f" -> Inferred Type: {profile.business_type}")
    print(f" -> Customer Type: {profile.customer_type}")
    print(f" -> Scope Guess:   {profile.scope_guess}")
    print(f" -> Keywords:      {profile.search_keywords}")
    if profile.clarifying_question:
        print(f" -> Clarifying Q:  {profile.clarifying_question}")

    # Stage 02
    print("\n[Stage 02] Entity Resolution (Self-Exclusion)...")
    excluded_domain, aliases = await run_stage_02_entity_resolution(profile.business_name, query)
    print(f" -> Excluded Domain: {excluded_domain} | Aliases: {aliases}")

    # Stage 03
    print("\n[Stage 03] Geographic Scope Detection...")
    effective_scope = await run_stage_03_scope_detection(profile.scope_guess, location=profile.location)
    print(f" -> Effective Scope: {effective_scope.upper()}")

    # Stage 05
    print("\n[Stage 05] Discovery Search Planning & Execution...")
    hits = await run_stage_05_discovery(
        gateway=gateway,
        business_name=profile.business_name,
        keywords=profile.search_keywords,
        tier_limits=tier,
        budget=budget,
        scope=effective_scope,
        location=profile.location,
        country_code=profile.country_code,
        offerings=profile.offerings,
    )
    print(f" -> Total Raw Hits Gathered: {len(hits)}")

    # Stage 06 & 07
    print("\n[Stage 06 & 07] Consensus Scoring & Candidate Extraction...")
    scores = await run_stage_06_consensus_scoring(hits, excluded_domain, aliases)
    candidates = await run_stage_07_extract_candidates(hits, scores, target_name=profile.business_name)
    print(f" -> Extracted Candidate Cards: {len(candidates)}")
    for c in candidates[:6]:
        print(f"    * {c.name} ({c.domain})")

    # Stage 08
    print("\n[Stage 08] Verification (DNS & HTTP probe)...")
    verified, unverified = await run_stage_08_verify(candidates, excluded_domain)
    print(f" -> Verified Live: {len(verified)} | Rejected: {len(unverified)}")

    # Stage 09
    print("\n[Stage 09] Finalist Pre-Ranking...")
    finalists = await run_stage_09_rank_cheaply(verified, scores, target_count=count, business_type=profile.business_type)
    print(f" -> Finalists Sent to AI Judge: {len(finalists)}")

    # Stage 11
    print("\n[Stage 11] LLM Judge Evaluation...")
    judge_output = await run_stage_11_llm_judge(
        profile=profile,
        candidates=finalists,
        target_count=count,
        allowed_types=["direct", "indirect", "leader"],
        tier_limits=tier,
        llm_provider=gateway.llm,
    )

    print(f"\n{'-'*60}")
    print(f"FINAL SHORTLIST RESULTS ({len(judge_output.competitors)} competitors):")
    print(f"{'-'*60}")
    for rank, comp in enumerate(judge_output.competitors, 1):
        print(f"#{rank} {comp.name} ({comp.domain}) - Score: {comp.match_score} | Type: {comp.type}")
        print(f"   Reason: {comp.reason}\n")

    if judge_output.shortfall:
        print(f"[!] Shortfall Flagged: {judge_output.shortfall_explanation}")


def main():
    preset_cases = {
        "1": ("Khaadi", "Pakistan", "National Retail Brand in a Country"),
        "2": ("Databiqs", "Lahore", "Local Service Agency in a City"),
        "3": ("Databiqs", "Lahore, Pakistan", "City + Country Combined Format"),
        "4": ("Figma", None, "Global B2B SaaS (No location)"),
        "5": ("Luigi's Pizza", "Brooklyn", "Single-Location Physical SMB"),
        "6": ("Xyzzynonexistentcorp999", "New York", "Non-Existent / Garbage Brand (Zero Hallucination Test)"),
    }

    print("\n" + "="*60)
    print("           COMPFINDER EDGE-CASE TEST RUNNER")
    print("="*60)
    for k, v in preset_cases.items():
        print(f"  [{k}] {v[2]}: '{v[0]}' ({v[1] or 'Global'})")
    print("  [7] Custom Query (Enter your own)")

    choice = input("\nSelect an option [1-7] (default 1): ").strip() or "1"

    if choice in preset_cases:
        query, loc, _ = preset_cases[choice]
    elif choice == "7":
        query = input("Enter business query: ").strip()
        loc = input("Enter location (or press Enter for none): ").strip() or None
    else:
        query, loc, _ = preset_cases["1"]

    asyncio.run(execute_edge_case(query, loc))


if __name__ == "__main__":
    main()
