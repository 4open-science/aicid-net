"""Live contract check against the production email relay declared in render.yaml.

The relay is an external service: it moved hosts (308 on the old URL) without any change in
this repo. CI runs this on a daily schedule so such drift fails CI instead of production logins.
Set AICID_SKIP_LIVE=1 to skip when offline.
"""

import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

RENDER_YAML = Path(__file__).resolve().parent.parent / "render.yaml"

pytestmark = pytest.mark.skipif(os.environ.get("AICID_SKIP_LIVE") == "1", reason="live checks disabled")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _production_relay_url() -> str:
    services = yaml.safe_load(RENDER_YAML.read_text())["services"]
    web = next(s for s in services if s["name"] == "aicid-web")
    env = {v["key"]: v.get("value") for v in web["envVars"]}
    assert env.get("POSTHORN_BASE_URL"), "POSTHORN_BASE_URL must be declared in render.yaml"
    return env["POSTHORN_BASE_URL"].rstrip("/")


def test_production_relay_answers_without_redirect():
    url = _production_relay_url() + "/healthz"
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=15) as resp:
            status, body = resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        pytest.fail(f"{url} answered {exc.code} (Location: {exc.headers.get('Location')})")
    assert (status, body.strip()) == (200, "ok")
