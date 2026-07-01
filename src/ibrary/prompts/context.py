"""Resolve ``{subject}`` and related placeholders for all pipeline prompts."""

from __future__ import annotations

from ibrary.config import EDUCATION_SYSTEM_LABEL, PIPELINE_SUBJECT


def resolve_subject(subject: str | None = None) -> str:
    """Display subject for prompts; falls back to ``PIPELINE_SUBJECT`` env."""
    return (subject or "").strip() or PIPELINE_SUBJECT


def prompt_context(subject: str | None = None) -> dict[str, str]:
    """Keyword args for ``str.format`` on prompt templates."""
    s = resolve_subject(subject)
    return {
        "subject": s,
        "subject_lower": s.lower(),
        "education_system": EDUCATION_SYSTEM_LABEL,
    }


def format_prompt(template: str, subject: str | None = None, **kwargs: str) -> str:
    """Format a prompt template with subject context plus extra fields."""
    ctx = prompt_context(subject)
    ctx.update(kwargs)
    return template.format(**ctx)
