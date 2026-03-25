from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models.agent import Agent
from app.models.work import Work
from app.models.employment import Employment
from app.models.funding import Funding

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


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
