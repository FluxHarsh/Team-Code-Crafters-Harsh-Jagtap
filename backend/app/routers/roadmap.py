"""
GET   /api/v1/projects/{project_id}/roadmap
GET   /api/v1/projects/{project_id}/roadmap/board
POST  /api/v1/projects/{project_id}/roadmap/replan
PATCH /api/v1/projects/{project_id}/roadmap/tasks/{task_id}

Architecture doc Section 5.2. Exposes the approved plan as a live,
editable roadmap — what the Kanban board reads and writes. Roadmap
tasks live inline as a JSONB list on projects.roadmap (Section 3.1),
not a separate table, so task lookups/updates operate on that list.

/roadmap/board is a read-only, board-shaped view of that same data for
the Queued/Building/Blocked/Shipped dashboard: it maps the internal
todo/in_progress/blocked/done status vocabulary to the board's column
names, computes per-column counts + percent-complete + commit count,
and turns each task's own `depends_on` into an explicit `edges` list --
see app/services/roadmap_service.py::build_roadmap_board for the whole
computation (pure, no DB/Neo4j calls of its own). This is a different
thing from GET /api/v1/projects/{id}/agent-graph/state
(app/routers/agent_graph.py), which is the LangGraph *reasoning* graph
(which agent node ran), not the task dependency graph.

Phase 4: replan and the PATCH route are both real now, wired through
app/services/roadmap_service.py --
  - replan invokes the Planner node directly (current scope +
    hours_remaining, no new chat message) and re-syncs the Neo4j
    Milestone/BLOCKED_BY graph from the result; a re-plan already in
    flight for this project returns 409 (Postgres advisory lock).
  - the PATCH route takes a row-level lock on the projects row before
    its read-modify-write, and flags risk_flagged when a task moves to
    "blocked" -- a simple, immediate signal ahead of Phase 6's real
    Risk Watcher, which reasons over github_state/ETAs instead of just
    the task's own status.
GET /projects/{id} (Section 5.1's full-state hydration route) lives in
projects.py, not here -- it was already real as of Phase 2/3.
"""

import logging

from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.routers.common import get_project_or_404, parse_uuid
from app.services import roadmap_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["roadmap"])


class RoadmapResponse(BaseModel):
    tasks: list


class ReplanRequest(BaseModel):
    reason: str = Field(default="manual_request")


class ReplanResponse(BaseModel):
    status: str
    roadmap: list
    next_action: str | None


class TaskPatchRequest(BaseModel):
    status: str | None = None
    owner: str | None = None
    eta: str | None = None
    note: str | None = None


class TaskPatchResponse(BaseModel):
    task: dict
    risk_flagged: bool


class BoardNodeOut(BaseModel):
    id: str
    task: str
    column: str
    owner: str
    eta: str


class BoardEdgeOut(BaseModel):
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class BoardSummaryOut(BaseModel):
    percent_complete: int
    total_tasks: int
    shipped_count: int
    commit_count: int
    counts: dict[str, int]


class RoadmapBoardResponse(BaseModel):
    summary: BoardSummaryOut
    nodes: list[BoardNodeOut]
    edges: list[BoardEdgeOut]


@router.get("/{project_id}/roadmap", response_model=RoadmapResponse)
async def get_roadmap(project_id: str, session: AsyncSession = Depends(get_db)) -> RoadmapResponse:
    project = await get_project_or_404(session, project_id)
    return RoadmapResponse(tasks=project.roadmap)


@router.get("/{project_id}/roadmap/board", response_model=RoadmapBoardResponse)
async def get_roadmap_board(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> RoadmapBoardResponse:
    """Board-shaped view of the roadmap for the Queued/Building/Blocked/
    Shipped dashboard: column-labeled nodes, per-column counts, overall
    percent-complete, commit count, and an explicit dependency-edge list
    -- everything the board needs in one call instead of the frontend
    re-deriving it from the raw task list GET /roadmap returns."""
    project = await get_project_or_404(session, project_id)
    result = roadmap_service.build_roadmap_board(project)
    return RoadmapBoardResponse(**result.__dict__)


@router.post("/{project_id}/roadmap/replan", response_model=ReplanResponse)
async def post_roadmap_replan(
    project_id: str,
    body: ReplanRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> ReplanResponse:
    project = await get_project_or_404(session, project_id)
    result = await roadmap_service.replan_roadmap(session, driver, project, reason=body.reason)
    return ReplanResponse(status=result.status, roadmap=result.roadmap, next_action=result.next_action)


@router.patch("/{project_id}/roadmap/tasks/{task_id}", response_model=TaskPatchResponse)
async def patch_roadmap_task(
    project_id: str,
    task_id: str,
    body: TaskPatchRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> TaskPatchResponse:
    pid = parse_uuid(project_id, label="project_id")
    result = await roadmap_service.patch_task(
        session,
        driver,
        pid,
        task_id,
        status=body.status,
        owner=body.owner,
        eta=body.eta,
        note=body.note,
    )
    return TaskPatchResponse(task=result.task, risk_flagged=result.risk_flagged)
