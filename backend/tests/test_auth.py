"""Authentication and Multi-Tenancy Unit Tests"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient):
    """Verify user registration provisions org, credits, and issues valid JWT."""
    # 1. Register
    register_payload = {
        "email": "founder@acme.com",
        "password": "SecurePassword123!",
        "full_name": "Jane Founder",
        "org_name": "Acme Innovations",
    }
    reg_response = await client.post("/api/auth/register", json=register_payload)
    assert reg_response.status_code == 201, reg_response.text
    data = reg_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "founder@acme.com"
    assert data["user"]["active_org"]["name"] == "Acme Innovations"

    token = data["access_token"]

    # 2. Access /api/auth/me with Bearer token
    me_response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == "founder@acme.com"
    assert me_data["active_org"]["slug"] is not None

    # 3. Login with form data
    login_response = await client.post(
        "/api/auth/login",
        data={"username": "founder@acme.com", "password": "SecurePassword123!"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(client: AsyncClient):
    """Verify registration with already existing email raises 400."""
    payload = {
        "email": "duplicate@test.com",
        "password": "Password123!",
    }
    first_res = await client.post("/api/auth/register", json=payload)
    assert first_res.status_code == 201

    second_res = await client.post("/api/auth/register", json=payload)
    assert second_res.status_code == 400
    assert "already exists" in second_res.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_fallback_to_demo(client: AsyncClient):
    """Verify accessing endpoints without token seamlessly resolves to demo user for testing."""
    res = await client.get("/api/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "demo@compfinder.ai"
    assert data["active_org"]["name"] == "Demo Workspace"
