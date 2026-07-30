"""
Structured logging (Phase 2).

One logger per module (via `logging.getLogger(__name__)` in each file,
same convention as app/errors.py), plus a request-id attached to every
log line for the duration of a request. This is what makes an
agent_run_log row traceable back to the specific HTTP request that
triggered it during judge Q&A (Implementation Plan, Phase 2).
"""

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request

from app.config import get_settings

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Injects the current request's id into every log record as
    %(request_id)s, falling back to '-' outside a request (startup,
    scheduler jobs before Phase 10 tags its own trigger id)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Quiet down noisy third-party loggers unless we're debugging.
    for noisy in ("httpx", "neo4j", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))


def install_request_id_middleware(app: FastAPI) -> None:
    logger = logging.getLogger("app.request")

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = _request_id_ctx.set(request_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - start) * 1000
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            # Reset only after the completion log line above has been
            # emitted -- resetting first (the original ordering here)
            # meant every "app.request" line logged "-" for its own
            # request's id, which defeated the whole point of tagging
            # log lines with request_id in the first place.
            _request_id_ctx.reset(token)


def get_request_id() -> str:
    """Read the current request's id — pass this into agent_run_log
    writes (Phase 3+) so a run can be traced back to its trigger."""
    return _request_id_ctx.get()
