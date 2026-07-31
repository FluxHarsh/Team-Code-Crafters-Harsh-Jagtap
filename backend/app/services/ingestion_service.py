"""
Orchestrates the ingestion chat turn (Implementation Plan Phase 3):
persist the user's turn, invoke the Intake node via the LangGraph
skeleton, persist the agent's reply, and fold any refined project_idea
back onto the projects row. Routes call this instead of touching
app.agents or app.repositories directly, keeping app/routers/ingestion.py
a thin HTTP shim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_intake_turn
from app.models.document import Document
from app.models.project import Project
from app.repositories import chat_messages as chat_messages_repo
from app.repositories import documents as documents_repo
from app.repositories import projects as projects_repo
from app.services.document_extraction import extract_text
from app.services.project_context import ProjectContext, detect_missing_fields, is_complete
from app.ws.connection_manager import broadcast

logger = logging.getLogger(__name__)


@dataclass
class IngestMessageResult:
    reply: str
    ready_for_planning: bool


async def handle_ingest_message(
    session: AsyncSession, project: Project, message: str, *, speaker_name: str | None = None
) -> IngestMessageResult:
    await chat_messages_repo.add_message(
        session,
        project_id=project.id,
        phase="intake",
        role="user",
        content=message,
        speaker_name=speaker_name,
    )

    result_state = await run_intake_turn(
        session,
        project_id=project.id,
        project_idea=project.project_idea or {},
        user_message=message,
    )

    reply = result_state["reply"]
    llm_ready = result_state["ready_for_planning"]
    updated_project_idea = result_state["updated_project_idea"]

    # A1: don't just trust the Intake node's self-reported flag -- run
    # the explicit Missing Information Detector against a preview of
    # the context this turn would leave behind (project_idea hasn't
    # been persisted yet, so build the preview in memory rather than
    # re-querying).
    preview_context = ProjectContext(
        hackathon_details=project.hackathon_details or {},
        team=project.team or [],
        project=updated_project_idea,
        repository=None,
        supporting_documents=[],
        presentation=project.pitch_outline,
    )
    ready_for_planning = llm_ready and is_complete(preview_context)
    missing_fields = detect_missing_fields(preview_context)

    if llm_ready and not ready_for_planning:
        required_missing = [f for f in missing_fields if f in ("problem", "solution", "target_user")]
        if required_missing:
            reply = (
                f"{reply}\n\n(Still need: {', '.join(required_missing)} before I can hand this to the Planner.)"
            )

    await chat_messages_repo.add_message(
        session,
        project_id=project.id,
        phase="intake",
        role="agent",
        content=reply,
        agent_node="intake",
    )

    fields: dict = {"project_idea": updated_project_idea, "next_action": "intake"}
    # Only ever moves intake -> planning here; approval (planning ->
    # active) is Phase 3's plan/approve route, not this one.
    if ready_for_planning and project.status == "intake":
        fields["status"] = "planning"

    await projects_repo.update_project(session, project.id, **fields)

    logger.info(
        "ingest_message_handled",
        extra={"project_id": str(project.id), "ready_for_planning": ready_for_planning},
    )
    return IngestMessageResult(reply=reply, ready_for_planning=ready_for_planning)


@dataclass
class IngestDocumentResult:
    document: Document
    extracted_chars: int


async def handle_ingest_document(
    session: AsyncSession,
    project: Project,
    *,
    filename: str,
    content_type: str,
    raw: bytes,
) -> IngestDocumentResult:
    extracted_text = extract_text(raw, content_type)
    extracted_chars = len(extracted_text) if extracted_text else len(raw)

    document = await documents_repo.create_document(
        session,
        project_id=project.id,
        filename=filename,
        mime_type=content_type,
        extracted_text=extracted_text or None,
    )

    if extracted_text:
        project_idea = dict(project.project_idea or {})
        raw_context = project_idea.get("raw", "")
        project_idea["raw"] = (
            f"{raw_context}\n\n[from uploaded document {filename!r}]\n{extracted_text}"
        ).strip()
        await projects_repo.update_project(session, project.id, project_idea=project_idea)

    logger.info(
        "document_ingested",
        extra={
            "project_id": str(project.id),
            "document_id": str(document.id),
            "extracted_chars": extracted_chars,
        },
    )
    return IngestDocumentResult(document=document, extracted_chars=extracted_chars)
