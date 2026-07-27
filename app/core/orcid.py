import re


_ORCID_PATTERN = re.compile(
    r"^(?:https?://(?:www\.)?orcid\.org/)?"
    r"(\d{4})-(\d{4})-(\d{4})-(\d{3}[\dXx])/?$"
)


def normalize_orcid(value: str | None) -> str | None:
    """Validate an ORCID iD and return its canonical HTTPS URL."""
    if value is None:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    match = _ORCID_PATTERN.fullmatch(candidate)
    if match is None:
        raise ValueError("Invalid ORCID iD")

    orcid_id = "-".join(match.groups()).upper()
    compact = orcid_id.replace("-", "")

    total = 0
    for digit in compact[:-1]:
        total = (total + int(digit)) * 2
    check_value = (12 - total % 11) % 11
    expected_check = "X" if check_value == 10 else str(check_value)
    if compact[-1] != expected_check:
        raise ValueError("Invalid ORCID iD checksum")

    return f"https://orcid.org/{orcid_id}"
