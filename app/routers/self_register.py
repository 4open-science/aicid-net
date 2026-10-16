"""Agent self-registration and the later human claim of a self-registered agent.

``POST /api/register``                 an agent registers itself (no auth), is published at once
``POST /api/agents/{aicid}/claim``     the agent asks AICID to e-mail a claim link to its human operator
``GET|POST /claim/{aicid}``            the human confirms the link and becomes the verified operator
"""

import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.email import EmailDeliveryError, send_email
from app.core.security import create_browser_session_token, generate_opaque_token, hash_opaque_token
from app.core.spam import blocked_email_domains, spam_reason
from app.database import get_db
from app.models.agent import MODERATION_PENDING_EMAIL, REGISTRATION_SELF, Agent
from app.models.auth_challenge import AuthChallenge
from app.models.user import User
from app.routers.agents import _unique_aicid
from app.routers.auth import _as_utc, _create_auth_challenge, _set_browser_session_cookie, _utcnow
from app.templating import templates

router = APIRouter()
logger = logging.getLogger(__name__)

# owner of every self-registered agent until a human claims it; inactive, so nobody can log in as it
UNCLAIMED_OWNER_EMAIL = "unclaimed@aicid.invalid"
REJECTED_DETAIL = "This registration could not be accepted. If you believe this is a mistake, contact team@aicid.net."


def _claim_purpose(aicid: str) -> str:
    return f"claim:{aicid}"


class SelfRegister(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    human_operator: Optional[str] = Field(default=None, max_length=255)
    operator_email: Optional[EmailStr] = Field(
        default=None, description="Unverified hint, never published; used as default claim address."
    )
    operator_telegram: Optional[str] = Field(default=None, max_length=255)
    operator_x: Optional[str] = Field(default=None, max_length=255)
    agent_type: str = Field(default="autonomous_agent", max_length=50)
    agent_harness: Optional[str] = Field(default=None, max_length=255)
    base_model: Optional[str] = Field(default=None, max_length=255)
    version: Optional[str] = Field(default=None, max_length=100)
    organization: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    keywords: Optional[str] = Field(default=None, max_length=1000)


class SelfRegisterResponse(BaseModel):
    aicid: str
    agent_secret: str
    profile_url: str
    claim_url: str
    note: str


class ClaimRequest(BaseModel):
    operator_email: Optional[EmailStr] = None


async def _unclaimed_owner(db: AsyncSession) -> User:
    user = (await db.execute(select(User).where(User.email == UNCLAIMED_OWNER_EMAIL))).scalar_one_or_none()
    if user is None:
        user = User(email=UNCLAIMED_OWNER_EMAIL, full_name="Unclaimed", hashed_password=None, is_active=False)
        db.add(user)
        await db.flush()
    return user


@router.post("/api/register", response_model=SelfRegisterResponse, status_code=status.HTTP_201_CREATED)
async def self_register(body: SelfRegister, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.client.host if request.client else "?"
    fields = body.model_dump(exclude={"operator_email", "agent_type"})
    fields["agent_name"] = fields.pop("name")
    reason = spam_reason(fields, body.operator_email)
    if reason:
        logger.warning("Rejected self-registration as spam (%s). ip=%s name=%r", reason, client_ip, body.name)
        raise HTTPException(status_code=422, detail=REJECTED_DETAIL)

    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent_total = await db.scalar(select(func.count()).select_from(Agent).where(Agent.created_at >= hour_ago))
    recent_self = await db.scalar(
        select(func.count())
        .select_from(Agent)
        .where(Agent.created_at >= hour_ago, Agent.registration_source == REGISTRATION_SELF)
    )
    if (recent_total or 0) >= settings.REGISTRATION_LIMIT_PER_HOUR or (
        recent_self or 0
    ) >= settings.SELF_REGISTRATION_LIMIT_PER_HOUR:
        logger.warning("Self-registration rate limit hit. ip=%s", client_ip)
        raise HTTPException(status_code=429, detail="Too many registrations right now. Try again in an hour.")

    owner = await _unclaimed_owner(db)
    secret = generate_opaque_token()
    aicid = await _unique_aicid(db)
    agent = Agent(
        owner_id=owner.id,
        aicid=aicid,
        name=body.name,
        human_operator=(body.human_operator or "").strip() or None,
        operator_email_hint=body.operator_email,
        operator_telegram=body.operator_telegram,
        operator_x=body.operator_x,
        agent_type=body.agent_type,
        agent_harness=body.agent_harness,
        base_model=body.base_model,
        version=body.version,
        organization=body.organization,
        description=body.description,
        keywords=body.keywords,
        registration_source=REGISTRATION_SELF,
        agent_secret_hash=hash_opaque_token(secret),
    )
    db.add(agent)
    await db.commit()

    try:
        await run_in_threadpool(
            send_email,
            settings.TEAM_EMAIL,
            f"New self-registration: {aicid}",
            f"AICID: {aicid}\nName: {agent.name}\nOperator (declared): {agent.human_operator}\n"
            f"IP: {client_ip}\nStatus: published, unclaimed\n\nIf this is spam: python -m app.admin spam {aicid}",
        )
    except EmailDeliveryError:
        pass  # best-effort; already logged

    base = settings.APP_URL.rstrip("/")
    return SelfRegisterResponse(
        aicid=aicid,
        agent_secret=secret,
        profile_url=f"{base}/agents/{aicid}",
        claim_url=f"{base}/api/agents/{aicid}/claim",
        note="Store agent_secret now: it is shown once and authorizes the claim request. "
        "The profile is marked self-registered until a human operator claims it.",
    )


@router.post("/api/agents/{aicid}/claim", status_code=status.HTTP_202_ACCEPTED)
async def request_claim(
    aicid: str,
    body: ClaimRequest,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    agent = (await db.execute(select(Agent).where(Agent.aicid == aicid))).scalar_one_or_none()
    scheme, _, secret = (authorization or "").partition(" ")
    if (
        agent is None
        or agent.registration_source != REGISTRATION_SELF
        or not agent.agent_secret_hash
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(agent.agent_secret_hash, hash_opaque_token(secret.strip()))
    ):
        # same answer for unknown agent and wrong secret: no way to probe which AICIDs exist
        raise HTTPException(status_code=403, detail="Invalid agent secret")
    if agent.claimed_at is not None:
        raise HTTPException(status_code=409, detail="Agent already claimed")

    email = body.operator_email or agent.operator_email_hint
    if not email:
        raise HTTPException(status_code=422, detail="operator_email is required (none was given at registration)")
    email = str(email).lower()
    if email.rsplit("@", 1)[-1] in blocked_email_domains():
        raise HTTPException(status_code=422, detail=REJECTED_DETAIL)

    purpose = _claim_purpose(aicid)
    since = _utcnow() - timedelta(minutes=settings.CLAIM_EMAIL_INTERVAL_MINUTES)
    recent = await db.scalar(
        select(func.count())
        .select_from(AuthChallenge)
        .where(AuthChallenge.purpose == purpose, AuthChallenge.created_at >= since)
    )
    if recent:
        raise HTTPException(status_code=429, detail="A claim e-mail was sent recently. Try again later.")

    token = await _create_auth_challenge(
        email=email, purpose=purpose, db=db, expire_minutes=settings.CLAIM_EXPIRE_MINUTES
    )
    link = f"{settings.APP_URL.rstrip('/')}/claim/{aicid}?token={token}"
    try:
        # deliberately carries no agent-supplied text, so this cannot be used to mail arbitrary content
        await run_in_threadpool(
            send_email,
            email,
            f"Claim AI agent {aicid} on AICID",
            f"An AI agent registered itself on AICID as {aicid} and named this address as its human operator.\n\n"
            f"To become its verified operator, open this one-time link:\n{link}\n\n"
            f"The link expires in {settings.CLAIM_EXPIRE_MINUTES // 60} hours.\n\n"
            "If you do not recognize this agent, ignore this email: nothing will change.",
        )
    except EmailDeliveryError:
        raise HTTPException(status_code=503, detail="Could not deliver the claim e-mail. Try again later.")
    response = {"status": "claim e-mail sent", "email": email}
    if settings.ENVIRONMENT != "production":
        response["challenge_token"] = token
    return response


async def _load_claim(aicid: str, token: str, db: AsyncSession) -> tuple[Agent, AuthChallenge] | str:
    """The agent and challenge for a valid claim link, or the reason it is not valid."""
    agent = (await db.execute(select(Agent).where(Agent.aicid == aicid))).scalar_one_or_none()
    challenge = (
        await db.execute(
            select(AuthChallenge).where(
                AuthChallenge.token_hash == hash_opaque_token(token),
                AuthChallenge.purpose == _claim_purpose(aicid),
            )
        )
    ).scalar_one_or_none()
    if agent is None or challenge is None or _as_utc(challenge.expires_at) < _utcnow():
        return "That claim link is invalid or expired. Ask the agent to send a new one."
    if challenge.used_at is not None or agent.claimed_at is not None:
        return "That claim link was already used."
    return agent, challenge


def _claim_page(request: Request, aicid: str, token: str, loaded, db_user: User | None, error=None, code=200):
    ctx = {"aicid": aicid, "token": token, "error": None, "email": None, "full_name": "", "need_name": False}
    if isinstance(loaded, str):
        ctx["error"] = loaded
    else:
        _, challenge = loaded
        ctx.update(
            email=challenge.email,
            full_name=db_user.full_name if db_user else "",
            need_name=db_user is None,
            error=error,
        )
    return templates.TemplateResponse(request, "claim.html", ctx, status_code=code)


@router.get("/claim/{aicid}", response_class=HTMLResponse)
async def claim_page(request: Request, aicid: str, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    loaded = await _load_claim(aicid, token, db)
    user = None
    if not isinstance(loaded, str):
        user = (await db.execute(select(User).where(User.email == loaded[1].email))).scalar_one_or_none()
    return _claim_page(request, aicid, token, loaded, user, code=401 if isinstance(loaded, str) else 200)


@router.post("/claim/{aicid}")
async def claim_confirm(
    request: Request,
    aicid: str,
    token: str = Form(...),
    full_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    loaded = await _load_claim(aicid, token, db)
    if isinstance(loaded, str):
        return _claim_page(request, aicid, token, loaded, None, code=401)
    agent, challenge = loaded

    user = (await db.execute(select(User).where(User.email == challenge.email))).scalar_one_or_none()
    if user is not None and not user.is_active:
        return _claim_page(request, aicid, token, "That account is disabled.", None, code=403)
    if user is None:
        name = " ".join((full_name or "").split())
        if not name:
            return _claim_page(request, aicid, token, loaded, None, error="Your full name is required.", code=422)
        user = User(email=challenge.email, full_name=name, hashed_password=None)
        db.add(user)
        await db.flush()

    challenge.used_at = _utcnow()
    agent.owner_id = user.id
    agent.claimed_at = _utcnow()
    agent.human_operator = user.full_name
    # the human also just proved control of this e-mail: publish registrations awaiting that proof
    await db.execute(
        update(Agent)
        .where(Agent.owner_id == user.id, Agent.moderation_status == MODERATION_PENDING_EMAIL)
        .values(moderation_status=None)
    )
    await db.commit()

    response = RedirectResponse(url=f"/agents/{aicid}", status_code=303)
    _set_browser_session_cookie(
        response,
        create_browser_session_token(
            user.email, expires_delta=timedelta(minutes=settings.BROWSER_SESSION_EXPIRE_MINUTES)
        ),
    )
    return response
