"""Search Endpoint Tests"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_search_unauthenticated(client: AsyncClient):
    """Verify POST /api/search works without signing in (using demo workspace)."""
    payload = {
        "query": "Linear",
        "location": "San Francisco",
        "num_competitors": 5,
        "scope_override": "global",
        "competitor_types": ["direct", "indirect"],
    }
    response = await client.post("/api/search", json=payload)
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["query"] == "Linear"
    assert data["status"] == "queued"
    assert data["num_competitors"] == 5
    assert data["tier"] == "free"
    assert "id" in data
    assert data["results"] == []


@pytest.mark.asyncio
async def test_create_search_exceeds_tier_max(client: AsyncClient):
    """Verify requesting more competitors than allowed by tier returns 400."""
    payload = {
        "query": "Acme",
        "num_competitors": 45,  # Free tier max is 10
    }
    response = await client.post("/api/search", json=payload)
    assert response.status_code == 400
    assert "exceeds free tier limit" in response.json()["detail"]
