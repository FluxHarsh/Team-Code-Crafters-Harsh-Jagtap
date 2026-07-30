"""
Postgres/pgvector engine setup -- talks to a hosted Neon instance, no
local/docker Postgres involved anymore.

Neon hands out connection strings shaped like:
  postgresql://user:password@ep-xxxx.us-east-2.aws.neon.tech/dbname?sslmode=require
(sometimes with a trailing &channel_binding=require too).

Paste that directly into DATABASE_URL -- normalize_asyncpg_url() below
takes care of everything the asyncpg driver needs that a raw copy-paste
doesn't already give it:

  1. "postgresql://" -> "postgresql+asyncpg://" (SQLAlchemy needs the
     driver named explicitly to build an async engine).
  2. "postgres://" -> "postgresql://" (some providers still hand out the
     old scheme; SQLAlchemy 1.4+ rejects it outright).
  3. Strips "sslmode" and "channel_binding" out of the URL's query
     string. SQLAlchemy's asyncpg dialect forwards every query-string
     key straight through as a **kwarg to asyncpg.connect(), and
     asyncpg.connect() has no "sslmode" or "channel_binding" parameter
     (only "ssl") -- left in place, every connection attempt raises
     `TypeError: connect() got an unexpected keyword argument 'sslmode'`
     before a single query ever runs.
  4. Turns that sslmode value into the "ssl" connect_arg asyncpg
     actually expects, so the encryption Neon requires still happens --
     it just gets passed the way this driver wants it, not stripped.

None of this applies to alembic's migration path (alembic/env.py), which
uses psycopg2 -- psycopg2 (via libpq) understands "sslmode" and
"channel_binding" natively, so that URL is left untouched.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None

# Query-string keys asyncpg.connect() doesn't accept as kwargs. Anything
# else in the query string (e.g. "options") is left alone and passed
# through as-is.
_ASYNCPG_UNSUPPORTED_QUERY_KEYS = {"sslmode", "channel_binding"}

# libpq/Neon sslmode values that mean "don't bother with TLS" -- anything
# else ("require", "verify-ca", "verify-full", or no sslmode at all for a
# non-localhost host) means "yes, encrypt".
_SSLMODE_NO_TLS = {"disable", "allow"}


def normalize_asyncpg_url(raw_url: str) -> tuple[str, dict]:
    """Returns (url_for_create_async_engine, connect_args)."""
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Paste your Neon connection string "
            "into .env as DATABASE_URL (see .env.example)."
        )

    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    sslmode: str | None = None
    kept_pairs = []
    for key, value in query_pairs:
        if key.lower() in _ASYNCPG_UNSUPPORTED_QUERY_KEYS:
            if key.lower() == "sslmode":
                sslmode = value.lower()
            continue
        kept_pairs.append((key, value))

    host = parts.hostname or ""
    is_local = host in ("localhost", "127.0.0.1", "::1")
    if sslmode is not None:
        use_ssl = sslmode not in _SSLMODE_NO_TLS
    else:
        use_ssl = not is_local  # Neon always requires TLS; local dev doesn't need it

    normalized_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(kept_pairs), parts.fragment)
    )
    connect_args = {"ssl": use_ssl}
    return normalized_url, connect_args


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        url, connect_args = normalize_asyncpg_url(settings.database_url)
        _engine = create_async_engine(
            url, pool_pre_ping=True, connect_args=connect_args
        )
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False
        )
    return _session_factory


async def ping_postgres() -> bool:
    """Returns True if Postgres answers a trivial query, else False."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def dispose_postgres() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
