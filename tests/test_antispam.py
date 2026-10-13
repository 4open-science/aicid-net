import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.spam import spam_reason
from app.models.agent import Agent
from tests.conftest import registered_aicid

# agent_name values of the spam campaign seen in production, 2026-10-09..12
REAL_SPAM_NAMES = [
    "A NEW MESSAGE for you #I5879 READ => graph.org/Sofia-10-03-6?hs=8148d5148b87131abc4687356ada27be&",
    "+ 2 BTC. WITHDRAW ▶ https://search.app/fZYLr?hs=8148d5148b87131abc4687356ada27be&",
    "+ 121,448 USDC - graph.org/Sofia-10-03-6?hs=8148d5148b87131abc4687356ada27be&",
    "+ 2 BTC. GET 👉🏾 https://search.app/XpAfH?hs=8148d5148b87131abc4687356ada27be&",
    "+2.84567261 BITCOIN. GET ->>> https://www.google.com/share.google?q=G8B3O8Bwfsd8lpbRM?hs=8148d5148b87131abc4687356ada27be&",
    "Tether Crypto Compensation Withdraw Bonus 🔥>> graph.org/Sofia-10-03-6?hs=8148d5148b87131abc4687356ada27be&",
    "graph.org/Sofia-10-03-6?hs=8148d5148b87131abc4687356ada27be& - unread message №PVSH",
]

LEGIT = [
    ("Gist.Science summarizer", "Gist Science", "GPT-4.1", "2025-04-14", "Claude Code"),
    ("Leo Vance", "Michele Renda", "claude-sonnet-4.5", "3.5-turbo", "Codex CLI"),
    ("Dr.DS", "Wu Junchen", "o3", "v1.2.3", "OpenCode"),
    ("hermes", "liuyuanjie", "Qwen2.5-72B", None, "AutoGen"),
]


def _fields(name, operator="Op", model=None, version=None, harness=None):
    return {"agent_name": name, "human_operator": operator, "base_model": model, "version": version, "agent_harness": harness}


@pytest.mark.parametrize("name", REAL_SPAM_NAMES)
def test_real_spam_flagged_by_content_alone(name: str):
    # neutral e-mail domain: the content rule must catch it without the domain blocklist
    assert spam_reason(_fields(name), "someone@example.org")


@pytest.mark.parametrize("row", LEGIT)
def test_legit_registrations_not_flagged(row):
    assert spam_reason(_fields(*row), "op@example.org") is None


@pytest.mark.parametrize(
    "fields,email",
    [
        (_fields("Nice bot", operator="see http://x.io"), "a@example.org"),
        (_fields("Nice bot", harness="mail me: a@b.co"), "a@example.org"),
        (_fields("Claim your USDT bonus now"), "a@example.org"),
        (_fields("Nice bot"), "x@maxxspace.com"),
    ],
)
def test_other_spam_signals(fields, email):
    assert spam_reason(fields, email)


def test_blocked_domains_extendable(monkeypatch):
    monkeypatch.setattr(settings, "SPAM_BLOCKED_EMAIL_DOMAINS", "spam.example, other.example")
    assert spam_reason(_fields("Nice bot"), "a@other.example")


def _form(name="RealBot", operator="Alice", email="alice@example.com", **extra):
    return {"agent_name": name, "human_operator": operator, "operator_email": email, **extra}


async def _agent_count(db: AsyncSession) -> int:
    return len((await db.execute(select(Agent))).scalars().all())


@pytest.mark.asyncio
async def test_spam_form_rejected_and_not_stored(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post("/register", data=_form(name=REAL_SPAM_NAMES[0], operator="igm144", email="x@maxxspace.com"))
    assert resp.status_code == 422
    assert b"could not be accepted" in resp.content
    assert await _agent_count(db_session) == 0


@pytest.mark.asyncio
async def test_honeypot_rejects(client: AsyncClient, db_session: AsyncSession):
    resp = await client.post("/register", data=_form(contact_website="http://spam.example"))
    assert resp.status_code == 422
    assert await _agent_count(db_session) == 0


@pytest.mark.asyncio
async def test_register_form_contains_hidden_honeypot(client: AsyncClient):
    resp = await client.get("/register")
    assert b'name="contact_website"' in resp.content
    assert b'class="form-honeypot"' in resp.content


@pytest.mark.asyncio
async def test_anonymous_registration_hidden_until_email_link_opened(client: AsyncClient):
    resp = await client.post("/register", data=_form(), follow_redirects=False)
    aicid = registered_aicid(resp)
    assert b"Check your email" in resp.content

    assert (await client.get(f"/agents/{aicid}")).status_code == 404
    assert (await client.get(f"/agents/{aicid}/json")).status_code == 404
    assert aicid.encode() not in (await client.get("/search-page")).content
    hidden_search = await client.get("/search")
    assert hidden_search.status_code == 200
    assert aicid not in hidden_search.text

    token = re.search(r"Development code: <code>([^<]+)</code>", resp.text).group(1)
    verify = await client.get(f"/auth/verify?token={token}&next=/agents/{aicid}", follow_redirects=False)
    assert verify.status_code == 303
    assert verify.headers["location"] == f"/agents/{aicid}"

    assert (await client.get(f"/agents/{aicid}")).status_code == 200
    assert aicid.encode() in (await client.get("/search-page")).content
    assert aicid in (await client.get("/search")).text


@pytest.mark.asyncio
async def test_any_later_login_publishes_pending_agents(client: AsyncClient):
    aicid = registered_aicid(await client.post("/register", data=_form(), follow_redirects=False))
    login = await client.post("/auth/browser/request", data={"email": "alice@example.com", "next": "/manage"})
    token = login.text.split("Development code: <code>")[1].split("</code>")[0]
    await client.post("/auth/browser/verify", data={"token": token, "next": "/manage"}, follow_redirects=False)
    assert (await client.get(f"/agents/{aicid}")).status_code == 200


@pytest.mark.asyncio
async def test_logged_in_operator_publishes_immediately(client: AsyncClient):
    first = registered_aicid(await client.post("/register", data=_form(), follow_redirects=False))
    login = await client.post("/auth/browser/request", data={"email": "alice@example.com", "next": "/manage"})
    token = login.text.split("Development code: <code>")[1].split("</code>")[0]
    await client.post("/auth/browser/verify", data={"token": token, "next": "/manage"}, follow_redirects=False)

    resp = await client.post("/register", data=_form(name="SecondBot"), follow_redirects=False)
    assert resp.status_code == 303
    second = registered_aicid(resp)
    assert second != first
    assert (await client.get(f"/agents/{second}")).status_code == 200


@pytest.mark.asyncio
async def test_session_for_other_operator_does_not_publish(client: AsyncClient):
    """The impersonation case: logged in as Alice, registering under Bob's e-mail stays pending."""
    registered_aicid(await client.post("/register", data=_form(), follow_redirects=False))
    login = await client.post("/auth/browser/request", data={"email": "alice@example.com", "next": "/manage"})
    token = login.text.split("Development code: <code>")[1].split("</code>")[0]
    await client.post("/auth/browser/verify", data={"token": token, "next": "/manage"}, follow_redirects=False)

    resp = await client.post("/register", data=_form(name="Fake", operator="Bob", email="bob@example.com"), follow_redirects=False)
    assert resp.status_code == 202
    assert (await client.get(f"/agents/{registered_aicid(resp)}")).status_code == 404


@pytest.mark.asyncio
async def test_admin_spam_hides_and_unspam_restores(client: AsyncClient, db_session: AsyncSession, auth_headers: dict):
    from app.admin import recent, set_moderation

    aicid = (await client.post("/api/agents", json={"name": "ApiBot", "human_operator": "Alice"}, headers=auth_headers)).json()["aicid"]
    assert (await client.get(f"/agents/{aicid}")).status_code == 200

    assert await set_moderation(db_session, [aicid, "AICID-0000-0000-0000-0000"], "spam") == ["AICID-0000-0000-0000-0000"]
    assert (await client.get(f"/agents/{aicid}")).status_code == 404
    assert aicid not in (await client.get("/search")).text
    assert [r["status"] for r in await recent(db_session, 1) if r["aicid"] == aicid] == ["spam"]

    await set_moderation(db_session, [aicid], None)
    assert (await client.get(f"/agents/{aicid}")).status_code == 200


def test_admin_cli_runs_standalone(tmp_path):
    """Run in a fresh interpreter: the app's other imports must not be needed to configure mappers."""
    import os
    import subprocess
    import sys

    db = tmp_path / "admin.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db}", "ENVIRONMENT": "test"}
    setup = (
        "import asyncio, app.admin\n"
        "from app.database import engine, Base\n"
        "async def go():\n"
        "    async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)\n"
        "asyncio.run(go())\n"
    )
    subprocess.run([sys.executable, "-c", setup], env=env, check=True)
    out = subprocess.run(
        [sys.executable, "-m", "app.admin", "spam", "AICID-0000-0000-0000-0000"], env=env, capture_output=True, text=True
    )
    assert out.returncode == 1, out.stderr
    assert out.stderr.strip() == "not found: AICID-0000-0000-0000-0000"


@pytest.mark.asyncio
async def test_spam_status_survives_owner_login(client: AsyncClient, db_session: AsyncSession):
    from app.admin import set_moderation

    aicid = registered_aicid(await client.post("/register", data=_form(), follow_redirects=False))
    await set_moderation(db_session, [aicid], "spam")
    login = await client.post("/auth/browser/request", data={"email": "alice@example.com", "next": "/manage"})
    token = login.text.split("Development code: <code>")[1].split("</code>")[0]
    await client.post("/auth/browser/verify", data={"token": token, "next": "/manage"}, follow_redirects=False)
    assert (await client.get(f"/agents/{aicid}")).status_code == 404


@pytest.mark.asyncio
async def test_rate_limit_per_email(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_LIMIT_PER_EMAIL_PER_HOUR", 2)
    for i in range(2):
        assert (await client.post("/register", data=_form(name=f"Bot{i}"))).status_code == 202
    resp = await client.post("/register", data=_form(name="Bot3"))
    assert resp.status_code == 429
    # another operator is not affected
    assert (await client.post("/register", data=_form(email="carol@example.com"))).status_code == 202


@pytest.mark.asyncio
async def test_rate_limit_global(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_LIMIT_PER_HOUR", 2)
    for i in range(2):
        assert (await client.post("/register", data=_form(email=f"op{i}@example.com"))).status_code == 202
    assert (await client.post("/register", data=_form(email="op9@example.com"))).status_code == 429
