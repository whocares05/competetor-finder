"""Pipeline Stage 06: Consensus Scoring (Zero LLM cost) and Domain Filtering"""
import re
from typing import List, Dict
from app.providers.base import SearchResultItemDTO

AGGREGATOR_BLOCKLIST = {
    # Search engines & knowledge bases
    "wikipedia.org",
    "reddit.com",
    "quora.com",
    "apple.com",
    "tiktok.com",
    "pinterest.com",
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "github.com",
    "stackoverflow.com",
    # Software & B2B directories
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "medium.com",
    "linkedin.com",
    "forbes.com",
    "businessinsider.com",
    "techcrunch.com",
    "producthunt.com",
    "crunchbase.com",
    "glassdoor.com",
    "investopedia.com",
    "wired.com",
    "theverge.com",
    "pcmag.com",
    "getapp.com",
    "softwareadvice.com",
    "slashdot.org",
    "sourceforge.net",
    "usnews.com",
    "trustradius.com",
    "peerspot.com",
    "cbinsights.com",
    "growjo.com",
    "owler.com",
    "pitchbook.com",
    "zoominfo.com",
    "apollo.io",
    "craft.co",
    "latka.com",
    # News & Lifestyle magazines
    "theglossarymagazine.com",
    "luxurylondon.co.uk",
    "cosmopolitan.com",
    "gq-magazine.co.uk",
    "adweek.com",
    "londonsweatguide.com",
    "timeout.com",
    "cntraveller.com",
    "standard.co.uk",
    "independent.co.uk",
    "theguardian.com",
    "dailymail.co.uk",
    "bbc.com",
    "nytimes.com",
    "bloomberg.com",
    "reuters.com",
    # Local & Food Delivery Aggregators
    "yelp.com",
    "tripadvisor.com",
    "foodpanda.pk",
    "foodpanda.com",
    "doordash.com",
    "ubereats.com",
    "zomato.com",
    "talabat.com",
    "swiggy.com",
    "deliveroo.com",
    "deliveroo.co.uk",
    "grubhub.com",
    "just-eat.co.uk",
    "just-eat.com",
    "postmates.com",
    "menulog.com.au",
    "hungerstation.com",
    "careem.com",
    "wheree.com",
    "dineinonline.net",
    "grexa.site",
}


def is_blocklisted_domain(domain: str) -> bool:
    """Check if domain matches aggregator, review directory, delivery platform, or social media blocklist."""
    clean_domain = domain.lower().strip()
    if clean_domain == "maps.google.com":
        return False
    for blocked in AGGREGATOR_BLOCKLIST:
        if clean_domain == blocked or clean_domain.endswith("." + blocked):
            return True
    return False


def get_hit_candidate_key(hit: SearchResultItemDTO) -> str:
    """Derive unique candidate identity key from domain or local place title."""
    if hit.domain and hit.domain != "maps.google.com":
        return hit.domain.lower().strip()
    # Normalize place title for Google Maps listings without standalone domain
    clean_title = re.sub(r"[^a-zA-Z0-9]", "", hit.title.lower())
    return f"local:{clean_title}" if clean_title else "local:unknown"


async def run_stage_06_consensus_scoring(
    search_hits: List[SearchResultItemDTO],
    excluded_domain: str | None = None,
    aliases: List[str] | None = None,
) -> Dict[str, int]:
    """Score candidates by occurrence frequency across queries, ads, and local maps."""
    scores: Dict[str, int] = {}
    normalized_excluded = (excluded_domain or "").lower().strip()
    clean_aliases = [a.lower().strip() for a in (aliases or []) if a]

    for hit in search_hits:
        if hit.domain and is_blocklisted_domain(hit.domain):
            continue

        cand_key = get_hit_candidate_key(hit)
        title_lower = hit.title.lower()

        # Strictly exclude the searched business's own domain, brand name, and aliases
        if normalized_excluded and (normalized_excluded in cand_key or normalized_excluded in title_lower):
            continue
        if any(alias in cand_key or alias in title_lower for alias in clean_aliases):
            continue

        # Ads indicate paid competitive intent (3x weighting)
        # Google Maps indicate physical local presence (2x weighting)
        # Organic results (1x weighting)
        if hit.is_ad:
            weight = 3
        elif hit.engine == "google_maps":
            weight = 2
        else:
            weight = 1

        scores[cand_key] = scores.get(cand_key, 0) + weight

    return scores
