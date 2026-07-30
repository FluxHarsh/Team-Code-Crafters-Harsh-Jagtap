"""
POST /api/v1/projects/{project_id}/ingest/message
POST /api/v1/projects/{project_id}/ingest/document
GET  /api/v1/projects/{project_id}/ingest/history

Architecture doc Section 5.1. Step 1 of the demo flow (Section 2.1) --
the conversational chat that turns a raw idea into enough context for
the Planner to take over.

Phase 3: ingest/message routes to the real Intake node (LangGraph
skeleton, app/agents/graph.py) via app/services/ingestion_service.py,
persists both turns to chat_messages(phase=intake), and lets the Intake
node decide ready_for_planning. ingest/document does real pdf/docx/txt/md
text extraction and folds it into project_idea.raw. Every node
invocation writes an agent_run_log row (inside the service/node layer).
"""

import logging

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.errors import UnsupportedMediaTypeError
from app.repositories import chat_messages as chat_messages_repo
from app.routers.common import get_project_or_404
from app.services.document_extraction import SUPPORTED_DOCUMENT_MIME_TYPES
from app.services.ingestion_service import handle_ingest_document, handle_ingest_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["ingestion"])


class IngestMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    speaker_name: str | None = Field(
        default=None, description="Display-only, not a credential (Section 4)."
    )


class IngestMessageResponse(BaseModel):
    reply: str
    ready_for_planning: bool


class IngestDocumentResponse(BaseModel):
    document_id: str
    filename: str
    extracted_chars: int


class ChatMessageOut(BaseModel):
    role: str
    content: str


class IngestHistoryResponse(BaseModel):
    messages: list[ChatMessageOut]


@router.post("/{project_id}/ingest/message", response_model=IngestMessageResponse)
async def post_ingest_message(
    project_id: str, body: IngestMessageRequest, session: AsyncSession = Depends(get_db)
) -> IngestMessageResponse:
    project = await get_project_or_404(session, project_id)

    result = await handle_ingest_message(
        session, project, body.message, speaker_name=body.speaker_name
    )

    return IngestMessageResponse(reply=result.reply, ready_for_planning=result.ready_for_planning)


@router.post(
    "/{project_id}/ingest/document",
    response_model=IngestDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_ingest_document(
    project_id: str,
    session: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
) -> IngestDocumentResponse:
    project = await get_project_or_404(session, project_id)

    content_type = file.content_type or ""
    if content_type not in SUPPORTED_DOCUMENT_MIME_TYPES:
        raise UnsupportedMediaTypeError(
            f"Unsupported file type {content_type!r}; expected one of "
            f"{sorted(SUPPORTED_DOCUMENT_MIME_TYPES.values())}"
        )

    raw = await file.read()

    result = await handle_ingest_document(
        session,
        project,
        filename=file.filename or "upload",
        content_type=content_type,
        raw=raw,
    )

    logger.info(
        "document ingested",
        extra={"project_id": str(project.id), "document_id": str(result.document.id)},
    )

    return IngestDocumentResponse(
        document_id=str(result.document.id),
        filename=result.document.filename,
        extracted_chars=result.extracted_chars,
    )


@router.get("/{project_id}/ingest/history", response_model=IngestHistoryResponse)
async def get_ingest_history(
    project_id: str, session: AsyncSession = Depends(get_db)
) -> IngestHistoryResponse:
    project = await get_project_or_404(session, project_id)
    messages = await chat_messages_repo.list_messages(session, project.id, phase="intake")
    return IngestHistoryResponse(
        messages=[ChatMessageOut(role=m.role, content=m.content) for m in messages]
    )
