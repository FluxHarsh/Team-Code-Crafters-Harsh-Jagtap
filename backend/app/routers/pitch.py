"""
POST /api/v1/projects/{project_id}/pitch/generate
GET  /api/v1/projects/{project_id}/pitch

Architecture doc Section 5.6. Also auto-triggers when the roadmap is
mostly done or hours_remaining is low (Phase 10's autonomous loop,
reusing app.services.pitch_service.is_pitch_ready).

Phase 7: generate is real now, via app/services/pitch_service.py --
the readiness threshold (>60% tasks done, or hours_remaining < 3) gates
a 409, otherwise the Pitch Agent synthesizes {hook, problem, solution,
demo_flow[], differentiator, ask} from project_idea/scope/resolved
risks/roadmap and it's persisted to a dedicated pitch_generated_at
column (no longer borrowing updated_at).
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.errors import NotFoundError
from app.routers.common import get_project_or_404
from app.services.pitch_service import generate_pitch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["pitch"])


class PitchOutlineOut(BaseModel):
    hook: str
    problem: str
    solution: str
    demo_flow: list[str]
    differentiator: str
    ask: str


class PitchGenerateResponse(BaseModel):
    pitch_outline: PitchOutlineOut


class PitchGetResponse(BaseModel):
    pitch_outline: dict
    generated_at: str


@router.post("/{project_id}/pitch/generate", response_model=PitchGenerateResponse)
async def post_pitch_generate(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> PitchGenerateResponse:
    project = await get_project_or_404(session, project_id)

    result = await generate_pitch(session, project, trigger="user_action")
    logger.info("pitch generated", extra={"project_id": str(project.id)})

    return PitchGenerateResponse(pitch_outline=PitchOutlineOut(**result.outline.__dict__))


@router.get("/{project_id}/pitch", response_model=PitchGetResponse)
async def get_pitch(project_id: str, session: AsyncSession = Depends(get_db)) -> PitchGetResponse:
    project = await get_project_or_404(session, project_id)

    if project.pitch_outline is None:
        raise NotFoundError("No pitch generated yet")

    generated_at = project.pitch_generated_at or project.updated_at
    return PitchGetResponse(pitch_outline=project.pitch_outline, generated_at=generated_at.isoformat())
