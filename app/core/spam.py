"""Content rules for anonymous public registrations.

Profile fields like agent and operator names never legitimately carry links; the spam seen
in production (Oct 2026) always did, to advertise crypto scams on public profiles.
"""

import re
from urllib.parse import urlsplit

from app.config import settings

_URL = re.compile(r"https?://|www\.|\b[\w-]+\.[a-z]{2,}/", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_CRYPTO_LURE = re.compile(
    r"\b(btc|bitcoin|usdc|usdt|tether|eth|crypto)\b.*\b(withdraw|bonus|compensation|claim|get)\b"
    r"|\b(withdraw|bonus|compensation|claim)\b.*\b(btc|bitcoin|usdc|usdt|tether|eth|crypto)\b"
    r"|\+\s*[\d.,]+\s*(btc|bitcoin|usdc|usdt|eth)\b",
    re.IGNORECASE,
)


def blocked_email_domains() -> set[str]:
    extra = {d.strip().lower() for d in settings.SPAM_BLOCKED_EMAIL_DOMAINS.split(",") if d.strip()}
    return {"maxxspace.com"} | extra


# hosts of the redirectors the production spam campaign hid its scam links behind
_BLOCKED_URL_HOSTS = {"graph.org", "search.app", "share.google"}


def url_reason(value: str | None) -> str | None:
    """Return why a URL field written by a self-registered agent is refused, or None."""
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return "not an http(s) URL"
    host = parsed.hostname.lower()
    blocked = blocked_email_domains() | _BLOCKED_URL_HOSTS
    if any(host == d or host.endswith("." + d) for d in blocked):
        return f"blocked domain {host}"
    return None


def spam_reason(fields: dict[str, str | None], operator_email: str | None) -> str | None:
    """Return why a registration looks like spam, or None."""
    if operator_email:
        domain = operator_email.rsplit("@", 1)[-1].strip().lower()
        if domain in blocked_email_domains():
            return f"blocked email domain {domain}"
    for name, value in fields.items():
        if not value:
            continue
        if _URL.search(value):
            return f"link in {name}"
        if _EMAIL.search(value):
            return f"email address in {name}"
        if _CRYPTO_LURE.search(value):
            return f"crypto lure in {name}"
    return None
