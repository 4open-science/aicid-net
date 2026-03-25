import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.agent import Agent
from app.models.work import Work
from app.models.user import User
from app.schemas.work import WorkCreate, WorkRead, WorkUpdate
from app.core.deps import get_current_user

router = APIRouter()


async def _get_owned_agent(aicid: str, user: User, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).where(Agent.aicid == aicid))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    return agent


@router.post("/{aicid}/works", response_model=WorkRead, status_code=status.HTTP_201_CREATED)
async def add_work(
    aicid: str,
    body: WorkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    work = Work(agent_id=agent.id, put_code=str(uuid.uuid4()), **body.model_dump())
    db.add(work)
    await db.commit()
    await db.refresh(work)
    return work


@router.get("/{aicid}/works", response_model=List[WorkRead])
async def list_works(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(select(Work).where(Work.agent_id == agent.id))
    return result.scalars().all()


@router.patch("/{aicid}/works/{work_id}", response_model=WorkRead)
async def update_work(
    aicid: str,
    work_id: int,
    body: WorkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(select(Work).where(Work.id == work_id, Work.agent_id == agent.id))
    work = result.scalar_one_or_none()
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(work, field, value)
    await db.commit()
    await db.refresh(work)
    return work


@router.delete("/{aicid}/works/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work(
    aicid: str,
    work_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(select(Work).where(Work.id == work_id, Work.agent_id == agent.id))
    work = result.scalar_one_or_none()
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    await db.delete(work)
    await db.commit()
