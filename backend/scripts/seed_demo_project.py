"""
Phase 12 -- seeds a "pre-baked" fallback project (Implementation Plan
Phase 12: "in case live GitHub polling misbehaves at demo time, keep
one project with realistic pre-seeded risks/roadmap/pitch as a fallback
talking point").

This is a deterministic, offline seed -- it does not call the LLM, does
not call OpenAI, and does not touch GitHub. It writes directly through
the same repository functions every live code path uses
(app/repositories/*, app/repositories/graph.py) so the resulting row is
indistinguishable from one a real 20-hour run would have produced: a
believable project_idea/scope, a roadmap with a mix of done/in_progress/
blocked/todo tasks and real depends_on edges, one resolved risk and one
still-open risk (so "watch a risk get flagged and resolved" has
something to point at even with zero live GitHub activity), a generated
pitch_outline, populated chat history across all three phases, matching
critique_history rows, agent_run_log rows for every node in the
pipeline, and the Neo4j Milestone/Risk graph kept in sync -- exactly
the shape app/repositories/graph.py's own module docstring says should
never drift from Postgres.

Deliberately left out: no github_connections row and project.status is
left at "pitch_ready" rather than "active", so Phase 10's scheduler
startup recovery (which only re-registers "active" projects) never
tries to poll a real repo for this project -- the whole point of a
fallback is that it doesn't depend on anything live.

Usage:
    python -m scripts.seed_demo_project
    python -m scripts.seed_demo_project --wipe   # delete a prior demo project of the same name first
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db.neo4j import get_driver
from app.db.postgres import get_session_factory
from app.models.chat_message import ChatMessage
from app.models.critique_history import CritiqueHistory
from app.models.agent_run_log import AgentRunLog
from app.models.project import Project
from app.repositories import agent_run_log as agent_run_log_repo
from app.repositories import chat_messages as chat_messages_repo
from app.repositories import critique_history as critique_history_repo
from app.repositories import graph as graph_repo
from app.repositories import projects as projects_repo

DEMO_PROJECT_NAME = "ShiftSwap (Demo Fallback)"

# --- Project idea / scope --------------------------------------------------

PROJECT_IDEA = {
    "raw": (
        "Hospital units end up understaffed on short notice because swapping "
        "an open shift today means texting a group chat and hoping someone "
        "sees it in time. We want a small real-time board where a nurse can "
        "post a shift they need covered, another nurse on the same unit can "
        "claim it instantly, and the charge nurse can see coverage gaps "
        "forming before a shift actually goes unstaffed."
    ),
    "refined": {
        "problem": "Open shifts get discovered too late for anyone to react.",
        "solution": "A real-time open-shift board with instant claim + a gap dashboard for the charge nurse.",
        "target_user": "Floor nurses and charge nurses on a single hospital unit.",
    },
}

SCOPE = {
    "mvp_features": [
        "Post an open shift that needs covering",
        "Claim an open shift (first-claim-wins, no approval step)",
        "Charge-nurse dashboard: open shifts + projected coverage gaps",
        "Live update when a shift is posted or claimed (no polling/refresh)",
    ],
    "cut_features": [
        "Full shift-scheduling engine (we're only handling swaps, not the base schedule)",
        "Payroll / HR system integration",
        "Native mobile app (mobile-responsive web is enough for the demo)",
    ],
    "assumptions": [
        "Nurses already have accounts in the hospital's existing scheduling system we're reading base shifts from",
        "A same-unit swap doesn't need manager approval -- only cross-unit swaps would, and those are out of scope",
    ],
}

# --- Roadmap -----------------------------------------------------------------
# ids are short and stable on purpose (matches the shape the Planner's
# own prompt produces) so Neo4j Milestone ids line up 1:1 with these.


def _hours_ago(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _eta_in(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


ROADMAP = [
    {
        "id": "t-1",
        "task": "FastAPI + Postgres skeleton, seed base shift data",
        "owner": "Dev A",
        "eta": None,
        "status": "done",
        "depends_on": [],
    },
    {
        "id": "t-2",
        "task": "POST /shifts/{id}/open + GET /shifts open-shift list API",
        "owner": "Dev B",
        "eta": None,
        "status": "done",
        "depends_on": ["t-1"],
    },
    {
        "id": "t-3",
        "task": "Claim-shift flow + coverage-gap detection logic",
        "owner": "Dev A",
        "eta": None,
        "status": "done",
        "depends_on": ["t-2"],
    },
    {
        "id": "t-4",
        "task": "Charge-nurse dashboard: open shifts + coverage gaps (frontend)",
        "owner": "Dev C",
        "eta": _hours_ago(1),
        "status": "blocked",
        "depends_on": ["t-3"],
    },
    {
        "id": "t-5",
        "task": "Live update via WebSocket on post/claim (no refresh needed)",
        "owner": "Dev B",
        "eta": _eta_in(1.5),
        "status": "in_progress",
        "depends_on": ["t-2"],
    },
    {
        "id": "t-6",
        "task": "Demo script + realistic seed data for judges",
        "owner": "Dev C",
        "eta": _eta_in(2.5),
        "status": "todo",
        "depends_on": ["t-4", "t-5"],
    },
]


# --- Risks -------------------------------------------------------------------
# One resolved (so the risk feed has real history), one still open (so
# there's something live to point the dashboard/reprioritize demo at
# even with zero real GitHub activity during the actual demo).

RISK_RESOLVED_ID = f"r-{uuid.uuid4().hex[:8]}"
RISK_OPEN_ID = f"r-{uuid.uuid4().hex[:8]}"

RISKS = [
    {
        "id": RISK_RESOLVED_ID,
        "risk": (
            "'Claim-shift flow + coverage-gap detection logic' (t-3) was overdue with no "
            "matching GitHub commit for over 3 hours."
        ),
        "severity": "high",
        "suggested_fix": "Reassign or extend the ETA for 'Claim-shift flow + coverage-gap detection logic'",
        "task_id": "t-3",
        "resolved": True,
        "resolution_note": (
            "Reprioritizer: reassign -- fixing this unblocks 2 downstream milestone(s) "
            "(Charge-nurse dashboard, Demo script + realistic seed data) -- reassigning for now."
        ),
    },
    {
        "id": RISK_OPEN_ID,
        "risk": "'Charge-nurse dashboard: open shifts + coverage gaps (frontend)' (t-4) was manually moved to blocked.",
        "severity": "medium",
        "suggested_fix": "Reassign or unblock 'Charge-nurse dashboard: open shifts + coverage gaps (frontend)'",
        "task_id": "t-4",
        "resolved": False,
    },
]

# --- GitHub state (simulated -- no real github_connections row) --------------

GITHUB_STATE = {
    "commits": [
        {"sha": "a1b2c3d", "message": "feat: shift model + seed data (t-1)", "matched_task": "t-1"},
        {"sha": "b2c3d4e", "message": "feat: open-shift list + claim API (t-2)", "matched_task": "t-2"},
        {"sha": "c3d4e5f", "message": "feat: coverage-gap detection (t-3)", "matched_task": "t-3"},
    ],
    "open_prs": [
        {"number": 14, "title": "WIP: charge-nurse dashboard (t-4)", "status": "stuck", "matched_task": "t-4"},
    ],
    "branches": ["main", "feat/coverage-gap", "feat/dashboard"],
    "issues": [
        {"number": 9, "title": "Coverage-gap dashboard needs a design decision on gap severity colors", "matched_task": "t-4"},
    ],
}

PROGRESS_LOG = [
    {"source": "manual", "text": "Base shift model + seed data merged, API skeleton up.", "ts": _hours_ago(15)},
    {"source": "manual", "text": "Claim flow works end to end against seed data.", "ts": _hours_ago(9)},
    {
        "source": "manual",
        "text": "Dashboard blocked on a design call for how to show gap severity -- pairing with Dev A to unblock.",
        "ts": _hours_ago(2),
    },
]

# --- Pitch ---------------------------------------------------------------

PITCH_OUTLINE = {
    "hook": "Every hospital unit has a group chat that's basically a 2am game of chicken over who covers the next shift.",
    "problem": (
        "Open shifts get discovered too late for anyone to react -- by the time a "
        "gap is visible, it's already a staffing crisis, not a heads-up."
    ),
    "solution": (
        "ShiftSwap is a real-time board: post an open shift, another nurse claims it "
        "instantly, and the charge nurse sees coverage gaps forming before they become "
        "a real problem."
    ),
    "demo_flow": [
        "Nurse posts an open shift on the board",
        "A second nurse claims it -- the charge-nurse dashboard updates live, no refresh",
        "We show the coverage-gap view catching a still-unclaimed shift before it goes unstaffed",
    ],
    "differentiator": "No new scheduling system to adopt -- it only handles the swap, live, on top of what units already use.",
    "ask": "Feedback on whether the same-unit-only swap assumption holds up outside a hackathon demo.",
}


async def _get_or_create_project(session) -> tuple[Project, bool]:
    result = await session.execute(select(Project).where(Project.name == DEMO_PROJECT_NAME))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing, False
    project = await projects_repo.create_project(session, name=DEMO_PROJECT_NAME)
    return project, True


async def _wipe_existing(session, driver) -> None:
    result = await session.execute(select(Project.id).where(Project.name == DEMO_PROJECT_NAME))
    project_ids = [row[0] for row in result.all()]
    for project_id in project_ids:
        await session.execute(delete(ChatMessage).where(ChatMessage.project_id == project_id))
        await session.execute(delete(CritiqueHistory).where(CritiqueHistory.project_id == project_id))
        await session.execute(delete(AgentRunLog).where(AgentRunLog.project_id == project_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        async with driver.session() as neo_session:
            await neo_session.run(
                "MATCH (p:Project {id: $pid}) "
                "OPTIONAL MATCH (p)<-[:BELONGS_TO]-(m:Milestone) "
                "OPTIONAL MATCH (r:Risk)-[:AFFECTS]->(m) "
                "DETACH DELETE p, m, r",
                pid=str(project_id),
            )
    await session.commit()
    if project_ids:
        print(f"Wiped {len(project_ids)} prior demo project row(s) (Postgres + Neo4j).")


async def _seed_chat_history(session, project_id: uuid.UUID) -> None:
    turns = [
        ("intake", "user", "We want to fix nurses missing open shifts on their unit until it's too late.", None),
        (
            "intake",
            "agent",
            "Got it -- who's the actual user claiming the shift, and is this within one unit or across units?",
            "intake",
        ),
        (
            "intake",
            "user",
            "Same unit only for now. A nurse posts a shift they can't cover, another nurse on the unit claims it.",
            None,
        ),
        (
            "planning",
            "user",
            "Can we also auto-approve cross-unit swaps? Might as well since we're already here.",
            None,
        ),
        (
            "planning",
            "agent",
            (
                "I'd cut that -- cross-unit swaps usually need manager sign-off in real hospitals, and building "
                "that approval flow on top of the live board eats most of your remaining build time for a feature "
                "that isn't in your core demo story. Keeping it same-unit-only for the MVP."
            ),
            "planner",
        ),
        (
            "planning",
            "user",
            "Fair, let's keep it same-unit only and cut cross-unit swaps.",
            None,
        ),
        (
            "coaching",
            "user",
            "What's currently blocking us?",
            None,
        ),
        (
            "coaching",
            "agent",
            (
                "One open risk: the charge-nurse dashboard (t-4) is manually flagged blocked -- Dev C is stuck on "
                "a design decision for how to color-code gap severity. Everything else is done or in progress."
            ),
            "team_assistant",
        ),
    ]
    for phase, role, content, agent_node in turns:
        await chat_messages_repo.add_message(
            session,
            project_id=project_id,
            phase=phase,
            role=role,
            content=content,
            agent_node=agent_node,
        )


async def _seed_critiques(session, project_id: uuid.UUID) -> None:
    critiques = [
        ("overscope", "Cross-unit swaps typically need manager approval in real hospitals -- building that approval flow isn't buildable alongside the core swap board in the remaining time."),
        ("assumption", "This assumes nurses already have accounts in an existing scheduling system to read base shifts from -- worth stating out loud since the demo doesn't build that system."),
        ("scope_gap", "There's no handling yet for what happens if two nurses claim the same open shift at nearly the same time -- worth at least a 'first write wins' rule before the demo."),
    ]
    for category, text in critiques:
        await critique_history_repo.add_critique(
            session, project_id=project_id, category=category, critique_text=text
        )


async def _seed_agent_run_log(session, project_id: uuid.UUID) -> None:
    runs = [
        ("supervisor", "user_action", {"requested_phase": "intake"}, {"route": "intake"}),
        ("intake", "user_action", {"user_message": "same unit only, first-claim-wins"}, {"ready_for_planning": True}),
        ("scope_critic", "user_action", {"retrieved_postmortem_count": 2}, {"new_critiques": 2}),
        ("planner", "user_action", {"critique_count": 3}, {"roadmap_task_count": len(ROADMAP)}),
        ("github_watcher", "scheduled_poll", {"repo": "demo-org/shiftswap"}, {"commits_matched": 3, "prs_flagged_stuck": 1}),
        ("risk_watcher", "scheduled_poll", {"roadmap_task_count": len(ROADMAP)}, {"new_risks": 1}),
        (
            "reprioritizer",
            "github_watcher",
            {"risk_id": RISK_RESOLVED_ID, "retrieved_postmortem_count": 2},
            {"decision": "reassign", "rationale": RISKS[0]["resolution_note"]},
        ),
        ("pitch_agent", "user_action", {"hours_remaining": 2.5}, {"pitch_generated": True}),
    ]
    now = datetime.now(timezone.utc)
    for i, (node_name, trigger, input_snapshot, output_snapshot) in enumerate(runs):
        run = await agent_run_log_repo.start_run(
            session, project_id=project_id, node_name=node_name, trigger=trigger, input_snapshot=input_snapshot
        )
        run.started_at = now - timedelta(hours=len(runs) - i)
        await agent_run_log_repo.finish_run(session, run.id, output_snapshot=output_snapshot, status="done")


async def _sync_neo4j(driver, project_id: uuid.UUID) -> None:
    await graph_repo.sync_roadmap(driver, project_id, ROADMAP)
    for risk in RISKS:
        await graph_repo.create_risk_node(
            driver, risk["id"], severity=risk["severity"], task_id=risk.get("task_id")
        )
        if risk["resolved"]:
            await graph_repo.mark_risk_resolved(driver, risk["id"])


async def seed(*, wipe: bool) -> None:
    session_factory = get_session_factory()
    driver = get_driver()

    async with session_factory() as session:
        if wipe:
            await _wipe_existing(session, driver)

        project, created = await _get_or_create_project(session)
        if not created:
            print(f"Demo project {project.id} already exists -- updating it in place (pass --wipe to start fresh).")

        await projects_repo.update_project(
            session,
            project.id,
            status="pitch_ready",
            project_idea=PROJECT_IDEA,
            scope=SCOPE,
            roadmap=ROADMAP,
            risks=RISKS,
            progress_log=PROGRESS_LOG,
            github_state=GITHUB_STATE,
            pitch_outline=PITCH_OUTLINE,
            pitch_generated_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            next_action="pitch_agent",
            hours_remaining=2.5,
            plan_approved_at=datetime.now(timezone.utc) - timedelta(hours=16),
        )

        if created:
            # Only seed history/critiques/run-log once -- re-running
            # without --wipe just refreshes the projects row above.
            await _seed_chat_history(session, project.id)
            await _seed_critiques(session, project.id)
            await _seed_agent_run_log(session, project.id)

        await session.commit()

        await _sync_neo4j(driver, project.id)

    print(f"Seeded fallback demo project {project.id!r} ({DEMO_PROJECT_NAME!r}).")
    print("status=pitch_ready, no github_connections row -- safe from live polling.")
    print(f"GET  /api/v1/projects/{project.id}")
    print(f"GET  /api/v1/projects/{project.id}/pitch")
    print(f"GET  /api/v1/projects/{project.id}/risks   (one resolved, one open: {RISK_OPEN_ID})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete any prior demo project of the same name (Postgres + Neo4j) before reseeding.",
    )
    args = parser.parse_args()
    asyncio.run(seed(wipe=args.wipe))


if __name__ == "__main__":
    main()
