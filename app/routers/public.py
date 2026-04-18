from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.aicid_id import generate_aicid
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.models.work import Work
from app.models.employment import Employment
from app.models.funding import Funding

router = APIRouter()
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"
_SKILL_DOC_PATH = _PROJECT_ROOT / "docs" / "SKILL.md"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/SKILL.md", response_class=FileResponse)
async def skill_md():
    return FileResponse(_SKILL_DOC_PATH, media_type="text/markdown")


@router.get("/agents/{aicid}", response_class=HTMLResponse)
async def public_profile(request: Request, aicid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None or agent.visibility == "private":
        raise HTTPException(status_code=404, detail="Agent not found")

    works = (await db.execute(select(Work).where(Work.agent_id == agent.id))).scalars().all()
    employments = (
        await db.execute(select(Employment).where(Employment.agent_id == agent.id))
    ).scalars().all()
    fundings = (
        await db.execute(select(Funding).where(Funding.agent_id == agent.id))
    ).scalars().all()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "agent": agent,
            "works": works,
            "employments": employments,
            "fundings": fundings,
        },
    )


@router.get("/agents/{aicid}/json")
async def public_profile_json(aicid: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None or agent.visibility == "private":
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
        "base_model": agent.base_model,
        "version": agent.version,
        "organization": agent.organization,
        "description": agent.description,
        "keywords": agent.keywords.split(",") if agent.keywords else [],
        "website_url": agent.website_url,
        "github_url": agent.github_url,
        "paper_url": agent.paper_url,
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
    return templates.TemplateResponse("register.html", {"request": request, "error": None, "values": {}})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent_name: str = Form(...),
    human_operator: str = Form(...),
    operator_email: str = Form(...),
    operator_password: str = Form(...),
    base_model: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    agent_harness: Optional[str] = Form(None),
):
    values = {
        "agent_name": agent_name,
        "human_operator": human_operator,
        "operator_email": operator_email,
        "base_model": base_model or "",
        "version": version or "",
        "agent_harness": agent_harness or "",
    }

    # Get or create user
    result = await db.execute(select(User).where(User.email == operator_email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=operator_email,
            full_name=human_operator,
            hashed_password=hash_password(operator_password),
        )
        db.add(user)
        await db.flush()
    elif not user.hashed_password or not verify_password(operator_password, user.hashed_password):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Registration failed. Please check your credentials.", "values": values},
            status_code=400,
        )

    aicid = await _unique_aicid(db)
    agent = Agent(
        owner_id=user.id,
        aicid=aicid,
        name=agent_name,
        human_operator=human_operator or None,
        agent_harness=agent_harness or None,
        base_model=base_model or None,
        version=version or None,
    )
    db.add(agent)
    await db.commit()

    return RedirectResponse(url=f"/agents/{aicid}", status_code=303)


@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})


@router.get("/search-page", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    agents = []
    if q:
        like = f"%{q}%"
        result = await db.execute(
            select(Agent)
            .where(
                Agent.visibility == "public",
                or_(
                    Agent.name.ilike(like),
                    Agent.keywords.ilike(like),
                    Agent.organization.ilike(like),
                    Agent.description.ilike(like),
                ),
            )
            .limit(50)
        )
        agents = result.scalars().all()

    return templates.TemplateResponse(
        "search.html", {"request": request, "q": q or "", "agents": agents}
    )
