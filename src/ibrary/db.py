"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ibrary.config import DATABASE_URL, POSTGRES_SCHEMA

# search_path so unqualified SQL hits ibrary.* first.
# Neon pooler rejects startup options — use the direct (non-pooler) host for migrations/loads.
_connect_args: dict = {}
if POSTGRES_SCHEMA and "-pooler" not in DATABASE_URL:
    _connect_args["options"] = f"-csearch_path={POSTGRES_SCHEMA},public"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Session:
    return SessionLocal()
