"""
Typed access to postmortem_embeddings (pgvector RAG store).

Read path (similarity_search) is used live by the Scope Critic and
Reprioritizer. The write path (add_embedding) is only ever called by
scripts/seed_postmortems.py ahead of the event — this table is not
written to live during the hackathon (architecture doc Section 3.2).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.postmortem_embedding import PostmortemEmbedding


async def add_embedding(
    session: AsyncSession,
    *,
    source_text: str,
    embedding: list[float],
    metadata: dict | None = None,
) -> PostmortemEmbedding:
    row = PostmortemEmbedding(
        source_text=source_text,
        embedding=embedding,
        metadata_=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def similarity_search(
    session: AsyncSession, query_embedding: list[float], *, top_k: int = 5
) -> list[tuple[PostmortemEmbedding, float]]:
    """Returns the top_k closest rows by cosine distance, each paired
    with its distance (lower = more similar, 0 = identical)."""
    distance = PostmortemEmbedding.embedding.cosine_distance(query_embedding)
    stmt = (
        select(PostmortemEmbedding, distance.label("distance"))
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return [(row.PostmortemEmbedding, row.distance) for row in result]
