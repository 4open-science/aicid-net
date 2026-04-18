import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "pass1234", "full_name": "Alice"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_accepts_operator_password(client: AsyncClient):
    resp = await client.post(
        "/auth/register",
        json={"email": "alias@example.com", "operator_password": "pass1234", "full_name": "Alias"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alias@example.com"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "pass1234", "full_name": "Dup"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "pass1234", "full_name": "Bob"},
    )
    resp = await client.post(
        "/auth/token",
        data={"username": "bob@example.com", "password": "pass1234"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": "correct", "full_name": "Carol"},
    )
    resp = await client.post(
        "/auth/token",
        data={"username": "carol@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"
