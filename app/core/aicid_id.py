"""
AICID unique identifier generation.

Format: AICID-DDDD-DDDD-DDDD  (16 digits, last is ISO 7064 MOD 11-2 checksum)
Mirrors ORCID's identifier format.
"""
import random
import string


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
    if not digits.isdigit():
        return False
    return _checksum(digits) == check
