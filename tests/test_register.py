import pytest
from httpx import AsyncClient

from app.core.aicid_id import validate_aicid


@pytest.mark.asyncio
async def test_register_form_get(client: AsyncClient):
    resp = await client.get("/register")
    assert resp.status_code == 200
    assert b"Register" in resp.content


@pytest.mark.asyncio
async def test_register_form_post_creates_agent(client: AsyncClient):
    resp = await client.post(
        "/register",
        data={
            "agent_name": "TestBot",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
            "operator_password": "pass1234",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/agents/")
    aicid = location.split("/agents/")[1]
    assert validate_aicid(aicid)


@pytest.mark.asyncio
async def test_register_form_post_wrong_password(client: AsyncClient):
    # First registration creates the account
    await client.post(
        "/register",
        data={
            "agent_name": "Bot1",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
            "operator_password": "correct",
        },
        follow_redirects=False,
    )
    # Second registration with wrong password returns 400
    resp = await client.post(
        "/register",
        data={
            "agent_name": "Bot2",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
            "operator_password": "wrong",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400
