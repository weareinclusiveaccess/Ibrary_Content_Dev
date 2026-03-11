"""Add textbook and curated content tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "textbooks",
        sa.Column("book_id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("edition", sa.String()),
        sa.Column("source_path", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "textbook_chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column(
            "book_id",
            sa.String(),
            sa.ForeignKey("textbooks.book_id"),
            nullable=False,
        ),
        sa.Column("chapter_num", sa.Integer()),
        sa.Column("section_num", sa.Integer()),
        sa.Column("subsection_num", sa.Integer()),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.execute(
        """
        CREATE TABLE textbook_chunk_embeddings (
            id SERIAL PRIMARY KEY,
            chunk_id VARCHAR REFERENCES textbook_chunks(chunk_id) NOT NULL,
            embedding vector(1536),
            model_version VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT now(),
            CONSTRAINT uq_chunk_model UNIQUE (chunk_id, model_version)
        )
        """
    )

    op.create_table(
        "textbook_images",
        sa.Column("image_id", sa.String(), primary_key=True),
        sa.Column(
            "chunk_id",
            sa.String(),
            sa.ForeignKey("textbook_chunks.chunk_id"),
        ),
        sa.Column("s3_url", sa.String()),
        sa.Column("caption", sa.Text()),
        sa.Column("alt_text", sa.Text()),
        sa.Column("page_num", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "curated_content",
        sa.Column("curriculum_unit_id", sa.String(), primary_key=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("class_name", sa.String(), nullable=False),
        sa.Column("theme", sa.String()),
        sa.Column("theme_number", sa.Integer()),
        sa.Column("topic_number", sa.Integer()),
        sa.Column("subtopic", sa.Text()),
        sa.Column("title", sa.String()),
        sa.Column("learning_objectives", sa.Text()),
        sa.Column("curated_content_md", sa.Text()),
        sa.Column("key_takeaways", sa.Text()),
        sa.Column("glossary_terms", sa.Text()),
        sa.Column("textbook_chunk_refs", sa.Text()),
        sa.Column("model_version", sa.String()),
        sa.Column("prompt_version", sa.String()),
        sa.Column("status", sa.String(), server_default="draft"),
        sa.Column("udl_score", sa.Float()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("curated_content")
    op.drop_table("textbook_images")
    op.drop_table("textbook_chunk_embeddings")
    op.drop_table("textbook_chunks")
    op.drop_table("textbooks")
