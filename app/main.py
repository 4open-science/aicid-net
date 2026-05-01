from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base

# Import models so Base.metadata is populated before create_all / migrations
import app.models.user  # noqa: F401
import app.models.agent  # noqa: F401
import app.models.work  # noqa: F401
import app.models.employment  # noqa: F401
import app.models.funding  # noqa: F401
import app.models.oauth  # noqa: F401

from app.routers import auth, agents, works, employment, funding, search, public, oauth  # noqa: F401


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Create tables for SQLite dev; production uses alembic migrations
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


application = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/openapi",
    redoc_url="/redoc",
)

application.mount("/static", StaticFiles(directory="static"), name="static")

application.include_router(auth.router, prefix="/auth", tags=["auth"])
application.include_router(agents.router, prefix="/api/agents", tags=["agents"])
application.include_router(works.router, prefix="/api/agents", tags=["works"])
application.include_router(employment.router, prefix="/api/agents", tags=["employment"])
application.include_router(funding.router, prefix="/api/agents", tags=["funding"])
application.include_router(search.router, tags=["search"])
application.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
application.include_router(public.router, tags=["public"])

# Alias for uvicorn entrypoint and imports
app = application
