import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.query import paginate
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.schemas.pagination import Page, PageParams, pagination_params
from app.schemas.patient import CreatePatientRequest, PatientOut

router = APIRouter(prefix="/patients", tags=["patients"])

CAN_CREATE_PATIENTS = (UserRole.clinician, UserRole.admin, UserRole.super_admin)


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: CreatePatientRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Patient:
    if current_user.role not in CAN_CREATE_PATIENTS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to create patients")

    patient = Patient(
        organization_id=current_user.organization_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
        external_reference=payload.external_reference,
    )
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return patient


@router.get("", response_model=Page[PatientOut])
async def list_patients(
    page_params: PageParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Page[PatientOut]:
    # Patient names are encrypted at rest (app/core/encryption.py) and are
    # therefore not searchable or sortable at the SQL level; only creation
    # order is offered here. Name-based search needs a separate searchable
    # index if/when that becomes a requirement.
    stmt = (
        select(Patient)
        .where(Patient.organization_id == current_user.organization_id)
        .order_by(Patient.created_at.desc())
    )
    items, total = await paginate(session, stmt, page_params)
    return Page[PatientOut](
        items=[PatientOut.model_validate(p) for p in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient
