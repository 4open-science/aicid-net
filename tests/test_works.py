import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_and_list_work(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/agents",
        json={"name": "WorkBot"},
        headers=auth_headers,
    )
    aicid = create_resp.json()["aicid"]

    work_resp = await client.post(
        f"/api/agents/{aicid}/works",
        json={"title": "Automated Drug Discovery", "work_type": "paper", "doi": "10.1234/test"},
        headers=auth_headers,
    )
    assert work_resp.status_code == 201
    work_data = work_resp.json()
    assert work_data["title"] == "Automated Drug Discovery"
    assert "put_code" in work_data

    list_resp = await client.get(f"/api/agents/{aicid}/works", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_update_work(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/agents", json={"name": "Bot"}, headers=auth_headers)
    aicid = create_resp.json()["aicid"]

    work_resp = await client.post(
        f"/api/agents/{aicid}/works",
        json={"title": "Original Title"},
        headers=auth_headers,
    )
    work_id = work_resp.json()["id"]

    upd_resp = await client.patch(
        f"/api/agents/{aicid}/works/{work_id}",
        json={"title": "Updated Title"},
        headers=auth_headers,
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_work(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/agents", json={"name": "Bot"}, headers=auth_headers)
    aicid = create_resp.json()["aicid"]

    work_resp = await client.post(
        f"/api/agents/{aicid}/works",
        json={"title": "To Delete"},
        headers=auth_headers,
    )
    work_id = work_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/agents/{aicid}/works/{work_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204
