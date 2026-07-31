"""
Team Members (spec doc Section 8, app/routers/team_members.py).

Backed by the projects.team JSONB list added in Workstream A1 -- no new
table needed, this is just structured mutation of that column with
per-member ids so PATCH/DELETE have something to target.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models.project import Project
from app.repositories import projects as projects_repo
from app.ws.connection_manager import broadcast


async def add_member(
    session: AsyncSession, project: Project, *, name: str, role: str | None, skills: list[str], availability: str | None
) -> dict:
    member = {
        "id": str(uuid.uuid4()),
        "name": name,
        "role": role or "",
        "skills": skills,
        "tech_stack": [],
        "availability": availability or "",
    }
    team = list(project.team or [])
    team.append(member)
    await projects_repo.update_project(session, project.id, team=team)
    await broadcast(project.id, "team_updated", {"team": team})
    return member


async def list_members(project: Project) -> list[dict]:
    return list(project.team or [])


async def update_member(session: AsyncSession, project: Project, member_id: str, **fields) -> dict:
    team = list(project.team or [])
    for i, m in enumerate(team):
        if m.get("id") == member_id:
            updated = {**m, **{k: v for k, v in fields.items() if v is not None}}
            team[i] = updated
            await projects_repo.update_project(session, project.id, team=team)
            await broadcast(project.id, "team_updated", {"team": team})
            return updated
    raise NotFoundError(f"Team member {member_id} not found")


async def remove_member(session: AsyncSession, project: Project, member_id: str) -> None:
    team = list(project.team or [])
    filtered = [m for m in team if m.get("id") != member_id]
    if len(filtered) == len(team):
        raise NotFoundError(f"Team member {member_id} not found")
    await projects_repo.update_project(session, project.id, team=filtered)
    await broadcast(project.id, "team_updated", {"team": filtered})
