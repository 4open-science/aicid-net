"""RFC 9421 HTTP Message Signature verification for SSH public keys (ed25519)."""

import base64
import hashlib
import hmac
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_ssh_public_key
from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_SKEW_SECONDS = 300


def compute_fingerprint(public_key_line: str) -> str:
    """Return the SHA256 fingerprint matching `ssh-keygen -lf` output."""
    parts = public_key_line.strip().split()
    if len(parts) < 2:
        raise ValueError("Invalid SSH public key format")
    key_blob = base64.b64decode(parts[1])
    digest = hashlib.sha256(key_blob).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _parse_signature_input(header: str) -> tuple[str, list[str], dict[str, str], str]:
    """
    Parse the first label from a Signature-Input header.
    Returns (label, components, params, raw_value_for_label).
    raw_value_for_label is the structured-field value used as @signature-params.
    """
    # Match: label=(component-list)params
    m = re.match(r'(\w+)=((?:\(.*?\))(?:;[^,]*)*)', header, re.DOTALL)
    if not m:
        raise ValueError("Cannot parse Signature-Input header")
    label = m.group(1)
    raw_value = m.group(2)

    # Extract quoted component names from inner list
    paren_m = re.match(r'\(([^)]*)\)', raw_value)
    if not paren_m:
        raise ValueError("Cannot parse component list in Signature-Input")
    components = re.findall(r'"([^"]+)"', paren_m.group(1))

    # Extract params after the closing paren
    params_str = raw_value[paren_m.end():]
    params: dict[str, str] = {}
    for pm in re.finditer(r';(\w+)=(?:"([^"]*?)"|(\d+))', params_str):
        key = pm.group(1)
        val = pm.group(2) if pm.group(2) is not None else pm.group(3)
        params[key] = val

    return label, components, params, raw_value


def _build_signature_base(components: list[str], sig_params_value: str, request: Request) -> bytes:
    """Construct the RFC 9421 §2.5 signature base."""
    lines: list[str] = []
    for comp in components:
        if comp == "@method":
            lines.append(f'"@method": {request.method}')
        elif comp == "@path":
            lines.append(f'"@path": {request.url.path}')
        elif comp == "@authority":
            lines.append(f'"@authority": {request.url.hostname}')
        else:
            val = request.headers.get(comp)
            if val is None:
                raise ValueError(f"Required header '{comp}' missing from request")
            lines.append(f'"{comp}": {val}')
    lines.append(f'"@signature-params": {sig_params_value}')
    return "\n".join(lines).encode("utf-8")


async def _verify_content_digest(request: Request) -> None:
    """Check Content-Digest (sha-256) against the actual request body."""
    header = request.headers.get("content-digest")
    if header is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="content-digest header required for requests with a body")
    m = re.match(r'sha-256=:([A-Za-z0-9+/=]+):', header)
    if not m:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="content-digest must use sha-256 algorithm")
    try:
        expected = base64.b64decode(m.group(1))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid base64 in content-digest")
    body = await request.body()
    actual = hashlib.sha256(body).digest()
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Content-Digest mismatch")


async def verify_http_signature(request: Request, db: AsyncSession) -> Optional["User"]:  # type: ignore[name-defined]
    """
    Authenticate via RFC 9421 HTTP Message Signature.
    Returns User on success, None if signature headers are absent, raises 401 on failure.
    """
    from app.models.ssh_key import SSHKey
    from app.models.user import User

    sig_input_header = request.headers.get("signature-input")
    sig_header = request.headers.get("signature")

    if not sig_input_header or not sig_header:
        return None

    try:
        label, components, params, raw_value = _parse_signature_input(sig_input_header)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid Signature-Input: {e}")

    keyid = params.get("keyid")
    alg = params.get("alg")
    created_str = params.get("created")

    if not keyid or not alg or not created_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature-Input must include keyid, alg, and created")

    if alg != "ed25519":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unsupported signature algorithm '{alg}'; only ed25519 is supported")

    # Replay protection via created timestamp
    try:
        created = int(created_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="created parameter must be an integer Unix timestamp")

    now = int(time.time())
    if abs(now - created) > MAX_SKEW_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature too old or too far in future (max 5 minutes skew)")

    # Date header replay check (belt-and-suspenders)
    date_header = request.headers.get("date")
    if date_header:
        try:
            date_dt = parsedate_to_datetime(date_header)
            skew = abs(datetime.now(timezone.utc).timestamp() - date_dt.timestamp())
            if skew > MAX_SKEW_SECONDS:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Date header too old or too far in future")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Date header format")

    # Extract the base64 signature value for this label
    sig_m = re.search(rf'{re.escape(label)}=:([A-Za-z0-9+/=]+):', sig_header)
    if not sig_m:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Signature label '{label}' not found in Signature header")
    try:
        sig_bytes = base64.b64decode(sig_m.group(1))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid base64 in Signature header")

    # Verify content-digest if it is a covered component
    if "content-digest" in components:
        await _verify_content_digest(request)

    # Build signature base
    try:
        sig_base = _build_signature_base(components, raw_value, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Look up the SSH key by fingerprint
    result = await db.execute(
        select(SSHKey).where(SSHKey.key_fingerprint == keyid, SSHKey.is_active.is_(True))
    )
    ssh_key = result.scalar_one_or_none()
    if ssh_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown or inactive SSH key fingerprint")

    # Load public key and verify
    try:
        pub_key = load_ssh_public_key(ssh_key.public_key.encode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Could not load SSH public key: {e}")

    if not isinstance(pub_key, Ed25519PublicKey):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SSH key is not an ed25519 key")

    try:
        pub_key.verify(sig_bytes, sig_base)
    except InvalidSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature verification failed")

    # Record last use
    ssh_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    # Fetch and return the user
    user_result = await db.execute(
        select(User).where(User.id == ssh_key.user_id, User.is_active.is_(True))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user
