"""SQLAlchemy ORM models for textbook storage and pipeline state."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from ibrary.config import POSTGRES_SCHEMA


class Base(DeclarativeBase):
    pass


_SCHEMA = {"schema": POSTGRES_SCHEMA}


class Textbook(Base):
    __tablename__ = "textbooks"
    __table_args__ = _SCHEMA

    book_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    edition = Column(String)
    source_path = Column(String)
    subject = Column(String, nullable=True)
    author = Column(String, nullable=True)
    publisher = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    isbn = Column(String, nullable=True)
    pages = Column(Integer, nullable=True)
    chapters = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    chunks = relationship("TextbookChunk", back_populates="textbook", cascade="all, delete-orphan")


class TextbookChunk(Base):
    __tablename__ = "textbook_chunks"
    __table_args__ = _SCHEMA

    chunk_id = Column(String, primary_key=True)
    book_id = Column(String, ForeignKey(f"{POSTGRES_SCHEMA}.textbooks.book_id"), nullable=False)
    chapter_num = Column(Integer)
    section_num = Column(Integer)
    subsection_num = Column(Integer)
    title = Column(String, nullable=False)
    summary = Column(Text)
    learning_objectives = Column(Text)
    ancillary_content = Column(Text)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64))
    page_start = Column(Integer)
    page_end = Column(Integer)
    chunk_length = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    textbook = relationship("Textbook", back_populates="chunks")
    embeddings = relationship(
        "TextbookChunkEmbedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )


class TextbookChunkEmbedding(Base):
    __tablename__ = "textbook_chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", "model_version", name="uq_chunk_model"),
        _SCHEMA,
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(
        String,
        ForeignKey(f"{POSTGRES_SCHEMA}.textbook_chunks.chunk_id"),
        nullable=False,
    )
    embedding = Column(Vector(1536))
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    chunk = relationship("TextbookChunk", back_populates="embeddings")


class TextbookImage(Base):
    __tablename__ = "textbook_images"
    __table_args__ = _SCHEMA

    image_id = Column(String, primary_key=True)
    chunk_id = Column(String, ForeignKey(f"{POSTGRES_SCHEMA}.textbook_chunks.chunk_id"))
    s3_url = Column(String)
    caption = Column(Text)
    alt_text = Column(Text)
    page_num = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class ChunkRelevance(Base):
    """Per (unit, chunk) relevance from filter_relevance agent."""

    __tablename__ = "chunk_relevance"
    __table_args__ = (
        UniqueConstraint("curriculum_unit_id", "chunk_id", name="uq_unit_chunk_relevance"),
        _SCHEMA,
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    curriculum_unit_id = Column(String, nullable=False, index=True)
    chunk_id = Column(
        String,
        ForeignKey(f"{POSTGRES_SCHEMA}.textbook_chunks.chunk_id"),
        nullable=False,
    )
    relevant = Column(Boolean, nullable=False)
    excerpt = Column(Text, nullable=True)
    embedding_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    rationale = Column(Text, nullable=True)
    agent_version = Column(String, nullable=True)
    content_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class CuratedContent(Base):
    """Curated modules stored in PostgreSQL (upserted when the curation step saves JSON).

    Default status is ``draft``. DynamoDB publish runs only for human-verified rows
    (``published`` or ``verified``). UDL scores live in ``ContentUdlScore``; manual QC
    in ``ContentManualQualityCheck``.
    """

    __tablename__ = "curated_content"
    __table_args__ = _SCHEMA

    curriculum_unit_id = Column(String, primary_key=True)
    subject = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    theme = Column(String)
    theme_number = Column(Integer)
    topic_number = Column(Integer)
    subtopic = Column(Text)
    title = Column(String)
    learning_objectives = Column(Text)
    curated_content_md = Column(Text)
    key_takeaways = Column(Text)
    glossary_terms = Column(Text)
    student_activities = Column(Text)
    teacher_activities = Column(Text)
    accessibility_checklist = Column(Text)
    textbook_chunk_refs = Column(Text)
    model_version = Column(String)
    prompt_version = Column(String)
    status = Column(String, default="draft")
    images = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    manual_quality_checks = relationship(
        "ContentManualQualityCheck",
        back_populates="curated_content",
        cascade="all, delete-orphan",
    )
    udl_score_row = relationship(
        "ContentUdlScore",
        back_populates="curated_content",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ContentManualQualityCheck(Base):
    """Human manual quality review: overall score, per-dimension scores (JSON), notes."""

    __tablename__ = "content_manual_quality_check"
    __table_args__ = _SCHEMA

    id = Column(Integer, primary_key=True, autoincrement=True)
    curriculum_unit_id = Column(
        String,
        ForeignKey(f"{POSTGRES_SCHEMA}.curated_content.curriculum_unit_id", ondelete="CASCADE"),
        nullable=False,
    )
    overall_score = Column(Float, nullable=True)
    scores = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    checked_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    curated_content = relationship("CuratedContent", back_populates="manual_quality_checks")


class ContentUdlScore(Base):
    """Automated UDL judge output per curriculum unit (one row per unit)."""

    __tablename__ = "content_udl_scores"
    __table_args__ = (
        UniqueConstraint("curriculum_unit_id", name="uq_content_udl_scores_unit"),
        _SCHEMA,
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    curriculum_unit_id = Column(
        String,
        ForeignKey(f"{POSTGRES_SCHEMA}.curated_content.curriculum_unit_id", ondelete="CASCADE"),
        nullable=False,
    )
    overall_score = Column(Float, nullable=True)
    scores = Column(JSON, nullable=True)
    judge_model_version = Column(String, nullable=False)
    judge_prompt_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    curated_content = relationship("CuratedContent", back_populates="udl_score_row")
