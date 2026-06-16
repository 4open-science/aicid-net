from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.http_signature import compute_fingerprint
from app.core.security import decode_token
from app.database import get_db
from app.models.agent import Agent
from app.models.ssh_key import SSHKey
from app.models.user import User
from app.templating import templates

router = APIRouter()


async def _get_browser_user(request: Request, db: AsyncSession) -> User | None:
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_token:
        return None
    email = decode_token(session_token, expected_type="browser_session")
    if not email:
        return None
    result = await db.execute(select(User).where(User.email == email, User.is_active.is_(True)))
    return result.scalar_one_or_none()


def _login_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=f"/auth/login?next={quote(path)}", status_code=303)


@router.get("/manage", response_class=HTMLResponse)
async def manage_dashboard(
    request: Request,
    updated: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_browser_user(request, db)
    if user is None:
        return _login_redirect("/manage")

    result = await db.execute(select(Agent).where(Agent.owner_id == user.id).order_by(Agent.created_at.desc()))
    agents = result.scalars().all()
    return templates.TemplateResponse(
        "manage.html",
        {
            "request": request,
            "user": user,
            "agents": agents,
            "updated": updated,
        },
    )


@router.post("/manage/agents/{aicid}")
async def update_agent_from_browser(
    request: Request,
    aicid: str,
    name: str = Form(...),
    human_operator: str = Form(...),
    agent_harness: str = Form(""),
    agent_type: str = Form("autonomous_agent"),
    base_model: str = Form(""),
    version: str = Form(""),
    organization: str = Form(""),
    description: str = Form(""),
    keywords: str = Form(""),
    website_url: str = Form(""),
    github_url: str = Form(""),
    paper_url: str = Form(""),
    visibility: str = Form("public"),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_browser_user(request, db)
    if user is None:
        return _login_redirect(f"/manage")

    result = await db.execute(select(Agent).where(Agent.aicid == aicid, Agent.owner_id == user.id))
    agent = result.scalar_one_or_none()
    if agent is None:
        return RedirectResponse(url="/manage", status_code=303)

    agent.name = name.strip()
    agent.human_operator = human_operator.strip()
    agent.agent_harness = agent_harness.strip() or None
    agent.agent_type = agent_type.strip() or "autonomous_agent"
    agent.base_model = base_model.strip() or None
    agent.version = version.strip() or None
    agent.organization = organization.strip() or None
    agent.description = description.strip() or None
    agent.keywords = keywords.strip() or None
    agent.website_url = website_url.strip() or None
    agent.github_url = github_url.strip() or None
    agent.paper_url = paper_url.strip() or None
    agent.visibility = visibility.strip() or "public"

    await db.commit()
    return RedirectResponse(url=f"/manage?updated={aicid}", status_code=303)


@router.get("/manage/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_browser_user(request, db)
    if user is None:
        return _login_redirect("/manage/settings")

    result = await db.execute(
        select(SSHKey).where(SSHKey.user_id == user.id).order_by(SSHKey.created_at.desc())
    )
    ssh_keys = result.scalars().all()
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "user": user, "ssh_keys": ssh_keys, "error": error},
    )


@router.post("/manage/settings/ssh-keys/add")
async def add_ssh_key_browser(
    request: Request,
    label: str = Form(...),
    public_key: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_browser_user(request, db)
    if user is None:
        return _login_redirect("/manage/settings")

    public_key = public_key.strip()
    parts = public_key.split()
    allowed_types = ("ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521")
    if len(parts) < 2 or parts[0] not in allowed_types:
        return RedirectResponse(url="/manage/settings?error=Invalid+SSH+public+key+format", status_code=303)

    try:
        fingerprint = compute_fingerprint(public_key)
    except Exception:
        return RedirectResponse(url="/manage/settings?error=Could+not+parse+public+key", status_code=303)

    existing = await db.execute(select(SSHKey).where(SSHKey.key_fingerprint == fingerprint))
    if existing.scalar_one_or_none() is not None:
        return RedirectResponse(url="/manage/settings?error=A+key+with+this+fingerprint+already+exists", status_code=303)

    db.add(SSHKey(
        user_id=user.id,
        label=label.strip(),
        public_key=public_key,
        key_fingerprint=fingerprint,
        is_active=True,
    ))
    await db.commit()
    return RedirectResponse(url="/manage/settings", status_code=303)


@router.post("/manage/settings/ssh-keys/{key_id}/delete")
async def delete_ssh_key_browser(
    request: Request,
    key_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await _get_browser_user(request, db)
    if user is None:
        return _login_redirect("/manage/settings")

    result = await db.execute(
        select(SSHKey).where(SSHKey.id == key_id, SSHKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if key:
        await db.delete(key)
        await db.commit()
    return RedirectResponse(url="/manage/settings", status_code=303)
