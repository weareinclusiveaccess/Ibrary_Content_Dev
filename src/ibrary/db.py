"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ibrary.config import DATABASE_URL, POSTGRES_SCHEMA

# search_path so unqualified SQL (embedder, aligner, curation) hits ibrary.* first
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"options": f"-csearch_path={POSTGRES_SCHEMA},public"},
)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()
