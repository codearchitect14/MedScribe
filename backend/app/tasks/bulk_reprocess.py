"""Background bulk re-processing of historical encounters (plan.md Phase 6):
"anything that could exceed a normal HTTP request timeout" belongs in a
Celery task rather than a synchronous endpoint. Regenerating a SOAP note
calls the LLM gateway once per encounter, which for a large batch would
comfortably blow past a typical request timeout if done inline.

Celery's default execution model is synchronous per task; the app's
clinical services are async (async DB session, async LLM gateway), so each
task drives its own event loop with asyncio.run() and a fresh AsyncSession/
Redis client, rather than trying to share the request-scoped ones from
app.core.db / app.core.redis.
"""

import asyncio
import uuid

import structlog

from app.core.db import async_session_factory
from app.core.redis import get_redis
from app.llm.gateway import GenerationContext
from app.models.encounter import Encounter
from app.services.clinical.soap_note_service import generate_soap_note
from app.services.clinical.workflow import SOAP_GENERATION_ALLOWED_FROM
from app.worker import celery_app

logger = structlog.get_logger(__name__)


async def _reprocess_one(session, redis, encounter_id: uuid.UUID) -> tuple[bool, str | None]:
    encounter = await session.get(Encounter, encounter_id)
    if encounter is None:
        return False, "encounter not found"
    if encounter.status not in SOAP_GENERATION_ALLOWED_FROM:
        return False, f"encounter status '{encounter.status.value}' does not allow SOAP note generation"

    context = GenerationContext(session=session, redis=redis, encounter_id=encounter.id)
    try:
        await generate_soap_note(encounter, context)
    except Exception as exc:  # noqa: BLE001 - one encounter's failure must not abort the batch
        return False, str(exc)
    return True, None


async def _bulk_reprocess(encounter_ids: list[str]) -> dict:
    redis = get_redis()
    succeeded: list[str] = []
    failed: list[dict] = []

    async with async_session_factory() as session:
        for raw_id in encounter_ids:
            encounter_id = uuid.UUID(raw_id)
            ok, error = await _reprocess_one(session, redis, encounter_id)
            if ok:
                succeeded.append(raw_id)
            else:
                failed.append({"encounter_id": raw_id, "error": error})

    logger.info("bulk_reprocess.completed", succeeded=len(succeeded), failed=len(failed))
    return {"succeeded": succeeded, "failed": failed}


@celery_app.task(name="bulk_reprocess_encounters")
def bulk_reprocess_encounters_task(encounter_ids: list[str]) -> dict:
    return asyncio.run(_bulk_reprocess(encounter_ids))
