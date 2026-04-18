import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_skill_md_is_served(client: AsyncClient):
    resp = await client.get("/SKILL.md")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "# AICID platform skill" in resp.text
    assert "POST /api/agents" in resp.text
