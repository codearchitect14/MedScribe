"""encrypt patient identifier fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Patient identifier columns move from plaintext varchar/date to
    # application-level Fernet-encrypted text (see app/core/encryption.py).
    # This is a destructive type change; any existing plaintext rows must be
    # re-encrypted by the caller before running this migration in an
    # environment that already has patient data (not a concern for the
    # sample/dev seed data used at this stage of the project).
    op.execute("TRUNCATE TABLE patients CASCADE")

    op.alter_column("patients", "external_reference", type_=sa.Text(), existing_nullable=True)
    op.alter_column("patients", "first_name", type_=sa.Text(), existing_nullable=False)
    op.alter_column("patients", "last_name", type_=sa.Text(), existing_nullable=False)
    op.alter_column(
        "patients",
        "date_of_birth",
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="date_of_birth::text",
    )
    op.alter_column("patients", "sex", type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.execute("TRUNCATE TABLE patients CASCADE")

    op.alter_column("patients", "sex", type_=sa.String(20), existing_nullable=True)
    op.alter_column(
        "patients",
        "date_of_birth",
        type_=sa.Date(),
        existing_nullable=True,
        postgresql_using="date_of_birth::date",
    )
    op.alter_column("patients", "last_name", type_=sa.String(150), existing_nullable=False)
    op.alter_column("patients", "first_name", type_=sa.String(150), existing_nullable=False)
    op.alter_column("patients", "external_reference", type_=sa.String(100), existing_nullable=True)
