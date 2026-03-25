"""
OAuth2 Authorization Code flow.

Endpoints:
  POST /oauth/clients           — register a new client (requires user auth)
  GET  /oauth/clients           — list my clients
  GET  /oauth/authorize         — show authorization page (GET) or redirect with code (POST)
  POST /oauth/token             — exchange code for access token
"""
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.oauth import OAuthAuthCode, OAuthClient, OAuthToken
from app.models.user import User
from app.schemas.oauth import OAuthClientCreate, OAuthClientCreated, OAuthClientRead, OAuthTokenResponse
from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password, decode_token

router = APIRouter()
templates = Jinja2Templates(directory="templates")

VALID_SCOPES = {"read:agent", "write:agent", "read:works", "write:works"}
TOKEN_LIFETIME_SECONDS = 3600


def _validate_scopes(requested: str) -> str:
    parts = set(requested.split())
    invalid = parts - VALID_SCOPES
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid scopes: {invalid}")
    return " ".join(parts)


@router.post("/clients", response_model=OAuthClientCreated, status_code=status.HTTP_201_CREATED)
async def register_client(
    body: OAuthClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_scopes(body.scopes)
    raw_secret = secrets.token_urlsafe(32)
    client_id = secrets.token_urlsafe(16)
    client = OAuthClient(
        owner_id=current_user.id,
        client_id=client_id,
        client_secret_hash=hash_password(raw_secret),
        name=body.name,
        redirect_uris=body.redirect_uris,
        scopes=body.scopes,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return OAuthClientCreated(
        id=client.id,
        client_id=client.client_id,
        name=client.name,
        redirect_uris=client.redirect_uris,
        scopes=client.scopes,
        created_at=client.created_at,
        client_secret=raw_secret,
    )


@router.get("/clients", response_model=list[OAuthClientRead])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(OAuthClient).where(OAuthClient.owner_id == current_user.id))
    return result.scalars().all()


@router.get("/authorize", response_class=HTMLResponse)
async def authorize_page(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query("read:agent"),
    state: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Show the authorization consent page."""
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only response_type=code is supported")

    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=400, detail="Unknown client_id")
    if redirect_uri not in client.redirect_uris.splitlines():
        raise HTTPException(status_code=400, detail="redirect_uri not allowed")

    return templates.TemplateResponse(
        "oauth_authorize.html",
        {
            "request": request,
            "client": client,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        },
    )


@router.post("/authorize")
async def authorize_submit(
    response_type: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    scope: str = Form("read:agent"),
    state: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """User submits credentials to approve the OAuth request."""
    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    client = result.scalar_one_or_none()
    if client is None or redirect_uri not in client.redirect_uris.splitlines():
        raise HTTPException(status_code=400, detail="Invalid client or redirect_uri")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    from app.core.security import verify_password as vp
    if not user or not vp(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    code = secrets.token_urlsafe(32)
    auth_code = OAuthAuthCode(
        client_id=client.id,
        user_id=user.id,
        code=code,
        scopes=scope,
        redirect_uri=redirect_uri,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(auth_code)
    await db.commit()

    params = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(f"{redirect_uri}?{urlencode(params)}", status_code=302)


@router.post("/token", response_model=OAuthTokenResponse)
async def token_exchange(
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail="Only authorization_code grant is supported")

    result = await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))
    client = result.scalar_one_or_none()
    if client is None or not verify_password(client_secret, client.client_secret_hash):
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    result = await db.execute(select(OAuthAuthCode).where(OAuthAuthCode.code == code))
    auth_code = result.scalar_one_or_none()
    if (
        auth_code is None
        or auth_code.used
        or auth_code.client_id != client.id
        or auth_code.redirect_uri != redirect_uri
        or auth_code.expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired authorization code")

    auth_code.used = True
    access_token = secrets.token_urlsafe(48)
    token = OAuthToken(
        client_id=client.id,
        user_id=auth_code.user_id,
        access_token=access_token,
        scopes=auth_code.scopes,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=TOKEN_LIFETIME_SECONDS),
    )
    db.add(token)
    await db.commit()

    return OAuthTokenResponse(
        access_token=access_token,
        expires_in=TOKEN_LIFETIME_SECONDS,
        scope=auth_code.scopes,
    )
