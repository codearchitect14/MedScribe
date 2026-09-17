"""Centralized error handling with a consistent response shape (plan.md
Phase 6). HTTPException and validation errors keep FastAPI's normal
{"detail": ...} shape (existing clients/tests already depend on that); this
module's job is specifically to make sure an *unhandled* exception never
leaks a bare traceback to the client and always carries the same
request_id that appears in the server logs for that request.
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.correlation import REQUEST_ID_HEADER

logger = structlog.get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            REQUEST_ID_HEADER, "unknown"
        )
        logger.exception("request.unhandled_exception", request_id=request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={REQUEST_ID_HEADER: request_id},
        )
