"""Pipeline Stage 07: Candidate Extraction from titles, snippets, and verified hits"""
import re
from typing import List, Dict, Optional, Tuple
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

    # 3. Competitor list patterns in text (e.g. 'competitors include X, Y', 'competitors: X, Y', 'rivals include X, Y', 'competition from X, Y')
    comp_matches = re.finditer(
        r'(?:competitors|rivals|alternatives|peers)(?:\s+(?:are|include)|:)\s+([^.\n]+)',
        text,
        re.IGNORECASE
    )
    for cm in comp_matches:
        items = re.split(r'[,;]|(?:\band\b)', cm.group(1))
        for item in items:
            cand = re.sub(r'\s+(?:in|for|across|such as|including|and more)\b.*$', '', item, flags=re.I).strip(' .·•-')
            if len(cand) >= 2 and cand.lower() != target_clean and not re.search(r'\d+\s+more', cand, re.I):
                found.append(cand)

    comp_from_matches = re.finditer(
        r'(?:competition from|competes with)\s+([^.\n]+)',
        text,
        re.IGNORECASE
    )
    for cm in comp_from_matches:
        items = re.split(r'[,;]|(?:\band\b)', cm.group(1))
        for item in items:
            cand = re.sub(r'\s+(?:in|for|across|such as|including|and more)\b.*$', '', item, flags=re.I).strip(' .·•-')
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

def resolve_canonical_domain(
    name: str,
    hit_domain: Optional[str],
    hit_url: Optional[str],
    canonical_domain_map: Dict[str, Tuple[str, str]],
) -> Tuple[str, str, bool]:
    """
    Resolve authentic, canonical corporate domain and URL for a candidate entity.
    Returns: (domain, source_url, is_synthetic_domain)
    """
    # 1. If hit already carries a verified authentic domain (e.g. from Knowledge Graph website or organic search)
    if hit_domain and hit_domain not in ("knowledge_graph", "maps.google.com") and not is_blocklisted_domain(hit_domain):
        clean_d = hit_domain.lower().strip()
        return clean_d, hit_url or f"https://{clean_d}", False

    ent_key = re.sub(r"[^a-z0-9]", "", name.lower())

    # 2. Exact match in canonical domain map
    if ent_key in canonical_domain_map:
        d, u = canonical_domain_map[ent_key]
        return d, u, False

    # 3. Match individual significant word tokens (e.g. "Samsung" from "Samsung Electronics")
    words = re.findall(r"[a-z0-9]+", name.lower())
    for w in words:
        if len(w) >= 3 and w in canonical_domain_map:
            d, u = canonical_domain_map[w]
            return d, u, False

    # 4. Match substring/stem in canonical domain map (e.g. known domain stem "samsung" in "samsungelectronics")
    for known_key, (d, u) in canonical_domain_map.items():
        if len(known_key) >= 3 and (known_key in ent_key or ent_key in known_key):
            return d, u, False

    # 5. Fallback: synthesize domain from entity key
    return f"{ent_key}.com", hit_url or f"https://{ent_key}.com", True


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

    # Build canonical domain map from verified organic hits and Knowledge Graph hits
    canonical_domain_map: Dict[str, Tuple[str, str]] = {}
    for hit in search_hits:
        if not hit.domain or is_blocklisted_domain(hit.domain) or hit.domain in ("knowledge_graph", "maps.google.com"):
            continue
        clean_d = hit.domain.lower().strip()
        stem = clean_d.split(".")[0]
        url = hit.url or f"https://{clean_d}"
        if stem and len(stem) >= 2 and stem != target_clean:
            canonical_domain_map.setdefault(stem, (clean_d, url))

        hit_brand = clean_brand_name(hit.title, hit.domain)
        hit_brand_key = re.sub(r"[^a-z0-9]", "", hit_brand.lower())
        if hit_brand_key and len(hit_brand_key) >= 2 and hit_brand_key != target_clean:
            canonical_domain_map.setdefault(hit_brand_key, (clean_d, url))

        if hit.engine == "knowledge_graph" and hit.title:
            kg_key = re.sub(r"[^a-z0-9]", "", hit.title.lower())
            if kg_key and kg_key != target_clean:
                canonical_domain_map[kg_key] = (clean_d, url)

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

        name_key = re.sub(r"[^a-z0-9]", "", name.lower())
        if name_key:
            seen_keys.add(name_key)
        if best_hit.domain:
            seen_keys.add(best_hit.domain.lower())

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

    # 2. Second, extract Knowledge Graph entities and brand/company competitors mentioned in snippets
    for hit in search_hits:
        # Knowledge Graph & People Also Search For entities
        if hit.engine == "knowledge_graph":
            clean_name = hit.title.strip()
            ent_key = re.sub(r"[^a-z0-9]", "", clean_name.lower())
            if ent_key and len(clean_name) >= 2 and clean_name.lower() != target_clean:
                domain, source_url, is_synth = resolve_canonical_domain(
                    name=clean_name,
                    hit_domain=hit.domain if hit.domain != "knowledge_graph" else None,
                    hit_url=hit.url,
                    canonical_domain_map=canonical_domain_map,
                )
                if ent_key not in seen_keys and domain not in seen_keys:
                    seen_keys.add(ent_key)
                    seen_keys.add(domain)
                    candidates.append(
                        CompactCandidateCard(
                            name=clean_name,
                            domain=domain,
                            description=f"Identified by Google Knowledge Graph as market competitor: {hit.snippet[:250]}",
                            source_url=source_url,
                            is_synthetic_domain=is_synth,
                        )
                    )
            continue

        if not hit.snippet:
            continue
        snippet_entities = extract_entities_from_snippet(hit.snippet, target_name)
        for ent_name in snippet_entities:
            clean_name = ent_name.strip()
            ent_key = re.sub(r"[^a-z0-9]", "", clean_name.lower())
            if ent_key and len(clean_name) >= 3 and clean_name.lower() != target_clean:
                domain, source_url, is_synth = resolve_canonical_domain(
                    name=clean_name,
                    hit_domain=None,
                    hit_url=hit.url,
                    canonical_domain_map=canonical_domain_map,
                )
                if ent_key not in seen_keys and domain not in seen_keys:
                    seen_keys.add(ent_key)
                    seen_keys.add(domain)
                    candidates.append(
                        CompactCandidateCard(
                            name=clean_name,
                            domain=domain,
                            description=f"Identified as market competitor in verified search results: {hit.snippet[:250]}",
                            source_url=source_url,
                            is_synthetic_domain=is_synth,
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

