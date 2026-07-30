"""
Typed CRUD for agent_run_log — one row per LangGraph node execution.
Powers the "Agent graph view" and the judge-facing debug trail.

Phase 9: start_run also broadcasts node_activated (architecture doc
Section 6, { node, trigger }) -- every node in this codebase calls
start_run before doing any work, so hooking the broadcast here (rather
than at each of the ~9 node call sites individually) guarantees the
agent graph view lights up for every node run, including ones added by
future phases, without each node needing to remember to broadcast.

start_run also stitches the current request's id
(app.logging_config.get_request_id) into input_snapshot under
"_request_id" -- this is the join key logging_config.py's own
docstring promises ("pass this into agent_run_log writes ... so a run
can be traced back to its trigger"), letting a judge-facing debug
session go from an X-Request-ID in an HTTP log line straight to every
node run it triggered, without adding a dedicated column/migration for
what's fundamentally debug metadata, not queryable domain data.
Falls back to "-" for runs triggered outside an HTTP request (the
scheduler's own jobs), same as every other consumer of
get_request_id().
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_request_id
from app.models.agent_run_log import AgentRunLog
from app.ws.connection_manager import broadcast


async def start_run(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    node_name: str,
    trigger: str,
    input_snapshot: dict,
) -> AgentRunLog:
    run = AgentRunLog(
        project_id=project_id,
        node_name=node_name,
        trigger=trigger,
        input_snapshot={**input_snapshot, "_request_id": get_request_id()},
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()
    await broadcast(project_id, "node_activated", {"node": node_name, "trigger": trigger})
    return run


async def finish_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    output_snapshot: dict,
    status: str = "done",
) -> AgentRunLog | None:
    """status should be 'done' or 'failed'."""
    run = await session.get(AgentRunLog, run_id)
    if run is None:
        return None
    run.output_snapshot = output_snapshot
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    await session.flush()
    return run


async def list_runs_for_project(
    session: AsyncSession, project_id: uuid.UUID, *, limit: int = 100
) -> list[AgentRunLog]:
    result = await session.execute(
        select(AgentRunLog)
        .where(AgentRunLog.project_id == project_id)
        .order_by(AgentRunLog.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
