"""
Neo4j driver setup -- talks to a hosted Aura instance, no local/docker
Neo4j involved anymore.

Aura connection URIs use the neo4j+s:// scheme (e.g.
"neo4j+s://xxxxxxxx.databases.neo4j.io"), which the driver reads as
"use TLS with a CA-signed cert" all on its own -- no extra ssl kwarg
needed here the way Postgres/asyncpg needs one (see app/db/postgres.py).
Paste the URI Aura gives you straight into NEO4J_URI as-is.
"""

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import get_settings

_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        settings = get_settings()
        if not settings.neo4j_uri:
            raise RuntimeError(
                "NEO4J_URI is not set. Paste your Aura connection URI "
                "into .env as NEO4J_URI (see .env.example)."
            )
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def ping_neo4j() -> bool:
    """Returns True if Neo4j answers a trivial query, else False."""
    try:
        driver = get_driver()
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS ok")
            record = await result.single()
            return bool(record and record["ok"] == 1)
    except Exception:
        return False


async def dispose_neo4j() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
