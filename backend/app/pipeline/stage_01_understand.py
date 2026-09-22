"""Pipeline Stage 01: Understand Input (LLM parsing into strict JSON schema with Web Grounding)"""
import re
import logging
from typing import Optional, Any
import httpx

from app.schemas.llm import BusinessProfileSchema
from app.providers.base import BaseLLMProvider
from app.providers.llm import create_llm_adapter

logger = logging.getLogger("pipeline.stage_01")


async def fetch_website_meta(domain_or_url: str) -> Optional[str]:
    """Extract <title> and <meta name="description"> from a company website."""
    url = domain_or_url if domain_or_url.startswith("http") else f"https://{domain_or_url}"
    try:
        async with httpx.AsyncClient(timeout=3.5, follow_redirects=True, verify=False) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                html = resp.text[:15000]
                title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
                if not desc_match:
                    desc_match = re.search(r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
                
                title = title_match.group(1).strip() if title_match else ""
                desc = desc_match.group(1).strip() if desc_match else ""
                if title or desc:
                    return f"Official Website [{domain_or_url}]: {title} - {desc}"
    except Exception:
        pass
    return None


async def probe_web_grounding(
    query: str,
    location: Optional[str] = None,
    gateway: Optional[Any] = None,
    tier_limits: Optional[Any] = None,
    budget: Optional[Any] = None,
) -> Optional[str]:
    """Execute a single fast search probe to discover how the business describes itself online."""
    # If the user typed a URL, scrape its meta description directly
    is_url = query.startswith("http") or (re.match(r"^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", query.split()[0]))
    if is_url:
        domain_guess = query.split()[0].replace("https://", "").replace("http://", "").replace("www.", "")
        meta = await fetch_website_meta(domain_guess)
        if meta:
            return meta

    if not gateway:
        return None

    try:
        search_term = f'"{query}" {location or ""}'.strip()
        hits = await gateway.search(
            query=search_term,
            tier_limits=tier_limits,
            budget=budget,
            num_results=3,
        )
        if not hits:
            hits = await gateway.search(
                query=f"{query} {location or ''}".strip(),
                tier_limits=tier_limits,
                budget=budget,
                num_results=3,
            )

        snippets = []
        clean_q = re.sub(r"[^a-zA-Z0-9]", "", query.lower())
        for h in hits:
            h_title_clean = re.sub(r"[^a-zA-Z0-9]", "", h.title.lower())
            if clean_q in h_title_clean or clean_q in h.domain.lower():
                snippets.append(f"Source [{h.domain}]: {h.title} - {h.snippet}")
            elif len(snippets) < 2:
                snippets.append(f"Source [{h.domain}]: {h.title} - {h.snippet}")

        if snippets:
            return "\n".join(snippets[:3])
    except Exception as e:
        logger.debug(f"Web grounding probe notice: {e}")
    return None


async def run_stage_01_understand_input(
    query: str,
    location: Optional[str] = None,
    llm_provider: Optional[BaseLLMProvider] = None,
    gateway: Optional[Any] = None,
    tier_limits: Optional[Any] = None,
    budget: Optional[Any] = None,
) -> BusinessProfileSchema:
    """Analyze user query and return structured business profile grounded by live web signals."""
    provider = llm_provider or create_llm_adapter()
    
    # 1. Gather real-world web grounding context
    web_grounding = await probe_web_grounding(
        query=query,
        location=location,
        gateway=gateway,
        tier_limits=tier_limits,
        budget=budget,
    )
    if web_grounding:
        logger.info(f"Stage 1 Web Grounding discovered:\n{web_grounding}")

    grounding_section = (
        f"\nReal-World Web Grounding (How this specific business describes itself online):\n{web_grounding}\n"
        if web_grounding
        else ""
    )

    prompt = f"""Analyze this business input and extract its profile:
Query: "{query}"
Optional Location context: "{location or 'Not provided'}"
{grounding_section}
Instructions:
1. Identify the exact business name and its primary category/type based on the real-world web grounding (e.g., "custom software development company", "enterprise AI solutions agency", "artisan bakery", "cross-border payment gateway"). Do NOT guess or hallucinate SaaS if the business describes itself as an agency, software house, or service company.
2. List 3-7 core offerings/features/services matching what the business actually provides.
3. Determine customer_type: "B2B", "B2C", or "both".
4. Determine scope_guess: "local" (physical local client base/presence required, e.g. software house, agency, salon, restaurant), "regional", "national", or "global" (pure self-serve online tools/SaaS).
5. If location was provided or can be deduced from the query or web grounding, populate location and 2-letter country_code.
6. Provide 3-5 high-intent search query keywords to find direct alternatives and market competitors on Google (e.g., if it is a software house in Lahore, output keywords like 'software development companies in Lahore', 'top software houses Lahore', 'custom software development agency Pakistan').
7. Set confidence between 0.0 and 1.0. If the business is unknown and cannot be identified from web grounding, set clarifying_question.
"""

    try:
        profile, _, _ = await provider.generate_structured(
            prompt=prompt,
            schema=BusinessProfileSchema,
            temperature=0.1,
        )
        # Ensure location from query takes precedence if LLM missed it
        if location and not profile.location:
            profile.location = location
            if profile.scope_guess == "global":
                from app.pipeline.stage_03_scope_detection import is_country_level_location
                profile.scope_guess = "national" if is_country_level_location(location) else "local"
        return profile
    except Exception as e:
        logger.warning(f"Stage 1 LLM parse error: {e}. Using intelligent fallback profile.")
        is_url = query.startswith("http") or "." in query.split()[0]
        name = query.split(".")[0].replace("https://", "").replace("http://", "").replace("www.", "") if is_url else query
        name = name.strip().title()
        
        keywords = [
            f"{name} alternatives",
            f"{name} competitors",
            f"best alternatives to {name}",
        ]
        if location:
            keywords.append(f"{name} in {location}")

        from app.pipeline.stage_03_scope_detection import is_country_level_location
        is_cntry = is_country_level_location(location) if location else False

        return BusinessProfileSchema(
            business_name=name,
            business_type="software & technology service" if is_url else "business service",
            offerings=[],
            customer_type="B2B",
            location=location,
            country_code=None,
            language="en",
            scope_guess="national" if is_cntry else ("local" if location else "global"),
            search_keywords=keywords,
            confidence=0.75,
            clarifying_question=None,
        )
