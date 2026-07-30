"""
Thin async wrapper around the GitHub REST API (Implementation Plan
Phase 5: "GitHub client wrapper -- centralize rate-limit header reading
here"). Every other module in this codebase that needs GitHub data goes
through here rather than calling httpx directly, so there's exactly one
place that knows the auth header shape and rate-limit budget.

Section 7.3's budget: a 120s poll interval per repo is well inside the
5,000 req/hr authenticated limit, with headroom even polling several
repos from one process -- so this module logs a warning if it ever sees
headroom get tight, rather than doing any client-side throttling that
isn't needed for a single hackathon demo repo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 15.0

# Below this many remaining requests in the current rate-limit window,
# log a warning -- informational only, per Section 7.3 there should
# never be real pressure here at a 120s interval against one repo.
RATE_LIMIT_WARN_THRESHOLD = 200


class GithubApiError(Exception):
    """Raised by the data-fetching methods (commits/pulls/branches/
    issues) on any non-2xx response. Callers in the poller catch this
    and record agent_run_log(status="failed") rather than letting a
    single bad poll crash the process."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


@dataclass
class RepoAccessResult:
    ok: bool
    status_code: int
    reason: str | None = None


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _log_rate_limit(response: httpx.Response, *, repo_full_name: str) -> None:
    remaining = response.headers.get("x-ratelimit-remaining")
    if remaining is None:
        return
    try:
        remaining_int = int(remaining)
    except ValueError:
        return
    if remaining_int < RATE_LIMIT_WARN_THRESHOLD:
        logger.warning(
            "github_rate_limit_low",
            extra={"repo_full_name": repo_full_name, "remaining": remaining_int},
        )


async def check_repo_access(access_token: str, repo_full_name: str) -> RepoAccessResult:
    """Used by POST .../github/connect (Section 5.3) to validate the
    token before storing it. Returns ok=False with the raw status so
    the router can map it to the documented 401 (bad token) vs 422
    (repo not found / no access) response codes -- this function
    itself doesn't raise, since "invalid" is an expected outcome here,
    not a transport failure."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(
            f"{API_BASE}/repos/{repo_full_name}", headers=_headers(access_token)
        )
    _log_rate_limit(response, repo_full_name=repo_full_name)

    if response.status_code == 200:
        return RepoAccessResult(ok=True, status_code=200)
    if response.status_code == 401:
        return RepoAccessResult(ok=False, status_code=401, reason="invalid_token")
    # 404 (not found) and 403 (rate-limited / no access on a private
    # repo) both surface to the caller as "repo not found or no access"
    # per Section 5.3's single 422 case -- GitHub deliberately returns
    # 404 rather than 403 for a private repo a bad token can't see, so
    # there's no reliable way to tell "doesn't exist" from "no access"
    # apart, and the doc doesn't ask us to.
    return RepoAccessResult(
        ok=False, status_code=response.status_code, reason="repo_not_found_or_no_access"
    )


async def _get_json(client: httpx.AsyncClient, url: str, access_token: str, *, repo_full_name: str) -> list | dict:
    response = await client.get(url, headers=_headers(access_token))
    _log_rate_limit(response, repo_full_name=repo_full_name)
    if response.status_code != 200:
        raise GithubApiError(response.status_code, f"GET {url} -> {response.status_code}")
    return response.json()


async def list_commits(access_token: str, repo_full_name: str, *, since: str | None = None) -> list[dict]:
    """https://docs.github.com/rest/commits/commits#list-commits"""
    params = {"since": since} if since else {}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, params=params) as client:
        return await _get_json(
            client, f"{API_BASE}/repos/{repo_full_name}/commits", access_token, repo_full_name=repo_full_name
        )


async def get_commit_files(access_token: str, repo_full_name: str, sha: str) -> list[str]:
    """Fetches the individual commit to read its changed-file paths --
    the list endpoint above doesn't include them. Used for the simple
    keyword/path match against roadmap tasks (Phase 5) and the
    CommitFile/MAPS_TO Neo4j sync (Section 3.3)."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        data = await _get_json(
            client,
            f"{API_BASE}/repos/{repo_full_name}/commits/{sha}",
            access_token,
            repo_full_name=repo_full_name,
        )
    return [f["filename"] for f in data.get("files", []) if "filename" in f]


async def list_open_pulls(access_token: str, repo_full_name: str) -> list[dict]:
    """https://docs.github.com/rest/pulls/pulls#list-pull-requests"""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, params={"state": "open"}) as client:
        return await _get_json(
            client, f"{API_BASE}/repos/{repo_full_name}/pulls", access_token, repo_full_name=repo_full_name
        )


async def list_branches(access_token: str, repo_full_name: str) -> list[dict]:
    """https://docs.github.com/rest/branches/branches#list-branches"""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        return await _get_json(
            client, f"{API_BASE}/repos/{repo_full_name}/branches", access_token, repo_full_name=repo_full_name
        )


async def list_open_issues(access_token: str, repo_full_name: str) -> list[dict]:
    """https://docs.github.com/rest/issues/issues#list-repository-issues
    Note: GitHub's issues endpoint also returns PRs (a PR is an issue
    under the hood) -- callers should filter out entries with a
    "pull_request" key if they need issues only."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, params={"state": "open"}) as client:
        return await _get_json(
            client, f"{API_BASE}/repos/{repo_full_name}/issues", access_token, repo_full_name=repo_full_name
        )
