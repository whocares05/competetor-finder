"""Pipeline Stage 02: Entity Resolution (Identify searched business domain to strictly exclude it)"""
from typing import Optional, List
from urllib.parse import urlparse
import re


def normalize_domain(url_or_domain: str) -> str:
    """Extract clean domain without www. or protocol."""
    s = url_or_domain.strip().lower()
    if s.startswith("http://") or s.startswith("https://"):
        try:
            netloc = urlparse(s).netloc
            s = netloc
        except Exception:
            pass
    if s.startswith("www."):
        s = s[4:]
    return s.split("/")[0].split(":")[0].strip()


async def run_stage_02_entity_resolution(
    profile_name: Optional[str],
    query: str,
    top_search_hits: Optional[List[str]] = None,
) -> tuple[Optional[str], List[str]]:
    """Resolve the searched business's own domain and aliases so we never return self-as-competitor."""
    # 1. Direct URL check in query
    if "http" in query or (".com" in query or ".app" in query or ".io" in query or ".co" in query):
        tokens = query.split()
        for tok in tokens:
            if "." in tok:
                domain = normalize_domain(tok)
                return domain, [domain, domain.split(".")[0]]

    # 2. Check profile name
    aliases = []
    if profile_name:
        clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", profile_name.lower()).strip()
        aliases.append(clean_name)
        # Probable domain heuristics
        probable_domain = clean_name.replace(" ", "") + ".com"
        probable_app = clean_name.replace(" ", "") + ".app"
        aliases.extend([probable_domain, probable_app])
        
        # If top search hits provided, the first hit for the brand name is usually self
        if top_search_hits:
            for hit_url in top_search_hits[:2]:
                hit_dom = normalize_domain(hit_url)
                if clean_name.replace(" ", "") in hit_dom:
                    return hit_dom, aliases + [hit_dom]

        return clean_name.replace(" ", ""), aliases

    return None, aliases
