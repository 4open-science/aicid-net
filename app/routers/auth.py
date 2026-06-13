from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.email import send_email
from app.templating import templates
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
    create_browser_session_token,
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
AUTH_CHALLENGE_PURPOSE_BROWSER = "browser_login"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _safe_next_path(next_path: str | None) -> str:
    if not next_path or not next_path.startswith("/") or next_path.startswith("//"):
        return "/manage"
    return next_path


async def _get_active_user(email: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def _create_auth_challenge(
    *,
    email: str,
    purpose: str,
    db: AsyncSession,
) -> str:
    token = generate_opaque_token()
    challenge = AuthChallenge(
        email=email,
        purpose=purpose,
        token_hash=hash_opaque_token(token),
        expires_at=_utcnow() + timedelta(minutes=settings.AUTH_CHALLENGE_EXPIRE_MINUTES),
    )
    db.add(challenge)
    await db.commit()
    return token


async def _consume_auth_challenge(*, token: str, purpose: str, db: AsyncSession) -> User:
    result = await db.execute(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == hash_opaque_token(token),
            AuthChallenge.purpose == purpose,
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

    user = await _get_active_user(challenge.email, db)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    challenge.used_at = now
    await db.commit()
    return user


def _build_browser_login_email(token: str, next_path: str) -> str:
    verify_url = f"{settings.APP_URL.rstrip('/')}/auth/verify?token={token}&next={next_path}"
    return (
        "Use this one-time link or code to open an authenticated AICID browser session.\n\n"
        f"Link: {verify_url}\n"
        f"Code: {token}\n\n"
        f"This login expires in {settings.AUTH_CHALLENGE_EXPIRE_MINUTES} minutes and can only be used once."
    )


def _render_login_page(
    request: Request,
    *,
    next_path: str,
    message: str | None = None,
    error: str | None = None,
    email: str = "",
    challenge_token: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        "auth_login.html",
        {
            "request": request,
            "next_path": next_path,
            "message": message,
            "error": error,
            "email": email,
            "challenge_token": challenge_token,
        },
        status_code=status_code,
    )


def _set_browser_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.BROWSER_SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
        path="/",
    )


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

    user = await _get_active_user(body.email, db)
    if user is None:
        return EmailLoginRequestResponse(detail=detail, expires_in_seconds=expires_in_seconds)

    token = await _create_auth_challenge(email=user.email, purpose=AUTH_CHALLENGE_PURPOSE_API, db=db)

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
    user = await _consume_auth_challenge(token=body.token, purpose=AUTH_CHALLENGE_PURPOSE_API, db=db)

    expires_in = settings.PASSWORDLESS_API_TOKEN_EXPIRE_MINUTES * 60
    return PasswordlessToken(
        access_token=create_access_token(
            user.email,
            expires_delta=timedelta(minutes=settings.PASSWORDLESS_API_TOKEN_EXPIRE_MINUTES),
            auth_method="email",
        ),
        expires_in_seconds=expires_in,
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = Query("/manage")):
    return _render_login_page(request, next_path=_safe_next_path(next))


@router.post("/browser/request", response_class=HTMLResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_browser_login(
    request: Request,
    email: str = Form(...),
    next: str = Form("/manage"),
    db: AsyncSession = Depends(get_db),
):
    next_path = _safe_next_path(next)
    detail = "If that operator email is registered, a one-time login email has been sent."
    user = await _get_active_user(email, db)

    challenge_token = None
    if user is not None:
        token = await _create_auth_challenge(email=user.email, purpose=AUTH_CHALLENGE_PURPOSE_BROWSER, db=db)
        await run_in_threadpool(
            send_email,
            user.email,
            "Your AICID browser login link",
            _build_browser_login_email(token, next_path),
        )
        if settings.ENVIRONMENT != "production":
            challenge_token = token

    return _render_login_page(
        request,
        next_path=next_path,
        message=detail,
        email=email,
        challenge_token=challenge_token,
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.post("/browser/verify")
async def verify_browser_code(
    request: Request,
    token: str = Form(...),
    next: str = Form("/manage"),
    db: AsyncSession = Depends(get_db),
):
    next_path = _safe_next_path(next)
    try:
        user = await _consume_auth_challenge(token=token, purpose=AUTH_CHALLENGE_PURPOSE_BROWSER, db=db)
    except HTTPException:
        return _render_login_page(
            request,
            next_path=next_path,
            error="That login code is invalid or expired. Request a new one.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url=next_path, status_code=303)
    _set_browser_session_cookie(
        response,
        create_browser_session_token(
            user.email,
            expires_delta=timedelta(minutes=settings.BROWSER_SESSION_EXPIRE_MINUTES),
        ),
    )
    return response


@router.get("/verify")
async def verify_browser_link(
    request: Request,
    token: str = Query(...),
    next: str = Query("/manage"),
    db: AsyncSession = Depends(get_db),
):
    next_path = _safe_next_path(next)
    try:
        user = await _consume_auth_challenge(token=token, purpose=AUTH_CHALLENGE_PURPOSE_BROWSER, db=db)
    except HTTPException:
        return _render_login_page(
            request,
            next_path=next_path,
            error="That login link is invalid or expired. Request a new one.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url=next_path, status_code=303)
    _set_browser_session_cookie(
        response,
        create_browser_session_token(
            user.email,
            expires_delta=timedelta(minutes=settings.BROWSER_SESSION_EXPIRE_MINUTES),
        ),
    )
    return response


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return response


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
