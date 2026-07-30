"""
One-off setup script for the Neo4j dependency/causality graph
(architecture doc Section 3.3).

Creates a uniqueness constraint (which also creates a backing index)
for every node label's key property, so repeated MERGEs from the
Planner and GitHub Watcher are idempotent and fast.

Usage:
    python -m scripts.neo4j_bootstrap
"""

import asyncio

from neo4j import AsyncGraphDatabase

from app.config import get_settings

# label -> key property, per the Section 3.3 node table.
CONSTRAINTS = {
    "Project": "id",
    "Milestone": "id",
    "Risk": "id",
    "CommitFile": "path",
}


async def bootstrap() -> None:
    settings = get_settings()
    if not settings.neo4j_uri:
        raise RuntimeError(
            "NEO4J_URI is not set. Paste your Aura connection URI into "
            ".env as NEO4J_URI (see .env.example) before running this."
        )
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )

    try:
        async with driver.session() as session:
            for label, key in CONSTRAINTS.items():
                constraint_name = f"{label.lower()}_{key}_unique"
                await session.run(
                    f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
                )
                print(f"ensured constraint: {constraint_name} ({label}.{key})")

            result = await session.run("SHOW CONSTRAINTS")
            records = [record async for record in result]
            print(f"\n{len(records)} constraint(s) now present in the database.")
    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
