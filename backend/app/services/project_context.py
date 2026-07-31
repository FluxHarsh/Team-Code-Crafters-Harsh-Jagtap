"""
ProjectContext + Missing Information Detector (Workstream A1).

Assembles the full context shape (hackathon details, team, project
idea, repository, supporting documents, presentation, design links)
from tables/columns that already exist -- Repository (github_connections),
Supporting Documents (documents), and Presentation (pitch_outline) all
already had first-class tracking before this workstream, so this is
purely a read-side assembly, not new storage for those three.

detect_missing_fields()/is_complete() is the explicit completeness rule
the Intake loop gates on, replacing "trust the Intake node's own
ready_for_planning opinion" with a real, inspectable check.

Judgment call: hackathon_details/team are reported as missing when
empty, but are NOT required for is_complete() -- nothing in this
codebase's intake flow collects them yet (no "what's your deadline"
question, no team-setup step), so making them required would
permanently block every project from reaching Planning. required vs.
optional is a plain dict below, not implicit logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories import documents as documents_repo
from app.repositories import github_connections as github_connections_repo

# field_name -> True if required to leave Intake, False if optional/
# informational-only (still reported by detect_missing_fields, just
# doesn't block readiness).
REQUIRED_FIELDS = {
    "problem": True,
    "solution": True,
    "target_user": True,
    "hackathon_details": False,
    "team": False,
    "repository": False,
    "supporting_documents": False,
    "presentation": False,
}


@dataclass
class ProjectContext:
    hackathon_details: dict
    team: list
    project: dict  # {raw, refined: {problem, solution, target_user, ...}}
    repository: dict | None
    supporting_documents: list
    presentation: dict | None
    design_links: list = field(default_factory=list)


async def build_project_context(session: AsyncSession, project: Project) -> ProjectContext:
    connection = await github_connections_repo.get_connection_for_project(session, project.id)
    repository = (
        {"repo_full_name": connection.repo_full_name, "connected": True}
        if connection
        else None
    )

    docs = await documents_repo.list_documents_for_project(session, project.id)
    supporting_documents = [
        {"id": str(d.id), "filename": d.filename, "mime_type": d.mime_type} for d in docs
    ]

    presentation = project.pitch_outline

    return ProjectContext(
        hackathon_details=project.hackathon_details or {},
        team=project.team or [],
        project=project.project_idea or {},
        repository=repository,
        supporting_documents=supporting_documents,
        presentation=presentation,
        design_links=(project.project_idea or {}).get("design_links", []),
    )


def _refined(context: ProjectContext) -> dict:
    return context.project.get("refined") or {}


def detect_missing_fields(context: ProjectContext) -> list[str]:
    """Returns field names that are missing/empty, in REQUIRED_FIELDS
    order. Required and optional fields are both reported here -- the
    caller (Intake loop) decides what to do with each via
    REQUIRED_FIELDS; a UI can use this list to prompt for anything
    missing, required or not."""
    refined = _refined(context)
    missing: list[str] = []

    if not refined.get("problem"):
        missing.append("problem")
    if not refined.get("solution"):
        missing.append("solution")
    if not refined.get("target_user"):
        missing.append("target_user")
    if not context.hackathon_details:
        missing.append("hackathon_details")
    if not context.team:
        missing.append("team")
    if not context.repository:
        missing.append("repository")
    if not context.supporting_documents:
        missing.append("supporting_documents")
    if not context.presentation:
        missing.append("presentation")

    return missing


def is_complete(context: ProjectContext) -> bool:
    """The explicit completeness gate: every field marked required in
    REQUIRED_FIELDS must be present. Optional fields being missing does
    not block this."""
    missing = set(detect_missing_fields(context))
    required_missing = missing & {f for f, req in REQUIRED_FIELDS.items() if req}
    return not required_missing
