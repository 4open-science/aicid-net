from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _make_engine_url(url: str) -> str:
    """Convert postgres:// or postgresql:// URLs to the async asyncpg driver format.

    Handles both Render's ``postgres://`` shorthand and Supabase's
    ``postgresql://`` connection strings (which may include ``?sslmode=require``).
    The ``sslmode`` query parameter is stripped because asyncpg does not
    recognise it; SSL is instead enabled via ``connect_args`` (see
    :func:`_make_connect_args`).
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg does not accept the sslmode query param; strip it here and let
    # _make_connect_args pass the equivalent native SSL option instead.
    url = url.replace("?sslmode=require", "")
    return url


def _make_connect_args(url: str) -> dict:
    """Return engine ``connect_args`` derived from the original database URL.

    When the URL contains ``sslmode=require`` (as Supabase connection strings
    do), asyncpg must be told to use SSL via ``connect_args`` rather than the
    query string.
    """
    if "sslmode=require" in url:
        return {"ssl": True}
    return {}


engine = create_async_engine(
    _make_engine_url(settings.DATABASE_URL),
    echo=settings.ENVIRONMENT == "development",
    connect_args=_make_connect_args(settings.DATABASE_URL),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
