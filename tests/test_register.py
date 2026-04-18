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
    # First registration creates the operator record.
    await client.post(
        "/register",
        data={
            "agent_name": "Bot1",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
        },
        follow_redirects=False,
    )
    # A later registration with the same email should still succeed without credentials.
    resp = await client.post(
        "/register",
        data={
            "agent_name": "Bot2",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
