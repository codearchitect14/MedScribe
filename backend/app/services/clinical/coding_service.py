from sqlalchemy import select

from app.core.config import get_settings
from app.embeddings.embedder import embed_text
from app.llm.gateway import GenerationContext, generate
from app.llm.prompts import build_coding_prompt
from app.llm.schemas import CodingJustificationResult, TaskType
from app.models.code_suggestion import CodeSuggestion, CodeType
from app.models.encounter import Encounter, EncounterStatus
from app.models.icd10_code import Icd10Code
from app.models.procedure_code import ProcedureCode
from app.models.soap_note import SoapNote


async def _retrieve_candidates(context: GenerationContext, assessment_embedding: list[float]) -> list[dict]:
    settings = get_settings()
    k = settings.coding_candidates_per_table

    icd10_rows = (
        await context.session.execute(
            select(Icd10Code)
            .order_by(Icd10Code.embedding.cosine_distance(assessment_embedding))
            .limit(k)
        )
    ).scalars().all()

    procedure_rows = (
        await context.session.execute(
            select(ProcedureCode)
            .order_by(ProcedureCode.embedding.cosine_distance(assessment_embedding))
            .limit(k)
        )
    ).scalars().all()

    candidates = [
        {"code": row.code, "description": row.short_description, "code_type": CodeType.icd10}
        for row in icd10_rows
    ]
    candidates += [
        {"code": row.code, "description": row.description, "code_type": CodeType.hcpcs}
        for row in procedure_rows
    ]
    return candidates


async def generate_code_suggestions(
    encounter: Encounter, soap_note: SoapNote, context: GenerationContext
) -> list[CodeSuggestion]:
    """Never asks the LLM to invent a code from memory: candidates are
    retrieved from the real, versioned reference tables via pgvector
    similarity search first, and the LLM only selects and justifies from
    that list (plan.md Phase 3/4). Any code the LLM returns that is not in
    the candidate list is discarded rather than persisted.
    """
    assessment = soap_note.assessment or ""
    assessment_embedding = embed_text(assessment)

    candidates = await _retrieve_candidates(context, assessment_embedding)
    candidates_by_code = {c["code"]: c for c in candidates}

    prompt = build_coding_prompt(assessment, [{"code": c["code"], "description": c["description"]} for c in candidates])
    result = await generate(TaskType.coding_justification, prompt, context)
    data: CodingJustificationResult = result.data  # type: ignore[assignment]

    suggestions: list[CodeSuggestion] = []
    for selected in data.selected_codes:
        candidate = candidates_by_code.get(selected.code)
        if candidate is None:
            continue  # not a real candidate; discard rather than trust the model's memory
        suggestion = CodeSuggestion(
            encounter_id=encounter.id,
            code_type=candidate["code_type"],
            code=selected.code,
            description=candidate["description"],
            confidence_score=selected.confidence,
            accepted=None,
        )
        context.session.add(suggestion)
        suggestions.append(suggestion)

    encounter.status = EncounterStatus.coded
    context.session.add(encounter)

    await context.session.commit()
    for suggestion in suggestions:
        await context.session.refresh(suggestion)
    return suggestions
