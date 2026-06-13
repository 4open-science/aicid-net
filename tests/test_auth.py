import pytest
from datetime import UTC, datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_challenge import AuthChallenge


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


@pytest.mark.asyncio
async def test_request_email_login_for_registered_operator(client: AsyncClient):
    await client.post(
        "/register",
        data={
            "agent_name": "MailboxBot",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
        },
        follow_redirects=False,
    )
    resp = await client.post("/auth/email/request", json={"email": "alice@example.com"})
    assert resp.status_code == 202
    data = resp.json()
    assert data["challenge_token"]
    assert data["expires_in_seconds"] > 0


@pytest.mark.asyncio
async def test_verify_email_login_issues_access_token(client: AsyncClient):
    await client.post(
        "/register",
        data={
            "agent_name": "VerifyBot",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
        },
        follow_redirects=False,
    )
    request_resp = await client.post("/auth/email/request", json={"email": "alice@example.com"})
    verify_resp = await client.post(
        "/auth/email/verify",
        json={"token": request_resp.json()["challenge_token"]},
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["access_token"]
    assert data["expires_in_seconds"] > 0


@pytest.mark.asyncio
async def test_email_login_challenge_single_use(client: AsyncClient, issued_challenge: tuple[str, int]):
    token, _challenge_id = issued_challenge
    first = await client.post("/auth/email/verify", json={"token": token})
    second = await client.post("/auth/email/verify", json={"token": token})
    assert first.status_code == 200
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_email_login_challenge_expired(
    client: AsyncClient,
    db_session: AsyncSession,
    issued_challenge: tuple[str, int],
):
    token, challenge_id = issued_challenge
    result = await db_session.execute(select(AuthChallenge).where(AuthChallenge.id == challenge_id))
    challenge = result.scalar_one()
    challenge.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post("/auth/email/verify", json={"token": token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_login_unknown_operator_returns_generic_response(client: AsyncClient):
    resp = await client.post("/auth/email/request", json={"email": "missing@example.com"})
    assert resp.status_code == 202
    data = resp.json()
    assert data["challenge_token"] is None
