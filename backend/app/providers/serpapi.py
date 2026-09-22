"""SerpAPI Search Provider Adapter

Implements BaseSearchProvider for Google Search and Google Maps live discovery.
Mines organic results, ads, related searches, knowledge graph, and local results.
"""
from typing import List, Optional
from urllib.parse import urlparse
import httpx

from app.config.settings import settings
from app.providers.base import (
    BaseSearchProvider,
    SearchResultItemDTO,
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
)


class SerpAPIAdapter(BaseSearchProvider):
    """Live adapter for SerpAPI discovery engine."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SERPAPI_KEY
        self.base_url = "https://serpapi.com/search"

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract clean domain from URL without www prefix."""
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
        """Execute a live search on Google or Google Maps via SerpAPI."""
        if not self.api_key:
            raise ProviderError("SERPAPI_KEY is not configured", provider="serpapi")

        params = {
            "api_key": self.api_key,
            "engine": engine,
            "q": query,
            "hl": language or "en",
            "num": min(num_results, 20),
        }

        if country_code:
            params["gl"] = country_code.lower()
        if location:
            params["location"] = location

        if engine == "google_maps" and "num" in params:
            del params["num"]

        import asyncio
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get(self.base_url, params=params)
                    if response.status_code == 429 and attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    if response.status_code == 400 and "location" in params:
                        params_retry = params.copy()
                        del params_retry["location"]
                        response = await client.get(self.base_url, params=params_retry)
                    break
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise ProviderError(f"SerpAPI request timed out for query: '{query}'", provider="serpapi")
                    await asyncio.sleep(1.0)
                except Exception as e:
                    raise ProviderError(f"Network error calling SerpAPI: {str(e)}", provider="serpapi")

        if "Your account has run out of searches" in response.text or "Monthly limit reached" in response.text or response.status_code == 403:
            raise QuotaExhaustedError("SerpAPI search quota exhausted: Your account has run out of searches.", provider="serpapi", status_code=response.status_code)
        elif response.status_code == 429:
            raise RateLimitError("SerpAPI rate limit hit", provider="serpapi", status_code=429)

        if not response.is_success:
            raise ProviderError(
                f"SerpAPI returned {response.status_code}: {response.text}",
                provider="serpapi",
                status_code=response.status_code,
            )

        data = response.json()
        results: List[SearchResultItemDTO] = []
        position_counter = 1

        # 1. Mine Ads (Strong signal for category rivals)
        ads = data.get("ads", [])
        for ad in ads:
            ad_url = ad.get("link") or ad.get("tracking_link") or ""
            domain = self._extract_domain(ad_url)
            if domain:
                results.append(
                    SearchResultItemDTO(
                        title=ad.get("title", ""),
                        url=ad_url,
                        snippet=ad.get("description", ""),
                        domain=domain,
                        position=position_counter,
                        engine=engine,
                        is_ad=True,
                        raw_data=ad,
                    )
                )
                position_counter += 1

        # 2. Mine Organic Results
        organic_results = data.get("organic_results", [])
        for item in organic_results:
            url = item.get("link", "")
            domain = self._extract_domain(url)
            if domain:
                snippet = item.get("snippet") or item.get("snippet_highlighted_words") or ""
                if isinstance(snippet, list):
                    snippet = " ".join(snippet)
                results.append(
                    SearchResultItemDTO(
                        title=item.get("title", ""),
                        url=url,
                        snippet=str(snippet),
                        domain=domain,
                        position=position_counter,
                        engine=engine,
                        is_ad=False,
                        raw_data=item,
                    )
                )
                position_counter += 1

        # 3. Mine Local Results (Maps Pack & Google Maps)
        import urllib.parse
        local_results = data.get("local_results", [])
        if isinstance(local_results, dict):
            local_results = local_results.get("places", [])
        for place in local_results:
            links_dict = place.get("links") if isinstance(place.get("links"), dict) else {}
            website = place.get("website") or links_dict.get("website") or place.get("link") or ""
            domain = self._extract_domain(website) if website else ""

            title = place.get("title", "")
            address = place.get("address", "")
            rating = place.get("rating", "")
            reviews = place.get("reviews", "")

            if website and domain:
                place_url = website
            else:
                domain = "maps.google.com"
                place_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(title + ' ' + address)}"

            rating_str = f"Rating: {rating} ({reviews} reviews)." if rating else ""
            desc = f"{place.get('type', 'Local Business')} at {address}. {rating_str} {place.get('description', '')}".strip()

            results.append(
                SearchResultItemDTO(
                    title=title,
                    url=place_url,
                    snippet=desc,
                    domain=domain,
                    position=position_counter,
                    engine="google_maps",
                    is_ad=False,
                    raw_data=place,
                )
            )
            position_counter += 1

        return results
