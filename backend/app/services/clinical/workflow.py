"""Encounter status state machine.

transcribed -> note_generated -> under_review -> finalized -> coded -> billed

Enforced at the API layer so encounters cannot skip required review steps
(per plan.md Phase 4). `recording` is only ever set by the Phase 5 live
transcription flow and is not reachable from these endpoints.
"""

from fastapi import HTTPException, status

from app.models.encounter import Encounter, EncounterStatus

# States from which generating a new SOAP note is allowed. Regenerating
# resets review progress back to note_generated, since the content changed.
SOAP_GENERATION_ALLOWED_FROM = {
    EncounterStatus.transcribed,
    EncounterStatus.note_generated,
    EncounterStatus.under_review,
}

# States from which a care plan may be (re)generated: any time a SOAP note exists.
CARE_PLAN_GENERATION_ALLOWED_FROM = {
    EncounterStatus.note_generated,
    EncounterStatus.under_review,
    EncounterStatus.finalized,
}

REVIEW_ALLOWED_FROM = {EncounterStatus.note_generated}
FINALIZE_ALLOWED_FROM = {EncounterStatus.under_review}
CODE_GENERATION_ALLOWED_FROM = {EncounterStatus.finalized}
CODE_DECISION_ALLOWED_FROM = {EncounterStatus.coded, EncounterStatus.billed}


def _require(encounter: Encounter, allowed: set[EncounterStatus], action: str) -> None:
    if encounter.status not in allowed:
        allowed_names = ", ".join(sorted(s.value for s in allowed))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot {action} while encounter is '{encounter.status.value}'. "
                f"Allowed from: {allowed_names}."
            ),
        )


def require_soap_generation_allowed(encounter: Encounter) -> None:
    _require(encounter, SOAP_GENERATION_ALLOWED_FROM, "generate a SOAP note")


def require_care_plan_generation_allowed(encounter: Encounter) -> None:
    _require(encounter, CARE_PLAN_GENERATION_ALLOWED_FROM, "generate a care plan")


def require_review_allowed(encounter: Encounter) -> None:
    _require(encounter, REVIEW_ALLOWED_FROM, "move the note into review")


def require_finalize_allowed(encounter: Encounter) -> None:
    _require(encounter, FINALIZE_ALLOWED_FROM, "finalize the note")


def require_code_generation_allowed(encounter: Encounter) -> None:
    _require(encounter, CODE_GENERATION_ALLOWED_FROM, "generate code suggestions")


def require_code_decision_allowed(encounter: Encounter) -> None:
    _require(encounter, CODE_DECISION_ALLOWED_FROM, "accept or reject a code suggestion")
