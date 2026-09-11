"""Tests for the AICID identifier: generation, validation, spec endpoint."""
import pytest
from httpx import AsyncClient

from app.core.aicid_id import _checksum, generate_aicid, validate_aicid


def test_generate_shape():
    aicid = generate_aicid()
    assert aicid.startswith("AICID-")
    groups = aicid[6:].split("-")
    assert len(groups) == 4
    assert all(len(g) == 4 for g in groups)
    assert aicid[6:].replace("-", "").isalnum()


def test_generated_ids_are_valid():
    for _ in range(100):
        assert validate_aicid(generate_aicid())


def test_doc_example_is_valid():
    # The example used in the docs and templates must pass validation.
    assert validate_aicid("AICID-5282-9748-4313-4513")


def test_checksum_known_values():
    # 15 zeros -> total 0 -> result (12 - 0) % 11 = 1
    assert _checksum("0" * 15) == "1"
    assert validate_aicid("AICID-0000-0000-0000-0001")
    assert not validate_aicid("AICID-0000-0000-0000-0000")


def test_x_check_character():
    # Find a 15-digit prefix whose check character is X (result == 10).
    digits = "0" * 14 + "1"  # total 1 -> 2 -> (12-2)%11 = 10 -> X
    assert _checksum(digits) == "X"
    assert validate_aicid(f"AICID-{digits[:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:]}X")


def test_invalid_inputs():
    assert not validate_aicid("AICID-5282-9748-4313-4514")  # wrong check char
    assert not validate_aicid("5282-9748-4313-4513")  # missing prefix
    assert not validate_aicid("AICID-5282-9748-4313")  # too short
    assert not validate_aicid("AICID-5282-9748-4313-4513-9999")  # too long
    assert not validate_aicid("AICID-5282-97a8-4313-4513")  # non-digit in digits
    assert not validate_aicid("")
    # Current implementation is case-sensitive on the prefix.
    assert not validate_aicid("aicid-5282-9748-4313-4513")


@pytest.mark.asyncio
async def test_identifier_spec_endpoint(client: AsyncClient):
    response = await client.get("/docs/identifier")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.text
    assert "ISO 7064 MOD 11-2" in body
    assert "AICID-5282-9748-4313-4513" in body


@pytest.mark.asyncio
async def test_docs_page_links_spec(client: AsyncClient):
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "/docs/identifier" in response.text
