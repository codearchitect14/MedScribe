"""Prompt construction, designed to minimize token usage per plan.md Phase 3.

Rules followed here:
- One short, fixed system prompt reused across every call (both providers
  support prompt caching for repeated prefixes).
- SOAP note generation returns all four sections in a single call.
- Care plan generation is built from the already-generated Assessment/Plan
  text only, never the raw transcript again.
- Coding generation is built from a small set of pre-retrieved candidate
  codes (pgvector similarity search happens before this module is reached),
  never asking the model to invent codes from memory.
"""

from app.llm.schemas import TaskType

SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. You structure text into the "
    "exact JSON schema requested. You never invent facts not present in the "
    "input. You output JSON only, with no prose, no markdown fences, and no "
    "explanation outside the JSON object."
)


def build_soap_note_prompt(transcript: str) -> str:
    return (
        "Convert the following doctor-patient transcript into a SOAP note.\n"
        "Return a JSON object with exactly these string fields: "
        '"subjective", "objective", "assessment", "plan".\n'
        "Each field should be a concise clinical paragraph. Do not include "
        "any field not listed above.\n\n"
        f"Transcript:\n{transcript}"
    )


def build_care_plan_prompt(assessment: str, plan: str) -> str:
    return (
        "Using only the clinical assessment and plan below (do not assume "
        "any information not stated here), produce a structured care plan.\n"
        "Return a JSON object with exactly these fields: "
        '"diagnosis_summary" (string), "follow_up_actions" (array of strings), '
        '"medications" (array of strings, each clearly a suggestion requiring '
        'clinician confirmation), "patient_education" (array of strings), '
        '"next_appointment_guidance" (string).\n\n'
        f"Assessment:\n{assessment}\n\nPlan:\n{plan}"
    )


def build_coding_prompt(assessment: str, candidates: list[dict]) -> str:
    candidate_lines = "\n".join(
        f"- {c['code']}: {c['description']}" for c in candidates
    )
    return (
        "Given the clinical assessment below and a short list of candidate "
        "medical codes retrieved from the reference code database, select the "
        "codes that are actually supported by the assessment and briefly "
        "justify each one. Only choose codes from the candidate list below; "
        "never invent a code that is not listed.\n"
        "Return a JSON object with exactly one field, \"selected_codes\", an "
        "array of objects each with fields \"code\" (string, must match a "
        "candidate exactly), \"justification\" (short string), and "
        '"confidence" (number from 0 to 1).\n\n'
        f"Assessment:\n{assessment}\n\nCandidate codes:\n{candidate_lines}"
    )


def build_retry_prompt(original_prompt: str) -> str:
    return (
        original_prompt
        + "\n\nYour previous response was not valid JSON matching the "
        "required schema. Respond again with a single valid JSON object "
        "only, matching the schema exactly, with no other text."
    )


PROMPT_BUILDERS = {
    TaskType.soap_note: build_soap_note_prompt,
    TaskType.care_plan: build_care_plan_prompt,
    TaskType.coding_justification: build_coding_prompt,
}
