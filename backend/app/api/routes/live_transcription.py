import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_token
from app.models.encounter import Encounter, EncounterStatus
from app.models.user import User, UserRole
from app.services.clinical.live_transcription import (
    LiveTranscriptionSession,
    get_worker_pool_semaphore,
    transcribe_segment,
)

router = APIRouter(prefix="/ws/encounters", tags=["live-transcription"])
logger = structlog.get_logger(__name__)


async def _authenticate(websocket: WebSocket, session: AsyncSession) -> User | None:
    token = websocket.query_params.get("token")
    if not token:
        return None
    payload = decode_token(token, expected_type="access")
    if payload is None:
        return None
    user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        return None
    return user


async def _acquire_worker_slot(websocket: WebSocket) -> None:
    semaphore = get_worker_pool_semaphore()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=0.001)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "queued"})
        await semaphore.acquire()


async def _finalize_pending(
    session: AsyncSession, encounter: Encounter, live_session: LiveTranscriptionSession, websocket: WebSocket
) -> None:
    if not live_session.has_pending_audio():
        return
    text = await transcribe_segment(live_session.snapshot_buffer())
    live_session.reset_after_finalize()
    if not text:
        return
    encounter.raw_transcript = ((encounter.raw_transcript or "") + " " + text).strip()
    await session.commit()
    await websocket.send_json({"type": "final", "seq": live_session.next_sequence(), "text": text})


@router.websocket("/{encounter_id}/live-transcribe")
async def live_transcribe(
    websocket: WebSocket,
    encounter_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    settings = get_settings()
    if not settings.live_transcription_enabled:
        await websocket.close(code=1013, reason="Live transcription is disabled on this server")
        return

    user = await _authenticate(websocket, session)
    if user is None:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    encounter = await session.get(Encounter, encounter_id)
    if encounter is None or encounter.organization_id != user.organization_id:
        await websocket.close(code=4404, reason="Encounter not found")
        return
    if user.role == UserRole.clinician and encounter.clinician_id != user.id:
        await websocket.close(code=4404, reason="Encounter not found")
        return
    if encounter.status != EncounterStatus.recording:
        await websocket.close(
            code=4409, reason=f"Encounter is not in recording state (status={encounter.status.value})"
        )
        return

    await websocket.accept()
    await _acquire_worker_slot(websocket)

    live_session = LiveTranscriptionSession()
    try:
        await websocket.send_json({"type": "ready"})

        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            text_frame = message.get("text")
            if text_frame is not None:
                try:
                    control = json.loads(text_frame)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "detail": "control message must be JSON"})
                    continue

                control_type = control.get("type")
                if control_type == "stop":
                    try:
                        await _finalize_pending(session, encounter, live_session, websocket)
                    except Exception as exc:  # noqa: BLE001 - still must close cleanly on stop
                        logger.warning("live_transcription.finalize_on_stop_error", error=str(exc))
                        await websocket.send_json(
                            {"type": "error", "detail": "failed to finalize the last audio segment"}
                        )
                    encounter.status = EncounterStatus.transcribed
                    await session.commit()
                    await websocket.send_json(
                        {"type": "stopped", "raw_transcript": encounter.raw_transcript}
                    )
                    await websocket.close()
                    return
                if control_type == "pause":
                    live_session.paused = True
                elif control_type == "resume":
                    live_session.paused = False
                continue

            audio_frame = message.get("bytes")
            if audio_frame is None:
                continue

            live_session.add_chunk(audio_frame)

            try:
                if live_session.should_finalize() or live_session.is_over_hard_cap():
                    text = await transcribe_segment(live_session.snapshot_buffer())
                    live_session.reset_after_finalize()
                    if text:
                        encounter.raw_transcript = ((encounter.raw_transcript or "") + " " + text).strip()
                        await session.commit()
                    await websocket.send_json(
                        {"type": "final", "seq": live_session.next_sequence(), "text": text}
                    )
                elif live_session.should_run_partial():
                    text = await transcribe_segment(live_session.snapshot_buffer())
                    live_session.mark_partial_run()
                    await websocket.send_json(
                        {"type": "partial", "seq": live_session.next_sequence(), "text": text}
                    )
            except Exception as exc:  # noqa: BLE001 - one bad chunk must not kill the session
                logger.warning("live_transcription.inference_error", error=str(exc))
                await websocket.send_json({"type": "error", "detail": "transcription failed for this segment"})

    except WebSocketDisconnect:
        # Client dropped without an explicit stop. Leave status as 'recording'
        # so a reconnect to the same encounter id can resume; whatever was
        # already finalized is already checkpointed in raw_transcript.
        pass
    finally:
        get_worker_pool_semaphore().release()
