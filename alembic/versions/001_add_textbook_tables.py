"""Add ibrary schema, textbook tables, quality/UDL tables, and grants.

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

SCHEMA = "ibrary"


def upgrade() -> None:
    # Schema must exist before installing pgvector into it.
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.execute(
        f"""
        DO $body$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                EXECUTE format('CREATE EXTENSION vector SCHEMA %I', '{SCHEMA}');
            ELSIF EXISTS (
                SELECT 1
                FROM pg_extension e
                JOIN pg_namespace n ON n.oid = e.extnamespace
                WHERE e.extname = 'vector' AND n.nspname <> '{SCHEMA}'
            ) THEN
                EXECUTE format('ALTER EXTENSION vector SET SCHEMA %I', '{SCHEMA}');
            END IF;
        END
        $body$;
        """
    )

    op.create_table(
        "textbooks",
        sa.Column("book_id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("edition", sa.String()),
        sa.Column("source_path", sa.String()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("publisher", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("isbn", sa.String(), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("chapters", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        schema=SCHEMA,
    )

    op.create_table(
        "textbook_chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column(
            "book_id",
            sa.String(),
            sa.ForeignKey(f"{SCHEMA}.textbooks.book_id"),
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
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("chunk_length", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )

    op.execute(
        f"""
        CREATE TABLE {SCHEMA}.textbook_chunk_embeddings (
            id SERIAL PRIMARY KEY,
            chunk_id VARCHAR NOT NULL REFERENCES {SCHEMA}.textbook_chunks(chunk_id),
            embedding {SCHEMA}.vector(1536),
            model_version VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now(),
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
            sa.ForeignKey(f"{SCHEMA}.textbook_chunks.chunk_id"),
        ),
        sa.Column("s3_url", sa.String()),
        sa.Column("caption", sa.Text()),
        sa.Column("alt_text", sa.Text()),
        sa.Column("page_num", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        schema=SCHEMA,
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
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "content_manual_quality_check",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "curriculum_unit_id",
            sa.String(),
            sa.ForeignKey(f"{SCHEMA}.curated_content.curriculum_unit_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "content_udl_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "curriculum_unit_id",
            sa.String(),
            sa.ForeignKey(f"{SCHEMA}.curated_content.curriculum_unit_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column("judge_model_version", sa.String(), nullable=False),
        sa.Column("judge_prompt_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("curriculum_unit_id", name="uq_content_udl_scores_unit"),
        schema=SCHEMA,
    )

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'der') THEN
                CREATE ROLE der WITH LOGIN PASSWORD 'der_ibrary_dev';
            END IF;
        END
        $$;
        GRANT USAGE ON SCHEMA {SCHEMA} TO der;
        GRANT CREATE ON SCHEMA {SCHEMA} TO der;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {SCHEMA} TO der;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {SCHEMA} TO der;
        ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} GRANT ALL ON TABLES TO der;
        ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} GRANT ALL ON SEQUENCES TO der;
        """
    )


def downgrade() -> None:
    # CASCADE removes embedding columns/tables that use the type, then drop the rest of the schema.
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
