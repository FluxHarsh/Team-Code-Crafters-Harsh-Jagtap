"""
Cross-cutting error handling (Phase 2).

Every route raises one of the AppError subclasses below instead of
constructing HTTPException ad hoc — that's what keeps 404/409/415/401
consistent across ~20 routes instead of drifting into ad hoc 400s
(Implementation Plan, Phase 2: "Global exception handler").

The response shape is always {"detail": "..."}, which matches FastAPI's
own default shape for validation errors (422) and HTTPException, so the
client never has to branch on which layer raised the error.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for all handled application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    """404 — e.g. unknown project_id, task_id, risk_id."""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    """409 — e.g. double-approve, plan not ready, re-plan already running."""

    status_code = status.HTTP_409_CONFLICT


class UnsupportedMediaTypeError(AppError):
    """415 — e.g. document upload with an unsupported extension."""

    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class UnauthorizedError(AppError):
    """401 — e.g. invalid GitHub token on /github/connect."""

    status_code = status.HTTP_401_UNAUTHORIZED


class UnprocessableEntityError(AppError):
    """422 — e.g. repo not found / no access on /github/connect.

    Distinct from FastAPI's own 422 (request-body validation) — this is
    for semantic validation failures that only surface after touching an
    external system or the DB, not shape validation.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info(
            "app_error",
            extra={"path": request.url.path, "status_code": exc.status_code, "detail": exc.detail},
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Keep FastAPI's default 422 behavior but log it consistently
        # with everything else.
        logger.info("validation_error", extra={"path": request.url.path, "errors": exc.errors()})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
