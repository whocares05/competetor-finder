"""Application Settings and Environment Variable Management"""
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    PROJECT_NAME: str = "Competitor Finder"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Plan Tier
    PLAN_TIER: str = Field(default="free", description="free or paid")

    # Databases (Defaults to zero-setup SQLite file; PostgreSQL in production/Docker)
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./compfinder.db",
        description="Async database connection URL",
    )
    DATABASE_SYNC_URL: str = Field(
        default="sqlite:///./compfinder.db",
        description="Sync database connection URL for Alembic migrations",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching, queues, and rate limiting",
    )

    # JWT Authentication
    JWT_SECRET: str = Field(
        default="super_secret_development_key_change_in_production_32chars",
        description="Secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # LLM Providers (Groq & Anthropic)
    LLM_PROVIDER: str = Field(default="groq", description="groq | anthropic")
    GROQ_API_KEY: Optional[str] = None
    GROQ_DEFAULT_MODEL: str = "openai/gpt-oss-120b"
    GROQ_ESCALATION_MODEL: str = "openai/gpt-oss-120b"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-5-haiku-latest"
    ANTHROPIC_ESCALATION_MODEL: str = "claude-3-7-sonnet-latest"

    # Search Providers
    SERPAPI_KEY: Optional[str] = None
    FALLBACK_SEARCH_API_KEY: Optional[str] = None
    FALLBACK_SEARCH_PROVIDER: str = "brave"

    # Scraping / Extraction Providers
    FIRECRAWL_API_KEY: Optional[str] = None
    FIRECRAWL_BASE_URL: str = "https://api.firecrawl.dev"

    # Enrichment Providers (Paid Tier)
    APIFY_TOKEN: Optional[str] = None
    APIFY_GOOGLE_MAPS_ACTOR_ID: str = "compass/crawler-google-places"
    APIFY_COMPANY_INFO_ACTOR_ID: str = "apify/web-scraper"

    # Embeddings
    EMBEDDING_PROVIDER: str = "local"  # "local" | "openai"
    EMBEDDING_MODEL_NAME: str = "paraphrase-multilingual-MiniLM-L12-v2"
    OPENAI_API_KEY: Optional[str] = None


settings = Settings()
