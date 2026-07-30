"""
In-memory per-project WebSocket connection registry + the single
broadcast() helper every state-changing code path calls (architecture
doc Section 6). Single-process only: connections live in this
process's memory, keyed by project_id. A multi-instance deployment
would need every instance subscribed to a shared pub/sub (e.g. Redis)
so a broadcast triggered on instance A reaches a client connected to
instance B -- out of scope for this single-instance hackathon MVP, but
worth calling out explicitly for anyone scaling this past a demo.

Design note on *where* broadcast() gets called from: three of the nine
events (node_activated, chat_message, and the generic state_updated)
are hooked directly into the shared repository functions every node/
service already funnels through (agent_run_log.start_run,
chat_messages.add_message, projects.update_project) rather than
sprinkled at each of the many individual call sites across Phases
3-8 -- those repo functions *are* the actual state-changing point for
those three events, so hooking there guarantees complete coverage
(nothing can update project state, log a node run, or post a chat
message without it) instead of relying on every call site remembering
to broadcast. The remaining five events (plan_draft_updated,
plan_approved, task_moved, risk_flagged, risk_resolved, pitch_ready)
need richer context than a generic repo write has on hand (e.g.
task_moved's `from`/`to`, risk_flagged's full risk dict) and are
broadcast explicitly at their actual service-layer call sites in each
phase's service module, per the Implementation Plan's own description
of this retrofit.

broadcast() is deliberately best-effort and never raises: a WebSocket
send failure must never break the Postgres write or business logic it
happened to be triggered from (some call sites are inside a repository
function mid-transaction). A dead/slow socket is dropped from the
registry rather than allowed to block or fail the caller.

Known tradeoff of hooking into the repo layer: these broadcasts fire
before the enclosing request's transaction commits (app.dependencies.get_db
commits once, at the very end of the request). If a later step in the
same request then fails and the transaction rolls back, a client could
see an event for a change that didn't actually persist. In every
current call path the repo write is the last thing that happens before
the request returns, so this is a theoretical gap, not an observed
one -- but worth a live-testing pass to confirm before relying on it
for a demo, and worth remembering if a future phase adds a write *after*
one of these calls within the same request.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

# How long a single send is allowed to hang before we give up on that
# socket -- protects broadcast() callers (some of them mid-transaction)
# from ever blocking on a slow/half-open client connection.
SEND_TIMEOUT_SECONDS = 2.0


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    def register(self, project_id: uuid.UUID, websocket: WebSocket) -> None:
        self._connections[project_id].add(websocket)

    def unregister(self, project_id: uuid.UUID, websocket: WebSocket) -> None:
        sockets = self._connections.get(project_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[project_id]

    def connection_count(self, project_id: uuid.UUID) -> int:
        return len(self._connections.get(project_id, ()))

    async def broadcast(self, project_id: uuid.UUID, event_type: str, payload: dict) -> None:
        sockets = list(self._connections.get(project_id, ()))
        if not sockets:
            return

        message = jsonable_encoder({"event": event_type, "payload": payload})
        dead: list[WebSocket] = []
        for socket in sockets:
            try:
                await asyncio.wait_for(socket.send_json(message), timeout=SEND_TIMEOUT_SECONDS)
            except Exception:
                logger.debug(
                    "ws_send_failed_dropping_socket",
                    extra={"project_id": str(project_id), "event": event_type},
                )
                dead.append(socket)

        for socket in dead:
            self.unregister(project_id, socket)


# Process-wide singleton -- every router/service/repository that needs
# to broadcast imports `manager` (or the `broadcast` convenience
# function below) from this module rather than constructing its own.
manager = ConnectionManager()


async def broadcast(project_id: uuid.UUID, event_type: str, payload: dict) -> None:
    await manager.broadcast(project_id, event_type, payload)
