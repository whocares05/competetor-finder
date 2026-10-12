"""Comprehensive Pipeline Tests: Stage 03, Stage 07, Stage 08 (Verification), Stage 09"""
import pytest
from app.schemas.llm import CompactCandidateCard
from app.pipeline.stage_03_scope_detection import run_stage_03_scope_detection, is_country_level_location
from app.pipeline.stage_05_discovery import format_loc_query, build_discovery_queries, clean_offering_name
from app.pipeline.stage_07_extract_candidates import is_listicle_or_article_title, extract_entities_from_snippet
from app.pipeline.stage_08_verify import run_stage_08_verify, verify_domain_online
from app.pipeline.stage_09_rank import run_stage_09_rank_cheaply


# =====================================================================
# 1. STAGE 08: VERIFICATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_verify_domain_valid():
    """Verify that real, active domains resolve and return True."""
    is_live = await verify_domain_online("google.com")
    assert is_live is True


@pytest.mark.asyncio
async def test_verify_domain_dead():
    """Verify that fake or dead domains are rejected and return False."""
    is_live = await verify_domain_online("fake-nonexistent-domain-xyz-987654321.biz")
    assert is_live is False


@pytest.mark.asyncio
async def test_verify_domain_maps_google():
    """Verify that maps.google.com passes immediately without DNS failure."""
    is_live = await verify_domain_online("maps.google.com")
    assert is_live is True


@pytest.mark.asyncio
async def test_run_stage_08_separation():
    """Verify that run_stage_08_verify separates live domains from dead ones."""
    candidates = [
        CompactCandidateCard(
            name="Google",
            domain="google.com",
            description="Search engine",
            source_url="https://google.com",
        ),
        CompactCandidateCard(
            name="Fake Company",
            domain="fake-dead-domain-12345-xyz.com",
            description="Fake company description",
            source_url="https://fake-dead-domain-12345-xyz.com",
        ),
    ]

    verified, unverified = await run_stage_08_verify(candidates)
    
    assert len(verified) == 1
    assert verified[0].domain == "google.com"
    assert len(unverified) == 1
    assert unverified[0].domain == "fake-dead-domain-12345-xyz.com"


@pytest.mark.asyncio
async def test_run_stage_08_self_exclusion():
    """Verify that the target business canonical domain is excluded from both lists."""
    candidates = [
        CompactCandidateCard(
            name="Khaadi Target",
            domain="khaadi.com",
            description="The target business itself",
            source_url="https://khaadi.com",
        ),
        CompactCandidateCard(
            name="GitHub",
            domain="github.com",
            description="Code hosting",
            source_url="https://github.com",
        ),
    ]

    verified, unverified = await run_stage_08_verify(candidates, excluded_domain="khaadi.com")
    
    # Target business must be completely removed
    assert not any(c.domain == "khaadi.com" for c in verified)
    assert not any(c.domain == "khaadi.com" for c in unverified)
    # Genuine competitor remains
    assert any(c.domain == "github.com" for c in verified)


# =====================================================================
# 2. STAGE 03: SCOPE & COUNTRY RECOGNITION TESTS
# =====================================================================

def test_country_level_detection():
    """Verify country vs city identification."""
    assert is_country_level_location("Pakistan") is True
    assert is_country_level_location("United States") is True
    assert is_country_level_location("UK") is True
    assert is_country_level_location("Lahore") is False
    assert is_country_level_location("Austin") is False
    assert is_country_level_location("Lahore, Pakistan") is False


@pytest.mark.asyncio
async def test_scope_detection_scenarios():
    """Verify scope resolution across national, local, and global archetypes."""
    # Country-wide retail chain
    s1 = await run_stage_03_scope_detection(inferred_scope="national", location="Pakistan")
    assert s1 == "national"

    # Local agency in city
    s2 = await run_stage_03_scope_detection(inferred_scope="local", location="Lahore")
    assert s2 == "local"

    # Global SaaS with no location
    s3 = await run_stage_03_scope_detection(inferred_scope="global", location=None)
    assert s3 == "global"

    # Explicit user override
    s4 = await run_stage_03_scope_detection(inferred_scope="national", scope_override="local", location="Pakistan")
    assert s4 == "local"


# =====================================================================
# 3. STAGE 05: QUERY DEDUPLICATION TESTS
# =====================================================================

def test_format_loc_query():
    """Verify that queries don't duplicate the location string."""
    q1 = format_loc_query("women clothing brands Pakistan", "Pakistan")
    assert q1 == "women clothing brands Pakistan"

    q2 = format_loc_query("brands like Khaadi", "Pakistan")
    assert q2 == "brands like Khaadi in Pakistan"


def test_niche_offering_queries_national():
    """Verify that national scope injects granular offerings into top query slots."""
    queries = build_discovery_queries(
        business_name="Khaadi",
        keywords=["clothing", "women apparel"],
        scope="national",
        location="Pakistan",
        offerings=["Unstitched Lawn", "Ready-to-Wear Pret"],
    )
    query_texts = [q[0] for q in queries]
    
    # Query 1: Peer brand comparison
    assert 'brands like "Khaadi" in Pakistan' in query_texts[0]
    # Query 2: Niche Offering #1
    assert 'top "Unstitched Lawn" brands in Pakistan' in query_texts[1]
    # Query 3: Niche Offering #2
    assert 'best "Ready-to-Wear Pret" brands in Pakistan' in query_texts[2]


def test_niche_offering_queries_global():
    """Verify that global scope injects granular offerings into software/tools queries."""
    queries = build_discovery_queries(
        business_name="Figma",
        keywords=["design software"],
        scope="global",
        location=None,
        offerings=["Collaborative Vector UI Design", "Interactive Prototyping"],
    )
    query_texts = [q[0] for q in queries]

    assert '"Figma" alternatives' in query_texts[0]
    assert 'best "Collaborative Vector UI Design" software' in query_texts[1]
    assert 'top "Interactive Prototyping" tools' in query_texts[2]


def test_niche_offering_queries_local():
    """Verify that local scope injects primary offering into Google search while keeping Google Maps intact."""
    queries = build_discovery_queries(
        business_name="Databiqs",
        keywords=["software house", "software development"],
        scope="local",
        location="Lahore",
        offerings=["Custom Web Development", "Enterprise AI Solutions"],
    )
    
    # Query 1 must be Google Maps for city places
    assert queries[0][1] == "google_maps"
    assert "in Lahore" in queries[0][0]

    # Query 2 must be Google Web targeting the niche offering
    assert queries[1][1] == "google"
    assert "best Custom Web Development in Lahore" in queries[1][0]


def test_niche_offering_queries_fallback_when_empty():
    """Verify backwards compatibility: when offerings are empty, standard queries are used."""
    queries = build_discovery_queries(
        business_name="Acme",
        keywords=["widgets", "gadgets"],
        scope="national",
        location="USA",
        offerings=[],
    )
    query_texts = [q[0] for q in queries]

    assert 'brands like "Acme" in USA' in query_texts[0]
    assert 'top gadgets in USA' in query_texts[1]



# =====================================================================
# 4. STAGE 07: CANDIDATE EXTRACTION & LISTICLE FILTERING TESTS
# =====================================================================

def test_listicle_filtering():
    """Verify that blog article titles are not treated as company names."""
    assert is_listicle_or_article_title("10 Clothing Brands in Karachi", "cocoon.pk") is True
    assert is_listicle_or_article_title("Top 20 Pakistani Women's Brands", "iqrafch.com") is True
    assert is_listicle_or_article_title("9 Best Pakistani Clothing Brands", "stringnthread.com") is True
    # Real brand homepages are NOT listicles
    assert is_listicle_or_article_title("Sana Safinaz Official", "sanasafinaz.com") is False
    assert is_listicle_or_article_title("Gul Ahmed Online Store", "gulahmed.com") is False


def test_snippet_entity_extraction():
    """Verify that candidate brand names are cleanly extracted from listicle snippets."""
    snippet = "9 Best Pakistani Clothing Brands: 1. Maria B · 2. Khaadi · 3. Gul Ahmed · 4. Sapphire · 5. Sana Safinaz"
    extracted = extract_entities_from_snippet(snippet, target_name="Khaadi")
    
    assert "Maria B" in extracted
    assert "Gul Ahmed" in extracted
    assert "Sapphire" in extracted
    assert "Sana Safinaz" in extracted
    # Target name must be excluded
    assert "Khaadi" not in extracted


# =====================================================================
# 5. STAGE 09: CANDIDATE PRE-RANKING & NON-STARVATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_stage_09_non_starvation():
    """Verify that Stage 09 preserves up to 30 candidates and does not starve the Judge."""
    test_candidates = [
        CompactCandidateCard(
            name=f"Brand {i}",
            domain=f"brand{i}.com",
            description=f"Identified as market competitor in verified search results: Fashion brand {i}",
            source_url=f"https://brand{i}.com",
        )
        for i in range(25)
    ]
    scores = {f"brand{i}.com": 1 for i in range(25)}

    finalists = await run_stage_09_rank_cheaply(
        candidates=test_candidates,
        consensus_scores=scores,
        target_count=5,
        business_type="fashion retail",
    )

    # When 25 candidates exist, Stage 09 should pass all 25 without starving the Judge
    assert len(finalists) == 25


# =====================================================================
# 6. ENHANCED SNIPPET & KNOWLEDGE GRAPH RETENTION TESTS
# =====================================================================

def test_broadened_snippet_entity_patterns():
    """Verify colon-delimited and competition-from phrasing in snippets."""
    s1 = "Discover the top Apple competitors: Samsung, Google, Huawei, Microsoft, Xiaomi, and more."
    e1 = extract_entities_from_snippet(s1, target_name="Apple")
    assert "Samsung" in e1
    assert "Google" in e1
    assert "Huawei" in e1
    assert "Microsoft" in e1

    s2 = "Apple faces fierce competition from Samsung, Microsoft, and Google in hardware."
    e2 = extract_entities_from_snippet(s2, target_name="Apple")
    assert "Samsung" in e2
    assert "Microsoft" in e2
    assert "Google" in e2


@pytest.mark.asyncio
async def test_synthetic_domain_retention_in_stage_08():
    """Verify that synthetic domain entities (from snippets/KG) are not dropped if synthetic .com fails DNS."""
    from app.pipeline.stage_08_verify import run_stage_08_verify

    candidates = [
        # Real organic crawled domain that does not exist -> must be rejected
        CompactCandidateCard(
            name="Fake Corp",
            domain="thisshouldneverexist123456789nonexistent.com",
            description="Organic search result",
            source_url="https://thisshouldneverexist123456789nonexistent.com",
            is_synthetic_domain=False,
        ),
        # Snippet/KG extracted entity with synthetic domain -> must be retained
        CompactCandidateCard(
            name="Google Pixel",
            domain="googlepixel.com",
            description="Hardware mobile division",
            source_url="https://en.wikipedia.org/wiki/Smartphone",
            is_synthetic_domain=True,
        ),
    ]

    verified, unverified = await run_stage_08_verify(candidates)
    verified_names = [c.name for c in verified]
    unverified_names = [c.name for c in unverified]

    assert "Google Pixel" in verified_names
    assert "Fake Corp" in unverified_names


# =====================================================================
# 7. CANONICAL DOMAIN RESOLUTION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_canonical_domain_resolution_from_kg_website():
    """Verify that Knowledge Graph entities with official websites resolve to authentic canonical domains."""
    from app.providers.base import SearchResultItemDTO
    from app.pipeline.stage_07_extract_candidates import run_stage_07_extract_candidates

    hits = [
        SearchResultItemDTO(
            title="Samsung Electronics",
            url="https://www.samsung.com",
            snippet="Official verified entity from Google Knowledge Graph: Samsung Electronics",
            domain="samsung.com",
            position=1,
            engine="knowledge_graph",
            is_ad=False,
        )
    ]
    scores = {"samsung.com": 3}

    candidates = await run_stage_07_extract_candidates(
        search_hits=hits,
        consensus_scores=scores,
        target_name="Apple",
    )

    samsung_card = next((c for c in candidates if "samsung" in c.name.lower()), None)
    assert samsung_card is not None
    assert samsung_card.domain == "samsung.com"
    assert samsung_card.source_url == "https://www.samsung.com"
    assert samsung_card.is_synthetic_domain is False


@pytest.mark.asyncio
async def test_canonical_domain_resolution_for_snippet_entities():
    """Verify that entities extracted from snippets resolve to discovered authentic domains rather than synthetic guesses."""
    from app.providers.base import SearchResultItemDTO
    from app.pipeline.stage_07_extract_candidates import run_stage_07_extract_candidates

    hits = [
        # Discovered organic corporate website
        SearchResultItemDTO(
            title="Samsung US | Mobile | TV | Home Electronics",
            url="https://www.samsung.com/us/",
            snippet="Samsung official website",
            domain="samsung.com",
            position=1,
            engine="google",
            is_ad=False,
        ),
        # Tech review listicle mentioning the entity
        SearchResultItemDTO(
            title="Top Smartphone Brands Overview",
            url="https://techreviewblog.com/smartphones",
            snippet="Apple's chief competitors include Samsung Electronics, Sony, and Google in mobile hardware.",
            domain="techreviewblog.com",
            position=2,
            engine="google",
            is_ad=False,
        ),
    ]
    scores = {"samsung.com": 2, "techreviewblog.com": 1}

    candidates = await run_stage_07_extract_candidates(
        search_hits=hits,
        consensus_scores=scores,
        target_name="Apple",
    )

    samsung_cands = [c for c in candidates if "samsung" in c.name.lower()]
    assert len(samsung_cands) >= 1
    # Canonical domain must be samsung.com, not samsungelectronics.com
    assert samsung_cands[0].domain == "samsung.com"
    assert samsung_cands[0].is_synthetic_domain is False


@pytest.mark.asyncio
async def test_canonical_domain_resolution_fallback_to_synthetic():
    """Verify that when no authentic corporate domain is discovered, the entity retains a synthetic fallback domain."""
    from app.providers.base import SearchResultItemDTO
    from app.pipeline.stage_07_extract_candidates import run_stage_07_extract_candidates

    hits = [
        SearchResultItemDTO(
            title="Niche Fashion Roundups",
            url="https://fashionblog.com/roundup",
            snippet="Top boutique rivals include RareBoutiqueXYZ in handcrafted pret.",
            domain="fashionblog.com",
            position=1,
            engine="google",
            is_ad=False,
        )
    ]
    scores = {"fashionblog.com": 1}

    candidates = await run_stage_07_extract_candidates(
        search_hits=hits,
        consensus_scores=scores,
        target_name="Khaadi",
    )

    rare_card = next((c for c in candidates if "rareboutiquexyz" in c.domain.lower()), None)
    assert rare_card is not None
    assert rare_card.domain == "rareboutiquexyz.com"
    assert rare_card.is_synthetic_domain is True

