"""Rejects oversized request bodies before they are read into memory or
parsed (plan.md Phase 9 security review). Pydantic's `max_length` on
individual fields (Phase 6) only bounds a field once the body has already
been fully read and JSON-decoded; this middleware bounds the raw body size
up front, which is the layer several known Starlette/ASGI-framework
denial-of-service advisories concern (unbounded body/multipart parsing).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

DEFAULT_MAX_BODY_BYTES = 50 * 1024 * 1024  # 50 MB: comfortably above a typical compressed audio upload


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"},
                    )
            except ValueError:
                pass  # malformed header; let normal request handling reject it
        return await call_next(request)
