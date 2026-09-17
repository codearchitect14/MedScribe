from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, encounters, live_transcription, patients, users
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware

settings = get_settings()

app = FastAPI(title="MedScribe AI API")

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(patients.router)
app.include_router(encounters.router)
app.include_router(live_transcription.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
