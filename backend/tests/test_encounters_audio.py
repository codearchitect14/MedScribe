"""Integration test for POST /encounters/audio: uploads a real (synthetic)
WAV file through the API and verifies faster-whisper runs and an encounter
is created with status=transcribed. Marked slow: loads the Whisper model.
"""

import math
import struct
import uuid
import wave
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models.organization import Organization
from app.models.user import User, UserRole

settings = get_settings()


def _write_tone_wav(path: Path) -> None:
    framerate = 16000
    n_frames = int(1.0 * framerate)
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        frames = bytearray()
        for i in range(n_frames):
            sample = int(3000 * math.sin(2 * math.pi * 440.0 * (i / framerate)))
            frames += struct.pack("<h", sample)
        wav_file.writeframes(bytes(frames))


def _require_db():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")


@pytest.mark.slow
@pytest.mark.asyncio(loop_scope="session")
async def test_create_encounter_from_audio_upload(tmp_path):
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Audio Test Org {suffix}")
        session.add(org)
        session.flush()
        email = f"clinician.{suffix}@example-medscribe.com"
        user = User(
            email=email,
            hashed_password=hash_password("TestPass123!"),
            full_name="Audio Test Clinician",
            role=UserRole.clinician,
            organization_id=org.id,
            is_active=True,
        )
        session.add(user)
        session.commit()

    wav_path = tmp_path / "encounter.wav"
    _write_tone_wav(wav_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/auth/login", data={"username": email, "password": "TestPass123!"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        patient = await client.post(
            "/patients", json={"first_name": "Audio", "last_name": "Patient"}, headers=headers
        )
        assert patient.status_code == 201
        patient_id = patient.json()["id"]

        with wav_path.open("rb") as f:
            response = await client.post(
                "/encounters/audio",
                data={"patient_id": patient_id},
                files={"audio": ("encounter.wav", f, "audio/wav")},
                headers=headers,
            )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "transcribed"
        assert isinstance(body["raw_transcript"], str)
