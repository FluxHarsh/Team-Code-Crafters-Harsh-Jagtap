"""
GitHub Watcher node -- architecture doc Section 7.1. Pulls the latest
commits/PRs/branches/issues for a project's connected repo, matches
commits (and issues) to roadmap tasks with a simple keyword/path match
(Implementation Plan Phase 5: "simple keyword/path match is enough for
a hackathon"), and returns the shape that gets written into
projects.github_state (Section 3.1) / returned by GET .../github/state
(Section 5.3).

Not part of the Phase 3 chat-turn StateGraph (app/agents/graph.py) --
like run_replan_turn's direct call to planner_node, this is invoked
directly as a plain async function (by app/services/github_service.py,
and later Phase 10's scheduler), since a poll isn't a chat turn and
doesn't fit CoachState's shape. It still writes its own agent_run_log
row (node_name="github_watcher") for the same debug-trail reasons every
other node does.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import agent_run_log as agent_run_log_repo
from app.services import github_client

logger = logging.getLogger(__name__)

# A PR open longer than this counts as "stuck" for github_state.open_prs
# (Section 5.3's { "status": "stuck", "hours_open": 6 } example).
STUCK_PR_HOURS_THRESHOLD = 4

# Words too common to be useful signal when matching a commit message
# or file path against a task's name.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
    "into", "onto", "add", "adds", "added", "update", "updates", "updated",
    "fix", "fixes", "fixed", "wip", "task", "build", "builds",
}
_WORD_RE = re.compile(r"[a-z0-9]+")


def _keywords(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


@dataclass
class MatchedCommit:
    sha: str
    message: str
    matched_task: str | None
    files: list[str] = field(default_factory=list)


def match_text_to_task(text: str, files: list[str], roadmap: list[dict]) -> str | None:
    """Scores each roadmap task by keyword overlap with `text` (a commit
    message or issue title) plus any changed file path, returns the id
    of the best-scoring task, or None if nothing scores above zero.
    Deliberately simple (word-overlap counting, no embeddings/LLM call)
    per Phase 5's explicit scope -- good enough to demo, and cheap
    enough to run on every commit without burning a model call."""
    text_keywords = _keywords(text)
    path_keywords: set[str] = set()
    for path in files:
        # "app/routers/roadmap.py" -> {"app", "routers", "roadmap"}
        for part in re.split(r"[/_\-.]", path):
            path_keywords |= _keywords(part)

    combined = text_keywords | path_keywords
    if not combined:
        return None

    best_task_id: str | None = None
    best_score = 0
    for task in roadmap:
        task_id = task.get("id")
        if not task_id:
            continue
        task_keywords = _keywords(task.get("task", ""))
        if not task_keywords:
            continue
        score = len(combined & task_keywords)
        if score > best_score:
            best_score = score
            best_task_id = task_id

    return best_task_id


async def run_github_watcher(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    repo_full_name: str,
    access_token: str,
    roadmap: list[dict],
    since: str | None,
    trigger: str,
) -> dict:
    """Fetches commits/PRs/branches/issues, matches them against the
    roadmap, and returns the github_state dict to persist. Raises
    app.services.github_client.GithubApiError on a fetch failure --
    callers (app/services/github_service.py) are responsible for
    catching it and writing agent_run_log(status="failed"); this
    function's own start/finish rows record that outcome regardless."""
    run = await agent_run_log_repo.start_run(
        session,
        project_id=project_id,
        node_name="github_watcher",
        trigger=trigger,
        input_snapshot={"repo_full_name": repo_full_name, "since": since},
    )

    try:
        commits_raw = await github_client.list_commits(access_token, repo_full_name, since=since)
        pulls_raw = await github_client.list_open_pulls(access_token, repo_full_name)
        branches_raw = await github_client.list_branches(access_token, repo_full_name)
        issues_raw = await github_client.list_open_issues(access_token, repo_full_name)

        matched_commits: list[MatchedCommit] = []
        for commit in commits_raw:
            sha = commit.get("sha", "")
            message = (commit.get("commit") or {}).get("message", "")
            files = await github_client.get_commit_files(access_token, repo_full_name, sha) if sha else []
            matched_task = match_text_to_task(message, files, roadmap)
            matched_commits.append(
                MatchedCommit(sha=sha[:7], message=message.splitlines()[0] if message else "", matched_task=matched_task, files=files)
            )

        now = datetime.now(timezone.utc)
        open_prs = []
        for pr in pulls_raw:
            created_at = pr.get("created_at")
            hours_open = 0.0
            if created_at:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                hours_open = round((now - created).total_seconds() / 3600, 1)
            open_prs.append(
                {
                    "number": pr.get("number"),
                    "status": "stuck" if hours_open >= STUCK_PR_HOURS_THRESHOLD else "open",
                    "hours_open": hours_open,
                }
            )

        issues = []
        for issue in issues_raw:
            if "pull_request" in issue:
                continue  # GitHub's issues endpoint also returns PRs.
            title = issue.get("title", "")
            matched_task_id = match_text_to_task(title, [], roadmap)
            matched_task = next((t for t in roadmap if t.get("id") == matched_task_id), None)
            eta_breach = False
            if matched_task and matched_task.get("eta"):
                try:
                    eta = datetime.fromisoformat(matched_task["eta"].replace("Z", "+00:00"))
                    eta_breach = now > eta
                except ValueError:
                    eta_breach = False
            issues.append({"number": issue.get("number"), "state": issue.get("state", "open"), "eta_breach": eta_breach})

        github_state = {
            "commits": [
                {"sha": c.sha, "message": c.message, "matched_task": c.matched_task}
                for c in matched_commits
            ],
            "open_prs": open_prs,
            "branches": [b.get("name") for b in branches_raw],
            "issues": issues,
            "last_polled_at": now.isoformat(),
        }

        await agent_run_log_repo.finish_run(
            session,
            run.id,
            output_snapshot={
                "commit_count": len(matched_commits),
                "matched_count": sum(1 for c in matched_commits if c.matched_task),
                "open_pr_count": len(open_prs),
                "issue_count": len(issues),
            },
            status="done",
        )
        return {"github_state": github_state, "matched_commits": matched_commits}
    except Exception:
        logger.exception("github_watcher_failed", extra={"project_id": str(project_id)})
        await agent_run_log_repo.finish_run(
            session, run.id, output_snapshot={"error": "github_watcher_failed"}, status="failed"
        )
        raise
