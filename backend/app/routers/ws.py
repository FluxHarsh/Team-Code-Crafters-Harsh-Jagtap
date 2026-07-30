"""
WS /api/v1/projects/{project_id}/updates

Architecture doc Section 6. Single channel per project — the dashboard
subscribes once and receives every event (plan_draft_updated,
plan_approved, node_activated, state_updated, task_moved, risk_flagged,
risk_resolved, pitch_ready, chat_message).

Phase 9: connections now really register with
app.ws.connection_manager.manager, so app.ws.connection_manager.broadcast
(called from the repo/service hooks described there) actually reaches
this socket. Reconnect handling (Section 6 / Phase 9's own task list):
this endpoint intentionally does NOT replay missed events -- a client
that was disconnected should call GET /projects/{id} on reconnect to
get full current state (cheap, and already the source of truth) rather
than this server trying to buffer/replay a backlog per-socket.
"""

import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.connection_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["websocket"])


@router.websocket("/{project_id}/updates")
async def project_updates(websocket: WebSocket, project_id: str) -> None:
    # A websocket can't return a normal HTTP error body, so a bad id
    # just closes the handshake with a policy-violation close code
    # instead of AppError. Not checking "does this project exist" in
    # Postgres here -- an invalid *format* id is a client bug worth
    # rejecting; a well-formed id for a project that doesn't exist yet
    # (or was deleted) just never receives any events, which is a
    # harmless no-op rather than something worth a DB round-trip on
    # every connection to prevent.
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        await websocket.close(code=1008, reason=f"Invalid project_id: {project_id!r}")
        return

    await websocket.accept()
    manager.register(pid, websocket)
    logger.info("ws connected", extra={"project_id": project_id})
    try:
        await websocket.send_json({"event": "connected", "payload": {"project_id": project_id}})
        while True:
            # This channel is server -> client only; nothing the client
            # sends drives any behavior. Just drain it so the socket
            # doesn't look idle/stalled to intermediary proxies, and so
            # receive() is what detects a disconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("ws disconnected", extra={"project_id": project_id})
    finally:
        manager.unregister(pid, websocket)
