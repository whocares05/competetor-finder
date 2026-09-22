"""Pipeline Stage 05: Discovery Search (SerpAPI web + maps queries within tier budget)"""
import logging
from typing import List, Optional
from app.config.tiers import TierLimits
from app.providers.base import SearchResultItemDTO, SearchBudget, QuotaExhaustedError
from app.providers.gateway import ProviderGateway

logger = logging.getLogger("pipeline.stage_05")


def format_loc_query(base: str, loc: Optional[str]) -> str:
    """Safely format query with location avoiding duplicate phrases like 'Pakistan in Pakistan'."""
    if not loc:
        return base.strip()
    loc_clean = loc.strip()
    if loc_clean.lower() in base.lower():
        return base.strip()
    return f"{base.strip()} in {loc_clean}"


async def run_stage_05_discovery(
    gateway: ProviderGateway,
    business_name: str,
    keywords: List[str],
    tier_limits: TierLimits,
    budget: SearchBudget,
    scope: str = "global",
    location: Optional[str] = None,
    country_code: Optional[str] = None,
    language: str = "en",
) -> List[SearchResultItemDTO]:
    """Execute live discovery queries on Google & Google Maps up to tier budget."""
    all_hits: List[SearchResultItemDTO] = []
    max_calls = tier_limits.serpapi_max_calls
    
    queries_to_run = []
    
    # 1. Scope-specific query prioritization
    if scope == "local" and location:
        # Local intent: prioritize Google Maps for city places, plus local web lists
        cat_kw = keywords[1] if len(keywords) > 1 else (keywords[0] if keywords else business_name)
        # Query 1: Google Maps search for category in city (yields up to 20 local verified places)
        queries_to_run.append((format_loc_query(cat_kw, location), "google_maps"))
        # Query 2: Google Web search for best in city (yields web results, ads, local pack)
        queries_to_run.append((format_loc_query(f"best {cat_kw}", location), "google"))
        # Query 3: Google Web search for places/alternatives like business (avoids wasting maps call on target business itself)
        if business_name:
            queries_to_run.append((format_loc_query(f"places like {business_name}", location), "google"))
            queries_to_run.append((format_loc_query(f"competitors to {business_name}", location), "google"))
        if keywords:
            queries_to_run.append((format_loc_query(keywords[0], location), "google"))

    elif scope == "national":
        # National retail / enterprise / countrywide brands
        cat_kw = keywords[1] if len(keywords) > 1 else (keywords[0] if keywords else "brands")
        # Query 1: High-yield brand comparison (surfaces direct brand peers like Sapphire, J., Gul Ahmed)
        if business_name:
            queries_to_run.append((format_loc_query(f"brands like {business_name}", location), "google"))
            queries_to_run.append((format_loc_query(f"competitors to {business_name}", location), "google"))
        # Query 2: Category market leaders in country
        queries_to_run.append((format_loc_query(f"top {cat_kw}", location), "google"))
        # Query 3: Best alternatives / competitors
        if business_name:
            queries_to_run.append((format_loc_query(f"best alternatives to {business_name}", location), "google"))
        # Remaining keywords
        for kw in keywords:
            formatted_kw = format_loc_query(kw, location)
            if formatted_kw not in [q[0] for q in queries_to_run]:
                queries_to_run.append((formatted_kw, "google"))

    else:
        # Global / Digital SaaS intent: prioritize direct alternatives and category software
        if business_name:
            queries_to_run.append((f"{business_name} alternatives", "google"))
            queries_to_run.append((f"competitors to {business_name}", "google"))
        for kw in keywords:
            if kw not in [q[0] for q in queries_to_run]:
                queries_to_run.append((kw, "google"))

    # Cap queries to max_calls allowed by plan
    selected_queries = queries_to_run[:max_calls]
    
    for q_text, engine in selected_queries:
        if budget.serpapi_calls_made >= max_calls:
            break
        try:
            logger.info(f"Running discovery query via {engine}: '{q_text}'")
            hits = await gateway.search(
                query=q_text,
                tier_limits=tier_limits,
                budget=budget,
                engine=engine,
                location=None,  # Included directly in query text for cross-country robustness
                country_code=country_code,
                language=language,
                num_results=20 if engine == "google_maps" else 10,
            )
            budget.serpapi_calls_made += 1
            all_hits.extend(hits)
            import asyncio
            await asyncio.sleep(0.8)
        except QuotaExhaustedError as qe:
            logger.error(f"Search provider quota exhausted during discovery: {qe}")
            raise qe
        except Exception as e:
            logger.warning(f"Error in discovery query '{q_text}': {e}")
            budget.serpapi_calls_made += 1
            import asyncio
            await asyncio.sleep(0.8)
            continue

    logger.info(f"Discovery stage gathered {len(all_hits)} raw search hits across {budget.serpapi_calls_made} calls.")
    return all_hits
