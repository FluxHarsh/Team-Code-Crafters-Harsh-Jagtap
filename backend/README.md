# Hackathon Project Coach — Backend

Single FastAPI service (REST + WebSocket + in-process LangGraph +
background scheduler). No separate agent microservice, no separate
Node layer. See `Backend Architecture & API Design` and
`Backend Implementation Plan` for the full spec.

This repo currently implements **Phase 0 — Project Setup & Environment**,
**Phase 1 — Database Layer**, **Phase 2 — FastAPI Skeleton, Routing &
Cross-Cutting Concerns**, **Phase 3 — Ingestion & Planning (Intake and
Planner Agents)**, **Phase 4 — Roadmap & Kanban APIs**, **Phase 5 —
GitHub Integration (Polling Watcher)**, **Phase 6 — Risk Watcher,
Reprioritizer & Neo4j Dependency Traversal**, **Phase 7 — Pitch
Agent**, **Phase 8 — Coach Chat (Post-Approval Panel)**, **Phase 9 —
WebSocket Event Layer**, **Phase 10 — Autonomous 24-Hour Operation**,
**Phase 11 — RAG Grounding (pgvector)**, and **Phase 12 — Testing,
Hardening & Demo Readiness**. All twelve phases from the Implementation
Plan are represented in this delivery — the "Still needs a live pass"
notes under each Done-when section are what's left for a live run
against real Postgres (Neon)/Neo4j (Aura)/API keys before the event,
not unbuilt functionality.

> **Infra note:** this project no longer uses Docker for local
> Postgres/Neo4j. The whole team connects to the same hosted Neon
> (Postgres/pgvector) and Neo4j Aura instances instead — one shared
> `.env` config, nothing to spin up locally. See Quickstart below.

## Phase 0 — what's here

- Repo scaffold: single service, `app/` package.
- `requirements.txt`, pinned per the Phase 0 checklist.
- `app/config.py` — one `Settings` class (pydantic-settings) reading
  all env vars. Never hardcode secrets.
- No `docker-compose.yml` — the whole team points at the same hosted
  Neon (Postgres/pgvector) and Neo4j Aura instances via `DATABASE_URL`
  / `NEO4J_URI` in `.env`, so there's nothing to install or run
  locally, and everyone's data stays in sync automatically.
- `GET /healthz` — hits both Postgres and Neo4j so infra problems
  surface immediately, not mid-demo.

## Phase 1 — what's here

- `app/models/` — one SQLAlchemy model per table: `projects`,
  `documents`, `critique_history`, `github_connections`,
  `agent_run_log`, `chat_messages`, `postmortem_embeddings`
  (architecture doc Section 3.1 / 3.2).
- `app/repositories/` — typed async CRUD, one module per table. This
  is the only layer that should ever touch a `Session` directly;
  everything above it (routes, agent nodes) calls these functions.
- `app/security.py` — Fernet encryption for
  `github_connections.access_token`. Only `app/repositories/
  github_connections.py` ever sees the plaintext token.
- `alembic/` + `alembic.ini` — async Alembic setup wired to
  `app.config.get_settings().database_url` and `app.models.Base.metadata`.
  `alembic/versions/0001_initial_schema.py` creates all seven tables,
  the `project_status` / `chat_phase` enums, the `vector` extension,
  and the HNSW cosine index on `postmortem_embeddings`.
- `scripts/neo4j_bootstrap.py` — creates the uniqueness constraints for
  `Project.id`, `Milestone.id`, `Risk.id`, `CommitFile.path` (Section 3.3).
- `scripts/seed_postmortems.py` + `scripts/seed_data/postmortems.json`
  — embeds curated postmortem text via OpenAI `text-embedding-3-small`
  and loads it into `postmortem_embeddings` ahead of the event.

## Phase 2 — what's here

- `app/errors.py` — `AppError` subclasses (`NotFoundError`/404,
  `ConflictError`/409, `UnsupportedMediaTypeError`/415,
  `UnauthorizedError`/401, `UnprocessableEntityError`/422) plus global
  exception handlers, so every route — including FastAPI's own
  validation errors and any unhandled exception — returns the same
  `{"detail": ...}` shape.
- `app/logging_config.py` — structured logging with a per-request
  request-id (`ContextVar`-based), echoed back as `X-Request-ID` and
  attached to every log line, so an `agent_run_log` entry can be traced
  back to the request that triggered it (Phase 3+).
- `app/dependencies.py` — shared `get_db` session dependency (commit on
  success, rollback on error) used by every router.
- `app/routers/common.py` — `get_project_or_404` helper shared across
  routers, since nearly every route starts with "look up
  `{project_id}`, 404 if missing."
- `app/routers/` — one module per domain (`projects`, `ingestion`,
  `planning`, `roadmap`, `github`, `risks`, `reprioritize`, `pitch`,
  `chat`, `agent_graph`, `ws`), mirroring architecture doc Section 5.
  All 22 REST routes from Appendix A are wired, plus the
  `WS /api/v1/projects/{project_id}/updates` channel skeleton
  (Section 6).
- Where a route only needs real CRUD, it's wired to the Phase 1
  repositories (project create/get, chat history, roadmap/risk reads,
  Kanban task patches, progress logging). Where a route depends on an
  agent that doesn't exist yet (Intake, Planner, Risk Watcher,
  Reprioritizer, Pitch Agent, Supervisor), it returns a clearly-labeled
  stub reply with a comment pointing at the phase that implements it —
  nothing here needs rewriting later, just filling in.
- No auth middleware anywhere, deliberately (Section 4) — every route
  in `app/routers/` is open, matching the MVP access model.

## Phase 3 — what's here

- `app/agents/` — the LangGraph skeleton: one `StateGraph` (`app/agents/graph.py`)
  with four nodes — `supervisor`, `intake`, `scope_critic`, `planner` —
  compiled once at import time and invoked fresh per request. State is
  a plain `CoachState` TypedDict (`app/agents/state.py`) that carries
  the live `AsyncSession` through the graph for a single invocation;
  nothing is checkpointed, since state lives in Postgres, not in
  LangGraph memory (a non-negotiable carried through every phase).
  - `supervisor` — routes to the `intake` branch or the
    `scope_critic -> planner` branch depending on which endpoint
    invoked the graph. Phase 8 extends this into real message
    classification for the post-approval coach chat panel.
  - `intake` — converses about the problem/solution/target user,
    decides `ready_for_planning` itself, folds refined context back
    into `project_idea`.
  - `scope_critic` — runs first on every planning turn (not its own
    route), writes `critique_history` rows (`scope_gap` /
    `overscope` / `assumption`), and hands its fresh critiques to the
    `planner` node in the same turn.
  - `planner` — proposes/revises `draft_scope` + `draft_roadmap` given
    the project idea, current draft, and all critiques so far.
  - `app/agents/llm.py` / `prompts.py` / `json_utils.py` — the shared
    Claude client, the system prompts, and a tolerant JSON-reply parser
    (nodes prompt for JSON-only output and degrade to a safe fallback
    reply rather than raising if a reply is malformed).
- `app/services/ingestion_service.py` / `planning_service.py` — the
  only callers of `app/agents`; they persist both sides of each chat
  turn to `chat_messages`, invoke the graph, and write the resulting
  state back onto the `projects` row. Routers stay thin HTTP shims.
- `app/services/document_extraction.py` — real pdf/docx/txt/md text
  extraction (`pypdf` / `python-docx`) for `POST .../ingest/document`,
  folded into `project_idea.raw`; a file that fails to parse degrades
  to an empty string rather than failing the upload.
- `agent_run_log` writes — every node call above (`supervisor`,
  `intake`, `scope_critic`, `planner`) writes its own
  start/finish row, `status=done` or `failed`, so `GET
  .../agent-graph/state` (Phase 2's route) now returns real data.
- `POST .../ingest/message` moves `projects.status` from `intake` to
  `planning` the moment the Intake node sets `ready_for_planning=true`.
- `POST .../plan/approve` now also rejects a second approve — it
  requires `status == "planning"`, so calling it twice (or before
  Intake has finished) both return `409`, matching the Phase 12
  error-path checklist ("409 on double-approve").

## Phase 4 — what's here

- `app/repositories/locks.py` — `try_acquire_replan_lock`, a
  transaction-scoped Postgres advisory lock
  (`pg_try_advisory_xact_lock(hashtext(...))`) keyed per project. Used
  by the manual replan route to return `409` if a re-plan is already
  in flight; released automatically at commit/rollback, so it can't be
  leaked by a crash mid-request. Phase 10's scheduler-level overlap
  guard (for the automatic Monitoring loop) is a separate, longer-lived
  concern and is *not* built here.
- `app/repositories/projects.py` — added `get_project_for_update`
  (`SELECT ... FOR UPDATE`), used by the Kanban PATCH route so two
  concurrent task edits can't clobber each other.
- `app/repositories/graph.py` (new) — Neo4j sync for the roadmap side
  of the dependency graph (Section 3.3): upserts `Milestone` nodes and
  `BELONGS_TO`/`BLOCKED_BY` edges from `projects.roadmap`, removing
  milestones/edges that no longer exist so the graph never drifts from
  Postgres. `depends_on: [task_id, ...]` is a new (optional) field on
  each roadmap task — a JSONB-native extension per Section 3.1 — and
  the Planner prompt (`app/agents/prompts.py`) now asks for it so
  there's real dependency data for the Reprioritizer's traversal
  (Phase 6) to walk later.
- `app/agents/graph.py` — added `run_replan_turn`, which invokes the
  Planner node directly (no Supervisor/Scope Critic routing) with the
  current scope + `hours_remaining` and a synthetic "re-plan requested"
  message, matching Phase 4's spec ("rebuild the roadmap from current
  scope + hours_remaining," not a fresh chat turn).
- `app/services/roadmap_service.py` (new) — `replan_roadmap` and
  `patch_task`, the shared code paths behind the routes below; both
  keep Neo4j in sync after every Postgres write.
- `app/routers/roadmap.py` — now real:
  - `GET .../roadmap` — unchanged (reads `projects.roadmap`).
  - `POST .../roadmap/replan` — invokes the Planner, persists the
    rebuilt scope/roadmap, re-syncs the graph, returns `409` if a
    replan is already running for this project.
  - `PATCH .../roadmap/tasks/{task_id}` — row-locked read-modify-write,
    syncs the task's status to its `Milestone` node, and sets
    `risk_flagged: true` when a task's status becomes `"blocked"`
    (a simple, immediate signal — Phase 6's Risk Watcher adds real
    `github_state`/ETA-driven detection on top of this).
- `app/dependencies.py` — added `get_neo4j`, a plain accessor for the
  process-wide driver (not a per-request generator like `get_db`,
  since the driver's own connection pooling already handles concurrency).
- `GET /projects/{id}` (Section 5.1's full-state hydration route) was
  already real as of Phase 2/3 — no change needed here.

## Phase 5 — what's here

- `app/services/github_client.py` (new) — thin async wrapper around
  the GitHub REST API (`repos`, `commits`, a single commit's changed
  files, `pulls`, `branches`, `issues`), with one shared place that
  sets the auth header and reads the `x-ratelimit-remaining` header
  (Section 7.3 — logs a warning below 200 remaining, informational
  only since 120s/repo never gets close in practice). `check_repo_access`
  returns a typed ok/401/422 result for the connect route; the
  data-fetching calls raise `GithubApiError` on any non-2xx response
  for the poller to catch.
- `app/agents/nodes/github_watcher.py` (new) — the GitHub Watcher node:
  fetches commits/PRs/branches/issues, matches each commit (and each
  open issue's title) against roadmap task names with a simple
  word-overlap keyword/path match (`match_text_to_task` — no LLM call,
  per Phase 5's explicit "simple keyword/path match is enough" scope),
  flags a PR "stuck" past `STUCK_PR_HOURS_THRESHOLD` (4h) and an issue
  `eta_breach` when its matched task's ETA has passed, and assembles
  the `github_state` shape (Section 3.1 / 5.3). Writes its own
  `agent_run_log` row (`node_name="github_watcher"`) like every other
  node — called directly as a plain async function (not through the
  Phase 3 chat-turn `StateGraph`), same pattern as `run_replan_turn`.
- `app/repositories/graph.py` — added `sync_commit_files`, upserting
  `CommitFile` nodes and `MAPS_TO` edges to the matched `Milestone` for
  every file in a matched commit (Section 3.3); unmatched commits are
  skipped rather than written as dangling nodes.
- `app/services/github_service.py` (new) — `poll_project`, the single
  code path a poll runs through: no-ops if the project has no
  connection yet, otherwise runs the Watcher, persists
  `projects.github_state`, syncs the `CommitFile` graph, stamps
  `github_connections.last_polled_at`, and calls a clearly-marked
  `_handoff_to_risk_watcher` stub (Phase 6 fills this in for real —
  same "stub now, no rewrite later" pattern Phase 2 used elsewhere).
  Called both by the connect route (once, immediately) and, later,
  by Phase 10's scheduler (on a timer) — one function, one code path,
  per the Implementation Plan's goal for the whole integration.
- `app/routers/github.py` — `POST .../github/connect` now actually
  calls the GitHub API before storing anything (`401` on a bad token,
  `422` on a repo that doesn't exist or the token can't see — GitHub
  itself returns `404`/`403` for both of those, so there's no reliable
  way to tell them apart and Section 5.3 only documents the one `422`
  case anyway), then runs one poll synchronously so `github_state`
  isn't empty until the next scheduled tick. A failed first poll is
  logged, not raised — the connection itself is still valid since the
  token/repo were already checked. `GET .../github/state` is unchanged
  (already read real data structurally as of Phase 2, and now the data
  behind it is real too).

## Phase 6 — what's here

- `app/agents/nodes/risk_watcher.py` (new) — pure, deterministic
  `detect_risks` (no LLM call — Phase 6's task list is explicit that
  "simple rules" suffice here) plus the `run_risk_watcher` wrapper that
  logs to `agent_run_log`. Three rules: (A) a task due within
  `ETA_RISK_WINDOW_HOURS` (3h, matching Section 5.4's own example) or
  overdue with no matching GitHub commit *or* progress-log entry
  (reuses Phase 5's `match_text_to_task` against progress text too, so
  a manual update can satisfy the same check a commit would); (B) a
  task manually moved to `"blocked"` (Phase 4's PATCH route flagged
  this on its response but never wrote a `risks[]` entry — this is
  where that actually happens); (C) a PR the GitHub Watcher already
  tagged `"stuck"`. De-duplicates on `(category, dedup_key)` so
  re-running every poll doesn't spam the same risk repeatedly.
- `app/agents/nodes/reprioritizer.py` (new) — the one Phase 6 node that
  calls Claude (`REPRIORITIZER_SYSTEM` in `app/agents/prompts.py`):
  given a risk, its roadmap task, and the downstream milestones a
  Neo4j traversal says depend on it, decides `drop`/`extend`/`reassign`
  and writes a one-sentence rationale. Falls back to a deterministic
  `reassign` + templated rationale (referencing the downstream count)
  on a malformed/failed LLM reply, same pattern as the Planner/Scope
  Critic.
- `app/repositories/graph.py` — added `create_risk_node`/
  `mark_risk_resolved` (`Risk`/`AFFECTS`, Section 3.3) and
  `traverse_downstream_milestones` — the exact
  `(m)<-[:BLOCKED_BY*1..3]-(downstream)` traversal from Section 3.3,
  run before every Reprioritizer call.
- `app/services/risk_service.py` (new) — `run_risk_watcher_for_project`
  (persists new risks + syncs `Risk`/`AFFECTS`, called from both the
  GitHub poll hand-off and the progress route — one code path, same
  goal as every other Phase 4/5 service) and `reprioritize_risk`
  (traversal → Reprioritizer → Phase 4's `replan_roadmap` → marks the
  risk resolved in Postgres and Neo4j).
- `app/services/github_service.py` — the Phase 5 `_handoff_to_risk_watcher`
  stub is gone; `poll_project` now really calls
  `run_risk_watcher_for_project` after every poll, with
  `trigger="github_watcher"` matching Section 5.8's own example
  (`{"node": "risk_watcher", "trigger": "github_watcher"}`).
- `app/routers/risks.py` — `POST .../progress` now really triggers the
  Risk Watcher (`risk_watcher_triggered` reflects whether it ran
  without erroring, same failure-isolation pattern as Phase 5's
  connect-then-poll: the progress entry itself is never lost to a
  watcher hiccup); `POST .../risks/{id}/resolve` now also calls
  `mark_risk_resolved` in Neo4j, not just the JSONB row.
- `app/routers/reprioritize.py` — no longer a stub; calls
  `risk_service.reprioritize_risk` and returns its real
  decision/rationale/`roadmap_replanned`.

## Phase 7 — what's here

- `app/models/project.py` + `alembic/versions/0002_add_pitch_generated_at.py`
  (new) — a dedicated `pitch_generated_at` column. The Phase 2 stub
  used `updated_at` as a stand-in; that was a latent bug (any later
  project write, e.g. a Kanban edit, would bump `updated_at` and make
  `GET .../pitch` report a wrong, too-recent `generated_at`) that this
  phase was the right point to fix for real, per the README's own
  Phase 2 note flagging it.
- `app/agents/nodes/pitch_agent.py` (new) — synthesizes
  `{hook, problem, solution, demo_flow[], differentiator, ask}` from
  `project_idea`, `scope`, resolved risks, and the final roadmap state
  (`PITCH_AGENT_SYSTEM` in `app/agents/prompts.py`). `hook`/`ask`
  extend Section 5.6's example response shape per Phase 7's task list
  ("plus a hook/ask, matching the shape used in the dashboard's pitch
  panel"). Falls back to a deterministic outline assembled directly
  from `project_idea`/`scope` (with `demo_flow` built from
  `mvp_features`) on a malformed/failed LLM reply — same
  degrade-gracefully pattern as the Planner/Reprioritizer, and
  arguably the single node in this codebase where that matters most:
  this fires right before a demo.
- `app/services/pitch_service.py` (new) — `is_pitch_ready` (the
  Section 5.6 / Phase 7 threshold: `hours_remaining < 3` OR
  `> 60%` of roadmap tasks `done` — either signal alone is enough,
  checked independently so Phase 10's `tick_hours_remaining` can reuse
  this exact function to auto-trigger later) and `generate_pitch`
  (gates on that threshold with a 409, runs the Pitch Agent, persists
  `pitch_outline` + `pitch_generated_at`, and moves `project.status` to
  `"pitch_ready"` — an enum value the schema already had, unused until
  now).
- `app/routers/pitch.py` — `POST .../pitch/generate` and
  `GET .../pitch` are both real now; `GET` prefers the new
  `pitch_generated_at` and falls back to `updated_at` only for a
  pre-Phase-7 row that has a `pitch_outline` but predates the new
  column.

## Phase 8 — what's here

- `app/agents/nodes/supervisor.py` — extended with
  `classify_coach_message` (rule-based: recognizes replan phrases
  like "re-plan"/"rebuild the roadmap", reprioritize phrases like
  "fix this"/"reprioritize" — resolving *which* risk from an explicit
  `r-xxxxxxxx` id in the message, or unambiguously from there being
  exactly one unresolved risk, or otherwise leaving `risk_id=None` so
  the caller asks which one was meant rather than guessing — and
  falling through to "question" for everything else) and
  `guess_answered_by` (keyword heuristic for which node's data a
  question is probably about, e.g. "flagging"/"blocked" →
  `risk_watcher`). Rule-based rather than an LLM call, same
  rules-vs-LLM split as the Risk Watcher's detection vs. the
  Reprioritizer's actual decision (Phase 6) — classifying "is this a
  command or a question" doesn't need a model call before the Team
  Assistant's own model call for the real answer.
- `app/agents/nodes/team_assistant.py` (new) — the one Phase 8 node
  that calls Claude: answers a question-type message grounded in the
  full current project state (`TEAM_ASSISTANT_SYSTEM` in
  `app/agents/prompts.py`), plain-text reply (no JSON — there's no
  structured field to parse, just an answer a person reads directly).
  Falls back to a plain apologetic reply on a call failure rather than
  inventing an answer the state doesn't support.
- `app/repositories/chat_messages.py` — added `list_messages_page`,
  real keyset pagination on `(created_at, id)` (not offset-based, so a
  message arriving mid-scroll can't shift an already-returned page) —
  Phase 8's "cursor-paginated history for the panel." The opaque
  cursor is base64 of `"created_at|id"`.
- `app/services/coach_chat_service.py` (new) — `handle_coach_message`:
  persists the user's turn, classifies it, and dispatches to Phase 4's
  `replan_roadmap`, Phase 6's `reprioritize_risk`, or the Team
  Assistant — reusing those exact service functions rather than
  reimplementing "trigger a replan" a second way, so typing
  "re-plan the roadmap" into chat and calling `POST .../roadmap/replan`
  directly are the same action taken two different ways, not two
  code paths that could drift apart.
- `app/routers/chat.py` — both routes are real now; `phase="coaching"`
  keeps this history on the shared `chat_messages` table separate from
  Phase 3's `"intake"`/`"planning"` chats (same table, same repository
  module, just filtered — the compiled SQL was checked directly against
  the Postgres dialect as part of this delivery's verification pass and
  confirmed to include `AND chat_messages.phase = 'coaching'`).

## Phase 9 — what's here

- `app/ws/connection_manager.py` (new) — `ConnectionManager` (in-memory,
  per-`project_id` registry of live sockets; single-process only, noted
  explicitly for anyone scaling past a demo) and the module-level
  `broadcast(project_id, event_type, payload)` every other module
  calls. Best-effort by design: payloads go through
  `fastapi.encoders.jsonable_encoder` first (so `Decimal`/`datetime`/
  `UUID` values coming straight off the ORM never break a send), each
  socket send is bounded by a 2s timeout, and a socket that fails or
  times out is silently dropped from the registry rather than ever
  raising back into the caller — several call sites are inside a
  repository function mid-transaction, and a dead browser tab must
  never break a database write.
- `app/routers/ws.py` — the endpoint now really registers/unregisters
  with the manager. Deliberately does **not** replay missed events on
  reconnect — a client that was disconnected is expected to call
  `GET /projects/{id}` for full current state instead of the server
  buffering a per-socket backlog.
- Three of the nine events (`node_activated`, `chat_message`, the
  generic `state_updated`) are hooked directly into the shared
  repository functions every node/service already funnels through --
  `agent_run_log.start_run`, `chat_messages.add_message`,
  `projects.update_project` -- rather than at each of the ~20+
  individual call sites across Phases 3-8. Those repo functions *are*
  the actual state-changing point for those three events, so hooking
  there guarantees complete coverage (including any future phase's
  node/chat/state write) instead of depending on every call site
  remembering to broadcast. `state_updated` fires once per changed
  field (`{path, value}`), so e.g. a `replan_roadmap` call that passes
  `scope=`, `roadmap=`, `next_action=` together produces three events.
  Documented tradeoff in the module docstring: these fire before the
  enclosing request's transaction commits, so a same-request failure
  *after* the write could broadcast a change that then rolls back — a
  theoretical gap in every current call path (the write is always the
  last thing before the request returns) but worth a live pass to
  confirm and worth remembering for future phases.
- The other six events need context a generic repo write doesn't have,
  so they're broadcast explicitly at their real service-layer call
  sites, per the Implementation Plan's own description of this
  retrofit: `plan_draft_updated` (`app/services/planning_service.py`,
  the combined `{draft_scope, draft_roadmap}` shape) and
  `plan_approved` (`app/routers/planning.py`) from Phase 3;
  `task_moved` (`app/services/roadmap_service.py`, only when `status`
  actually changes, not on an owner/eta/note-only edit) from Phase 4;
  `risk_flagged` and `risk_resolved` (`app/services/risk_service.py` --
  resolution logic was factored out into a new shared `resolve_risk`
  function so both the manual resolve route and
  `reprioritize_risk`'s auto-resolve broadcast from exactly one place)
  from Phase 6; `pitch_ready` (`app/services/pitch_service.py`) from
  Phase 7.

## Phase 10 — what's here

- `app/scheduler/scheduler.py` (new) — `AsyncIOScheduler` singleton
  backed by `SQLAlchemyJobStore` (a sync `postgresql+psycopg2` URL
  derived from `settings.database_url` — APScheduler's jobstores are
  sync-only, so this is a second, separate connection from the app's
  main asyncpg pool). `register_project_jobs`/`deregister_project_jobs`
  add/remove both jobs for a project by deterministic id
  (`poll_github:{id}`, `tick_hours:{id}`) with `replace_existing=True`,
  so calling either more than once for the same project is always
  safe. `start_scheduler` (called from `app.main`'s lifespan) does
  **not** trust the jobstore's own persisted job list as the source of
  truth for "which projects are active" — it re-queries Postgres for
  `status="active"` projects and re-registers fresh, since Postgres
  (not APScheduler's persistence) is what Section 7.2 says should
  survive a restart.
- `app/scheduler/jobs.py` (new) — `poll_github_job` and
  `tick_hours_remaining_job`. Both: run their whole body in one
  session/transaction (so `app/repositories/locks.py`'s
  transaction-scoped advisory lock naturally spans the whole job —
  reused from Phase 4's `try_acquire_replan_lock` via two new keyed
  variants, `try_acquire_poll_lock`/`try_acquire_tick_lock`, rather
  than adding a separate `is_running` column); re-check
  `project.status` at the top and self-deregister + return early if
  it's no longer `"active"` (a safety net independent of whether
  `POST .../submit` was actually called); and wrap everything in an
  outer try/except that logs and swallows rather than re-raising, so
  one project's failure can never take down the scheduler for others
  (Section 7.2) — node-level failures still get their own
  `agent_run_log(status="failed")` row from that node's own
  `start_run`/`finish_run`, this outer catch is a last-resort net for
  failures *outside* a node. `tick_hours_remaining_job` decrements by
  exactly the tick interval (60s ≈ 0.0167h, using `Decimal` to match
  the column's `Numeric(5,2)` type) and auto-triggers the Pitch Agent
  via Phase 7's `is_pitch_ready` the moment a project crosses
  threshold and doesn't already have a `pitch_outline` — the thing
  Phase 7's README section flagged as a reuse point for exactly this.
- `app/repositories/locks.py` — generalized into `try_acquire_lock(session, key)`
  plus three thin keyed wrappers (`_replan`, `_poll`, `_tick`), so
  each concern's overlap guard can't collide with another's for the
  same `project_id`.
- `app/routers/planning.py` — `POST .../plan/approve` now also calls
  `register_project_jobs` — this is the point Section 7's Monitoring
  loop actually starts from. No GitHub connection yet at approval time
  is fine; `poll_github_job`'s own no-op path just does nothing useful
  until `.../github/connect` is called.
- `app/routers/github.py` — `.../github/connect` re-registers the poll
  job with the connection's real `poll_interval_seconds` when the
  project is already `"active"` (the common order — GitHub usually
  isn't connected until after planning) — approval only had a 120s
  default to register with, since no connection existed yet to read a
  real value from.
- `app/routers/projects.py` (new route) — `POST .../submit`: `projects.status`
  already had `"submitted"` as a valid terminal value in the schema
  (Section 3.1's lifecycle), but nothing could ever reach it before
  this phase. Rejects from `"intake"`/`"planning"` (nothing approved
  yet) or if already `"submitted"`; on success, deregisters both jobs
  so a submitted project stops consuming poll budget.

## Phase 11 — what's here

- `app/services/embeddings.py` (new) — the one place that ever calls
  the OpenAI embeddings API (`text-embedding-3-small`, 1536 dims).
  `scripts/seed_postmortems.py` (Phase 1) is refactored to call this
  same module instead of its own inline `httpx` call, so a seeded
  document embedding and a live query embedding are always produced by
  identical code — never two copies that could quietly drift onto
  different models/shapes.
- `app/services/rag_service.py` (new) — `retrieve_similar_postmortems`,
  the "one shared function used by both nodes" Phase 11's task list
  calls for: embeds the caller's query text via the module above, then
  runs Phase 1's `postmortem_embeddings_repo.similarity_search`
  (read-only here — this table is never written to live, Section
  3.2). Best-effort by design: a missing `OPENAI_API_KEY` or a failed
  OpenAI/DB call logs and returns an empty list rather than raising, so
  a transient embeddings outage degrades a node's prompt back to its
  pre-Phase-11 behavior (no retrieved context) instead of failing the
  critique/reprioritize call outright — same "degrade gracefully"
  posture as every LLM call in this codebase. `format_snippets_for_prompt`
  renders the retrieved rows (or an explicit "none found") as a labeled
  block for direct inclusion in a node's human message.
- `app/agents/nodes/scope_critic.py` — before calling Claude, embeds
  the project idea + draft scope (not the team's latest chat message,
  which might just be "sounds good") and injects the retrieved
  snippets as a "similar teams historically missed" block alongside
  the existing project idea/scope/roadmap/message context;
  `agent_run_log`'s `input_snapshot` now also records
  `retrieved_postmortem_count` for traceability.
- `app/agents/nodes/reprioritizer.py` — before calling Claude, embeds
  the flagged risk's own description + `suggested_fix` (not the
  downstream milestone list or scope, which describe this project's
  structure rather than the kind of blocker being hit) and injects the
  retrieved snippets as a "projects that hit this kind of blocker
  historically recovered by" block alongside the existing risk/task/
  downstream-milestones/scope/hours_remaining context from the Neo4j
  traversal (Phase 6); same `retrieved_postmortem_count` addition to
  `input_snapshot`.
- `app/agents/prompts.py` — `SCOPE_CRITIC_SYSTEM` and
  `REPRIORITIZER_SYSTEM` both updated to explain the new "Retrieved
  historical context" block: use it to ground at least one
  critique/decision when it has real snippets, reason exactly as
  before when it says "none found," and never fabricate a historical
  reference that wasn't actually retrieved.
- `scripts/rag_sanity_check.py` (new) — Phase 11's own task list
  ("confirm the seed data from Phase 1 actually returns relevant
  neighbors ... before wiring it into live prompts"). Read-only; runs
  two built-in test queries (one shaped like Scope Critic grounding,
  one like Reprioritizer grounding) through the exact same retrieval
  path the live nodes use, prints each neighbor's cosine distance and a
  text preview, and exits with a pass/fail summary. Accepts `--query`
  (repeatable) and `--top-k` for ad hoc checks:
  ```bash
  python -m scripts.rag_sanity_check
  python -m scripts.rag_sanity_check --query "our team is scoping a real-time multiplayer game" --top-k 5
  ```

## Phase 12 — what's here

- `scripts/seed_demo_project.py` (new) — the Phase 12 "pre-baked
  fallback project" deliverable. Deterministic and fully offline: no
  Claude call, no OpenAI call, no GitHub call. Writes through the same
  repository functions every live code path uses
  (`app/repositories/*`, `app/repositories/graph.py`) so the resulting
  row is indistinguishable from a real 20-hour run — a believable
  `project_idea`/`scope`, a roadmap with real `depends_on` edges and a
  mix of `done`/`in_progress`/`blocked`/`todo` tasks, one resolved risk
  and one still-open risk (so there's something to point the live
  "flag → reprioritize → resolve" demo at even with zero real GitHub
  activity in the room), a generated `pitch_outline`, chat history
  across all three phases, matching `critique_history` rows, and
  `agent_run_log` rows for every node in the pipeline. Deliberately
  left out: no `github_connections` row, and `status` is left at
  `"pitch_ready"` rather than `"active"`, so Phase 10's scheduler
  startup recovery (which only re-registers `"active"` projects) never
  tries to poll a real repo for it — the whole point of a fallback is
  that it doesn't depend on anything live. Idempotent: re-running
  without `--wipe` just refreshes the same project's fields; `--wipe`
  deletes a prior demo project (Postgres + Neo4j) first.
  ```bash
  python -m scripts.seed_demo_project
  python -m scripts.seed_demo_project --wipe
  ```
- Error-path contract re-verified end-to-end (not just re-read) via a
  `TestClient` run against the real app with `get_db`/`get_neo4j`
  dependency-overridden and the repository/GitHub-client calls mocked:
  `GET /projects/{malformed-id}` → 404, `GET /projects/{well-formed
  but missing}` → 404, `POST .../plan/approve` on a project already
  past `"planning"` → 409, `POST .../ingest/document` with an
  unsupported content type → 415, and `POST .../github/connect` with a
  token GitHub rejects → 401 — all five came back exactly as Section
  5's route table and Phase 2's `AppError` mapping document, confirming
  the contract holds through real routing/dependency/exception-handler
  code, not only at the point each `raise` was written.
- No new application code otherwise — Phase 12 is verification and a
  fallback asset, not new endpoints. The remaining Phase 12 tasks (a
  live end-to-end dry run through the actual dashboard, a two-tab
  WebSocket check, and a cold-start/process-restart check) need a
  running `docker compose up` + frontend and are out of scope for this
  delivery; see "Still needs a live pass" below.
- README note on the access model and the destructive-action boundary,
  ready as a direct answer if a judge asks — see "Access Model &
  Agent Boundaries" below.

## Access Model & Agent Boundaries (for judges)

**No authentication anywhere in this MVP.** This is a single-project
workspace tool used by one team during one hackathon, not a
multi-tenant product — there's no login, no invite codes, no per-user
identity. Every `/api/v1/projects/{id}/*` route is open: anyone with
the dashboard URL has full access. `chat_messages.speaker_name` is a
free-text, client-side field purely for display in the chat log — it
is never a credential. (If this ever needed to run for multiple teams
at once, the schema would need a `teams`/`projects` relationship and a
lightweight per-team access code added back in — a deliberate,
documented gap, not an oversight.)

**"Autonomous" means the Monitoring loop keeps running, not that
agents act unsupervised.** The GitHub Watcher → Risk Watcher →
Reprioritizer → Planner loop (Phase 10) keeps updating project state
without anyone opening the dashboard. It does **not** mean agents take
destructive action on the team's behalf: the Reprioritizer decides and
replans, but nothing in this codebase ever pushes a commit, merges a
PR, or closes an issue. That boundary is enforced structurally, not by
convention — `app/services/github_client.py` only ever calls read
endpoints (`repos`/`commits`/`pulls`/`branches`/`issues`), and there is
no write-capable GitHub call anywhere in the codebase for an agent to
reach for.

## Quickstart (should take under 10 minutes)

1. **Python env**

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   # fill in DATABASE_URL (Neon) and NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD (Aura) --
   # paste the connection strings each service gives you, as-is
   # fill in LLM_PROVIDER, LLM_API_KEY, LLM_MODEL_NAME, OPENAI_API_KEY, GITHUB_TOKEN_ENCRYPTION_KEY
   ```

   No local Postgres/Neo4j to install or run — this connects straight to
   your team's shared hosted Neon and Aura instances. Everyone uses the
   same `DATABASE_URL` / `NEO4J_URI`, so there's nothing to keep in sync
   between machines.

3. **Apply migrations / bootstrap the graph** (first time only, or after
   pulling new migrations)

   ```bash
   alembic upgrade head
   python -m scripts.neo4j_bootstrap
   ```

4. **Run the app**

   ```bash
   uvicorn app.main:app --reload
   ```

5. **Verify**

   ```bash
   curl http://localhost:8000/healthz
   # {"status":"ok","postgres":"ok","neo4j":"ok"}
   ```

   If this comes back `"degraded"` with `"postgres":"unreachable"` or
   `"neo4j":"unreachable"`, double check `DATABASE_URL` / `NEO4J_URI` in
   `.env` — a value that's missing entirely raises a clear `RuntimeError`
   right at `uvicorn` startup naming exactly which one; a wrong
   password, host, or `sslmode` shows up here instead, since the engine
   itself still constructs fine and only the actual connection fails.

## Done-when (Phase 0 deliverable)

> `docker compose up` + `uvicorn app.main:app --reload` boots cleanly;
> `/healthz` returns 200.

## Done-when (Phase 1 deliverable)

> `alembic upgrade head` applies cleanly against a fresh Postgres;
> `python -m scripts.neo4j_bootstrap` creates all four constraints
> (confirm with `SHOW CONSTRAINTS` in the Neo4j browser); a manual
> insert/select round trip works against every table via the
> `app/repositories/*` functions.
>
> To run the migration once your containers are up:
> ```bash
> alembic upgrade head
> python -m scripts.neo4j_bootstrap
> python -m scripts.seed_postmortems   # requires OPENAI_API_KEY
> ```

## Done-when (Phase 2 deliverable)

> Empty routers respond with correct shapes/stub data; Swagger UI at
> `/docs` shows the full route list matching Section 5.
>
> Verified: all 22 REST routes from Appendix A + the WS channel are
> registered under `/api/v1`; `/healthz` reports `503 degraded` cleanly
> with no DB running; a malformed request body returns `422` with the
> standard `{"detail": [...]}` shape; a request that reaches the DB
> layer with no Postgres/Neo4j running returns a clean
> `500 {"detail": "Internal server error"}` instead of a stack trace —
> confirms the global exception handler works end to end. Full
> 404/200 success-path verification needs `docker compose up` (not run
> in this delivery's build environment).

## Done-when (Phase 3 deliverable)

> A team can create a project, chat through ingestion, upload a doc,
> chat through planning with visible plan changes, and approve —
> verified end-to-end via Swagger or curl before any frontend is wired.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here, so this is unit-level, not a
> live `docker compose up` run — do that pass before the event): the
> full app still imports and registers all 28 routes with the new
> agent/service modules wired in; the compiled LangGraph correctly
> routes to the `intake` branch vs. the `scope_critic -> planner`
> branch depending on which endpoint invoked it (verified by running
> both branches with a stubbed Claude client); the JSON-reply parser
> correctly strips fenced code blocks and falls back to `{}` on
> malformed output instead of raising; `extract_text` round-trips a
> real in-memory `.docx` and `.txt` file and degrades to `""` (not an
> exception) on a corrupt PDF.
>
> Still needs a live pass once Postgres, Neo4j, and
> `LLM_API_KEY` are available: `alembic upgrade head` +
> `docker compose up`, then create a project, send a couple of
> `ingest/message` turns until `ready_for_planning` flips true (status
> becomes `planning`), send a `plan/chat` turn and confirm
> `critique_history` rows appear and `draft_scope`/`draft_roadmap`
> change, call `plan/approve` twice and confirm the second call
> returns `409`, and check `GET .../agent-graph/state` shows real
> `supervisor`/`intake`/`scope_critic`/`planner` rows in `recent_runs`.

## Done-when (Phase 4 deliverable)

> Dragging a Kanban card (via `PATCH`) reflects immediately in `GET
> .../roadmap` and `GET /projects/{id}`; a manual replan call visibly
> changes the roadmap.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here — do a live pass before the
> event): the full app still imports and registers all 22 REST routes
> + the WS channel with the new service/repository modules wired in;
> `app/repositories/graph.py`'s Cypher sequence was exercised against a
> fake driver and confirmed to (1) `MERGE` the `Project` node, (2)
> delete `Milestone`s no longer present in the roadmap, (3) upsert one
> `Milestone` per task with `BELONGS_TO`, (4) clear and rebuild each
> task's `BLOCKED_BY` edges from its `depends_on` list; a mocked
> `roadmap_service` test suite confirms `replan_roadmap` returns the
> Planner's rebuilt roadmap and calls `graph_repo.sync_roadmap` exactly
> once, `replan_roadmap` raises `ConflictError` (409) when the advisory
> lock is already held, `patch_task` sets `risk_flagged: true` and
> syncs the single `Milestone`'s status when a task moves to
> `"blocked"`, and `patch_task` raises `NotFoundError` (404) for an
> unknown `task_id`.
>
> Still needs a live pass once Postgres, Neo4j, and `LLM_API_KEY`
> are available: `alembic upgrade head` + `docker compose up`, approve
> a plan so a roadmap exists, `PATCH` a task to `"blocked"` and confirm
> `risk_flagged: true` plus the `Milestone` node's `status` updates in
> the Neo4j browser, call `replan` twice back-to-back (e.g. two tabs)
> and confirm the second returns `409`, and confirm `BLOCKED_BY` edges
> in Neo4j match whatever `depends_on` values the Planner produced.

## Done-when (Phase 5 deliverable)

> Connecting a real (or test) repo returns 200; `GET .../github/state`
> reflects real commit/PR/issue data within one poll interval of a
> manual trigger.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, GitHub token, or LLM key available here — do a live
> pass before the event): the full app still imports and registers
> all 22 REST routes + the WS channel with the new
> service/repository/node modules wired in; `github_client` was
> exercised against a mocked `httpx` transport and confirmed to map
> `200 -> ok`, `401 -> invalid_token`, `404 -> repo_not_found_or_no_access`,
> and any other non-2xx on a data-fetch call to `GithubApiError`;
> `match_text_to_task` was tested against a small roadmap and correctly
> matched a commit message by keyword, a commit by its changed file
> path, an issue title by keyword, and returned `None` for an unrelated
> message; a full `run_github_watcher` pass against mocked GitHub
> responses confirmed a commit gets tagged with the right
> `matched_task`, a PR open 6 hours is flagged `"stuck"`, and an issue
> matched to a task with a past ETA gets `eta_breach: true`;
> `github_service.poll_project` was tested for both the "no connection
> yet" no-op path and the full happy path (`github_state` persisted,
> `sync_commit_files` called, `last_polled_at` stamped); `graph.py`'s
> `sync_commit_files` Cypher was exercised against a fake driver and
> confirmed it writes one `MERGE`/`MAPS_TO` pair per changed file for a
> matched commit and skips an unmatched commit entirely.
>
> Still needs a live pass once Postgres, Neo4j, a real (or disposable
> test) GitHub token, and `LLM_API_KEY` are available:
> `alembic upgrade head` + `docker compose up`, approve a plan with a
> roadmap task whose name overlaps a real commit message/file path in
> a test repo, call `github/connect`, and confirm `GET .../github/state`
> shows that commit with the right `matched_task` immediately (not
> after a wait, since connect polls once synchronously); try connecting
> with a bad token and confirm `401`; try a nonexistent repo and
> confirm `422`; check the Neo4j browser for the new `CommitFile`
> nodes and `MAPS_TO` edges.

## Done-when (Phase 6 deliverable)

> Simulate a stalled task (no matching commits) and confirm: risk
> appears in `GET /risks`, the Neo4j traversal returns real downstream
> milestones, and a manual reprioritize call returns a rationale
> referencing them.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here — do a live pass before the
> event): the full app still imports and registers all 22 REST routes
> + the WS channel with the new node/service modules wired in;
> `detect_risks` was tested against a small roadmap + github_state and
> confirmed to flag an overdue task with no matching commit (rule A), a
> manually-blocked task (rule B), and a stuck PR (rule C), correctly
> skip a task with a matching commit, correctly treat a matching
> progress-log entry as equivalent activity to a commit, and produce
> zero new risks on a second pass over the same already-flagged
> conditions (de-dup); `risk_service.run_risk_watcher_for_project` was
> tested for both "new risks detected → persists + syncs
> `create_risk_node`" and "nothing detected → skips both writes
> entirely"; `risk_service.reprioritize_risk` was tested for both a 404
> on an unknown `risk_id` and the full happy path (traversal called
> with the risk's `task_id`, `replan_roadmap` called, the risk's JSONB
> entry ends up `resolved: true`, `mark_risk_resolved` called in
> Neo4j); `traverse_downstream_milestones`, `create_risk_node` (with
> and without a `task_id`), and `mark_risk_resolved` were all exercised
> against a fake Neo4j driver and produce exactly the Cypher Section
> 3.3 specifies (including the `*1..3` hop bound).
>
> Still needs a live pass once Postgres, Neo4j, and `LLM_API_KEY`
> are available: `alembic upgrade head` + `docker compose up`, approve
> a plan with a roadmap task whose ETA is in the past and that has no
> matching commits/progress entries, confirm it shows up in
> `GET /risks` after a poll or a `POST /progress` call, check the Neo4j
> browser for the new `Risk` node and `AFFECTS` edge, then call
> `POST /reprioritize` with that risk's id and confirm the
> `rationale` references the real downstream milestones returned by the
> traversal (set up a `depends_on` chain first so there's something
> for it to find) and that the risk shows `resolved: true` afterward.

## Done-when (Phase 7 deliverable)

> Manually pushing `hours_remaining` low or roadmap completion high
> causes a pitch outline to appear without any explicit generate call.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here — do a live pass before the
> event): the full app still imports and registers all 22 REST routes
> + the WS channel; the migration chain resolves to a single head
> (`a1c9f2d7e6b3 <- ff23a8c084bc <- None`) so `alembic upgrade head`
> will pick up the new column cleanly; `is_pitch_ready` was tested
> against an empty roadmap with plenty of time (not ready), an empty
> roadmap with `hours_remaining` under the threshold (ready — time
> pressure alone is enough), a roadmap just over 60% done (ready), and
> a roadmap at *exactly* 60% done (correctly not ready — the threshold
> is strictly `>`, not `>=`); the Pitch Agent's fallback outline was
> tested directly (pulls `problem`/`solution` from `project_idea`,
> builds `demo_flow` from `mvp_features`) and confirmed to kick in
> automatically when the model returns unparseable output; the full
> `generate_pitch` orchestration was tested for both the 409
> not-ready path and the happy path (only *resolved* risks get passed
> to the Pitch Agent, `pitch_outline`/`pitch_generated_at`/
> `status="pitch_ready"` all get persisted together).
>
> Still needs a live pass once Postgres, Neo4j, and `LLM_API_KEY`
> are available: `alembic upgrade head` + `docker compose up`, get a
> roadmap to >60% done (or edit `projects.hours_remaining` directly to
> under 3) and confirm `POST /pitch/generate` succeeds where it 409'd
> before; check that the returned `hook`/`ask` read like real pitch
> copy grounded in the actual `project_idea`/`scope`, not generic
> filler; call `GET /pitch` after a later, unrelated write (e.g. a
> Kanban `PATCH`) and confirm `generated_at` didn't change.

## Done-when (Phase 8 deliverable)

> A judge can type "why is X flagged?" or "re-plan the roadmap" into
> the chat panel and get a grounded, useful reply.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here — do a live pass before the
> event): the full app still imports and registers all 22 REST routes
> + the WS channel with the new node/service modules wired in;
> `classify_coach_message` was tested against a replan phrase, a
> reprioritize phrase with an explicit risk id, a reprioritize phrase
> with exactly one unresolved risk (resolves unambiguously), a
> reprioritize phrase with zero *and* with multiple unresolved risks
> and no explicit id (both correctly return `risk_id=None` rather than
> guessing), and a plain question; `guess_answered_by` was checked
> against one example per keyword group; the full
> `handle_coach_message` orchestration was tested end-to-end for all
> six paths — replan happy path, replan-while-locked (409 →
> conversational reply, not an error), reprioritize happy path,
> ambiguous-risk clarifying reply (confirmed the LLM is never even
> called for this case), reprioritize against a stale/unknown risk id,
> and a genuine question dispatching to (a mocked) Team Assistant; the
> Team Assistant node was tested for both a clean reply (whitespace
> trimmed) and a call failure correctly producing the fallback string;
> the cursor encode/decode round-trips correctly, and the keyset
> pagination query was compiled against the real Postgres dialect and
> confirmed to produce a correct `(created_at, id) > (cursor_created_at,
> cursor_id)` row-value WHERE clause plus the `phase = 'coaching'`
> filter.
>
> Still needs a live pass once Postgres, Neo4j, and `LLM_API_KEY`
> are available: `alembic upgrade head` + `docker compose up`, approve
> a plan, flag a risk (or wait for one), ask "why is X flagged?" in
> `POST /chat` and confirm the reply is actually grounded in that
> risk's real data (not generic); say "re-plan the roadmap" and confirm
> it visibly changes (cross-check against `GET /roadmap`); say "fix
> this" with 0 and then 2+ open risks and confirm both get the
> clarifying reply instead of acting on the wrong one; page through
> `GET /chat/history` with `limit=1` across a handful of messages and
> confirm `next_cursor` correctly walks forward with no gaps or repeats,
> and returns `null` on the last page.

## Done-when (Phase 9 deliverable)

> Opening two browser tabs on the same project and triggering a risk in
> one updates the Kanban/risk feed in the other within ~1s, with no
> manual refresh.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here — do a live pass before the
> event): the full app still imports and registers all 22 REST routes
> + the WS channel; `ConnectionManager` was tested directly (no FastAPI
> test client needed, since it has no dependency on the rest of the
> app) and confirmed to: deliver a broadcast only to sockets registered
> for that exact `project_id` (a second project's socket never
> receives it), produce the documented `{event, payload}` shape,
> no-op silently on a broadcast to a project with zero connections,
> auto-drop a socket whose `send_json` raises without affecting other
> sockets on the same broadcast, correctly encode `Decimal`/`datetime`/
> `UUID` payload values (exactly what come off the ORM) via
> `jsonable_encoder`, and never block longer than the 2s send timeout
> even when one socket hangs forever (confirmed a broadcast to a hung
> socket + a healthy one still completes in ~2s and drops only the
> hung one); each of the nine Section 6 events was then tested at its
> actual call site with the rest of that call mocked out — `start_run`
> broadcasts `node_activated` with the right node/trigger, `add_message`
> broadcasts `chat_message` with the right phase/role/content/
> agent_node, `update_project` broadcasts one `state_updated` per
> changed field, `patch_task` broadcasts `task_moved` only when
> `status` actually changes and not on an owner/eta/note-only edit,
> `run_risk_watcher_for_project` broadcasts `risk_flagged` with the
> full risk dict, `resolve_risk` broadcasts `risk_resolved`,
> `generate_pitch` broadcasts `pitch_ready`, `handle_plan_chat`
> broadcasts `plan_draft_updated` with the combined
> `{draft_scope, draft_roadmap}` shape, and `post_plan_approve`
> broadcasts `plan_approved` with a real `plan_approved_at` timestamp.
>
> Still needs a live pass once Postgres, Neo4j, and `LLM_API_KEY`
> are available, and is the one item from this deliverable that
> specifically needs it: open two browser tabs (or two `wscat`/`websocat`
> sessions) on `WS /projects/{id}/updates` for the same project,
> trigger something in a third channel (e.g. `PATCH` a Kanban task in
> Postman) and confirm both sockets receive the event within ~1s;
> disconnect one tab, confirm the other keeps receiving events
> uninterrupted and the manager's registry drops the disconnected
> socket; specifically re-verify the module docstring's noted
> broadcast-before-commit tradeoff doesn't cause visible issues in
> practice for any of the current call paths.

## Done-when (Phase 10 deliverable)

> Approve a plan, close the browser entirely, and confirm via
> `agent_run_log` that `scheduled_poll`-triggered runs keep appearing
> every ~2 minutes with no client connected.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or LLM key available here — do a live pass before the
> event, and this phase in particular has the least test coverage
> that's possible without one): the full app still imports and
> registers all 23 REST routes + the WS channel with the scheduler
> wired into the lifespan; `_sync_database_url` correctly derives a
> `postgresql+psycopg2://` URL from the app's asyncpg one;
> `register_project_jobs`/`deregister_project_jobs` were tested against
> a real (in-memory-backed) `AsyncIOScheduler` — confirmed to add both
> jobs with the right ids and intervals, be idempotent on repeated
> calls, correctly update an existing job's interval on re-registration
> (the exact path `.../github/connect` depends on), and safely no-op
> when deregistering jobs that were never registered; every branch of
> both job bodies was tested with the DB/service layer mocked out —
> self-deregistration when a project is no longer `"active"`, skipping
> work when the overlap lock is already held, the happy path
> (commits the session, passes `trigger="scheduled_poll"` through),
> and — critically — that an unexpected exception is swallowed rather
> than propagated, confirming one project's failure can't crash the
> scheduler; the tick job's decrement math was checked precisely
> (`Decimal` arithmetic, not float, matching the column type) and its
> pitch auto-trigger was confirmed to fire exactly once when a project
> crosses threshold with no existing `pitch_outline`, and to correctly
> skip when a pitch already exists; `POST .../submit`'s state-machine
> guards (reject from `intake`/`planning`, reject if already
> `submitted`) and its job-deregistration call were both tested
> directly.
>
> Still needs a live pass once Postgres, Neo4j, and `LLM_API_KEY`
> are available — this is the single most important live-testing item
> in the whole delivery, since Phase 10's entire value proposition
> (unattended 24-hour operation) is inherently about behavior over
> real time that a mocked unit test can't observe: run
> `alembic upgrade head` (confirms the `SQLAlchemyJobStore` can create
> its table against the real schema) + `docker compose up`, approve a
> plan, connect a real test repo, close every client, and watch
> `agent_run_log` over several minutes for `trigger="scheduled_poll"`
> rows appearing roughly every 2 minutes; kill and restart the
> container mid-run and confirm polling resumes for the same project
> without re-approving; manually edit `projects.hours_remaining` down
> past the Phase 7 threshold and confirm a pitch gets auto-generated
> within a minute with no client involved; call `POST .../submit` and
> confirm the `scheduled_poll` rows actually stop appearing.

## Done-when (Phase 11 deliverable)

> A deliberately-triggered risk produces a Reprioritizer rationale that
> visibly references retrieved historical pattern text, not just the
> live Neo4j graph.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, OpenAI, or LLM key available here — do a live pass with
> real seeded data before the event): the full app still imports and
> registers all 23 REST routes + the WS channel with the new
> `app/services/embeddings.py` / `app/services/rag_service.py` modules
> wired in; `format_snippets_for_prompt` renders a real snippet list
> into a labeled block and renders an explicit "none found" line for an
> empty list (never a blank/omitted section); `retrieve_similar_postmortems`
> was confirmed to catch a missing `OPENAI_API_KEY` and return `[]`
> rather than raising (a fake session, no real DB call attempted); with
> `get_chat_model` and `retrieve_similar_postmortems` both mocked, the
> Scope Critic node's actual outbound prompt was captured and confirmed
> to contain the `"Retrieved historical context (similar teams
> historically missed):"` header plus the mocked snippet text, and its
> `agent_run_log` `input_snapshot` was confirmed to include
> `retrieved_postmortem_count`; the same check was repeated for the
> Reprioritizer node against its own label
> (`"...historically recovered by"`) and its own `input_snapshot`
> field, with a decision still coming back correctly (`"reassign"`)
> once the mocked model reply was parsed.
>
> Still needs a live pass once Postgres, Neo4j, `OPENAI_API_KEY`, and
> `LLM_API_KEY` are available: `python -m scripts.seed_postmortems`
> against a fresh DB, then `python -m scripts.rag_sanity_check` and
> confirm both built-in queries return neighbors with a genuinely low
> (not near-1.0) cosine distance; trigger a real risk (e.g. leave a PR
> open past the stuck-PR threshold from Phase 5) and call
> `POST .../reprioritize`, then read the returned `rationale` and
> confirm it references retrieved pattern text specifically, not just
> the downstream-milestone count from the Neo4j traversal; send a
> planning chat turn for a project idea deliberately similar to one of
> the seeded postmortems and confirm at least one new `critique_history`
> row visibly reflects that historical pattern rather than only generic
> scope-critique language.

## Done-when (Phase 12 deliverable)

> A full run-through, unattended for at least 10 minutes with the
> dashboard closed, produces visible new activity in `agent_run_log`
> and the risk feed when reopened.
>
> Verified in this delivery's build environment (no live Postgres,
> Neo4j, or API keys available here — do a live pass before the
> event): the full app still imports and registers all 23 REST routes
> + the WS channel; `scripts/seed_demo_project.py` was executed at the
> module level (its `ROADMAP`/`RISKS` construction, which previously
> had an ordering bug where `_hours_ago`/`_eta_in` were referenced
> before their `def` — caught and fixed here — now evaluates cleanly)
> and confirmed to produce a roadmap with real `depends_on` edges, one
> resolved and one open risk, and a populated `pitch_outline`; the
> five documented error paths were re-verified end-to-end with a
> `TestClient` against the real app (dependency-overridden `get_db`/
> `get_neo4j`, mocked repository/GitHub-client calls) rather than by
> re-reading the `raise` statements: `GET /projects/{malformed-id}`
> → 404, `GET /projects/{well-formed but missing}` → 404,
> `POST .../plan/approve` on a project already past `"planning"` →
> 409, `POST .../ingest/document` with an unsupported content type →
> 415, and `POST .../github/connect` with a token GitHub rejects →
> 401 — all five matched Section 5 / Phase 2's documented contract
> exactly.
>
> Still needs a live pass once Postgres, Neo4j, and both API keys are
> available, and this is the one phase whose core deliverable *is*
> that live pass — none of it can be meaningfully substituted at the
> unit level: `python -m scripts.seed_demo_project` against the real
> database, then a genuine end-to-end dry run through the dashboard
> (create → ingest → plan → approve → connect a real repo → push a
> commit → watch a risk get flagged and resolved → generate a pitch);
> open the dashboard on two devices/tabs simultaneously and confirm
> both receive live WebSocket events for the same action; kill and
> restart the FastAPI process mid-run and confirm the scheduler resumes
> polling the active project with no manual intervention (Phase 10's
> recovery logic); and a final read-through of the demo project seeded
> above to confirm it still reads as a believable talking point, not
> obviously synthetic, if it ever needs to carry an actual demo.

## Codebase review pass (post-Phase 12)

A full end-to-end read-through of every router, service, agent node,
repository, model, migration, and config file, plus a `pyflakes` sweep
and a `TestClient` re-run of all five documented error paths. Real bugs
found and fixed:

- **`app/config.py`** — the `DATABASE_URL` fallback default used port
  `5432`; `docker-compose.yml` maps Postgres to host port `5433`
  (which `.env.example` already had right). Skipping
  `cp .env.example .env` would have silently pointed at nothing.
- **`scripts/seed_postmortems.py`** — a `NameError` regression from the
  Phase 11 refactor onto `app/services/embeddings.py`: the script's own
  `EMBEDDING_MODEL` constant was removed but a `print(...)` still
  referenced it, so the script would crash on its first line of
  output. Caught by `pyflakes`, not by `py_compile` (syntax-only) or an
  app-import check — the gap that let it through in the first place.
- **`app/logging_config.py`** — `install_request_id_middleware` reset
  the request-id contextvar in a `finally` block *before* logging the
  request-completion line, so every `app.request` log line reported
  `-` for its own request's id. Reordered so the log line is emitted
  before the reset.
- **`app/repositories/agent_run_log.py`** — `get_request_id()` had a
  docstring promising it feeds `agent_run_log` writes for
  request-to-run traceability, but nothing ever called it. `start_run`
  now stitches it into `input_snapshot["_request_id"]` (no migration
  needed, that column is JSONB).
- **`app/services/github_client.py`** — `_get_json`'s return type was
  annotated `-> list`, but the single-commit endpoint it's also used
  for returns a dict. Harmless at runtime, corrected to `list | dict`.
- Three dead `uuid` imports (`risk_service.py`, `pitch_service.py`,
  `postmortem_embeddings.py`) removed.

Nothing else turned up across the full read-through — no other
mismatched field names, broken call paths, or logic errors. The one
remaining `pyflakes` hit (`chat_messages.py`'s `extra` variable) is an
intentional pagination lookahead throwaway, not a bug.

## Non-negotiables (carried through every phase)

- Single FastAPI process — REST, WebSocket broadcaster, LangGraph
  nodes, and the scheduler all run in-process.
- No authentication anywhere in the MVP — every route is open;
  `speaker_name` is display-only, never a credential.
- Polling, not webhooks, for GitHub sync — no public callback URL to
  keep alive during the demo.
- Agents replan, they don't act destructively — nothing pushes commits
  or closes issues on the team's behalf.
- State lives in Postgres, not memory.

## What's next

All twelve phases from the Implementation Plan are represented in this
delivery. What's left is exclusively the "Still needs a live pass"
items called out under each phase's Done-when section above — a real
run against live hosted Postgres (Neon)/Neo4j (Aura)/`LLM_API_KEY`/
`OPENAI_API_KEY`, a frontend to drive the dashboard/two-tab/cold-start
checks against, and a real GitHub repo to connect for the end-to-end
dry run. None of that needs new backend code; it needs the live
infrastructure this delivery's build environment didn't have.
