"""SQLAlchemy ORM models for textbook storage and pipeline state."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
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


class Base(DeclarativeBase):
    pass


class Textbook(Base):
    __tablename__ = "textbooks"

    book_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    edition = Column(String)
    source_path = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    chunks = relationship("TextbookChunk", back_populates="textbook", cascade="all, delete-orphan")


class TextbookChunk(Base):
    __tablename__ = "textbook_chunks"

    chunk_id = Column(String, primary_key=True)
    book_id = Column(String, ForeignKey("textbooks.book_id"), nullable=False)
    chapter_num = Column(Integer)
    section_num = Column(Integer)
    subsection_num = Column(Integer)
    title = Column(String, nullable=False)
    summary = Column(Text)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64))
    page_start = Column(Integer)
    page_end = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    textbook = relationship("Textbook", back_populates="chunks")
    embedding_row = relationship(
        "TextbookChunkEmbedding",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TextbookChunkEmbedding(Base):
    __tablename__ = "textbook_chunk_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(
        String, ForeignKey("textbook_chunks.chunk_id"), nullable=False, unique=True
    )
    embedding = Column(Vector(1536))
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    chunk = relationship("TextbookChunk", back_populates="embedding_row")

    __table_args__ = (
        UniqueConstraint("chunk_id", "model_version", name="uq_chunk_model"),
    )


class TextbookImage(Base):
    __tablename__ = "textbook_images"

    image_id = Column(String, primary_key=True)
    chunk_id = Column(String, ForeignKey("textbook_chunks.chunk_id"))
    s3_url = Column(String)
    caption = Column(Text)
    alt_text = Column(Text)
    page_num = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class CuratedContent(Base):
    """Draft / reviewed / approved curated content stored in PostgreSQL.

    Only items with status='published' are also written to DynamoDB.
    """

    __tablename__ = "curated_content"

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
    textbook_chunk_refs = Column(Text)
    model_version = Column(String)
    prompt_version = Column(String)
    status = Column(String, default="draft")
    udl_score = Column(Float)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
