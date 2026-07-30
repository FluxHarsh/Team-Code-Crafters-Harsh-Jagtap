"""
Risk Watcher node -- architecture doc Section 5.4 / Implementation Plan
Phase 6. Evaluates projects.github_state, progress_log, and roadmap
ETAs against a handful of simple, deterministic rules and returns any
newly-detected risks (Section 3.1 shape: {id, risk, severity,
suggested_fix, resolved}).

Deliberately rule-based, not an LLM call -- Phase 6's task list is
explicit that "simple rules" are enough here (the Reprioritizer is
where an LLM earns its keep: deciding drop/extend/reassign and writing
a rationale is a genuinely qualitative call; "is this task overdue with
no matching activity" is not). That also makes this node fully testable
without a live LLM key.

Called directly as a plain async function (not through the Phase 3
chat-turn StateGraph) by app/services/risk_service.py, itself called
from both the GitHub poll hand-off (Phase 5's
_handoff_to_risk_watcher, now wired for real) and the manual
POST .../progress route.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes.github_watcher import match_text_to_task
from app.repositories import agent_run_log as agent_run_log_repo

logger = logging.getLogger(__name__)

# A task due within this many hours (or already overdue) with no
# matched activity gets flagged -- matches the "3 hours" framing in
# Section 5.4's own example risk message.
ETA_RISK_WINDOW_HOURS = 3

# A PR the GitHub Watcher already tagged "stuck" (open >=4h, Phase 5)
# becomes a risk too rather than just sitting quietly in github_state.
STUCK_PR_SEVERITY = "medium"


@dataclass
class NewRisk:
    risk: str
    severity: str
    suggested_fix: str
    task_id: str | None  # real roadmap task id, for the Neo4j AFFECTS edge + Reprioritizer traversal; None if not tied to one task
    category: str  # "eta_risk" | "blocked_task" | "stuck_pr"
    dedup_key: str  # (category, dedup_key) is what _existing_keys checks -- usually == task_id, but a stuck-PR risk isn't tied to a task, so it dedupes on the PR number instead


def _existing_keys(risks: list[dict]) -> set[tuple[str, str | None]]:
    """(category, dedup_key) pairs already present (resolved or not) --
    used so re-running the watcher every poll doesn't spam duplicate
    entries for a condition that's still true."""
    keys = set()
    for r in risks:
        category = r.get("category")
        if category:
            keys.add((category, r.get("dedup_key")))
    return keys


def detect_risks(
    *, roadmap: list[dict], github_state: dict, progress_log: list[dict], existing_risks: list[dict]
) -> list[NewRisk]:
    """Pure function, no I/O -- easy to unit test in isolation from the
    DB/Neo4j calls that wrap it in run_risk_watcher below."""
    now = datetime.now(timezone.utc)
    existing = _existing_keys(existing_risks)
    new_risks: list[NewRisk] = []

    commit_matched_ids = {c.get("matched_task") for c in github_state.get("commits", []) if c.get("matched_task")}
    progress_matched_ids = set()
    for entry in progress_log:
        text = entry.get("text", "")
        if not text:
            continue
        matched = match_text_to_task(text, [], roadmap)
        if matched:
            progress_matched_ids.add(matched)
    activity_task_ids = commit_matched_ids | progress_matched_ids

    # Rule A: task due soon (or overdue) with no matched activity.
    for task in roadmap:
        task_id = task.get("id")
        if not task_id or task.get("status") == "done":
            continue
        eta_raw = task.get("eta")
        if not eta_raw:
            continue
        try:
            eta = datetime.fromisoformat(eta_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        hours_until_eta = (eta - now).total_seconds() / 3600
        if hours_until_eta > ETA_RISK_WINDOW_HOURS:
            continue
        if task_id in activity_task_ids:
            continue
        if ("eta_risk", task_id) in existing:
            continue
        overdue = hours_until_eta < 0
        new_risks.append(
            NewRisk(
                risk=f"No commits on '{task.get('task', task_id)}' task within "
                f"{ETA_RISK_WINDOW_HOURS} hours of its ETA",
                severity="high" if overdue else "medium",
                suggested_fix=f"Reassign or extend the ETA for '{task.get('task', task_id)}'",
                task_id=task_id,
                category="eta_risk",
                dedup_key=task_id,
            )
        )

    # Rule B: task manually moved to "blocked" (Phase 4's PATCH route
    # flags this on the response, but doesn't write a risks[] entry --
    # this is where that actually happens).
    for task in roadmap:
        task_id = task.get("id")
        if not task_id or task.get("status") != "blocked":
            continue
        if ("blocked_task", task_id) in existing:
            continue
        new_risks.append(
            NewRisk(
                risk=f"'{task.get('task', task_id)}' is blocked" + (f": {task['note']}" if task.get("note") else ""),
                severity="high",
                suggested_fix=f"Reprioritize or reassign '{task.get('task', task_id)}'",
                task_id=task_id,
                category="blocked_task",
                dedup_key=task_id,
            )
        )

    # Rule C: a PR the GitHub Watcher already flagged "stuck".
    for pr in github_state.get("open_prs", []):
        if pr.get("status") != "stuck":
            continue
        pr_number = pr.get("number")
        if ("stuck_pr", str(pr_number)) in existing:
            continue
        new_risks.append(
            NewRisk(
                risk=f"PR #{pr_number} has been open {pr.get('hours_open')}h with no merge",
                severity=STUCK_PR_SEVERITY,
                suggested_fix=f"Review and merge or close PR #{pr_number}",
                task_id=None,
                category="stuck_pr",
                dedup_key=str(pr_number),
            )
        )

    return new_risks


async def run_risk_watcher(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    roadmap: list[dict],
    github_state: dict,
    progress_log: list[dict],
    existing_risks: list[dict],
    trigger: str,
) -> list[dict]:
    """Writes its own agent_run_log row and returns the new risk dicts
    (Section 3.1 shape, plus internal category/task_id bookkeeping
    fields) to append to projects.risks -- persistence and the Neo4j
    Risk/AFFECTS sync are the caller's job (app/services/risk_service.py),
    same split as every other node in this codebase."""
    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="risk_watcher",
        trigger=trigger,
        input_snapshot={
            "roadmap_task_count": len(roadmap),
            "commit_count": len(github_state.get("commits", [])),
            "progress_log_count": len(progress_log),
        },
    )
    try:
        detected = detect_risks(
            roadmap=roadmap,
            github_state=github_state,
            progress_log=progress_log,
            existing_risks=existing_risks,
        )
        new_risk_dicts = [
            {
                "id": f"r-{uuid.uuid4().hex[:8]}",
                "risk": r.risk,
                "severity": r.severity,
                "suggested_fix": r.suggested_fix,
                "resolved": False,
                "task_id": r.task_id,
                "category": r.category,
                "dedup_key": r.dedup_key,
            }
            for r in detected
        ]
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"new_risk_count": len(new_risk_dicts)}, status="done"
        )
        return new_risk_dicts
    except Exception:
        logger.exception("risk_watcher_failed", extra={"project_id": str(project_id)})
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "risk_watcher_failed"}, status="failed"
        )
        raise
