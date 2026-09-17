from app.llm.gateway import GenerationContext, generate
from app.llm.prompts import build_soap_note_prompt
from app.llm.schemas import SoapNoteResult, TaskType
from app.models.encounter import Encounter, EncounterStatus
from app.models.soap_note import SoapNote, SoapNoteStatus


async def generate_soap_note(encounter: Encounter, context: GenerationContext) -> SoapNote:
    prompt = build_soap_note_prompt(encounter.raw_transcript or "")
    result = await generate(TaskType.soap_note, prompt, context)
    data: SoapNoteResult = result.data  # type: ignore[assignment]

    soap_note = SoapNote(
        encounter_id=encounter.id,
        subjective=data.subjective,
        objective=data.objective,
        assessment=data.assessment,
        plan=data.plan,
        model_used=result.model,
        tokens_used=result.tokens_input + result.tokens_output,
        status=SoapNoteStatus.draft,
    )
    context.session.add(soap_note)

    encounter.status = EncounterStatus.note_generated
    context.session.add(encounter)

    await context.session.commit()
    await context.session.refresh(soap_note)
    return soap_note
