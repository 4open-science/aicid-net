import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

import markdown
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.aicid_id import generate_aicid
from app.core.email import EmailDeliveryError, send_email
from app.core.spam import spam_reason
from app.database import get_db
from app.models.agent import MODERATION_PENDING_EMAIL, Agent
from app.models.employment import Employment
from app.models.funding import Funding
from app.models.user import User
from app.models.work import Work
from app.routers.auth import AUTH_CHALLENGE_PURPOSE_BROWSER, _create_auth_challenge
from app.routers.manage import _get_browser_user
from app.templating import templates

router = APIRouter()
logger = logging.getLogger(__name__)
REGISTRATION_REJECTED_DETAIL = (
    "This registration could not be accepted. If you believe this is a mistake, contact team@aicid.net."
)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILL_DOC_PATH = _PROJECT_ROOT / "docs" / "SKILL.md"
_IDENTIFIER_SPEC_PATH = _PROJECT_ROOT / "docs" / "identifier.md"


def _render_skill_doc() -> tuple[str, list[dict]]:
    """docs/SKILL.md as HTML (a repo-owned, trusted file) plus its section headings for the nav."""
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc"],
        extension_configs={"toc": {"baselevel": 2}},  # the document's H1 becomes an H2 of the docs page
    )
    html = md.convert(_SKILL_DOC_PATH.read_text(encoding="utf-8"))
    tokens = md.toc_tokens  # type: ignore[attr-defined]
    sections = tokens[0]["children"] if len(tokens) == 1 else tokens
    return html, [{"id": t["id"], "name": t["name"]} for t in sections]


def _normalized_name(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _verified_operator_orcid_url(agent: Agent, owner: User | None) -> str | None:
    if owner is None or not owner.orcid_verified or not owner.orcid_id:
        return None
    if not _normalized_name(agent.human_operator):
        return None
    if _normalized_name(agent.human_operator) != _normalized_name(owner.full_name):
        return None
    return f"https://orcid.org/{owner.orcid_id}"


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {})


@router.get("/SKILL.md", response_class=FileResponse)
async def skill_md():
    return FileResponse(_SKILL_DOC_PATH, media_type="text/markdown")


def _publicly_visible(agent: Agent | None) -> bool:
    return agent is not None and agent.visibility != "private" and agent.moderation_status is None


@router.get("/agents/{aicid}", response_class=HTMLResponse)
async def public_profile(request: Request, aicid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None or not _publicly_visible(agent):
        raise HTTPException(status_code=404, detail="Agent not found")

    works = (await db.execute(select(Work).where(Work.agent_id == agent.id))).scalars().all()
    employments = (
        await db.execute(select(Employment).where(Employment.agent_id == agent.id))
    ).scalars().all()
    fundings = (
        await db.execute(select(Funding).where(Funding.agent_id == agent.id))
    ).scalars().all()

    owner = (await db.execute(select(User).where(User.id == agent.owner_id))).scalar_one_or_none()

    verified_operator_orcid_url = _verified_operator_orcid_url(agent, owner)

    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "agent": agent,
            "works": works,
            "employments": employments,
            "fundings": fundings,
            "orcid_verified": verified_operator_orcid_url is not None,
            "operator_orcid_url": verified_operator_orcid_url,
            "orcid_unverified": agent.orcid_unverified,
        },
    )


@router.get("/agents/{aicid}/json")
async def public_profile_json(aicid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None or not _publicly_visible(agent):
        raise HTTPException(status_code=404, detail="Agent not found")

    works = (await db.execute(select(Work).where(Work.agent_id == agent.id))).scalars().all()
    employments = (
        await db.execute(select(Employment).where(Employment.agent_id == agent.id))
    ).scalars().all()
    fundings = (
        await db.execute(select(Funding).where(Funding.agent_id == agent.id))
    ).scalars().all()

    return {
        "aicid": agent.aicid,
        "name": agent.name,
        "agent_type": agent.agent_type,
        "human_operator": agent.human_operator,
        "orcid_unverified": agent.orcid_unverified,
        "operator_telegram": agent.operator_telegram,
        "operator_x": agent.operator_x,
        "registration_source": agent.registration_source,
        "claimed": agent.claimed_at is not None,
        "claimed_at": agent.claimed_at.isoformat() if agent.claimed_at else None,
        "base_model": agent.base_model,
        "version": agent.version,
        "organization": agent.organization,
        "description": agent.description,
        "keywords": agent.keywords.split(",") if agent.keywords else [],
        "website_url": agent.website_url,
        "github_url": agent.github_url,
        "paper_url": agent.paper_url,
        "agent_email": agent.agent_email,
        "agent_telegram": agent.agent_telegram,
        "agent_discord": agent.agent_discord,
        "agent_twitter": agent.agent_twitter,
        "agent_url": agent.agent_url,
        "visibility": agent.visibility,
        "created_at": agent.created_at.isoformat(),
        "works": [
            {
                "put_code": w.put_code,
                "work_type": w.work_type,
                "title": w.title,
                "doi": w.doi,
                "url": w.url,
                "journal": w.journal,
                "published_date": w.published_date.isoformat() if w.published_date else None,
            }
            for w in works
        ],
        "employments": [
            {
                "organization": e.organization,
                "role": e.role,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "end_date": e.end_date.isoformat() if e.end_date else None,
            }
            for e in employments
        ],
        "fundings": [
            {
                "title": f.title,
                "funder": f.funder,
                "grant_number": f.grant_number,
                "url": f.url,
            }
            for f in fundings
        ],
    }


async def _unique_aicid(db: AsyncSession) -> str:
    for _ in range(10):
        candidate = generate_aicid()
        result = await db.execute(select(Agent).where(Agent.aicid == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("Could not generate a unique AICID after 10 attempts")


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None, "values": {}})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent_name: str = Form(...),
    human_operator: str = Form(...),
    operator_email: str = Form(...),
    base_model: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    agent_harness: Optional[str] = Form(None),
    contact_website: Optional[str] = Form(None),  # honeypot: hidden from humans, left empty by scripts
):
    values = {
        "agent_name": agent_name,
        "human_operator": human_operator,
        "operator_email": operator_email,
        "base_model": base_model or "",
        "version": version or "",
        "agent_harness": agent_harness or "",
    }

    def form_error(message: str, status_code: int) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "register.html", {"error": message, "values": values}, status_code=status_code
        )

    if not human_operator or not human_operator.strip():
        return form_error("Operator name is required.", 422)

    client_ip = request.client.host if request.client else "?"
    reason = "honeypot field filled" if contact_website else spam_reason(
        {
            "agent_name": agent_name,
            "human_operator": human_operator,
            "base_model": base_model,
            "version": version,
            "agent_harness": agent_harness,
        },
        operator_email,
    )
    if reason:
        logger.warning("Rejected registration as spam (%s). ip=%s email=%s name=%r", reason, client_ip, operator_email, agent_name)
        return form_error(REGISTRATION_REJECTED_DETAIL, 422)

    # Group public registrations by operator email without requiring account auth.
    result = await db.execute(select(User).where(User.email == operator_email))
    user = result.scalar_one_or_none()

    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent_total = await db.scalar(select(func.count()).select_from(Agent).where(Agent.created_at >= hour_ago))
    recent_for_email: int | None = 0
    if user is not None:
        recent_for_email = await db.scalar(
            select(func.count()).select_from(Agent).where(Agent.owner_id == user.id, Agent.created_at >= hour_ago)
        )
    if (recent_total or 0) >= settings.REGISTRATION_LIMIT_PER_HOUR or (
        recent_for_email or 0
    ) >= settings.REGISTRATION_LIMIT_PER_EMAIL_PER_HOUR:
        logger.warning("Registration rate limit hit. ip=%s email=%s", client_ip, operator_email)
        return form_error("Too many registrations right now. Please try again in an hour.", 429)

    if user is None:
        user = User(
            email=operator_email,
            full_name=human_operator,
            hashed_password=None,
        )
        db.add(user)
        await db.flush()

    # Publish immediately only when the browser is already logged in as this operator;
    # otherwise anyone could publish under any e-mail address.
    session_user = await _get_browser_user(request, db)
    confirmed = session_user is not None and session_user.id == user.id

    aicid = await _unique_aicid(db)
    agent = Agent(
        owner_id=user.id,
        aicid=aicid,
        name=agent_name,
        human_operator=human_operator.strip(),
        agent_harness=agent_harness or None,
        base_model=base_model or None,
        version=version or None,
        moderation_status=None if confirmed else MODERATION_PENDING_EMAIL,
    )
    db.add(agent)
    await db.commit()

    await _notify_team_of_registration(agent, operator_email, client_ip, confirmed)

    if confirmed:
        return RedirectResponse(url=f"/agents/{aicid}", status_code=303)

    token = await _create_auth_challenge(
        email=user.email,
        purpose=AUTH_CHALLENGE_PURPOSE_BROWSER,
        db=db,
        expire_minutes=settings.REGISTRATION_CONFIRM_EXPIRE_MINUTES,
    )
    email_sent = True
    try:
        await run_in_threadpool(
            send_email,
            user.email,
            f"Confirm your AICID registration {aicid}",
            _build_registration_confirm_email(aicid, token),
        )
    except EmailDeliveryError:
        email_sent = False
    return templates.TemplateResponse(
        request,
        "register_pending.html",
        {
            "aicid": aicid,
            "email": user.email,
            "email_sent": email_sent,
            "expire_hours": settings.REGISTRATION_CONFIRM_EXPIRE_MINUTES // 60,
            "challenge_token": token if settings.ENVIRONMENT != "production" else None,
        },
        status_code=202,
    )


def _build_registration_confirm_email(aicid: str, token: str) -> str:
    # deliberately carries no submitted text, so the form cannot be used to mail arbitrary content
    verify_url = f"{settings.APP_URL.rstrip('/')}/auth/verify?token={token}&next=/agents/{aicid}"
    return (
        f"An AI agent was registered on AICID with this address as its human operator.\n\n"
        f"To publish {aicid}, open this one-time link:\n{verify_url}\n\n"
        f"The link expires in {settings.REGISTRATION_CONFIRM_EXPIRE_MINUTES // 60} hours. "
        "You can also publish it later by logging in at "
        f"{settings.APP_URL.rstrip('/')}/auth/login with this address.\n\n"
        "If you did not register this agent, ignore this email: nothing will be published."
    )


async def _notify_team_of_registration(agent: Agent, operator_email: str, client_ip: str, confirmed: bool) -> None:
    status_line = "published (logged-in operator)" if confirmed else "pending e-mail confirmation"
    try:
        await run_in_threadpool(
            send_email,
            settings.TEAM_EMAIL,
            f"New web registration: {agent.aicid}",
            f"AICID: {agent.aicid}\nName: {agent.name}\nOperator: {agent.human_operator}\n"
            f"E-mail: {operator_email}\nIP: {client_ip}\nStatus: {status_line}\n\n"
            f"If this is spam: python -m app.admin spam {agent.aicid}",
        )
    except EmailDeliveryError:
        pass  # best-effort; already logged


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    skill_html, skill_nav = _render_skill_doc()
    return templates.TemplateResponse(request, "docs.html", {"skill_html": skill_html, "skill_nav": skill_nav})


@router.get("/docs/identifier", response_class=FileResponse)
async def identifier_spec():
    return FileResponse(_IDENTIFIER_SPEC_PATH, media_type="text/markdown")


@router.get("/search-page", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if q:
        like = f"%{q}%"
        result = await db.execute(
            select(Agent)
            .where(
                Agent.visibility == "public",
                Agent.moderation_status.is_(None),
                or_(
                    Agent.name.ilike(like),
                    Agent.keywords.ilike(like),
                    Agent.organization.ilike(like),
                    Agent.description.ilike(like),
                ),
            )
            .order_by(Agent.created_at.desc())
            .limit(50)
        )
        agents = result.scalars().all()
        latest_agents: Sequence[Agent] = []
    else:
        agents = []
        result = await db.execute(
            select(Agent)
            .where(Agent.visibility == "public", Agent.moderation_status.is_(None))
            .order_by(Agent.created_at.desc())
            .limit(10)
        )
        latest_agents = result.scalars().all()

    return templates.TemplateResponse(
        request, "search.html", {"q": q or "", "agents": agents, "latest_agents": latest_agents}
    )
