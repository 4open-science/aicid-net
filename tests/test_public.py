import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User


@pytest.mark.asyncio
async def test_skill_md_is_served(client: AsyncClient):
    resp = await client.get("/SKILL.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "# AICID platform skill" in resp.text
    assert "POST /api/agents" in resp.text


@pytest.mark.asyncio
async def test_base_template_links_favicons(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert '<link rel="icon" href="/favicon.ico" sizes="any">' in resp.text
    assert '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">' in resp.text


@pytest.mark.asyncio
async def test_favicon_ico_is_served(client: AsyncClient):
    resp = await client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.headers["content-type"] in {
        "image/vnd.microsoft.icon",
        "image/x-icon",
    }
    assert resp.content


@pytest.mark.asyncio
async def test_public_profile_shows_orcid_verified_badge_for_verified_operator(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "VerifiedBot",
            "human_operator": "Test User",
            "visibility": "public",
        },
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]

    user = (await db_session.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    user.full_name = "Test User"
    user.orcid_id = "0000-0002-1825-0097"
    user.orcid_verified = True
    await db_session.commit()

    resp = await client.get(f"/agents/{aicid}")
    assert resp.status_code == 200
    assert "ORCID Verified" in resp.text
    assert 'href="https://orcid.org/0000-0002-1825-0097"' in resp.text
    assert 'href="https://orcid.org/0000-0000-0000-0000"' not in resp.text


@pytest.mark.asyncio
async def test_public_profile_hides_orcid_verified_badge_for_different_operator(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
):
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "MismatchBot",
            "human_operator": "Someone Else",
            "visibility": "public",
        },
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]

    user = (await db_session.execute(select(User).where(User.email == "test@example.com"))).scalar_one()
    user.full_name = "Test User"
    user.orcid_id = "0000-0002-1825-0097"
    user.orcid_verified = True
    await db_session.commit()

    resp = await client.get(f"/agents/{aicid}")
    assert resp.status_code == 200
    assert "ORCID Verified" not in resp.text


@pytest.mark.asyncio
async def test_public_profile_does_not_link_unverified_manual_operator_orcid(
    client: AsyncClient,
    auth_headers: dict,
):
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "ManualOrcidBot",
            "human_operator": "Test User",
            "visibility": "public",
        },
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]
    update_resp = await client.patch(
        f"/api/agents/{aicid}",
        json={"operator_orcid": "https://orcid.org/0000-0002-1825-0097"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200

    resp = await client.get(f"/agents/{aicid}")
    assert resp.status_code == 200
    assert "ORCID Verified" not in resp.text
    assert 'href="https://orcid.org/0000-0002-1825-0097"' not in resp.text
