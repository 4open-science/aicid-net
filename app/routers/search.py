from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aicid_id import parse_aicid
from app.database import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentRead

router = APIRouter()


def agent_text_filter(q: str):
    """Free-text match shared by /search and /search-page.

    A query that is a whole AICID in any accepted display form (see
    parse_aicid) matches that identifier exactly; anything else is a
    case-insensitive substring match, AICID included.
    """
    aicid = parse_aicid(q)
    if aicid is not None:
        return Agent.aicid == aicid
    like = f"%{q}%"
    return or_(
        Agent.aicid.ilike(like),
        Agent.name.ilike(like),
        Agent.keywords.ilike(like),
        Agent.organization.ilike(like),
        Agent.description.ilike(like),
        Agent.human_operator.ilike(like),
    )


@router.get("/search", response_model=List[AgentRead])
async def search_agents(
    q: Optional[str] = Query(
        None, description="Search by AICID, name, keywords, organization, description, or human operator"
    ),
    agent_type: Optional[str] = Query(None),
    organization: Optional[str] = Query(None),
    base_model: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Agent).where(Agent.visibility == "public", Agent.moderation_status.is_(None))

    if q:
        stmt = stmt.where(agent_text_filter(q))
    if agent_type:
        stmt = stmt.where(Agent.agent_type == agent_type)
    if organization:
        stmt = stmt.where(Agent.organization.ilike(f"%{organization}%"))
    if base_model:
        stmt = stmt.where(Agent.base_model.ilike(f"%{base_model}%"))

    stmt = stmt.order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()
