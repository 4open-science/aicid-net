from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, hash_opaque_token
from app.core.spam import spam_reason, url_reason
from app.database import get_db
from app.models.agent import Agent
from app.models.user import User

# auto_error=False so that missing Bearer tokens don't immediately 401;
# we fall through to HTTP signature auth instead.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Try HTTP signature auth when Signature-Input header is present
    if "signature-input" in request.headers:
        from app.core.http_signature import verify_http_signature
        user = await verify_http_signature(request, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return user

    # Fall back to Bearer token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    email = decode_token(token, expected_type="access")
    if not email:
        raise credentials_exception
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


@dataclass
class Principal:
    """Who is calling: a human account, or a self-registered agent acting with its own agent_secret."""

    user: User | None = None
    agent: Agent | None = None


async def get_principal(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    # an agent_secret is an opaque token, so it never decodes as one of our JWTs
    if token and "signature-input" not in request.headers and decode_token(token, expected_type="access") is None:
        agent = (
            await db.execute(select(Agent).where(Agent.agent_secret_hash == hash_opaque_token(token)))
        ).scalar_one_or_none()
        if agent is not None:
            return Principal(agent=agent)
    return Principal(user=await get_current_user(request, token, db))


async def owned_agent(aicid: str, principal: Principal, db: AsyncSession) -> Agent:
    """The agent `aicid` if the caller owns it, or is that agent itself."""
    agent = (await db.execute(select(Agent).where(Agent.aicid == aicid))).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if principal.agent is not None:
        if principal.agent.id != agent.id:
            raise HTTPException(status_code=403, detail="Not your agent")
    elif principal.user is None or agent.owner_id != principal.user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    return agent


_NOT_FREE_TEXT = {"doi", "url", "grant_number", "agent_type", "work_type", "visibility"}


def ensure_clean_content(principal: Principal, values: dict) -> None:
    """Apply the registration spam rules to what an unauthenticated-by-a-human agent writes."""
    if principal.agent is None:
        return
    texts: dict[str, str | None] = {
        k: v
        for k, v in values.items()
        if isinstance(v, str) and k not in _NOT_FREE_TEXT and not k.endswith("_url")
    }
    reason = spam_reason(texts, None) or next(
        (
            url_reason(v)
            for k, v in values.items()
            if isinstance(v, str) and (k == "url" or k.endswith("_url")) and url_reason(v)
        ),
        None,
    )
    if reason:
        raise HTTPException(status_code=422, detail="This content could not be accepted.")
