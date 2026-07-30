"""
POST /api/v1/projects/{project_id}/chat
GET  /api/v1/projects/{project_id}/chat/history

Architecture doc Section 5.7. The post-approval coach chat panel --
separate from the Phase 3 ingestion/planning chats (phase="intake"/
"planning" vs this router's phase="coaching" on the shared
chat_messages table).

Phase 8: chat is real now, via app/services/coach_chat_service.py --
the Supervisor classifies each message as "replan" (Phase 4's
replan_roadmap), "reprioritize" (Phase 6's reprioritize_risk), or a
question (the Team Assistant's grounded Q&A). history is now really
cursor-paginated (keyset on created_at/id) instead of always returning
next_cursor: null.
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_neo4j
from app.repositories import chat_messages as chat_messages_repo
from app.routers.common import get_project_or_404
from app.services.coach_chat_service import PHASE, handle_coach_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    speaker_name: str | None = None


class ChatResponse(BaseModel):
    reply: str
    answered_by: str


class ChatHistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    agent_node: str | None
    speaker_name: str | None
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
    next_cursor: str | None


@router.post("/{project_id}/chat", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def post_chat(
    project_id: str,
    body: ChatRequest,
    session: AsyncSession = Depends(get_db),
    driver: AsyncDriver = Depends(get_neo4j),
) -> ChatResponse:
    project = await get_project_or_404(session, project_id)

    reply, answered_by = await handle_coach_message(
        session, driver, project, body.message, speaker_name=body.speaker_name
    )
    logger.info("coach chat turn", extra={"project_id": str(project.id), "answered_by": answered_by})

    return ChatResponse(reply=reply, answered_by=answered_by)


@router.get("/{project_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    project_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    project = await get_project_or_404(session, project_id)

    page = await chat_messages_repo.list_messages_page(
        session, project.id, phase=PHASE, cursor=cursor, limit=limit
    )

    return ChatHistoryResponse(
        messages=[
            ChatHistoryMessage(
                id=str(m.id),
                role=m.role,
                content=m.content,
                agent_node=m.agent_node,
                speaker_name=m.speaker_name,
                created_at=m.created_at.isoformat(),
            )
            for m in page.messages
        ],
        next_cursor=page.next_cursor,
    )
