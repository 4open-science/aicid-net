from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class SSHKeyCreate(BaseModel):
    label: str
    public_key: str

    @field_validator("public_key")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        v = v.strip()
        parts = v.split()
        if len(parts) < 2 or parts[0] not in ("ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"):
            raise ValueError("public_key must be a valid OpenSSH public key (ssh-ed25519, ssh-rsa, or ecdsa-*)")
        return v


class SSHKeyRead(BaseModel):
    id: int
    label: str
    key_fingerprint: str
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
