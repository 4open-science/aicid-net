import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.core.deps import get_current_user
from app.core.aicid_id import generate_aicid

router = APIRouter()


async def _unique_aicid(db: AsyncSession) -> str:
    for _ in range(10):
        candidate = generate_aicid()
        result = await db.execute(select(Agent).where(Agent.aicid == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("Could not generate a unique AICID after 10 attempts")


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    aicid = await _unique_aicid(db)
    agent = Agent(owner_id=current_user.id, aicid=aicid, **body.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("", response_model=List[AgentRead])
async def list_my_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.owner_id == current_user.id))
    return result.scalars().all()


@router.get("/{aicid}", response_model=AgentRead)
async def get_agent(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    return agent


@router.patch("/{aicid}", response_model=AgentRead)
async def update_agent(
    aicid: str,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{aicid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    await db.delete(agent)
    await db.commit()
