"""Agent self-registration and the human claim flow."""

import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.models.user import User


@pytest.fixture
def mails(monkeypatch):
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr("app.routers.self_register.send_email", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


async def _register(client: AsyncClient, **extra):
    resp = await client.post("/api/register", json={"name": "SelfBot", **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_self_registration_publishes_immediately_without_auth(client: AsyncClient, mails):
    data = await _register(client, operator_telegram="@jane", operator_x="@jane_x", operator_email="jane@example.org")
    assert data["agent_secret"]
    page = await client.get(f"/agents/{data['aicid']}")
    assert page.status_code == 200
    assert "Self-registered · unclaimed" in page.text
    assert "Verified operator" not in page.text
    public = (await client.get(f"/agents/{data['aicid']}/json")).json()
    assert public["registration_source"] == "self"
    assert public["claimed"] is False
    assert public["operator_telegram"] == "@jane"
    assert public["operator_x"] == "@jane_x"
    assert "jane@example.org" not in str(public)
    assert data["agent_secret"] not in str(public)
    assert any(subject.startswith("New self-registration") for _, subject, _ in mails)


@pytest.mark.asyncio
async def test_self_registered_agent_is_searchable(client: AsyncClient, mails):
    await _register(client, name="FindableSelfBot")
    results = (await client.get("/search", params={"q": "FindableSelfBot"})).json()
    assert [r["name"] for r in results] == ["FindableSelfBot"]
    assert results[0]["registration_source"] == "self"


@pytest.mark.asyncio
async def test_operator_registration_has_no_self_badge(client: AsyncClient, auth_headers, mails):
    created = await client.post(
        "/api/agents", headers=auth_headers, json={"name": "OpBot", "human_operator": "Test User"}
    )
    page = await client.get(f"/agents/{created.json()['aicid']}")
    assert "Self-registered" not in page.text
    assert (await client.get(f"/agents/{created.json()['aicid']}/json")).json()["registration_source"] == "operator"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"name": "+ 2 BTC. WITHDRAW ▶ https://search.app/fZYLr"},
        {"name": "Bot", "description": "visit graph.org/Sofia-10-03-6 now"},
        {"name": "Bot", "operator_x": "https://evil.example/x"},
        {"name": "Bot", "operator_email": "x@maxxspace.com"},
    ],
)
async def test_spam_rules_apply_to_self_registration(client: AsyncClient, db_session: AsyncSession, mails, payload):
    resp = await client.post("/api/register", json=payload)
    assert resp.status_code == 422
    assert (await db_session.execute(select(Agent))).first() is None


@pytest.mark.asyncio
async def test_name_is_required(client: AsyncClient):
    assert (await client.post("/api/register", json={})).status_code == 422


@pytest.mark.asyncio
async def test_self_registration_rate_limit(client: AsyncClient, mails, monkeypatch):
    monkeypatch.setattr(settings, "SELF_REGISTRATION_LIMIT_PER_HOUR", 2)
    await _register(client)
    await _register(client)
    assert (await client.post("/api/register", json={"name": "Third"})).status_code == 429


@pytest.mark.asyncio
async def test_unclaimed_owner_cannot_log_in(client: AsyncClient, db_session: AsyncSession, mails):
    await _register(client)
    owner = (await db_session.execute(select(User).where(User.email == "unclaimed@aicid.invalid"))).scalar_one()
    assert owner.is_active is False
    resp = await client.post("/auth/email/request", json={"email": owner.email})
    assert "challenge_token" not in resp.json() or resp.status_code >= 400


def _auth(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


@pytest.mark.asyncio
async def test_claim_request_needs_the_agent_secret(client: AsyncClient, mails):
    data = await _register(client, operator_email="jane@example.org")
    url = f"/api/agents/{data['aicid']}/claim"
    assert (await client.post(url, json={})).status_code == 403
    assert (await client.post(url, json={}, headers=_auth("wrong"))).status_code == 403
    unknown = "/api/agents/AICID-0000-0000-0000-0000/claim"
    assert (await client.post(unknown, json={}, headers=_auth(data["agent_secret"]))).status_code == 403
    assert not [m for m in mails if m[1].startswith("Claim")]


@pytest.mark.asyncio
async def test_claim_requires_an_email(client: AsyncClient, mails):
    data = await _register(client)
    resp = await client.post(f"/api/agents/{data['aicid']}/claim", json={}, headers=_auth(data["agent_secret"]))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_full_claim_flow_new_operator(client: AsyncClient, db_session: AsyncSession, mails):
    data = await _register(client, human_operator="Declared Name", operator_email="jane@example.org")
    aicid = data["aicid"]
    resp = await client.post(f"/api/agents/{aicid}/claim", json={}, headers=_auth(data["agent_secret"]))
    assert resp.status_code == 202
    to, subject, body = next(m for m in mails if m[1].startswith("Claim"))
    assert to == "jane@example.org"
    assert "SelfBot" not in body  # no agent-supplied text in the mail
    link = re.search(r"/claim/(AICID-[\dX-]+)\?token=([\w-]+)", body)
    assert link and link.group(1) == aicid

    page = await client.get(f"/claim/{aicid}", params={"token": link.group(2)})
    assert page.status_code == 200 and "jane@example.org" in page.text
    # still unclaimed: a GET (mail scanner) must not consume the link
    assert "Self-registered · unclaimed" in (await client.get(f"/agents/{aicid}")).text

    no_name = await client.post(f"/claim/{aicid}", data={"token": link.group(2)})
    assert no_name.status_code == 422

    done = await client.post(
        f"/claim/{aicid}", data={"token": link.group(2), "full_name": "Jane Roe"}, follow_redirects=False
    )
    assert done.status_code == 303 and done.headers["location"] == f"/agents/{aicid}"
    assert settings.SESSION_COOKIE_NAME in done.headers["set-cookie"]

    profile = await client.get(f"/agents/{aicid}")
    assert "Verified operator" in profile.text and "Self-registered" in profile.text
    assert "Self-registered · unclaimed" not in profile.text
    public = (await client.get(f"/agents/{aicid}/json")).json()
    assert public["claimed"] is True and public["human_operator"] == "Jane Roe"

    agent = (await db_session.execute(select(Agent).where(Agent.aicid == aicid))).scalar_one()
    owner = (await db_session.execute(select(User).where(User.id == agent.owner_id))).scalar_one()
    assert owner.email == "jane@example.org" and agent.agent_secret_hash is None

    # the link and the secret are dead afterwards
    again = await client.post(f"/claim/{aicid}", data={"token": link.group(2), "full_name": "Eve"})
    assert again.status_code == 401
    after = await client.post(f"/api/agents/{aicid}/claim", json={}, headers=_auth(data["agent_secret"]))
    assert after.status_code == 403


@pytest.mark.asyncio
async def test_claim_by_existing_operator_keeps_their_name(client: AsyncClient, mails):
    await client.post(
        "/register",
        data={"agent_name": "First", "human_operator": "Existing Person", "operator_email": "ex@example.org"},
    )
    data = await _register(client)
    await client.post(
        f"/api/agents/{data['aicid']}/claim",
        json={"operator_email": "ex@example.org"},
        headers=_auth(data["agent_secret"]),
    )
    token = re.search(r"token=([\w-]+)", next(m[2] for m in mails if m[1].startswith("Claim"))).group(1)
    done = await client.post(f"/claim/{data['aicid']}", data={"token": token}, follow_redirects=False)
    assert done.status_code == 303
    assert (await client.get(f"/agents/{data['aicid']}/json")).json()["human_operator"] == "Existing Person"


@pytest.mark.asyncio
async def test_claim_link_is_bound_to_its_agent(client: AsyncClient, mails):
    a = await _register(client, operator_email="a@example.org")
    b = await _register(client, name="Other", operator_email="b@example.org")
    await client.post(f"/api/agents/{a['aicid']}/claim", json={}, headers=_auth(a["agent_secret"]))
    token = re.search(r"token=([\w-]+)", next(m[2] for m in mails if m[1].startswith("Claim"))).group(1)
    resp = await client.post(f"/claim/{b['aicid']}", data={"token": token, "full_name": "Eve"})
    assert resp.status_code == 401
    assert (await client.get(f"/agents/{b['aicid']}/json")).json()["claimed"] is False


@pytest.mark.asyncio
async def test_claim_email_is_rate_limited(client: AsyncClient, mails):
    data = await _register(client, operator_email="jane@example.org")
    url = f"/api/agents/{data['aicid']}/claim"
    assert (await client.post(url, json={}, headers=_auth(data["agent_secret"]))).status_code == 202
    assert (await client.post(url, json={}, headers=_auth(data["agent_secret"]))).status_code == 429
    assert len([m for m in mails if m[1].startswith("Claim")]) == 1


@pytest.mark.asyncio
async def test_expired_claim_link_rejected(client: AsyncClient, mails, monkeypatch):
    monkeypatch.setattr(settings, "CLAIM_EXPIRE_MINUTES", -1)
    data = await _register(client, operator_email="jane@example.org")
    await client.post(f"/api/agents/{data['aicid']}/claim", json={}, headers=_auth(data["agent_secret"]))
    token = re.search(r"token=([\w-]+)", next(m[2] for m in mails if m[1].startswith("Claim"))).group(1)
    resp = await client.post(f"/claim/{data['aicid']}", data={"token": token, "full_name": "Jane"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_operator_registered_agent_cannot_be_claimed(client: AsyncClient, auth_headers, mails):
    created = (await client.post("/api/agents", headers=auth_headers, json={"name": "Op", "human_operator": "T"})).json()
    resp = await client.post(
        f"/api/agents/{created['aicid']}/claim", json={"operator_email": "x@example.org"}, headers=_auth("anything")
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_docs_page_renders_skill_md(client: AsyncClient):
    page = await client.get("/docs")
    assert page.status_code == 200
    assert "POST /api/register" in page.text  # fenced block rendered from docs/SKILL.md
    assert "```" not in page.text
    assert 'href="#self-registration-fully-autonomous"' in page.text  # nav entry built from its headings
    assert 'id="self-registration-fully-autonomous"' in page.text
