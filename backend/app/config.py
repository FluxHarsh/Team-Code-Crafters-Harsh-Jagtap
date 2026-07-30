"""
Single source of truth for configuration.

Every setting is read from the environment (via a .env file locally, or
real environment variables in any other deployment). Nothing here is ever
hardcoded — secrets always come from outside the repo.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Postgres + pgvector (Neon) ---
    # No local/docker default anymore -- this must be a real Neon
    # connection string (postgresql:// or postgresql+asyncpg://, with or
    # without ?sslmode=require -- app/db/postgres.py normalizes either
    # form for the async driver; alembic normalizes it for the sync one).
    database_url: str = Field(default="", alias="DATABASE_URL")

    # --- Neo4j (Aura) ---
    # Real Aura URIs use the neo4j+s:// scheme (encrypted, no separate
    # ssl flag needed -- the scheme itself tells the driver to use TLS).
    neo4j_uri: str = Field(default="", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")

    # --- LLM (reasoning model used by every LangGraph node) ---
    # Provider-agnostic: set these three and every agent node picks it up
    # via app/agents/llm.py. Swapping OpenAI <-> Gemini is a one-line env
    # change (LLM_PROVIDER + LLM_MODEL_NAME), no code changes needed.
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")  # "openai" | "gemini"
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model_name: str = Field(default="gpt-4o", alias="LLM_MODEL_NAME")

    # --- OpenAI embeddings key (Phase 11 RAG, Section 3.2) ---
    # Kept separate from the reasoning LLM above: embeddings always go
    # through OpenAI's text-embedding-3-small regardless of which
    # LLM_PROVIDER is chosen for reasoning. If LLM_PROVIDER=openai you can
    # reuse the same key for both.
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # --- GitHub integration ---
    github_token_encryption_key: str = Field(
        default="", alias="GITHUB_TOKEN_ENCRYPTION_KEY"
    )
    default_poll_interval_seconds: int = Field(
        default=120, alias="DEFAULT_POLL_INTERVAL_SECONDS"
    )


@lru_cache
def get_settings() -> Settings:
    """Cached so we parse the environment exactly once per process."""
    return Settings()
