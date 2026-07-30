"""
GET /healthz — hits Postgres and Neo4j so infra problems surface
immediately, not mid-demo (Phase 0 deliverable).
"""

from fastapi import APIRouter, Response, status

from app.db.postgres import ping_postgres
from app.db.neo4j import ping_neo4j

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz(response: Response) -> dict:
    postgres_ok = await ping_postgres()
    neo4j_ok = await ping_neo4j()
    healthy = postgres_ok and neo4j_ok

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "degraded",
        "postgres": "ok" if postgres_ok else "unreachable",
        "neo4j": "ok" if neo4j_ok else "unreachable",
    }
