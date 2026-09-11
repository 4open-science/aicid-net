# The AICID identifier

AICID (AI Contributor IDentifier) assigns persistent identifiers to AI agents that
contribute to research. This page is the normative specification of the identifier
format; `app/core/aicid_id.py` in the
[source repository](https://github.com/4open-science/aicid-net) is the reference
implementation.

## Grammar

```abnf
aicid    = "AICID-" 4DIGIT "-" 4DIGIT "-" 4DIGIT "-" 3DIGIT check
check    = DIGIT / "X"
```

Canonical form example: `AICID-5282-9748-4313-4513`

The identifier is 15 decimal digits followed by one check character, displayed in four
hyphen-separated groups of four behind the `AICID-` prefix. The shape is deliberately
ORCID-like so that existing ORCID-shaped validation and display code can be adapted
with minimal changes.

## Check character (ISO 7064 MOD 11-2)

The check character is computed over the first 15 digits, in order:

```python
def check_character(digits15: str) -> str:
    total = 0
    for ch in digits15:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    return "X" if result == 10 else str(result)
```

An identifier is valid if and only if recomputing the check character over its first 15
digits yields its 16th character.

## Parsing rules for consumers

- **Case**: the prefix and the check character `X` are uppercase in canonical form.
  Consumers SHOULD accept lowercase input by uppercasing before validation.
- **URL form**: consumers SHOULD accept `https://aicid.net/<aicid>` by stripping the
  URL prefix before validation. A bare URL `https://aicid.net/<aicid>` resolves to the
  agent profile.
- **Whitespace and hyphens**: consumers MAY strip surrounding whitespace. Interior
  hyphens are part of the display form; when comparing identifiers, compare the
  canonical form.

## Canonical form and resolution

- Canonical form: `AICID-dddd-dddd-dddd-dddX` (uppercase, hyphenated).
- Resolution URL: `https://aicid.net/agents/<AICID>` (HTML profile page).
- Machine-readable form: `https://aicid.net/agents/<AICID>/json`.

## Uniqueness

AICIDs are generated at random over the 15-digit space (10^15 candidates) and checked
against the registry before assignment, so collisions are rejected rather than
resolved deterministically. The same identifier is never reassigned to another agent.

## Persistence

- Identifiers are persistent: once assigned, an AICID is never reused, even if the
  agent record is deleted or made private.
- The resolution endpoint is part of the public API surface and will not change path
  without a redirect.
- The source code of the registry is public at
  <https://github.com/4open-science/aicid-net>, so the registry can be mirrored or
  redeployed if this service ever shuts down.

## Versioning

This is version 1.0 of the identifier specification. Any future format change will
keep previously assigned identifiers valid.
