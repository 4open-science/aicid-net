import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_manage_requires_browser_session(client: AsyncClient):
    resp = await client.get("/manage", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/auth/login")


@pytest.mark.asyncio
async def test_browser_login_page_get(client: AsyncClient):
    resp = await client.get("/auth/login")
    assert resp.status_code == 200
    assert b"Manage your AICID profiles" in resp.content


@pytest.mark.asyncio
async def test_browser_verify_link_sets_session_cookie_and_allows_manage(client: AsyncClient):
    register_resp = await client.post(
        "/register",
        data={
            "agent_name": "CookieBot",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
        },
        follow_redirects=False,
    )
    aicid = register_resp.headers["location"].split("/agents/")[1]

    request_resp = await client.post(
        "/auth/browser/request",
        data={"email": "alice@example.com", "next": "/manage"},
    )
    assert request_resp.status_code == 202
    assert b"Development code:" in request_resp.content
    token = request_resp.text.split("Development code: <code>")[1].split("</code>")[0]

    verify_resp = await client.get(f"/auth/verify?token={token}&next=/manage", follow_redirects=False)
    assert verify_resp.status_code == 303
    assert verify_resp.headers["location"] == "/manage"
    set_cookie = verify_resp.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie

    manage_resp = await client.get("/manage")
    assert manage_resp.status_code == 200
    assert aicid.encode() in manage_resp.content
    assert b"CookieBot" in manage_resp.content


@pytest.mark.asyncio
async def test_browser_manage_updates_public_registered_agent(client: AsyncClient):
    register_resp = await client.post(
        "/register",
        data={
            "agent_name": "EditBot",
            "human_operator": "Alice",
            "operator_email": "alice@example.com",
        },
        follow_redirects=False,
    )
    aicid = register_resp.headers["location"].split("/agents/")[1]

    request_resp = await client.post(
        "/auth/browser/request",
        data={"email": "alice@example.com", "next": "/manage"},
    )
    assert request_resp.status_code == 202
    token = request_resp.text.split("Development code: <code>")[1].split("</code>")[0]
    verify_resp = await client.post(
        "/auth/browser/verify",
        data={"token": token, "next": "/manage"},
        follow_redirects=False,
    )
    assert verify_resp.status_code == 303

    update_resp = await client.post(
        f"/manage/agents/{aicid}",
        data={
            "name": "EditBot 2",
            "human_operator": "Alice Example",
            "agent_harness": "Claude Code",
            "agent_type": "co_scientist",
            "base_model": "gpt-4o",
            "version": "2026-06",
            "organization": "Open Science Lab",
            "description": "Updated from the browser.",
            "keywords": "science,automation",
            "website_url": "https://example.com",
            "github_url": "https://github.com/example/repo",
            "paper_url": "https://example.com/paper",
            "visibility": "limited",
        },
        follow_redirects=False,
    )
    assert update_resp.status_code == 303
    assert update_resp.headers["location"] == f"/manage?updated={aicid}"

    public_resp = await client.get(f"/agents/{aicid}/json")
    assert public_resp.status_code == 200
    data = public_resp.json()
    assert data["name"] == "EditBot 2"
    assert data["human_operator"] == "Alice Example"
    assert data["agent_type"] == "co_scientist"
    assert data["organization"] == "Open Science Lab"
    assert data["description"] == "Updated from the browser."
    assert data["visibility"] == "limited"
