"""Add chunk_relevance table for filter_relevance step.

Revision ID: 006
Revises: 005
Create Date: 2026-05-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "ibrary"


def upgrade() -> None:
    op.create_table(
        "chunk_relevance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("curriculum_unit_id", sa.String(), nullable=False),
        sa.Column("chunk_id", sa.String(), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("embedding_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            [f"{SCHEMA}.textbook_chunks.chunk_id"],
        ),
        sa.UniqueConstraint(
            "curriculum_unit_id",
            "chunk_id",
            name="uq_unit_chunk_relevance",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_chunk_relevance_unit",
        "chunk_relevance",
        ["curriculum_unit_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_relevance_unit", table_name="chunk_relevance", schema=SCHEMA)
    op.drop_table("chunk_relevance", schema=SCHEMA)
