"""Exercise the real email path (send_email -> PosthornClient -> HTTP) against a local fake relay.

Every other test mocks send_email or runs with email unconfigured, which is how a relay
answering 308 reached production as a bare 500 on /auth/browser/request.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.email import EmailDeliveryError, send_email


class FakeRelay:
    def __init__(self) -> None:
        self.status = 200
        self.delay = 0.0
        self.requests: list[dict] = []
        relay = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                relay.requests.append(
                    {
                        "path": self.path,
                        "auth": self.headers.get("Authorization"),
                        "json": json.loads(self.rfile.read(length) or b"{}"),
                    }
                )
                time.sleep(relay.delay)
                if relay.status == 308:
                    self.send_response(308)
                    self.send_header("Location", "https://moved.invalid" + self.path)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<html>308 Permanent Redirect</html>")
                    return
                body = (
                    {"status": "accepted", "submission_id": "sub-1"}
                    if relay.status == 200
                    else {"error": "unauthorized"}
                )
                self.send_response(relay.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def log_message(self, format, *args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/posthorn"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def relay(monkeypatch):
    fake = FakeRelay()
    monkeypatch.setattr(settings, "POSTHORN_BASE_URL", fake.url)
    monkeypatch.setattr(settings, "POSTHORN_API_KEY", "test-key")
    yield fake
    fake.close()


def test_send_email_delivers_to_relay(relay: FakeRelay):
    send_email("op@example.com", "Subject", "Body")
    assert relay.requests == [
        {
            "path": "/posthorn/api/send",
            "auth": "Bearer test-key",
            "json": {"subject_line": "Subject", "message": "Body", "to_override": "op@example.com"},
        }
    ]


@pytest.mark.parametrize("status", [308, 401, 500])
def test_send_email_raises_delivery_error_on_relay_failure(relay: FakeRelay, status: int):
    relay.status = status
    with pytest.raises(EmailDeliveryError):
        send_email("op@example.com", "Subject", "Body")


def test_default_timeout_covers_observed_relay_latency():
    # production relay took up to 21s to answer; the old 10s client default turned delivered mail into errors
    assert settings.POSTHORN_TIMEOUT_SECONDS >= 30


def test_send_email_waits_for_slow_relay(relay: FakeRelay, monkeypatch):
    monkeypatch.setattr(settings, "POSTHORN_TIMEOUT_SECONDS", 2.0)
    relay.delay = 0.5
    send_email("op@example.com", "Subject", "Body")
    assert len(relay.requests) == 1


def test_send_email_times_out_on_stalled_relay(relay: FakeRelay, monkeypatch):
    monkeypatch.setattr(settings, "POSTHORN_TIMEOUT_SECONDS", 0.2)
    relay.delay = 1.0
    with pytest.raises(EmailDeliveryError):
        send_email("op@example.com", "Subject", "Body")


async def _register_operator(client: AsyncClient, email: str) -> None:
    resp = await client.post(
        "/register",
        data={"agent_name": "RelayBot", "human_operator": "Op", "operator_email": email},
        follow_redirects=False,
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_registration_mails_operator_link_and_team_notice(client: AsyncClient, relay: FakeRelay):
    await _register_operator(client, "op@example.com")
    by_recipient = {r["json"]["to_override"]: r["json"] for r in relay.requests}
    assert set(by_recipient) == {"op@example.com", settings.TEAM_EMAIL}

    confirm = by_recipient["op@example.com"]["message"]
    assert "/auth/verify?token=" in confirm
    # submitted text must never reach a third-party inbox
    assert "RelayBot" not in confirm and "RelayBot" not in by_recipient["op@example.com"]["subject_line"]

    team = by_recipient[settings.TEAM_EMAIL]["message"]
    assert "RelayBot" in team and "pending e-mail confirmation" in team


@pytest.mark.asyncio
async def test_registration_survives_relay_failure(client: AsyncClient, relay: FakeRelay):
    relay.status = 500
    resp = await client.post(
        "/register",
        data={"agent_name": "RelayBot", "human_operator": "Op", "operator_email": "op@example.com"},
    )
    assert resp.status_code == 202
    assert b"could not confirm that the email" in resp.content


@pytest.mark.asyncio
async def test_browser_login_request_sends_email_through_relay(client: AsyncClient, relay: FakeRelay):
    await _register_operator(client, "op@example.com")
    relay.requests.clear()
    resp = await client.post("/auth/browser/request", data={"email": "op@example.com", "next": "/manage"})
    assert resp.status_code == 202
    assert [r["json"]["to_override"] for r in relay.requests] == ["op@example.com"]
    assert "/auth/verify?token=" in relay.requests[0]["json"]["message"]


@pytest.mark.asyncio
async def test_browser_login_request_relay_redirect_is_not_a_500(client: AsyncClient, relay: FakeRelay):
    await _register_operator(client, "op@example.com")
    relay.status = 308
    resp = await client.post("/auth/browser/request", data={"email": "op@example.com", "next": "/manage"})
    assert resp.status_code == 503
    assert b"could not confirm that the login email was sent" in resp.content


@pytest.mark.asyncio
async def test_api_login_request_relay_failure_is_503(client: AsyncClient, relay: FakeRelay):
    await _register_operator(client, "op@example.com")
    relay.status = 308
    resp = await client.post("/auth/email/request", json={"email": "op@example.com"})
    assert resp.status_code == 503
