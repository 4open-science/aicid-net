from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.funding import Funding
from app.schemas.funding import FundingCreate, FundingRead, FundingUpdate
from app.core.deps import Principal, ensure_clean_content, get_principal, owned_agent as _get_owned_agent

router = APIRouter()


@router.post("/{aicid}/fundings", response_model=FundingRead, status_code=status.HTTP_201_CREATED)
async def add_funding(
    aicid: str,
    body: FundingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Principal = Depends(get_principal),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    ensure_clean_content(current_user, body.model_dump())
    fund = Funding(agent_id=agent.id, **body.model_dump())
    db.add(fund)
    await db.commit()
    await db.refresh(fund)
    return fund


@router.get("/{aicid}/fundings", response_model=List[FundingRead])
async def list_fundings(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: Principal = Depends(get_principal),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(select(Funding).where(Funding.agent_id == agent.id))
    return result.scalars().all()


@router.patch("/{aicid}/fundings/{fund_id}", response_model=FundingRead)
async def update_funding(
    aicid: str,
    fund_id: int,
    body: FundingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Principal = Depends(get_principal),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(
        select(Funding).where(Funding.id == fund_id, Funding.agent_id == agent.id)
    )
    fund = result.scalar_one_or_none()
    if fund is None:
        raise HTTPException(status_code=404, detail="Funding not found")
    ensure_clean_content(current_user, body.model_dump(exclude_unset=True))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(fund, field, value)
    await db.commit()
    await db.refresh(fund)
    return fund


@router.delete("/{aicid}/fundings/{fund_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_funding(
    aicid: str,
    fund_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Principal = Depends(get_principal),
):
    agent = await _get_owned_agent(aicid, current_user, db)
    result = await db.execute(
        select(Funding).where(Funding.id == fund_id, Funding.agent_id == agent.id)
    )
    fund = result.scalar_one_or_none()
    if fund is None:
        raise HTTPException(status_code=404, detail="Funding not found")
    await db.delete(fund)
    await db.commit()
