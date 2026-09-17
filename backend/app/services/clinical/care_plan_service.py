import json

from app.llm.gateway import GenerationContext, generate
from app.llm.prompts import build_care_plan_prompt
from app.llm.schemas import CarePlanResult, TaskType
from app.models.care_plan import CarePlan
from app.models.soap_note import SoapNote


async def generate_care_plan(soap_note: SoapNote, context: GenerationContext) -> CarePlan:
    """Builds the care plan from the already-generated Assessment/Plan text
    only, never the raw transcript again (token minimization, plan.md
    Phase 3/4).
    """
    prompt = build_care_plan_prompt(soap_note.assessment or "", soap_note.plan or "")
    result = await generate(TaskType.care_plan, prompt, context)
    data: CarePlanResult = result.data  # type: ignore[assignment]

    care_plan = CarePlan(
        encounter_id=soap_note.encounter_id,
        # care_plans.content is a single text column (see docs/database-schema.md);
        # the structured result is stored as JSON so the frontend can render each
        # field individually rather than a single opaque paragraph.
        content=json.dumps(data.model_dump()),
    )
    context.session.add(care_plan)
    await context.session.commit()
    await context.session.refresh(care_plan)
    return care_plan
