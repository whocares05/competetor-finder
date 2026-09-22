"""Pipeline Stage 07: Candidate Extraction from titles, snippets, and verified hits"""
import re
from typing import List, Dict, Optional
from app.providers.base import SearchResultItemDTO
from app.schemas.llm import CompactCandidateCard
from app.pipeline.stage_06_consensus_scoring import is_blocklisted_domain, get_hit_candidate_key


def is_listicle_or_article_title(title: str, domain: str) -> bool:
    """Check if title is an article/listicle rather than a company name."""
    t = title.strip().lower()
    # Check if starts with a number (e.g. "10 Best...", "20 Pakistani...", "9 Best...")
    if re.match(r"^\d+[\s\.-]", t):
        return True
    article_patterns = [
        r"\btop\s+\d+", r"\bbest\s+\d+", r"\blist of\b", r"\bbrands in\b",
        r"\bclothing brands\b", r"\bcompanies in\b", r"\btools in\b",
        r"\bsoftware in\b", r"\balternatives to\b", r"\bcompetitors to\b",
        r"\bguide to\b", r"\bhow to\b", r"\breels on\b", r"\btakeover\b"
    ]
    for p in article_patterns:
        if re.search(p, t):
            return True
    return False


def clean_brand_name(title: str, domain: str) -> str:
    """Extract clean company/brand name from page title and domain."""
    # Split common title delimiters: -, |, :, •, —
    parts = re.split(r"[-|:•—–]", title)
    candidate_name = parts[0].strip()
    
    # Strip marketing buzzwords
    buzzwords = [
        "The Best", "Best", "Official Site", "Pricing", "Features", "Alternative",
        "Alternatives", "Home", "Software", "Platform", "Download", "Top", "Order",
        "Menu", "Reviews", "Updated"
    ]
    for b in buzzwords:
        if candidate_name.lower().startswith(b.lower() + " "):
            candidate_name = candidate_name[len(b) + 1:].strip()

    if not candidate_name or len(candidate_name) > 40:
        if domain and domain != "maps.google.com":
            candidate_name = domain.split(".")[0].capitalize()
        else:
            candidate_name = title.strip()[:30]

    return candidate_name.strip()


def extract_entities_from_snippet(text: str, target_name: Optional[str] = None) -> List[str]:
    """Extract individual company/brand entities mentioned in numbered, bulleted, or competitor listicles."""
    if not text:
        return []
    target_clean = (target_name or "").lower().strip()
    found = []
    
    # 1. Numbered items: '1. Brand' or '1) Brand'
    num_matches = re.findall(r'(?:\d+[\.\)]\s*)([A-Za-z0-9\s&\'\.-]{2,30}?)(?=[·•\|\n,]|\s*\d+[\.\)]|$)', text)
    for m in num_matches:
        cand = m.strip(' .·•-')
        if len(cand) >= 2 and cand.lower() != target_clean:
            found.append(cand)

    # 2. Bullet-delimited items: '· Brand · Brand'
    if not found:
        bullet_matches = re.findall(r'[·•]\s*([A-Za-z0-9\s&\'\.-]{2,30}?)(?=[·•\|\n]|$)', text)
        for m in bullet_matches:
            cand = re.sub(r'^\d+[\.\)]\s*', '', m).strip(' .·•-')
            if len(cand) >= 2 and cand.lower() != target_clean:
                found.append(cand)

    # 3. 'competitors are/include X, Y, Z'
    comp_match = re.search(r'competitors (?:are|include)\s+([^.]+)', text, re.IGNORECASE)
    if comp_match:
        items = re.split(r'[,;]|(?:\band\b)', comp_match.group(1))
        for item in items:
            cand = item.strip(' .·•-')
            if len(cand) >= 2 and cand.lower() != target_clean and not re.search(r'\d+\s+more', cand, re.I):
                found.append(cand)

    # Filter out generic filler phrases
    res = []
    stopwords = {
        'clothing brands', 'summer wardrobe', 'ready to wear', 'full guide', 'top', 
        'lawn collection', 'pakistani brands', 'alternatives', 'competitors', 'companies',
        'solutions', 'services', 'tools', 'platforms'
    }
    for f in found:
        if len(f.split()) > 4:
            continue
        if any(sw in f.lower() for sw in stopwords):
            continue
        if f.lower() not in [x.lower() for x in res]:
            res.append(f)
    return res


async def run_stage_07_extract_candidates(
    search_hits: List[SearchResultItemDTO],
    consensus_scores: Dict[str, int],
    cached_candidates: Optional[List[CompactCandidateCard]] = None,
    target_name: Optional[str] = None,
) -> List[CompactCandidateCard]:
    """Extract unique company candidate cards with verified source URLs and aggregated descriptions."""
    grouped_hits: Dict[str, List[SearchResultItemDTO]] = {}
    
    for hit in search_hits:
        if hit.domain and is_blocklisted_domain(hit.domain):
            continue

        cand_key = get_hit_candidate_key(hit)
        if cand_key not in consensus_scores:
            continue
        grouped_hits.setdefault(cand_key, []).append(hit)

    candidates: List[CompactCandidateCard] = []
    seen_keys = set()
    target_clean = (target_name or "").lower().strip()

    # 1. First, extract direct company domains from search hits (skipping obvious listicle articles)
    for cand_key, hits in grouped_hits.items():
        if cand_key in seen_keys:
            continue
        seen_keys.add(cand_key)

        # Primary hit (prefer ads, then maps, then organic position)
        hits.sort(key=lambda h: (0 if h.is_ad else (1 if h.engine == "google_maps" else 2), h.position))
        best_hit = hits[0]

        # If the page title is an obvious listicle or directory article, do NOT treat the article itself as a company
        if is_listicle_or_article_title(best_hit.title, best_hit.domain):
            continue

        name = clean_brand_name(best_hit.title, best_hit.domain)
        if not name or name.lower() == target_clean:
            continue

        # Combine snippets to form rich description
        snippets = []
        for h in hits:
            if h.snippet and h.snippet not in snippets:
                snippets.append(h.snippet)
        combined_desc = " ".join(snippets)[:500]

        candidates.append(
            CompactCandidateCard(
                name=name,
                domain=best_hit.domain or "maps.google.com",
                description=combined_desc or best_hit.title,
                source_url=best_hit.url,
            )
        )

    # 2. Second, extract individual brand/company competitors mentioned inside comparison & listicle snippets
    for hit in search_hits:
        if not hit.snippet:
            continue
        snippet_entities = extract_entities_from_snippet(hit.snippet, target_name)
        for ent_name in snippet_entities:
            clean_name = ent_name.strip()
            ent_key = re.sub(r"[^a-z0-9]", "", clean_name.lower())
            if ent_key and ent_key not in seen_keys and len(clean_name) >= 3 and clean_name.lower() != target_clean:
                seen_keys.add(ent_key)
                candidates.append(
                    CompactCandidateCard(
                        name=clean_name,
                        domain=f"{ent_key}.com",
                        description=f"Identified as market competitor in verified search results: {hit.snippet[:250]}",
                        source_url=hit.url,
                    )
                )

    # 3. Third, append cached market map candidates ONLY as fallback if live search returned fewer than 15 candidates
    if cached_candidates and len(candidates) < 15:
        for c in cached_candidates:
            c_key = re.sub(r"[^a-z0-9]", "", c.name.lower())
            if c.domain not in seen_keys and c_key not in seen_keys and c.name.lower() != target_clean:
                seen_keys.add(c.domain)
                seen_keys.add(c_key)
                candidates.append(c)

    return candidates
