"""Database engine for the review portal (Neon or local)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ibrary.config import DATABASE_URL_REVIEW, POSTGRES_SCHEMA

_connect_args: dict = {}
if POSTGRES_SCHEMA and "-pooler" not in DATABASE_URL_REVIEW:
    _connect_args["options"] = f"-csearch_path={POSTGRES_SCHEMA},public"

review_engine = create_engine(
    DATABASE_URL_REVIEW,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
ReviewSessionLocal = sessionmaker(bind=review_engine, class_=Session, expire_on_commit=False)


def get_review_session() -> Session:
    return ReviewSessionLocal()
