from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.email import send_email
from app.database import get_db
from app.models.auth_challenge import AuthChallenge
from app.models.user import User
from app.schemas.user import (
    EmailLoginRequest,
    EmailLoginRequestResponse,
    EmailLoginVerify,
    PasswordlessToken,
    Token,
    TokenRefresh,
    UserCreate,
    UserRead,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.core.deps import get_current_user

router = APIRouter()

AUTH_CHALLENGE_PURPOSE_API = "api_login"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/email/request", response_model=EmailLoginRequestResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_email_login(body: EmailLoginRequest, db: AsyncSession = Depends(get_db)):
    detail = "If that operator email is registered, a one-time login code has been sent."
    expires_in_seconds = settings.AUTH_CHALLENGE_EXPIRE_MINUTES * 60

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return EmailLoginRequestResponse(detail=detail, expires_in_seconds=expires_in_seconds)

    token = generate_opaque_token()
    challenge = AuthChallenge(
        email=user.email,
        purpose=AUTH_CHALLENGE_PURPOSE_API,
        token_hash=hash_opaque_token(token),
        expires_at=_utcnow() + timedelta(minutes=settings.AUTH_CHALLENGE_EXPIRE_MINUTES),
    )
    db.add(challenge)
    await db.commit()

    body_text = (
        "Use this one-time code to authenticate to the AICID API.\n\n"
        f"Code: {token}\n\n"
        f"This code expires in {settings.AUTH_CHALLENGE_EXPIRE_MINUTES} minutes and can only be used once."
    )
    await run_in_threadpool(
        send_email,
        user.email,
        "Your AICID API login code",
        body_text,
    )

    challenge_token = token if settings.ENVIRONMENT != "production" else None
    return EmailLoginRequestResponse(
        detail=detail,
        expires_in_seconds=expires_in_seconds,
        challenge_token=challenge_token,
    )


@router.post("/email/verify", response_model=PasswordlessToken)
async def verify_email_login(body: EmailLoginVerify, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == hash_opaque_token(body.token),
            AuthChallenge.purpose == AUTH_CHALLENGE_PURPOSE_API,
        )
    )
    challenge = result.scalar_one_or_none()
    now = _utcnow()
    if (
        challenge is None
        or challenge.used_at is not None
        or _as_utc(challenge.expires_at) < now
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired login challenge")

    result = await db.execute(select(User).where(User.email == challenge.email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    challenge.used_at = now
    await db.commit()

    expires_in = settings.PASSWORDLESS_API_TOKEN_EXPIRE_MINUTES * 60
    return PasswordlessToken(
        access_token=create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.PASSWORDLESS_API_TOKEN_EXPIRE_MINUTES),
            auth_method="email",
        ),
        expires_in_seconds=expires_in,
    )


@router.post("/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(user.email, auth_method="password"),
        refresh_token=create_refresh_token(user.email),
    )


@router.post("/refresh", response_model=Token)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    email = decode_token(body.refresh_token, expected_type="refresh")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return Token(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
    )


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
