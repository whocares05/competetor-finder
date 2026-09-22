"""Firecrawl Scraping and Extraction Provider Adapter

Implements BaseFetchProvider for reading, extracting, and verifying candidate web pages.
"""
from typing import Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.config.settings import settings
from app.providers.base import (
    BaseFetchProvider,
    ScrapedDocumentDTO,
    ProviderError,
    QuotaExhaustedError,
)

T = TypeVar("T", bound=BaseModel)


class FirecrawlAdapter(BaseFetchProvider):
    """Live adapter for Firecrawl web scraping and structured extraction endpoints."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FIRECRAWL_API_KEY
        self.base_url = (settings.FIRECRAWL_BASE_URL or "https://api.firecrawl.dev").rstrip("/")

    async def fetch(self, url: str) -> ScrapedDocumentDTO:
        """Scrape webpage content as clean markdown via Firecrawl."""
        if not self.api_key:
            # Fallback to simple HTTP GET if no Firecrawl key
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "CompFinderBot/1.0"})
                    return ScrapedDocumentDTO(
                        url=url,
                        title="",
                        markdown=resp.text[:3000],
                        text=resp.text[:3000],
                        status_code=resp.status_code,
                    )
            except Exception:
                return ScrapedDocumentDTO(url=url, status_code=500, markdown="", text="")

        endpoint = f"{self.base_url}/v1/scrape"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except Exception as e:
                return ScrapedDocumentDTO(url=url, status_code=500, metadata={"error": str(e)})

        if response.status_code == 402 or "Payment Required" in response.text:
            raise QuotaExhaustedError("Firecrawl quota exhausted", provider="firecrawl", status_code=response.status_code)

        if not response.is_success:
            return ScrapedDocumentDTO(url=url, status_code=response.status_code, metadata={"error": response.text})

        data = response.json()
        doc_data = data.get("data", {})
        markdown = doc_data.get("markdown", "")
        metadata = doc_data.get("metadata", {})

        return ScrapedDocumentDTO(
            url=url,
            title=metadata.get("title", ""),
            markdown=markdown,
            text=markdown[:4000],
            status_code=200,
            metadata=metadata,
        )

    async def extract(self, url: str, schema: Type[T]) -> T:
        """Extract structured data conforming to a Pydantic schema using Firecrawl or fallback."""
        doc = await self.fetch(url)
        # In free tier or fallback, doc is parsed via LLM gateway
        from app.providers.llm import create_llm_adapter
        llm = create_llm_adapter()
        parsed, _, _ = await llm.generate_structured(
            prompt=f"Extract company information matching this schema from page text:\n\n{doc.text[:3500]}",
            schema=schema,
        )
        return parsed
