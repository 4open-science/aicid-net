from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.agent import Agent
from app.models.employment import Employment
from app.models.user import User
from app.schemas.employment import EmploymentCreate, EmploymentRead, EmploymentUpdate
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


@router.post("/{aicid}/employments", response_model=EmploymentRead, status_code=status.HTTP_201_CREATED)
async def add_employment(
    aicid: str,
    body: EmploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    emp = Employment(agent_id=agent.id, **body.model_dump())
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


@router.get("/{aicid}/employments", response_model=List[EmploymentRead])
async def list_employments(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(select(Employment).where(Employment.agent_id == agent.id))
    return result.scalars().all()


@router.patch("/{aicid}/employments/{emp_id}", response_model=EmploymentRead)
async def update_employment(
    aicid: str,
    emp_id: int,
    body: EmploymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(
        select(Employment).where(Employment.id == emp_id, Employment.agent_id == agent.id)
    )
    emp = result.scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Employment not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    await db.commit()
    await db.refresh(emp)
    return emp


@router.delete("/{aicid}/employments/{emp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employment(
    aicid: str,
    emp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(
        select(Employment).where(Employment.id == emp_id, Employment.agent_id == agent.id)
    )
    emp = result.scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Employment not found")
    await db.delete(emp)
    await db.commit()
