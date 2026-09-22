"""Fallback Search Provider Adapter (DuckDuckGo HTML / Instant Answers)

Implements BaseSearchProvider to act as automatic zero-cost failover when SerpAPI is exhausted.
"""
import re
from typing import List, Optional
from urllib.parse import unquote, urlparse
import httpx
from app.config.settings import settings
from app.providers.base import (
    BaseSearchProvider,
    SearchResultItemDTO,
)


class FallbackSearchAdapter(BaseSearchProvider):
    """Fallback search provider adapter using DuckDuckGo HTML endpoint."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FALLBACK_SEARCH_API_KEY
        self.base_url = "https://html.duckduckgo.com/html/"

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            netloc = urlparse(url).netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    async def search(
        self,
        query: str,
        engine: str = "google",
        location: Optional[str] = None,
        country_code: Optional[str] = None,
        language: str = "en",
        num_results: int = 10,
    ) -> List[SearchResultItemDTO]:
        """Execute fallback search via DuckDuckGo HTML."""
        full_query = query
        if location and location not in query:
            full_query = f"{query} in {location}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.post(self.base_url, data={"q": full_query}, headers=headers)
                if resp.status_code != 200:
                    return []

                html = resp.text
                results: List[SearchResultItemDTO] = []
                
                # Simple regex parser for DDG HTML results: <a class="result__url" href="...uddg=...
                # Each result is inside class="result ...
                result_blocks = re.findall(r'<div class="result results_links[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
                
                pos = 1
                for block in result_blocks[:num_results]:
                    # Extract title
                    title_match = re.search(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
                    link_match = re.search(r'href="([^"]*uddg=([^"&]*))"', block)
                    snippet_match = re.search(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
                    title_elem = re.search(r'<a class="result__url"[^>]*>(.*?)</a>', block, re.DOTALL)

                    if link_match:
                        raw_url = link_match.group(2)
                        url = unquote(raw_url)
                        domain = self._extract_domain(url)
                        if domain:
                            title = re.sub(r'<[^>]+>', '', title_elem.group(1)).strip() if title_elem else domain
                            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                            results.append(
                                SearchResultItemDTO(
                                    title=title,
                                    url=url,
                                    snippet=snippet,
                                    domain=domain,
                                    position=pos,
                                    engine="fallback",
                                    is_ad=False,
                                )
                            )
                            pos += 1

                return results
        except Exception:
            return []
