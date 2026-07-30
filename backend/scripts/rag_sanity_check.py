"""
Phase 11 sanity check (Implementation Plan Phase 11, task 4): confirm
the seed data from Phase 1 (scripts/seed_postmortems.py) actually
returns relevant neighbors for a couple of test queries *before* the
retrieval helper (app/services/rag_service.py) gets wired into the live
Scope Critic / Reprioritizer prompts.

This is a read-only check -- it never writes to postmortem_embeddings
(only scripts/seed_postmortems.py does that, per architecture doc
Section 3.2) -- and it exercises the exact same code path the live
nodes use (embed via app/services/embeddings.py, then
app/services/rag_service.retrieve_similar_postmortems), so a clean run
here is a real guarantee about what the nodes will see, not a separate
approximation of it.

Usage:
    python -m scripts.rag_sanity_check
    python -m scripts.rag_sanity_check --query "our team is scoping a real-time multiplayer game" --top-k 5
"""

import argparse
import asyncio

from app.db.postgres import get_session_factory
from app.services.rag_service import retrieve_similar_postmortems

# One query shaped like Scope Critic grounding (a project idea/scope),
# one shaped like Reprioritizer grounding (a flagged risk) -- covers
# both call sites this helper feeds.
DEFAULT_QUERIES = [
    "We're building a real-time collaborative whiteboard app with live cursors, "
    "shared drawing, and undo history for a hackathon demo.",
    "The pull request for our auth service integration has been open for 6 hours "
    "with no reviews, and the milestone it's tied to is now blocked.",
]


async def run_query(session, query: str, top_k: int) -> bool:
    print(f"\nQuery: {query!r}")
    results = await retrieve_similar_postmortems(session, query, top_k=top_k)
    if not results:
        print(
            "  (no results -- check OPENAI_API_KEY is set and that "
            "`python -m scripts.seed_postmortems` has been run against this database)"
        )
        return False

    for i, row in enumerate(results, start=1):
        preview = row["source_text"][:120].replace("\n", " ")
        print(f"  {i}. distance={row['distance']:.4f}  {preview}")
    return True


async def main(queries: list[str], top_k: int) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        all_ok = True
        for query in queries:
            ok = await run_query(session, query, top_k)
            all_ok = all_ok and ok

    print()
    if all_ok:
        print("Sanity check passed -- every test query returned at least one neighbor.")
    else:
        print(
            "Sanity check FAILED -- at least one query returned nothing. "
            "Do not wire this into live prompts until this is resolved."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Add a custom test query (repeatable). Defaults to two built-in queries if omitted.",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(main(args.queries or DEFAULT_QUERIES, args.top_k))
