import pytest
from httpx import AsyncClient


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
