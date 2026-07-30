"""
Orchestrates pitch generation (Implementation Plan Phase 7): the
readiness threshold check (Section 5.6's "409 Roadmap not far enough
along yet"), running the Pitch Agent, and persisting the result. Routes
call this instead of touching the node/repositories directly, same
split as every other Phase 4-6 service.

is_pitch_ready is exported on its own (not just inlined into
generate_pitch) because Phase 10's tick_hours_remaining needs the exact
same check to decide whether to auto-trigger generation on its own,
per Section 7.1 -- "wire the same threshold check ... so the Pitch
Agent can fire on its own."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.pitch_agent import PitchOutline, run_pitch_agent
from app.errors import ConflictError
from app.models.project import Project
from app.repositories import projects as projects_repo
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)

# Section 5.6 / Phase 7's suggested threshold: either signal alone is
# enough -- a mostly-done roadmap even with time to spare, or a nearly
# out-of-time team regardless of completion percentage.
DONE_RATIO_THRESHOLD = 0.6
HOURS_REMAINING_THRESHOLD = 3.0


@dataclass
class GeneratedPitch:
    outline: PitchOutline
    generated_at: datetime


def is_pitch_ready(roadmap: list[dict], hours_remaining: float | None) -> bool:
    if hours_remaining is not None and hours_remaining < HOURS_REMAINING_THRESHOLD:
        return True
    if not roadmap:
        return False
    done_count = sum(1 for t in roadmap if t.get("status") == "done")
    return (done_count / len(roadmap)) > DONE_RATIO_THRESHOLD


async def generate_pitch(session: AsyncSession, project: Project, *, trigger: str) -> GeneratedPitch:
    hours_remaining = float(project.hours_remaining) if project.hours_remaining is not None else None
    if not is_pitch_ready(project.roadmap or [], hours_remaining):
        raise ConflictError("Roadmap not far enough along yet")

    resolved_risks = [r for r in (project.risks or []) if r.get("resolved")]

    outline = await run_pitch_agent(
        session,
        project_id=project.id,
        project_idea=project.project_idea or {},
        scope=project.scope or {},
        resolved_risks=resolved_risks,
        roadmap=project.roadmap or [],
        trigger=trigger,
    )

    generated_at = datetime.now(timezone.utc)
    await projects_repo.update_project(
        session,
        project.id,
        pitch_outline=outline.__dict__,
        pitch_generated_at=generated_at,
        status="pitch_ready",
    )
    logger.info("pitch_generated", extra={"project_id": str(project.id), "trigger": trigger})
    await broadcast(project.id, "pitch_ready", {})

    return GeneratedPitch(outline=outline, generated_at=generated_at)
