"""
Seeds postmortem_embeddings ahead of the hackathon (architecture doc
Section 3.2 — "seeded ahead of the hackathon ... not written to live
during the event").

Reads curated postmortem text from scripts/seed_data/postmortems.json,
embeds each chunk with OpenAI text-embedding-3-small (1536 dims), and
inserts into the pgvector table via the repository layer.

As of Phase 11, the actual OpenAI call goes through
app/services/embeddings.py -- the same module the live retrieval helper
(app/services/rag_service.py) uses -- so a seeded document embedding and
a live query embedding are always produced by identical code, never two
copies that could drift apart.

Usage:
    python -m scripts.seed_postmortems
    python -m scripts.seed_postmortems --file path/to/other.json
    python -m scripts.seed_postmortems --wipe   # delete existing rows first
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.db.postgres import get_session_factory
from app.models.postmortem_embedding import PostmortemEmbedding
from app.repositories.postmortem_embeddings import add_embedding
from app.services.embeddings import EMBEDDING_MODEL, embed_texts

DEFAULT_SEED_FILE = Path(__file__).parent / "seed_data" / "postmortems.json"


async def wipe_existing(session) -> int:
    from sqlalchemy import delete

    result = await session.execute(delete(PostmortemEmbedding))
    return result.rowcount or 0


async def seed(seed_file: Path, *, wipe: bool) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in the environment.")

    entries = json.loads(seed_file.read_text())
    if not entries:
        print(f"{seed_file} is empty — nothing to seed.")
        return

    texts = [entry["source_text"] for entry in entries]
    print(f"Embedding {len(texts)} postmortem chunk(s) via {EMBEDDING_MODEL}...")
    embeddings = await embed_texts(texts)

    session_factory = get_session_factory()
    async with session_factory() as session:
        if wipe:
            deleted = await wipe_existing(session)
            print(f"Deleted {deleted} existing row(s).")

        for entry, embedding in zip(entries, embeddings):
            await add_embedding(
                session,
                source_text=entry["source_text"],
                embedding=embedding,
                metadata=entry.get("metadata", {}),
            )
        await session.commit()

    print(f"Seeded {len(entries)} row(s) into postmortem_embeddings.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_SEED_FILE,
        help="Path to a JSON file of {source_text, metadata} entries.",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete all existing postmortem_embeddings rows first.",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.file, wipe=args.wipe))


if __name__ == "__main__":
    main()
