"""
POST /api/v1/projects/{project_id}/chat
GET  /api/v1/projects/{project_id}/chat/history
POST /api/v1/projects/{project_id}/chat/upload

Architecture doc Section 5.7, extended by Workstream A5/A6:
  - A5: chat now splits into Personal ("chat_scope": "personal") and
    Group ("group") chat via the `chat_scope` query/body param -- both
    already share `chat_messages` (phase="coaching"), just filtered.
    Only a message that mentions "@AI" (case-insensitive) invokes the
    Supervisor; every other message is stored only (both roles are
    already team members -- there's no reason to run every group-chat
    line through an LLM call).
  - A6: file intake now works from either chat surface, not just the
    ingestion screen -- POST .../chat/upload extracts text the same
    way app/services/ingestion_service.py's document upload does,
    folds it into project_idea.raw, and links the resulting document
    to a chat_attachments row so the chat UI can show "file: x.pdf"
    inline.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.errors import UnsupportedMediaTypeError
from app.models.chat_message import CHAT_SCOPES
from app.repositories import chat_attachments as chat_attachments_repo
from app.repositories import chat_messages as chat_messages_repo
from app.routers.common import get_project_or_404
from app.services.coach_chat_service import PHASE, handle_coach_message
from app.services.document_extraction import SUPPORTED_DOCUMENT_MIME_TYPES
from app.services.ingestion_service import handle_ingest_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    speaker_name: str | None = None
    chat_scope: str = Field(default="group", description="'personal' or 'group' (A5)")


class ChatResponse(BaseModel):
    reply: str | None
    answered_by: str | None
    ai_invoked: bool


class ChatHistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    agent_node: str | None
    speaker_name: str | None
    chat_scope: str
    mentions_ai: bool
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
    next_cursor: str | None


class ChatUploadResponse(BaseModel):
    document_id: str
    filename: str
    extracted_chars: int
    ai_invoked: bool
    reply: str | None
    answered_by: str | None


def _mentions_ai(message: str) -> bool:
    return "@ai" in message.lower()


@router.post("/{project_id}/chat", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def post_chat(
    project_id: str,
    body: ChatRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChatResponse:
    project = await get_project_or_404(session, project_id)

    if body.chat_scope not in CHAT_SCOPES:
        raise UnsupportedMediaTypeError(f"chat_scope must be one of {CHAT_SCOPES}")

    if not _mentions_ai(body.message):
        # A5: not an @AI message -- store only, no Supervisor call.
        await chat_messages_repo.add_message(
            session,
            project_id=project.id,
            phase=PHASE,
            role="user",
            content=body.message,
            speaker_name=body.speaker_name,
            chat_scope=body.chat_scope,
            mentions_ai=False,
        )
        return ChatResponse(reply=None, answered_by=None, ai_invoked=False)

    reply, answered_by = await handle_coach_message(
        session,
        driver,
        project,
        body.message,
        speaker_name=body.speaker_name,
        chat_scope=body.chat_scope,
    )
    logger.info(
        "coach chat turn",
        extra={"project_id": str(project.id), "answered_by": answered_by, "chat_scope": body.chat_scope},
    )

    return ChatResponse(reply=reply, answered_by=answered_by, ai_invoked=True)


@router.get("/{project_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    project_id: str,
    chat_scope: str | None = Query(default=None, description="filter to 'personal' or 'group'"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    project = await get_project_or_404(session, project_id)

    page = await chat_messages_repo.list_messages_page(
        session, project.id, phase=PHASE, chat_scope=chat_scope, cursor=cursor, limit=limit
    )

    return ChatHistoryResponse(
        messages=[
            ChatHistoryMessage(
                id=str(m.id),
                role=m.role,
                content=m.content,
                agent_node=m.agent_node,
                speaker_name=m.speaker_name,
                chat_scope=m.chat_scope,
                mentions_ai=m.mentions_ai,
                created_at=m.created_at.isoformat(),
            )
            for m in page.messages
        ],
        next_cursor=page.next_cursor,
    )


class ScopedChatRequest(BaseModel):
    message: str = Field(min_length=1)
    speaker_name: str | None = None


@router.post("/{project_id}/chat/personal", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def post_personal_chat(
    project_id: str, body: ScopedChatRequest, session: AsyncSession = Depends(get_db), driver: AsyncDriver = Depends(get_neo4j)
) -> ChatResponse:
    """Spec Section 8's dedicated Personal Chat route -- same logic as
    POST /chat with chat_scope='personal' baked in."""
    return await post_chat(
        project_id, ChatRequest(message=body.message, speaker_name=body.speaker_name, chat_scope="personal"), session, driver
    )


@router.get("/{project_id}/chat/personal/history", response_model=ChatHistoryResponse)
async def get_personal_chat_history(
    project_id: str, cursor: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    return await get_chat_history(project_id, "personal", cursor, limit, session)


@router.post("/{project_id}/chat/group", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def post_group_chat(
    project_id: str, body: ScopedChatRequest, session: AsyncSession = Depends(get_db), driver: AsyncDriver = Depends(get_neo4j)
) -> ChatResponse:
    """Spec Section 8's dedicated Group Chat route -- same logic as
    POST /chat with chat_scope='group' baked in."""
    return await post_chat(
        project_id, ChatRequest(message=body.message, speaker_name=body.speaker_name, chat_scope="group"), session, driver
    )


@router.get("/{project_id}/chat/group/history", response_model=ChatHistoryResponse)
async def get_group_chat_history(
    project_id: str, cursor: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    return await get_chat_history(project_id, "group", cursor, limit, session)


@router.post(
    "/{project_id}/chat/upload",
    response_model=ChatUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_chat_upload(
    project_id: str,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
    file: UploadFile = File(...),
    chat_scope: str = Form(default="group"),
    speaker_name: str | None = Form(default=None),
    message: str = Form(default=""),
) -> ChatUploadResponse:
    """A6: file intake from anywhere in chat, not just the ingestion
    screen. Reuses ingestion_service.handle_ingest_document for the
    actual extraction/project_idea fold-in (one code path for "a file
    landed in this project"), then records a chat message + a
    chat_attachments row linking the two, and -- if the accompanying
    caption mentions @AI -- runs it through the Supervisor same as a
    text message would."""
    project = await get_project_or_404(session, project_id)

    if chat_scope not in CHAT_SCOPES:
        raise UnsupportedMediaTypeError(f"chat_scope must be one of {CHAT_SCOPES}")

    content_type = file.content_type or ""
    if content_type not in SUPPORTED_DOCUMENT_MIME_TYPES:
        raise UnsupportedMediaTypeError(
            f"Unsupported file type {content_type!r}; expected one of "
            f"{sorted(SUPPORTED_DOCUMENT_MIME_TYPES.values())}"
        )

    raw = await file.read()
    result = await handle_ingest_document(
        session, project, filename=file.filename or "upload", content_type=content_type, raw=raw
    )

    caption = message or f"[file] {result.document.filename}"
    chat_message = await chat_messages_repo.add_message(
        session,
        project_id=project.id,
        phase=PHASE,
        role="user",
        content=caption,
        speaker_name=speaker_name,
        chat_scope=chat_scope,
        mentions_ai=_mentions_ai(caption),
    )
    await chat_attachments_repo.create_attachment(
        session, message_id=chat_message.id, document_id=result.document.id
    )

    reply: str | None = None
    answered_by: str | None = None
    ai_invoked = _mentions_ai(caption)
    if ai_invoked:
        # Re-fetch the project so the Supervisor/Team Assistant sees the
        # just-updated project_idea (handle_ingest_document already
        # folded the extracted text in).
        project = await get_project_or_404(session, project_id)
        reply, answered_by = await handle_coach_message(
            session, driver, project, caption, speaker_name=speaker_name, chat_scope=chat_scope
        )

    logger.info(
        "chat file intake",
        extra={"project_id": str(project.id), "document_id": str(result.document.id), "chat_scope": chat_scope},
    )
    return ChatUploadResponse(
        document_id=str(result.document.id),
        filename=result.document.filename,
        extracted_chars=result.extracted_chars,
        ai_invoked=ai_invoked,
        reply=reply,
        answered_by=answered_by,
    )
