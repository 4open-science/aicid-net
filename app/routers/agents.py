from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aicid_id import generate_aicid
from app.core.deps import Principal, ensure_clean_content, get_current_user, get_principal, owned_agent
from app.core.email import EmailDeliveryError, send_email
from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate

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
    try:
        send_email(
            "team@aicid.net",
            f"New agent registered: {agent.name}",
            f"Agent {agent.name} ({agent.aicid}) registered by {current_user.email}.",
        )
    except EmailDeliveryError:
        pass  # best-effort team notification; already logged, agent is created
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
    principal: Principal = Depends(get_principal),
):
    return await owned_agent(aicid, principal, db)


# Once a human has claimed the agent these name the verified operator, so the agent itself cannot change them.
_OPERATOR_FIELDS = {"human_operator", "operator_telegram", "operator_x"}


@router.patch("/{aicid}", response_model=AgentRead)
async def update_agent(
    aicid: str,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    agent = await owned_agent(aicid, principal, db)
    changes = body.model_dump(exclude_unset=True)
    if principal.agent is not None and agent.claimed_at is not None and _OPERATOR_FIELDS & changes.keys():
        raise HTTPException(status_code=403, detail="Operator fields of a claimed agent are managed by its operator")
    ensure_clean_content(principal, changes)
    for field, value in changes.items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{aicid}/agent-secret", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_agent_secret(
    aicid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The operator revokes the agent's own credential (the agent can no longer edit its profile)."""
    agent = (await db.execute(select(Agent).where(Agent.aicid == aicid))).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    agent.agent_secret_hash = None
    await db.commit()


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
