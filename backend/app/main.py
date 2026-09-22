"""Main FastAPI Application Entrypoint"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.api.auth import router as auth_router
from app.api.search import router as search_router
from app.api.feedback import router as feedback_router
from app.api.limits import router as limits_router


from app.db.base import Base
from app.db.session import async_engine
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # If using SQLite for zero-setup local testing, auto-create tables
    if "sqlite" in settings.DATABASE_URL:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: close connection pools


app = FastAPI(
    title="Competitor Finder API",
    description="Production MVP for global competitor intelligence and verification",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(search_router)
app.include_router(feedback_router)
app.include_router(limits_router)


@app.get("/healthz", tags=["Health"])
async def healthcheck():
    """Liveness and readiness healthcheck probe."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "plan_tier": settings.PLAN_TIER,
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Ensure unhandled server exceptions return structured JSON."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "type": type(exc).__name__},
    )
