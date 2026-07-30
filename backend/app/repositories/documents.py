"""Typed CRUD for the documents table."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


async def create_document(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    filename: str,
    mime_type: str,
    extracted_text: str | None = None,
) -> Document:
    document = Document(
        project_id=project_id,
        filename=filename,
        mime_type=mime_type,
        extracted_text=extracted_text,
    )
    session.add(document)
    await session.flush()
    return document


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> Document | None:
    return await session.get(Document, document_id)


async def list_documents_for_project(
    session: AsyncSession, project_id: uuid.UUID
) -> list[Document]:
    result = await session.execute(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.uploaded_at.asc())
    )
    return list(result.scalars().all())
