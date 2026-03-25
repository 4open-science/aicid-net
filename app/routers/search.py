from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentRead

router = APIRouter()


@router.get("/search", response_model=List[AgentRead])
async def search_agents(
    q: Optional[str] = Query(None, description="Search by name, keywords, organization, or description"),
    agent_type: Optional[str] = Query(None),
    organization: Optional[str] = Query(None),
    base_model: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Agent).where(Agent.visibility == "public")

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Agent.name.ilike(like),
                Agent.keywords.ilike(like),
                Agent.organization.ilike(like),
                Agent.description.ilike(like),
            )
        )
    if agent_type:
        stmt = stmt.where(Agent.agent_type == agent_type)
    if organization:
        stmt = stmt.where(Agent.organization.ilike(f"%{organization}%"))
    if base_model:
        stmt = stmt.where(Agent.base_model.ilike(f"%{base_model}%"))

    stmt = stmt.order_by(Agent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()
