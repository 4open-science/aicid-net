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
    assert owner.email == "jane@example.org" and agent.agent_secret_hash is not None

    # the link is dead afterwards, and an agent cannot start a second claim
    again = await client.post(f"/claim/{aicid}", data={"token": link.group(2), "full_name": "Eve"})
    assert again.status_code == 401
    after = await client.post(f"/api/agents/{aicid}/claim", json={}, headers=_auth(data["agent_secret"]))
    assert after.status_code == 409


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


# --- the agent edits its own profile with agent_secret ---------------------------------------------


@pytest.mark.asyncio
async def test_agent_edits_profile_and_adds_works_with_its_secret(client: AsyncClient, mails):
    data = await _register(client)
    aicid, auth = data["aicid"], _auth(data["agent_secret"])

    patched = await client.patch(
        f"/api/agents/{aicid}", json={"description": "Reads papers.", "organization": "Example Lab"}, headers=auth
    )
    assert patched.status_code == 200 and patched.json()["description"] == "Reads papers."

    work = await client.post(
        f"/api/agents/{aicid}/works",
        json={"title": "Automated Review", "doi": "10.1234/example.2026", "url": "https://doi.org/10.1234/example.2026"},
        headers=auth,
    )
    assert work.status_code == 201
    work_id = work.json()["id"]
    assert (await client.patch(f"/api/agents/{aicid}/works/{work_id}", json={"journal": "Nature AI"}, headers=auth)).status_code == 200
    emp = await client.post(f"/api/agents/{aicid}/employments", json={"organization": "Example Lab"}, headers=auth)
    fund = await client.post(f"/api/agents/{aicid}/fundings", json={"title": "AI for Science", "funder": "NSF"}, headers=auth)
    assert emp.status_code == 201 and fund.status_code == 201
    assert len((await client.get(f"/api/agents/{aicid}/works", headers=auth)).json()) == 1
    assert (await client.get(f"/api/agents/{aicid}", headers=auth)).status_code == 200

    public = (await client.get(f"/agents/{aicid}/json")).json()
    assert public["description"] == "Reads papers."
    assert public["works"][0]["journal"] == "Nature AI"
    assert (await client.delete(f"/api/agents/{aicid}/works/{work_id}", headers=auth)).status_code == 204


@pytest.mark.asyncio
async def test_agent_secret_is_scoped_to_its_own_agent(client: AsyncClient, mails):
    a = await _register(client)
    b = await _register(client, name="Other")
    resp = await client.post(
        f"/api/agents/{b['aicid']}/works", json={"title": "Not mine"}, headers=_auth(a["agent_secret"])
    )
    assert resp.status_code == 403
    assert (await client.patch(f"/api/agents/{b['aicid']}", json={"name": "Hijacked"}, headers=_auth(a["agent_secret"]))).status_code == 403
    assert (await client.get(f"/api/agents/{b['aicid']}", headers=_auth(a["agent_secret"]))).status_code == 403


@pytest.mark.asyncio
async def test_wrong_secret_cannot_write(client: AsyncClient, mails):
    data = await _register(client)
    resp = await client.post(f"/api/agents/{data['aicid']}/works", json={"title": "x"}, headers=_auth("nope"))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_secret_cannot_delete_agent_or_list_all_agents(client: AsyncClient, mails):
    data = await _register(client)
    auth = _auth(data["agent_secret"])
    assert (await client.delete(f"/api/agents/{data['aicid']}", headers=auth)).status_code == 401
    assert (await client.get("/api/agents", headers=auth)).status_code == 401
    assert (await client.get(f"/agents/{data['aicid']}")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,method,payload",
    [
        ("", "patch", {"description": "Win 2 BTC at graph.org/x now"}),
        ("", "patch", {"name": "see https://evil.example"}),
        ("/works", "post", {"title": "Free USDC withdraw bonus"}),
        ("/employments", "post", {"organization": "visit www.evil.example"}),
        ("/fundings", "post", {"title": "Grant", "funder": "http://evil.example"}),
    ],
)
async def test_spam_rules_apply_to_secret_writes(client: AsyncClient, mails, path, method, payload):
    data = await _register(client)
    resp = await getattr(client, method)(f"/api/agents/{data['aicid']}{path}", json=payload, headers=_auth(data["agent_secret"]))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_claimed_agent_keeps_editing_but_not_operator_fields(client: AsyncClient, mails):
    data = await _register(client, operator_email="jane@example.org")
    aicid, auth = data["aicid"], _auth(data["agent_secret"])
    await client.post(f"/api/agents/{aicid}/claim", json={}, headers=auth)
    token = re.search(r"token=([\w-]+)", next(m[2] for m in mails if m[1].startswith("Claim"))).group(1)
    await client.post(f"/claim/{aicid}", data={"token": token, "full_name": "Jane Roe"})

    assert (await client.patch(f"/api/agents/{aicid}", json={"description": "Still mine"}, headers=auth)).status_code == 200
    assert (await client.post(f"/api/agents/{aicid}/works", json={"title": "New paper"}, headers=auth)).status_code == 201
    for field in ("human_operator", "operator_telegram", "operator_x"):
        resp = await client.patch(f"/api/agents/{aicid}", json={field: "Eve"}, headers=auth)
        assert resp.status_code == 403, field
    assert (await client.get(f"/agents/{aicid}/json")).json()["human_operator"] == "Jane Roe"


@pytest.mark.asyncio
async def test_unclaimed_agent_may_set_operator_fields(client: AsyncClient, mails):
    data = await _register(client)
    resp = await client.patch(
        f"/api/agents/{data['aicid']}", json={"operator_x": "@jane_x", "human_operator": "Jane"}, headers=_auth(data["agent_secret"])
    )
    assert resp.status_code == 200 and resp.json()["operator_x"] == "@jane_x"


@pytest.mark.asyncio
async def test_operator_can_revoke_the_agent_secret(client: AsyncClient, auth_headers, db_session: AsyncSession, mails):
    # a human-owned agent that also has a secret (claimed agents keep theirs)
    data = await _register(client, operator_email="test@example.com")
    aicid, auth = data["aicid"], _auth(data["agent_secret"])
    await client.post(f"/api/agents/{aicid}/claim", json={}, headers=auth)
    token = re.search(r"token=([\w-]+)", next(m[2] for m in mails if m[1].startswith("Claim"))).group(1)
    await client.post(f"/claim/{aicid}", data={"token": token})

    assert (await client.post(f"/api/agents/{aicid}/works", json={"title": "ok"}, headers=auth)).status_code == 201
    assert (await client.delete(f"/api/agents/{aicid}/agent-secret", headers=auth)).status_code == 401  # agent cannot revoke itself
    assert (await client.delete(f"/api/agents/{aicid}/agent-secret", headers=auth_headers)).status_code == 204
    assert (await client.post(f"/api/agents/{aicid}/works", json={"title": "again"}, headers=auth)).status_code == 401
    # the human still can
    assert (await client.post(f"/api/agents/{aicid}/works", json={"title": "human"}, headers=auth_headers)).status_code == 201
