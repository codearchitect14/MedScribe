"""add reimbursement_rates and analytics_rollups (Phase 7)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reimbursement_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        # Reuses the "code_type" enum created by migration 0001 for code_suggestions.code_type.
        sa.Column(
            "code_type",
            postgresql.ENUM("icd10", "hcpcs", name="code_type", create_type=False),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("rate", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_reimbursement_rates_organization_id", "reimbursement_rates", ["organization_id"])
    op.create_index("ix_reimbursement_rates_code", "reimbursement_rates", ["code"])
    op.create_index(
        "ix_reimbursement_rates_org_code_unique",
        "reimbursement_rates",
        ["organization_id", "code_type", "code"],
        unique=True,
    )

    op.create_table(
        "analytics_rollups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "rollup_type",
            sa.Enum(
                "encounter_volume",
                "coding_mix",
                "estimated_reimbursement",
                "turnaround_time",
                "llm_usage",
                "clinician_productivity",
                name="rollup_type",
            ),
            nullable=False,
        ),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_analytics_rollups_organization_id", "analytics_rollups", ["organization_id"])
    op.create_index("ix_analytics_rollups_rollup_type", "analytics_rollups", ["rollup_type"])
    op.create_index("ix_analytics_rollups_period", "analytics_rollups", ["period"])
    op.create_index(
        "ix_analytics_rollups_org_type_period_unique",
        "analytics_rollups",
        ["organization_id", "rollup_type", "period"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("analytics_rollups")
    op.execute("DROP TYPE IF EXISTS rollup_type")
    op.drop_table("reimbursement_rates")
