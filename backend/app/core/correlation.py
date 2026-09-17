"""Request correlation IDs, for support/debugging (plan.md Phase 6).

Every response carries an X-Request-ID header (reusing the client's value if
it sent one, so a request can be traced end to end across a load balancer
or reverse proxy). The same id is bound into structlog's contextvars so
every log line emitted while handling the request includes it, and it is
included in the body of any 500 response so a support ticket can reference
one id that appears in both the client-visible error and the server logs.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation id and logs one structured line per request.

    Deliberately logs only method, path, status, and duration - never the
    request or response body, which for this application can contain PHI
    (raw transcripts, SOAP note content, patient identifiers). See
    docs/security.md.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "request.unhandled_error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
