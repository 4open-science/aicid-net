import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.models.auth_challenge import AuthChallenge
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "secret123", "full_name": "Test User"},
    )
    request_resp = await client.post(
        "/auth/email/request",
        json={"email": "test@example.com"},
    )
    token = request_resp.json()["challenge_token"]
    verify_resp = await client.post(
        "/auth/email/verify",
        json={"token": token},
    )
    token = verify_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def issued_challenge(client: AsyncClient, db_session: AsyncSession):
    await client.post(
        "/register",
        data={
            "agent_name": "FixtureBot",
            "human_operator": "Challenge User",
            "operator_email": "challenge@example.com",
        },
        follow_redirects=False,
    )
    response = await client.post("/auth/email/request", json={"email": "challenge@example.com"})
    token = response.json()["challenge_token"]
    result = await db_session.execute(select(AuthChallenge).where(AuthChallenge.email == "challenge@example.com"))
    challenge = result.scalar_one()
    return token, challenge.id
