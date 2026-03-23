"""Add learning_objectives and ancillary_content to textbook_chunks.

Revision ID: 003
Revises: 001
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "ibrary"


def upgrade() -> None:
    op.add_column(
        "textbook_chunks",
        sa.Column("learning_objectives", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "textbook_chunks",
        sa.Column("ancillary_content", sa.Text(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("textbook_chunks", "ancillary_content", schema=SCHEMA)
    op.drop_column("textbook_chunks", "learning_objectives", schema=SCHEMA)
