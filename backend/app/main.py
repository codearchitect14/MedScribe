from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    auth,
    contact,
    encounters,
    live_transcription,
    organizations,
    patients,
    reimbursement_rates,
    tasks,
    users,
)
from app.core.body_size_limit import BodySizeLimitMiddleware
from app.core.config import get_settings
from app.core.correlation import RequestContextMiddleware
from app.core.error_handlers import register_error_handlers
from app.core.logging_config import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.monitoring import configure_sentry

configure_logging()
configure_sentry()

settings = get_settings()

app = FastAPI(title="MedScribe AI API")

register_error_handlers(app)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
# Added last so it is outermost: it sees (and times) the full middleware
# stack, and every response - including ones CORS/security headers already
# touched - still passes back through it to get X-Request-ID attached.
app.add_middleware(RequestContextMiddleware)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(organizations.router)
app.include_router(patients.router)
app.include_router(encounters.router)
app.include_router(live_transcription.router)
app.include_router(tasks.router)
app.include_router(reimbursement_rates.router)
app.include_router(analytics.router)
app.include_router(contact.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
