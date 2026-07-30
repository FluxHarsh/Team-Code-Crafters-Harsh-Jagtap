"""
Small helpers shared across every router-per-domain file. Kept here
instead of duplicated per file since almost every route in Section 5
starts with "look up {project_id}, 404 if missing."
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models.project import Project
from app.repositories import projects as projects_repo


def parse_uuid(value: str, *, label: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise NotFoundError(f"Invalid {label}: {value!r}")


async def get_project_or_404(session: AsyncSession, project_id: str) -> Project:
    pid = parse_uuid(project_id, label="project_id")
    project = await projects_repo.get_project(session, pid)
    if project is None:
        raise NotFoundError(f"Project {project_id} not found")
    return project
