"""
AICID unique identifier generation.

Format: AICID-DDDD-DDDD-DDDD-DDDX — four groups of four digits followed by
an ISO 7064 MOD 11-2 check character (0-9 or X), computed over the first
15 digits. Deliberately ORCID-shaped.

The normative specification lives in docs/identifier.md, served at
https://aicid.net/docs/identifier.
"""
import random
import re
import string

# Prefixes and separators tolerated by parse_aicid (docs/identifier.md, "Parsing rules").
_URL_PREFIX = re.compile(r"^(?:https?://)?(?:www\.)?aicid\.net/(?:agents/)?", re.IGNORECASE)
_URL_SUFFIX = re.compile(r"/(?:json)?$", re.IGNORECASE)
_SEPARATORS = re.compile(r"[\s\-‐‑‒–—]+")


def _checksum(digits: str) -> str:
    """Compute ISO 7064 MOD 11-2 check character for a 15-digit string."""
    total = 0
    for ch in digits:
        total = (total + int(ch)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    return "X" if result == 10 else str(result)


def generate_aicid() -> str:
    """Generate a new AICID string, e.g. AICID-0000-0002-1825-X."""
    digits = "".join(random.choices(string.digits, k=15))
    check = _checksum(digits)
    full = digits + check
    return f"AICID-{full[0:4]}-{full[4:8]}-{full[8:12]}-{full[12:16]}"


def validate_aicid(aicid: str) -> bool:
    """Return True if the AICID checksum is valid."""
    if not aicid.startswith("AICID-"):
        return False
    parts = aicid[6:].replace("-", "")
    if len(parts) != 16:
        return False
    digits = parts[:15]
    check = parts[15]
    if not (digits.isascii() and digits.isdigit()):
        return False
    return _checksum(digits) == check


def parse_aicid(text: str) -> str | None:
    """Return the canonical AICID written in ``text``, or None.

    Lenient on the display form, strict on the identifier: accepts lowercase,
    the profile URL, a missing ``AICID`` prefix, and spaces, hyphens or nothing
    between the groups (``aicid 5292 9078 3865 2458``, ``5292907838652458``),
    but only returns identifiers whose check character is valid.
    """
    body = _URL_SUFFIX.sub("", _URL_PREFIX.sub("", text.strip())).upper()
    body = _SEPARATORS.sub("", body.removeprefix("AICID").lstrip(":"))
    if len(body) != 16:
        return None
    candidate = f"AICID-{body[0:4]}-{body[4:8]}-{body[8:12]}-{body[12:16]}"
    return candidate if validate_aicid(candidate) else None
