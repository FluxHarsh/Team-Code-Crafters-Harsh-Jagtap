"""
POST   /api/v1/projects/{project_id}/team-members
GET    /api/v1/projects/{project_id}/team-members
PATCH  /api/v1/projects/{project_id}/team-members/{member_id}
DELETE /api/v1/projects/{project_id}/team-members/{member_id}

Spec doc Section 8.
"""

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.routers.common import get_project_or_404
from app.services import team_members_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["team"])


class TeamMemberIn(BaseModel):
    name: str = Field(min_length=1)
    role: str | None = None
    skills: list[str] = Field(default_factory=list)
    availability: str | None = None


class TeamMemberPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    skills: list[str] | None = None
    availability: str | None = None


class TeamMemberOut(BaseModel):
    id: str
    name: str
    role: str
    skills: list[str]
    tech_stack: list[str]
    availability: str


class TeamMembersResponse(BaseModel):
    members: list[TeamMemberOut]


@router.post("/{project_id}/team-members", response_model=TeamMemberOut, status_code=status.HTTP_201_CREATED)
async def post_team_member(
    project_id: str, body: TeamMemberIn, session: AsyncSession = Depends(get_db)
) -> TeamMemberOut:
    project = await get_project_or_404(session, project_id)
    member = await team_members_service.add_member(
        session, project, name=body.name, role=body.role, skills=body.skills, availability=body.availability
    )
    return TeamMemberOut(**member)


@router.get("/{project_id}/team-members", response_model=TeamMembersResponse)
async def get_team_members(project_id: str, session: AsyncSession = Depends(get_db)) -> TeamMembersResponse:
    project = await get_project_or_404(session, project_id)
    members = await team_members_service.list_members(project)
    return TeamMembersResponse(members=[TeamMemberOut(**m) for m in members])


@router.patch("/{project_id}/team-members/{member_id}", response_model=TeamMemberOut)
async def patch_team_member(
    project_id: str, member_id: str, body: TeamMemberPatch, session: AsyncSession = Depends(get_db)
) -> TeamMemberOut:
    project = await get_project_or_404(session, project_id)
    updated = await team_members_service.update_member(session, project, member_id, **body.model_dump())
    return TeamMemberOut(**updated)


@router.delete("/{project_id}/team-members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_member(project_id: str, member_id: str, session: AsyncSession = Depends(get_db)) -> None:
    project = await get_project_or_404(session, project_id)
    await team_members_service.remove_member(session, project, member_id)
