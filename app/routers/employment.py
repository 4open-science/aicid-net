from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.employment import Employment
from app.schemas.employment import EmploymentCreate, EmploymentRead, EmploymentUpdate
from app.core.deps import Principal, ensure_clean_content, get_principal, owned_agent as _get_owned_agent

router = APIRouter()


@router.post("/{aicid}/employments", response_model=EmploymentRead, status_code=status.HTTP_201_CREATED)
async def add_employment(
    aicid: str,
    body: EmploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Principal = Depends(get_principal),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    ensure_clean_content(current_user, body.model_dump())
    emp = Employment(agent_id=agent.id, **body.model_dump())
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


@router.get("/{aicid}/employments", response_model=List[EmploymentRead])
async def list_employments(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: Principal = Depends(get_principal),
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
    current_user: Principal = Depends(get_principal),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(
        select(Employment).where(Employment.id == emp_id, Employment.agent_id == agent.id)
    )
    emp = result.scalar_one_or_none()
    if emp is None:
        raise HTTPException(status_code=404, detail="Employment not found")
    ensure_clean_content(current_user, body.model_dump(exclude_unset=True))
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
    current_user: Principal = Depends(get_principal),
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
