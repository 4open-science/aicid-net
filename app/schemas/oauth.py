from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OAuthClientCreate(BaseModel):
    name: str
    redirect_uris: str  # newline-separated list of allowed redirect URIs
    scopes: str = "read:agent"


class OAuthClientRead(BaseModel):
    id: int
    client_id: str
    name: str
    redirect_uris: str
    scopes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OAuthClientCreated(OAuthClientRead):
    client_secret: str  # returned once on creation, not stored in plain text


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
