"""Add student_activities and teacher_activities to curated_content.

Revision ID: 004
Revises: 003
Create Date: 2026-03-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "ibrary"


def upgrade() -> None:
    op.add_column(
        "curated_content",
        sa.Column("student_activities", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "curated_content",
        sa.Column("teacher_activities", sa.Text(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("curated_content", "teacher_activities", schema=SCHEMA)
    op.drop_column("curated_content", "student_activities", schema=SCHEMA)
