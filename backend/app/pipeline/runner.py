"""End-to-End Search Pipeline Orchestrator (Stages 1 through 13)

Orchestrates input understanding, discovery search, verification, LLM judging,
streaming SSE events, and atomic persistence.
"""
import uuid
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.search import Search
from app.config.tiers import PlanTier, get_tier_limits
from app.providers.base import SearchBudget, QuotaExhaustedError
from app.providers.gateway import provider_gateway
from app.core.ledger import CreditLedgerService

# Import All 13 Stages
from app.pipeline.stage_01_understand import run_stage_01_understand_input
from app.pipeline.stage_02_entity_resolution import run_stage_02_entity_resolution
from app.pipeline.stage_03_scope_detection import run_stage_03_scope_detection
from app.pipeline.stage_04_market_map_lookup import run_stage_04_market_map_lookup
from app.pipeline.stage_05_discovery import run_stage_05_discovery
from app.pipeline.stage_06_consensus_scoring import run_stage_06_consensus_scoring
from app.pipeline.stage_07_extract_candidates import run_stage_07_extract_candidates
from app.pipeline.stage_08_verify import run_stage_08_verify
from app.pipeline.stage_09_rank import run_stage_09_rank_cheaply
from app.pipeline.stage_10_enrich import run_stage_10_enrich
from app.pipeline.stage_11_llm_judge import run_stage_11_llm_judge
from app.pipeline.stage_12_stream import emit_sse_event
from app.pipeline.stage_13_persistence import run_stage_13_persistence

logger = logging.getLogger("pipeline.runner")


async def run_search_pipeline(search_id: uuid.UUID) -> None:
    """Execute the full 13-stage competitor discovery pipeline for a search job."""
    sid_str = str(search_id)
    logger.info(f"Starting pipeline execution for search {sid_str}")

    async with AsyncSessionLocal() as db:
        # 1. Load search record
        query = select(Search).where(Search.id == search_id).options(selectinload(Search.results))
        res = await db.execute(query)
        search = res.scalar_one_or_none()
        if not search:
            logger.error(f"Search {sid_str} not found in database")
            await emit_sse_event(sid_str, "error", {"message": "Search job not found"})
            return

        if search.status == "completed":
            logger.info(f"Search {sid_str} already completed, skipping.")
            return

        # Mark search as running
        search.status = "running"
        await db.commit()

        # Tier limits & budget
        try:
            tier_enum = PlanTier(search.tier)
        except ValueError:
            tier_enum = PlanTier.FREE
        tier_limits = get_tier_limits(tier_enum)
        budget = SearchBudget(serpapi_max_calls=tier_limits.serpapi_max_calls)
        gateway = provider_gateway
        providers_used = []

        try:
            # -------------------------------------------------------------
            # Stage 01: Understand Input
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 1,
                "stage_name": "Understanding Input",
                "message": f"Analyzing '{search.query}' with AI to extract business profile & category...",
            })
            profile = await run_stage_01_understand_input(
                query=search.query,
                location=search.location,
                llm_provider=gateway.llm,
                gateway=gateway,
                tier_limits=tier_limits,
                budget=budget,
            )
            providers_used.append("groq")
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 1,
                "stage_name": "Input Understood",
                "data": profile.model_dump(),
            })

            # -------------------------------------------------------------
            # Stage 02: Entity Resolution (Strict Self-Exclusion)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 2,
                "stage_name": "Entity Resolution",
                "message": "Resolving canonical domain to guarantee self-exclusion...",
            })
            excluded_domain, aliases = await run_stage_02_entity_resolution(
                profile_name=profile.business_name,
                query=search.query,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 2,
                "stage_name": "Entity Resolved",
                "data": {"excluded_domain": excluded_domain, "aliases": aliases},
            })

            # Auto-detect location for local physical businesses if omitted by user
            if not search.location and not profile.location and profile.scope_guess == "local":
                try:
                    probe_hits = await gateway.search(
                        query=search.query,
                        tier_limits=tier_limits,
                        budget=budget,
                        num_results=5,
                    )
                    for ph in probe_hits:
                        if ph.engine == "google_maps" and ph.raw_data and isinstance(ph.raw_data, dict):
                            addr = ph.raw_data.get("address")
                            if addr:
                                profile.location = addr
                                break
                        combined = (ph.title + " " + ph.snippet).lower()
                        for city in ["lahore", "karachi", "islamabad", "rawalpindi", "london", "manchester", "birmingham", "new york", "los angeles", "chicago", "houston", "austin", "dubai", "toronto"]:
                            if city in combined:
                                profile.location = city.title()
                                break
                        if profile.location:
                            break
                    if profile.location:
                        logger.info(f"Auto-detected location for '{search.query}': {profile.location}")
                except Exception as loc_e:
                    logger.debug(f"Auto-location probe notice: {loc_e}")

            # -------------------------------------------------------------
            # Stage 03: Scope & Region Detection
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 3,
                "stage_name": "Scope Detection",
                "message": "Determining local, national, or global competitor scope...",
            })
            effective_scope = await run_stage_03_scope_detection(
                inferred_scope=profile.scope_guess,
                scope_override=search.scope_override,
                location=search.location or profile.location,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 3,
                "stage_name": "Scope Detected",
                "data": {"scope": effective_scope},
            })

            # -------------------------------------------------------------
            # Stage 04: Market Map Lookup (Cache / Fast Seed)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 4,
                "stage_name": "Market Map Cache",
                "message": "Querying verified market map cache for existing rivals...",
            })
            cached_candidates = await run_stage_04_market_map_lookup(
                db=db,
                category=profile.business_type,
                region=effective_scope,
                required_count=search.num_competitors,
                excluded_domain=excluded_domain,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 4,
                "stage_name": "Cache Checked",
                "data": {"cached_count": len(cached_candidates)},
            })

            # -------------------------------------------------------------
            # Stage 05: Discovery Search (SerpAPI Web + Maps)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 5,
                "stage_name": "Live Web & Maps Discovery",
                "message": f"Executing live Google & Maps queries for '{profile.business_name}'...",
            })
            search_hits = await run_stage_05_discovery(
                gateway=gateway,
                business_name=profile.business_name or search.query,
                keywords=profile.search_keywords,
                tier_limits=tier_limits,
                budget=budget,
                scope=effective_scope,
                location=search.location or profile.location,
                country_code=profile.country_code,
                language=profile.language or "en",
                offerings=profile.offerings,
            )
            providers_used.append("serpapi")
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 5,
                "stage_name": "Discovery Complete",
                "data": {"search_hits_found": len(search_hits)},
            })

            # -------------------------------------------------------------
            # Stage 06: Consensus Scoring & Blocklist Filtering
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 6,
                "stage_name": "Consensus Scoring",
                "message": "Filtering aggregator directories and scoring frequency & ad signals...",
            })
            consensus_scores = await run_stage_06_consensus_scoring(
                search_hits=search_hits,
                excluded_domain=excluded_domain,
                aliases=aliases,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 6,
                "stage_name": "Consensus Scoring Complete",
                "data": {"unique_candidate_domains": len(consensus_scores)},
            })

            # -------------------------------------------------------------
            # Stage 07: Candidate Extraction
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 7,
                "stage_name": "Candidate Extraction",
                "message": "Extracting clean brand names, snippets, and verified source URLs...",
            })
            candidates = await run_stage_07_extract_candidates(
                search_hits=search_hits,
                consensus_scores=consensus_scores,
                cached_candidates=cached_candidates,
                target_name=profile.business_name or search.query,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 7,
                "stage_name": "Candidate Extraction Complete",
                "data": {"extracted_count": len(candidates)},
            })

            # -------------------------------------------------------------
            # Stage 08: Cheap Verification (DNS & HTTP probe)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 8,
                "stage_name": "Live Web Verification",
                "message": "Verifying DNS and live web availability in parallel...",
            })
            verified_cands, unverified_cands = await run_stage_08_verify(
                candidates=candidates,
                excluded_domain=excluded_domain,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 8,
                "stage_name": "Verification Complete",
                "data": {"verified_count": len(verified_cands), "unverified_count": len(unverified_cands)},
            })

            # -------------------------------------------------------------
            # Stage 09: Cheap Pre-Ranking
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 9,
                "stage_name": "Pre-Ranking Finalists",
                "message": "Sorting candidate finalists by consensus weights and category relevance...",
            })
            finalists = await run_stage_09_rank_cheaply(
                candidates=verified_cands,
                consensus_scores=consensus_scores,
                target_count=search.num_competitors,
                business_type=profile.business_type,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 9,
                "stage_name": "Pre-Ranking Complete",
                "data": {"finalists_count": len(finalists)},
            })

            # -------------------------------------------------------------
            # Stage 10: Enrichment (Firecrawl fetch for thin snippets)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 10,
                "stage_name": "Content Enrichment",
                "message": "Scraping landing page text for thin candidate snippets...",
            })
            enriched_finalists = await run_stage_10_enrich(
                candidates=finalists,
                gateway=gateway,
                tier_limits=tier_limits,
            )
            providers_used.append("firecrawl")
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 10,
                "stage_name": "Content Enrichment Complete",
                "data": {"candidates_ready": len(enriched_finalists)},
            })

            # -------------------------------------------------------------
            # Stage 11: LLM Judge (Strict grounding, Zero hallucination)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 11,
                "stage_name": "AI Judge Evaluation",
                "message": "Evaluating competitor overlap, classification, and match scores...",
            })
            allowed_types = search.competitor_types or ["direct", "indirect", "leader"]
            judge_output = await run_stage_11_llm_judge(
                profile=profile,
                candidates=enriched_finalists,
                target_count=search.num_competitors,
                allowed_types=allowed_types,
                tier_limits=tier_limits,
                llm_provider=gateway.llm,
            )

            # Emit competitor_found event for each judged competitor
            for comp in judge_output.competitors:
                await emit_sse_event(sid_str, "competitor_found", {
                    "competitor": comp.model_dump(),
                })

            if judge_output.shortfall:
                await emit_sse_event(sid_str, "shortfall", {
                    "shortfall": True,
                    "reason": judge_output.shortfall_explanation,
                    "found_count": len(judge_output.competitors),
                    "target_count": search.num_competitors,
                })

            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 11,
                "stage_name": "Judge Evaluation Complete",
                "data": {
                    "competitors_count": len(judge_output.competitors),
                    "shortfall": judge_output.shortfall,
                },
            })

            # -------------------------------------------------------------
            # Stage 13: Persistence & Credit Settlement
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "stage_started", {
                "stage": 13,
                "stage_name": "Saving Verified Results",
                "message": "Persisting verified competitors and updating credit ledger...",
            })
            await run_stage_13_persistence(
                db=db,
                search=search,
                competitors=judge_output.competitors,
                providers_used=list(set(providers_used)),
                actual_cost=float(tier_limits.credit_cost_per_search),
                category=profile.business_type,
                region=effective_scope,
            )
            await emit_sse_event(sid_str, "stage_completed", {
                "stage": 13,
                "stage_name": "Persistence Complete",
                "data": {"status": "saved"},
            })

            # -------------------------------------------------------------
            # Stage 12 Stream Termination (Done event)
            # -------------------------------------------------------------
            await emit_sse_event(sid_str, "done", {
                "search_id": sid_str,
                "status": "completed",
                "competitors_count": len(judge_output.competitors),
                "shortfall": judge_output.shortfall,
                "shortfall_explanation": judge_output.shortfall_explanation,
                "competitors": [c.model_dump() for c in judge_output.competitors],
            })
            logger.info(f"Pipeline finished successfully for search {sid_str}. Found {len(judge_output.competitors)} competitors.")

        except QuotaExhaustedError as qe:
            logger.warning(f"Pipeline search quota exhausted for search {sid_str}: {qe}")
            err_msg = "SerpAPI Search Quota Exhausted: Your monthly quota (250/250 searches) on talalrao04@gmail.com has been reached. Please update SERPAPI_KEY in backend/.env with a valid API key."
            search.status = "failed"
            search.error_message = err_msg
            try:
                await CreditLedgerService.refund_credits(
                    db=db,
                    org_id=search.org_id,
                    search_id=search.id,
                    amount=int(search.estimated_cost or 1),
                    reason="Search provider monthly quota exhausted",
                )
            except Exception as ref_err:
                logger.warning(f"Credit refund failed: {ref_err}")
            await db.commit()

            await emit_sse_event(sid_str, "pipeline_error", {
                "message": err_msg,
            })
            await emit_sse_event(sid_str, "error", {
                "message": err_msg,
            })

        except Exception as e:
            logger.exception(f"Pipeline failure for search {sid_str}: {e}")
            err_msg = f"Search failed: {str(e)}"
            search.status = "failed"
            search.error_message = err_msg
            # Refund reserved credits
            try:
                await CreditLedgerService.refund_credits(
                    db=db,
                    org_id=search.org_id,
                    search_id=search.id,
                    amount=int(search.estimated_cost or 1),
                    reason=f"Pipeline error: {str(e)}",
                )
            except Exception as ref_err:
                logger.warning(f"Credit refund failed: {ref_err}")
            await db.commit()

            await emit_sse_event(sid_str, "pipeline_error", {
                "message": err_msg,
            })
            await emit_sse_event(sid_str, "error", {
                "message": err_msg,
            })
