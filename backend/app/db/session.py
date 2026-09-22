"""Database session management and connection pooling"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from app.config.settings import settings

# Engine connection arguments
engine_kwargs = {"echo": False, "pool_pre_ping": True}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

# Async Engine for FastAPI routes and asynchronous workers
async_engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

sync_kwargs = {"pool_pre_ping": True}
if "sqlite" not in settings.DATABASE_SYNC_URL:
    sync_kwargs.update({"pool_size": 10, "max_overflow": 20})

# Sync Engine (used for Alembic and maintenance commands)
sync_engine = create_engine(
    settings.DATABASE_SYNC_URL,
    **sync_kwargs,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
