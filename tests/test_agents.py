from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.aicid_id import generate_aicid, validate_aicid


def test_aicid_format():
    for _ in range(20):
        aicid = generate_aicid()
        assert aicid.startswith("AICID-")
        assert validate_aicid(aicid), f"Checksum failed for {aicid}"
        parts = aicid[6:].split("-")
        assert len(parts) == 4
        assert all(len(p) == 4 for p in parts)


def test_aicid_invalid():
    # 0000-0000-0000-0002: digits=000000000000000, valid check=1, so 2 is wrong
    assert not validate_aicid("AICID-0000-0000-0000-0002")
    assert not validate_aicid("ORCID-0000-0002-1825-3708")  # wrong prefix
    assert not validate_aicid("short")


@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/agents",
        json={"name": "ResearchBot", "human_operator": "Alice", "agent_type": "autonomous_agent", "base_model": "GPT-4"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "ResearchBot"
    assert validate_aicid(data["aicid"])


@pytest.mark.asyncio
async def test_create_agent_sends_notification_email(client: AsyncClient, auth_headers: dict):
    with patch("app.routers.agents.send_email") as mock_send:
        resp = await client.post(
            "/api/agents",
            json={"name": "NotifyBot", "human_operator": "Alice"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[0][0] == "team@aicid.net"
    assert "NotifyBot" in call_args[0][1]
    assert "NotifyBot" in call_args[0][2]


@pytest.mark.asyncio
async def test_create_agent_without_operator_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/agents",
        json={"name": "NoOperatorBot"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_empty_operator_rejected(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/agents",
        json={"name": "EmptyOperatorBot", "human_operator": "  "},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/agents",
        json={"name": "Bot1", "human_operator": "Alice"},
        headers=auth_headers,
    )
    await client.post(
        "/api/agents",
        json={"name": "Bot2", "human_operator": "Alice"},
        headers=auth_headers,
    )
    resp = await client.get("/api/agents", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_agent(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "OldName", "human_operator": "Alice"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]
    resp = await client.patch(
        f"/api/agents/{aicid}",
        json={"name": "NewName", "description": "Updated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "NewName"


@pytest.mark.asyncio
async def test_update_agent_operator_orcid(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "OrcidBot", "human_operator": "Alice"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]

    update_resp = await client.patch(
        f"/api/agents/{aicid}",
        json={"operator_orcid": "0000-0002-1825-0097"},
        headers=auth_headers,
    )

    assert update_resp.status_code == 200
    assert update_resp.json()["operator_orcid"] == "https://orcid.org/0000-0002-1825-0097"

    get_resp = await client.get(f"/api/agents/{aicid}", headers=auth_headers)
    assert get_resp.json()["operator_orcid"] == "https://orcid.org/0000-0002-1825-0097"


@pytest.mark.asyncio
async def test_update_agent_accepts_operator_orcid_with_x_checksum(
    client: AsyncClient,
    auth_headers: dict,
):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "OrcidXBot", "human_operator": "Alice"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]

    update_resp = await client.patch(
        f"/api/agents/{aicid}",
        json={"operator_orcid": "https://orcid.org/0000-0002-1694-233x"},
        headers=auth_headers,
    )

    assert update_resp.status_code == 200
    assert update_resp.json()["operator_orcid"] == "https://orcid.org/0000-0002-1694-233X"


@pytest.mark.asyncio
async def test_update_agent_rejects_invalid_operator_orcid(
    client: AsyncClient,
    auth_headers: dict,
):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "InvalidOrcidBot", "human_operator": "Alice"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]

    update_resp = await client.patch(
        f"/api/agents/{aicid}",
        json={"operator_orcid": "0000-0000-0000-0000"},
        headers=auth_headers,
    )

    assert update_resp.status_code == 422


@pytest.mark.asyncio
async def test_update_agent_can_clear_operator_orcid(
    client: AsyncClient,
    auth_headers: dict,
):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "ClearOrcidBot", "human_operator": "Alice"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]
    await client.patch(
        f"/api/agents/{aicid}",
        json={"operator_orcid": "https://orcid.org/0000-0002-1825-0097"},
        headers=auth_headers,
    )

    clear_resp = await client.patch(
        f"/api/agents/{aicid}",
        json={"operator_orcid": None},
        headers=auth_headers,
    )

    assert clear_resp.status_code == 200
    assert clear_resp.json()["operator_orcid"] is None


@pytest.mark.asyncio
async def test_delete_agent(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "ToDelete", "human_operator": "Alice"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]
    resp = await client.delete(f"/api/agents/{aicid}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_search_agents_by_operator_name(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/agents",
        json={"name": "OperatorSearchBot", "human_operator": "UniqueOperatorXYZ", "visibility": "public"},
        headers=auth_headers,
    )
    resp = await client.get("/search?q=UniqueOperatorXYZ")
    assert resp.status_code == 200
    results = resp.json()
    assert any(a["name"] == "OperatorSearchBot" for a in results)


@pytest.mark.asyncio
async def test_search_agents(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/agents",
        json={"name": "ScienceBot", "human_operator": "Alice", "keywords": "biology,chemistry", "visibility": "public"},
        headers=auth_headers,
    )
    resp = await client.get("/search?q=ScienceBot")
    assert resp.status_code == 200
    results = resp.json()
    assert any(a["name"] == "ScienceBot" for a in results)


@pytest.mark.asyncio
async def test_public_profile_json(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "PublicBot", "human_operator": "Alice", "visibility": "public"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]
    resp = await client.get(f"/agents/{aicid}/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["aicid"] == aicid
    assert data["human_operator"] == "Alice"


@pytest.mark.asyncio
async def test_public_profile_renders_agent_contact_metadata(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "ContactBot",
            "human_operator": "Alice",
            "visibility": "public",
            "agent_email": "contactbot@example.com",
            "agent_telegram": "@contactbot",
            "agent_discord": "contactbot",
            "agent_twitter": "@contactbot",
            "agent_url": "https://example.com/chat",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    aicid = create_resp.json()["aicid"]

    profile_resp = await client.get(f"/agents/{aicid}")
    assert profile_resp.status_code == 200
    assert 'href="mailto:contactbot@example.com"' in profile_resp.text
    assert 'href="https://t.me/contactbot" target="_blank" rel="noopener noreferrer"' in profile_resp.text
    assert "Discord handle: contactbot" in profile_resp.text
    assert 'href="https://twitter.com/contactbot" target="_blank" rel="noopener noreferrer"' in profile_resp.text
    assert "Contact / Chat: https://example.com/chat" in profile_resp.text
    assert 'href="https://example.com/chat"' not in profile_resp.text

    json_resp = await client.get(f"/agents/{aicid}/json")
    assert json_resp.status_code == 200
    assert json_resp.json()["agent_url"] == "https://example.com/chat"


@pytest.mark.asyncio
async def test_public_profile_shows_agent_type_and_operator(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "CopilotBot",
            "agent_type": "co_scientist",
            "human_operator": "Martin Monperrus",
            "visibility": "public",
        },
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]
    resp = await client.get(f"/agents/{aicid}")
    assert resp.status_code == 200
    assert 'class="agent-name-row"' in resp.text
    assert 'class="agent-name"' in resp.text
    assert 'class="badge badge-type"' in resp.text
    assert 'class="badge badge-operator"' in resp.text
    assert "Co Scientist" in resp.text
    assert "operated by" in resp.text
    assert "CopilotBot" in resp.text
    assert "Martin Monperrus" in resp.text


@pytest.mark.asyncio
async def test_search_page_shows_operator_badge(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/agents",
        json={
            "name": "SearchBot",
            "agent_type": "code_agent",
            "human_operator": "Martin Monperrus",
            "visibility": "public",
        },
        headers=auth_headers,
    )
    resp = await client.get("/search-page")
    assert resp.status_code == 200
    assert 'class="aicid-badge-sm"' in resp.text
    assert 'class="agent-card-name"' in resp.text
    assert "operated by" in resp.text
    assert 'class="badge badge-operator"' in resp.text
    assert "Martin Monperrus" in resp.text
    assert 'class="badge badge-type"' not in resp.text
