# Hackathon Coach — Frontend

React + TypeScript frontend for the Hackathon Coach AI agent system.

## Quick start

```bash
npm install
npm run dev
```

Runs on `http://localhost:5173`. The Vite dev server proxies `/api` and WebSocket `/ws` to `http://localhost:8000` (your FastAPI backend).

## Stack

| Layer | Library |
|---|---|
| Framework | React 18 + TypeScript |
| Routing | React Router v6 |
| Server state | TanStack Query v5 |
| Client state | Zustand v4 |
| Drag-and-drop | dnd-kit |
| Styling | Tailwind CSS v3 |
| Icons | Lucide React |
| Build | Vite 5 |

## Project structure

```
src/
  pages/
    LandingPage/        # / — create project
    IngestPage/         # /projects/:id/ingest — intake chat
    PlanPage/           # /projects/:id/plan — planner chat + draft plan
    dashboard/
      OverviewPage/     # /dashboard — stats, Kanban, risks, agent graph
      AgentPage/        # /dashboard/agents/:agentKey — per-agent detail
      PitchPage/        # /dashboard/pitch — pitch outline + export
  components/
    chat/               # ChatThread, ChatComposer, CoachChatPanel, DocumentDropzone
    dashboard/          # DashboardShell, AgentNavItem, AgentGraphView, StatTile, etc.
    kanban/             # KanbanBoard (dnd-kit drag-and-drop)
    risks/              # RiskFeedItem
    plan/               # DraftPlanPanel, ApprovalBar
    ui/                 # Button, Input, Card, EmptyState, SkeletonTile, etc.
  hooks/
    useProject.ts       # TanStack Query wrapper for GET /projects/:id
    useProjectSocket.ts # Single WebSocket connection per project
  store/
    index.ts            # Zustand store — project, agentGraph, connection, ui slices
  api/
    client.ts           # Base fetch wrapper with error handling
    index.ts            # All API domain functions
  lib/
    agents.ts           # Agent metadata (labels, colors, descriptions)
    utils.ts            # cn(), formatTime(), KANBAN_COLUMNS, etc.
  types/
    index.ts            # All shared TypeScript types
```

## Key design decisions

**Phase routing** — `project.status` from the backend is always the source of truth. Route guards in `DashboardShell` redirect to `/ingest` or `/plan` if status doesn't match. The dashboard is only reachable when `status === 'active'`.

**Single WebSocket** — `useProjectSocket` opens one connection per project in the `DashboardShell`. Events are dispatched to the Zustand store; components subscribe to the store, not the socket. On reconnect, `GET /projects/:id` is re-fetched to patch any missed events.

**Optimistic Kanban** — drag-and-drop updates the local task status immediately, calls `PATCH /roadmap/tasks/:id`, and reverts with an inline card error on failure.

**`@AI` mentions** — the `ChatComposer` detects `@AI` in the text and routes the message to the coach API. Plain text (no `@AI`) is treated as a team note stored locally with the `speaker_name` field.

**Coach Chat Panel** — a slide-in drawer toggled from the top bar, persistent across all dashboard routes. Fetches `chat/history` on first open, then appends to local state from direct API responses + WebSocket `chat_message` events (de-duplicated by `id`).

## Backend proxy

`vite.config.ts` proxies:
- `/api` → `http://localhost:8000`  
- WebSocket `/api/v1/projects/:id/updates` → `ws://localhost:8000`

Change the target in `vite.config.ts` if your backend runs on a different port.

## Build for production

```bash
npm run build
# Output: dist/
```
