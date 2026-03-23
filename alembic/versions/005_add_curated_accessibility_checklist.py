"""Add accessibility_checklist to curated_content.

Revision ID: 005
Revises: 004
Create Date: 2026-03-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "ibrary"


def upgrade() -> None:
    op.add_column(
        "curated_content",
        sa.Column("accessibility_checklist", sa.Text(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("curated_content", "accessibility_checklist", schema=SCHEMA)
