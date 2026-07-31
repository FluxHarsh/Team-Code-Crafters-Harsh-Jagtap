"""
App entrypoint.

Mounts every domain router under /api/v1, wires structured logging with
a per-request request-id, and registers the global exception handlers
so every route returns the same {"detail": ...} error shape.

Phase 10: the lifespan now also starts/stops the APScheduler instance
(app/scheduler/scheduler.py) -- this is what makes the Monitoring loop
run whether or not anyone has the dashboard open (architecture doc
Section 7).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.postgres import dispose_postgres, get_engine
from app.db.neo4j import dispose_neo4j, get_driver

from app.errors import register_exception_handlers
from app.logging_config import configure_logging, install_request_id_middleware
from app.routers import (
    agent_graph,
    chat,
    dashboard,
    github,
    health,
    ingestion,
    pitch,
    planner_suggestions,
    planning,
    reprioritize,
    risks,
    roadmap,
    projects,
    team_members,
    ws,
)
from app.scheduler.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm up connections to both databases, then start the
    # scheduler -- it needs those connections (and re-queries Postgres
    # for active projects) as part of its own startup recovery.
    get_engine()
    get_driver()
    await start_scheduler()
    yield
    # Shutdown: stop the scheduler first (so no job starts using a pool
    # that's about to be disposed), then release the pool / driver.
    await shutdown_scheduler()
    await dispose_postgres()
    await dispose_neo4j()


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="Hackathon Project Coach — Backend", lifespan=lifespan)

    # Security: CORS middleware configuration
    settings = get_settings()
    origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True if origins and "*" not in origins else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_request_id_middleware(app)
    register_exception_handlers(app)

    # Router-per-domain layout (Implementation Plan, Phase 2) — mirrors
    # architecture doc Section 5's grouping exactly. health.py stays
    # unprefixed (/healthz); everything else lives under /api/v1/projects.
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(ingestion.router)
    app.include_router(planning.router)
    app.include_router(roadmap.router)
    app.include_router(github.router)
    app.include_router(risks.router)
    app.include_router(reprioritize.router)
    app.include_router(planner_suggestions.router)
    app.include_router(pitch.router)
    app.include_router(chat.router)
    app.include_router(team_members.router)
    app.include_router(dashboard.router)
    app.include_router(agent_graph.router)
    app.include_router(ws.router)

    return app



app = create_app()
