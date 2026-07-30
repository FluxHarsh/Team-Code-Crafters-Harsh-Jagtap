"""
Phase 11 -- RAG grounding (Implementation Plan Phase 11 / architecture
doc Section 3.2). Gives the Scope Critic and Reprioritizer real
grounding from curated past-postmortem text instead of pure model
guesswork, on top of the postmortem_embeddings table Phase 1 already
built and scripts/seed_postmortems.py already seeded.

`retrieve_similar_postmortems` is the "one shared function used by both
nodes" the Phase 11 task list calls for: embed the caller's query text
with the same OpenAI model the seed script used
(app/services/embeddings.py), then run a top-k cosine-similarity read
against postmortem_embeddings
(app/repositories/postmortem_embeddings.similarity_search -- read-only
here, this table is never written to live, per Section 3.2).

Grounding is deliberately best-effort: if OPENAI_API_KEY is missing or
the OpenAI call fails, this returns an empty list rather than raising,
so a transient embeddings outage degrades a node's prompt back to its
pre-Phase-11 behavior (no retrieved context) instead of failing the
critique/reprioritize call outright -- the same "degrade gracefully on
a bad external call" posture every LLM call in this codebase already
follows (Scope Critic / Planner / Reprioritizer / Pitch Agent all fall
back rather than raising on a malformed LLM reply).
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import postmortem_embeddings as postmortem_repo
from app.services.embeddings import EmbeddingsUnavailableError, embed_text

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 3


async def retrieve_similar_postmortems(
    session: AsyncSession, query_text: str, *, top_k: int = DEFAULT_TOP_K
) -> list[dict]:
    """Returns up to top_k {source_text, metadata, distance} dicts, most
    similar (lowest cosine distance) first. Returns an empty list -- never
    raises -- on a blank query, a missing OPENAI_API_KEY, or an
    OpenAI/DB failure; callers treat "nothing retrieved" and "retrieval
    failed" identically, since either way the prompt just gets no
    snippet for this turn."""
    if not query_text or not query_text.strip():
        return []

    try:
        query_embedding = await embed_text(query_text)
        rows = await postmortem_repo.similarity_search(session, query_embedding, top_k=top_k)
    except EmbeddingsUnavailableError:
        logger.warning("rag_retrieval_skipped_no_embeddings")
        return []
    except Exception:
        logger.exception("rag_retrieval_failed")
        return []

    return [
        {"source_text": row.source_text, "metadata": row.metadata_, "distance": distance}
        for row, distance in rows
    ]


def format_snippets_for_prompt(snippets: list[dict], *, label: str) -> str:
    """Renders retrieved snippets as a labeled block for direct
    inclusion in a node's human message, e.g.
    label="similar teams historically missed" (Scope Critic) or
    label="projects that hit this kind of blocker historically
    recovered by" (Reprioritizer). Always returns a non-empty string --
    an explicit "none found" line when there's nothing to show, rather
    than an empty section the model would have to guess the meaning
    of."""
    if not snippets:
        return f"Retrieved historical context ({label}): none found."

    lines = [f"Retrieved historical context ({label}):"]
    for snippet in snippets:
        lines.append(f"- {snippet['source_text']}")
    return "\n".join(lines)
