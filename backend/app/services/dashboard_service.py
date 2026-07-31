"""
Dashboard aggregation (spec doc Section 8, app/routers/dashboard.py).

Deliberately no new storage -- every endpoint here reads fields that
already exist on `projects` (roadmap, risks, github_state, team) or in
planner_suggestions, and reshapes them. Only unlocked once a plan is
approved (plan_approved_at is set), matching Workstream A13's "dashboard
unlocks only after Planner approval."
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.repositories import planner_suggestions as planner_suggestions_repo
from app.services.roadmap_service import build_roadmap_board


def overview(project: Project) -> dict:
    board = build_roadmap_board(project)
    return {
        "project_id": str(project.id),
        "name": project.name,
        "status": project.status,
        "percent_complete": board.summary["percent_complete"],
        "hours_remaining": float(project.hours_remaining) if project.hours_remaining is not None else None,
        "open_risks": len([r for r in (project.risks or []) if not r.get("resolved")]),
        "team_size": len(project.team or []),
    }


def timeline(project: Project) -> list[dict]:
    return [
        {"id": t.get("id"), "task": t.get("task"), "owner": t.get("owner"), "eta": t.get("eta"), "status": t.get("status")}
        for t in (project.roadmap or [])
    ]


def kanban(project: Project) -> dict:
    board = build_roadmap_board(project)
    return {"summary": board.summary, "nodes": board.nodes, "edges": board.edges}


def health(project: Project) -> dict:
    risks = project.risks or []
    open_risks = [r for r in risks if not r.get("resolved")]
    insights = (project.github_state or {}).get("insights", [])
    status = "on_track"
    if any(r.get("severity") in ("high", "critical") for r in open_risks):
        status = "at_risk"
    elif open_risks or insights:
        status = "watch"
    return {
        "health_status": status,
        "open_risk_count": len(open_risks),
        "github_insight_count": len(insights),
        "hours_remaining": float(project.hours_remaining) if project.hours_remaining is not None else None,
    }


def team_status(project: Project) -> list[dict]:
    board = build_roadmap_board(project)
    by_owner: dict[str, list[str]] = {}
    for node in board.nodes:
        owner = node.get("owner") or "unassigned"
        by_owner.setdefault(owner, []).append(node["column"])
    return [
        {
            "name": m.get("name"),
            "role": m.get("role"),
            "skills": m.get("skills", []),
            "assigned_columns": by_owner.get(m.get("name"), []),
        }
        for m in (project.team or [])
    ]


def activity_feed(project: Project) -> list[dict]:
    events = [
        {"source": "progress", "text": e.get("text"), "ts": e.get("ts")} for e in (project.progress_log or [])
    ]
    events += [
        {"source": "github", "text": c.get("message"), "ts": None}
        for c in (project.github_state or {}).get("commits", [])[:10]
    ]
    events.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return events[:30]


async def recommendations(session: AsyncSession, project: Project) -> list[dict]:
    suggestions = await planner_suggestions_repo.list_suggestions_for_project(session, project.id, status="pending")
    return [
        {
            "id": str(s.id),
            "source": s.source,
            "risk_id": s.risk_id,
            "decision": s.decision,
            "rationale": s.rationale,
        }
        for s in suggestions
    ]
