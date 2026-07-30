"""
Shared OpenAI embeddings client (Phase 11 / architecture doc Section 3.2).

`text-embedding-3-small`, 1536 dims -- the same model
`scripts/seed_postmortems.py` used to build `postmortem_embeddings` ahead
of the event. This is now the *one* place that ever calls the OpenAI
embeddings API: `app/services/rag_service.py`'s live retrieval path and
`scripts/seed_postmortems.py`'s offline seeding path both call through
here, so a query embedding and a stored document embedding can never
silently drift onto different models/shapes (same "one shared function"
reasoning Phase 11's task list applies to the retrieval helper itself).

Uses `OPENAI_API_KEY` -- separate from `LLM_API_KEY`, which
`app/agents/llm.py` uses for actual agent reasoning.
"""

from __future__ import annotations

import httpx

from app.config import get_settings

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingsUnavailableError(RuntimeError):
    """Raised when OPENAI_API_KEY isn't configured or the OpenAI call fails.

    A distinct type (rather than letting httpx's exception bubble up) so
    callers like app/services/rag_service.py can catch specifically this
    and degrade gracefully instead of accidentally swallowing unrelated
    bugs.
    """


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds a batch of strings in one OpenAI call, preserving input
    order (OpenAI's own response order isn't guaranteed, so this sorts
    by the `index` field it returns)."""
    if not texts:
        return []

    settings = get_settings()
    if not settings.openai_api_key:
        raise EmbeddingsUnavailableError("OPENAI_API_KEY is not set in the environment.")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                OPENAI_EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": EMBEDDING_MODEL, "input": texts},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingsUnavailableError(f"OpenAI embeddings call failed: {exc}") from exc

        data = response.json()

    ordered = sorted(data["data"], key=lambda row: row["index"])
    return [row["embedding"] for row in ordered]


async def embed_text(text: str) -> list[float]:
    """Single-string convenience wrapper around embed_texts -- what the
    live retrieval path (one query at a time) actually calls."""
    (embedding,) = await embed_texts([text])
    return embedding
