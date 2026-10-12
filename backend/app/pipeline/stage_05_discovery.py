import re
import logging
from typing import List, Optional, Tuple
from app.config.tiers import TierLimits
from app.providers.base import SearchResultItemDTO, SearchBudget, QuotaExhaustedError
from app.providers.gateway import ProviderGateway

logger = logging.getLogger("pipeline.stage_05")


def format_loc_query(base: Optional[str], loc: Optional[str]) -> str:
    """Safely format query with location avoiding duplicate phrases like 'Pakistan in Pakistan'."""
    if not base:
        return (loc or "").strip()
    base_str = str(base).strip()
    if not loc:
        return base_str
    loc_clean = loc.strip()
    if loc_clean.lower() in base_str.lower():
        return base_str
    return f"{base_str} in {loc_clean}"


def clean_offering_name(offering: Optional[str]) -> str:
    """Strip bullet points, leading numbers, outer quotes, and extra whitespace from offering name."""
    if not offering:
        return ""
    cleaned = re.sub(r"^[0-9•\-\*\.]+\s*", "", offering).strip(' "\'').strip()
    return cleaned


def build_discovery_queries(
    business_name: str,
    keywords: List[str],
    scope: str = "global",
    location: Optional[str] = None,
    offerings: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """
    Construct prioritized discovery queries for Google Web & Google Maps.
    Injects granular offerings (e.g. 'Unstitched Lawn', 'Interactive Prototyping')
    into high-priority query slots for sharp niche precision.
    """
    queries_to_run: List[Tuple[str, str]] = []

    def add_query(q_text: str, engine: str = "google"):
        q_clean = q_text.strip()
        if q_clean and not any(q[0].lower() == q_clean.lower() for q in queries_to_run):
            queries_to_run.append((q_clean, engine))

    clean_bname = business_name.strip('"\'') if business_name else ""
    clean_offerings = [clean_offering_name(o) for o in (offerings or []) if clean_offering_name(o)]

    if scope == "local" and location:
        cat_kw = (keywords[1] if len(keywords) > 1 else (keywords[0] if keywords else business_name)) or "business"
        # Query 1: Google Maps search for category in city (yields up to 20 local verified places)
        add_query(format_loc_query(cat_kw, location), "google_maps")

        # Query 2 (Niche Offering #1 if available, otherwise best category)
        if clean_offerings:
            add_query(format_loc_query(f"best {clean_offerings[0]}", location), "google")
        else:
            add_query(format_loc_query(f"best {cat_kw}", location), "google")

        # Query 3: Competitors & alternatives to business in city
        if clean_bname:
            add_query(format_loc_query(f'places like "{clean_bname}"', location), "google")
            add_query(format_loc_query(f'competitors to "{clean_bname}"', location), "google")

        # Query 4: Niche Offering #2 if available
        if len(clean_offerings) > 1:
            add_query(format_loc_query(f"top {clean_offerings[1]}", location), "google")

        # Remaining category keywords
        for kw in keywords:
            add_query(format_loc_query(kw, location), "google")

    elif scope == "national":
        # National retail / enterprise / countrywide brands
        cat_kw = keywords[1] if len(keywords) > 1 else (keywords[0] if keywords else "brands")

        # Query 1: High-yield brand comparison (surfaces direct brand peers like Sapphire, J., Gul Ahmed)
        if clean_bname:
            add_query(format_loc_query(f'brands like "{clean_bname}"', location), "google")

        # Query 2: Granular Niche Offering #1 (e.g. top "Unstitched Lawn" brands in Pakistan)
        if clean_offerings:
            add_query(format_loc_query(f'top "{clean_offerings[0]}" brands', location), "google")
        else:
            add_query(format_loc_query(f"top {cat_kw}", location), "google")

        # Query 3: Granular Niche Offering #2 (e.g. best "Ready-to-Wear Pret" brands in Pakistan)
        if len(clean_offerings) > 1:
            add_query(format_loc_query(f'best "{clean_offerings[1]}" brands', location), "google")
        elif clean_bname:
            add_query(format_loc_query(f'competitors to "{clean_bname}"', location), "google")

        # Query 4: Direct competitors & alternatives
        if clean_bname:
            add_query(format_loc_query(f'competitors to "{clean_bname}"', location), "google")
            add_query(format_loc_query(f'best alternatives to "{clean_bname}"', location), "google")

        # Query 5: Fallback category market leaders if not already queried
        add_query(format_loc_query(f"top {cat_kw}", location), "google")

        # Remaining keywords
        for kw in keywords:
            add_query(format_loc_query(kw, location), "google")

    else:
        # Global / Digital SaaS intent: prioritize direct alternatives and niche sub-product software
        # Query 1: Direct alternatives to brand
        if clean_bname:
            add_query(f'"{clean_bname}" alternatives', "google")

        # Query 2: Granular Niche Offering #1
        if clean_offerings:
            off1 = clean_offerings[0]
            if any(term in off1.lower() for term in ("tool", "software", "platform", "app", "service", "system")):
                add_query(f'best "{off1}"', "google")
            else:
                add_query(f'best "{off1}" software', "google")

        # Query 3: Granular Niche Offering #2 or direct competitors
        if len(clean_offerings) > 1:
            off2 = clean_offerings[1]
            if any(term in off2.lower() for term in ("tool", "software", "platform", "app", "service", "system")):
                add_query(f'top "{off2}"', "google")
            else:
                add_query(f'top "{off2}" tools', "google")
        elif clean_bname:
            add_query(f'competitors to "{clean_bname}"', "google")

        # Query 4: Direct competitors
        if clean_bname:
            add_query(f'competitors to "{clean_bname}"', "google")

        # Remaining keywords
        for kw in keywords:
            add_query(kw, "google")

    return queries_to_run


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
    offerings: Optional[List[str]] = None,
) -> List[SearchResultItemDTO]:
    """Execute live discovery queries on Google & Google Maps up to tier budget."""
    all_hits: List[SearchResultItemDTO] = []
    max_calls = tier_limits.serpapi_max_calls

    queries_to_run = build_discovery_queries(
        business_name=business_name,
        keywords=keywords,
        scope=scope,
        location=location,
        offerings=offerings,
    )

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
