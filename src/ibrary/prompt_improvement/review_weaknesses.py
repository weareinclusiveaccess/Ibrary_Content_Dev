"""Normalize review evidence for weakness summarization."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from ibrary.llm.client import chat_completion_json
from ibrary.prompt_improvement.review_weakness_prompts import (
    CONTENT_SUMMARY_SYSTEM_PROMPT,
    ROLLUP_SYSTEM_PROMPT,
    build_content_summary_user_prompt,
    build_rollup_user_prompt,
)

ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_PATH = Path(
    "data/docs/extracted_source_content/biology/review_weakness_summaries.json"
)

_SUBSTANTIVE_KINDS = {None, "rubric", "rejection"}
_UTC_MIN = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
_REDACTED = "[REDACTED]"
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_IDENTITY_KEYS = {
    "checked_by",
    "email",
    "reviewer",
    "reviewer_email",
    "reviewer_id",
    "user_id",
}

_NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
_VALIDATION_ATTEMPTS = 3
_VALIDATION_RETRY_BACKOFF = 2


class Weakness(BaseModel):
    """One evidence-grounded weakness in a curriculum unit."""

    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "correctness",
        "clarity",
        "pedagogy",
        "udl_accessibility",
        "engagement",
        "structure",
        "other",
    ]
    summary: _NonEmptyString
    severity: Literal["low", "medium", "high"]
    occurrence_count: int = Field(ge=1, strict=True)
    evidence_source_ids: list[_NonEmptyString] = Field(min_length=1)
    prompt_instruction_suggestion: _NonEmptyString


class ContentWeaknessSummary(BaseModel):
    """Validated model response for one curriculum unit."""

    model_config = ConfigDict(extra="forbid")

    weaknesses: list[Weakness] = Field(default_factory=list)


class RecurringWeakness(BaseModel):
    """One evidence-grounded weakness recurring across units."""

    model_config = ConfigDict(extra="forbid")

    theme: _NonEmptyString
    priority: Literal["low", "medium", "high"]
    affected_unit_ids: list[_NonEmptyString] = Field(min_length=1)
    occurrence_count: int = Field(ge=1, strict=True)
    evidence_source_ids: list[_NonEmptyString] = Field(min_length=1)
    recommended_instruction: _NonEmptyString


class WeaknessRollup(BaseModel):
    """Validated cross-unit weakness rollup."""

    model_config = ConfigDict(extra="forbid")

    recurring_weaknesses: list[RecurringWeakness] = Field(default_factory=list)
    instruction_themes: list[str] = Field(default_factory=list)
    excluded_failed_units: list[str] = Field(default_factory=list)


def _as_utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _iso_utc(value: dt.datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None


def _scores(row: Any) -> dict[str, Any]:
    scores = getattr(row, "scores", None)
    return scores if isinstance(scores, dict) else {}


def _kind(row: Any) -> str | None:
    kind = _scores(row).get("kind")
    return kind if isinstance(kind, str) else None


def _has_malformed_kind(row: Any) -> bool:
    scores = _scores(row)
    return "kind" in scores and scores["kind"] is not None and not isinstance(scores["kind"], str)


def _contains_substantive_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_contains_substantive_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_substantive_value(item) for item in value)
    return True


def _is_identity_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    return normalized in _IDENTITY_KEYS or "reviewer" in normalized or "email" in normalized


def _is_forbidden_value(value: Any, forbidden_values: frozenset[str]) -> bool:
    return isinstance(value, str) and value.strip().casefold() in forbidden_values


def _redact_human_text(value: str, identities: frozenset[str]) -> str:
    redacted = value
    for identity in sorted(identities, key=len, reverse=True):
        redacted = re.sub(re.escape(identity), _REDACTED, redacted, flags=re.IGNORECASE)
    return _EMAIL_PATTERN.sub(_REDACTED, redacted)


def _sanitize_human_mapping(
    value: Mapping[Any, Any],
    forbidden_values: frozenset[str],
) -> dict[Any, Any]:
    entries: list[tuple[tuple[bool, str, str, str], Any, Any]] = []
    for key, item in value.items():
        sensitive = False
        sanitized_key = key
        if isinstance(key, str):
            redacted_key = _redact_human_text(key, forbidden_values)
            sensitive = redacted_key != key or _is_identity_key(key)
            if sensitive:
                sanitized_key = _REDACTED
        sort_key = (
            sensitive,
            str(key).casefold(),
            type(key).__name__,
            repr(key),
        )
        entries.append((sort_key, sanitized_key, item))

    result: dict[Any, Any] = {}
    for _sort_key, base_key, item in sorted(entries, key=lambda entry: entry[0]):
        output_key = base_key
        suffix = 2
        while output_key in result:
            output_key = f"{base_key}#{suffix}"
            suffix += 1
        result[output_key] = (
            _REDACTED
            if _sort_key[0]
            else _sanitize(
                item,
                forbidden_values,
                redact_human_text=True,
            )
        )
    return result


def _sanitize(
    value: Any,
    forbidden_values: frozenset[str] = frozenset(),
    *,
    redact_human_text: bool = False,
) -> Any:
    if isinstance(value, Mapping):
        if redact_human_text:
            return _sanitize_human_mapping(value, forbidden_values)
        return {
            key: _sanitize(item, forbidden_values)
            for key, item in value.items()
            if key != "kind"
            and not _is_identity_key(key)
            and not _is_forbidden_value(item, forbidden_values)
        }
    if isinstance(value, (list, tuple)):
        return [
            _sanitize(
                item,
                forbidden_values,
                redact_human_text=redact_human_text,
            )
            for item in value
            if redact_human_text or not _is_forbidden_value(item, forbidden_values)
        ]
    if isinstance(value, str) and redact_human_text:
        return _redact_human_text(value, forbidden_values)
    if _is_forbidden_value(value, forbidden_values):
        return None
    return value


def _reviewer_identity(row: Any) -> str | None:
    checked_by = getattr(row, "checked_by", None)
    if not isinstance(checked_by, str):
        return checked_by
    return checked_by.strip() or None


def _is_substantive(row: Any) -> bool:
    if _has_malformed_kind(row) or _kind(row) not in _SUBSTANTIVE_KINDS:
        return False
    notes = getattr(row, "notes", None)
    identity = _reviewer_identity(row)
    forbidden_values = (
        frozenset({identity.casefold()}) if isinstance(identity, str) else frozenset()
    )
    score_payload = _sanitize(_scores(row), forbidden_values)
    return (
        _contains_substantive_value(notes)
        or getattr(row, "overall_score", None) is not None
        or _contains_substantive_value(score_payload)
    )


def _selection_key(row: Any) -> tuple[dt.datetime, dt.datetime, Any]:
    created_at = _as_utc(getattr(row, "created_at", None)) or _UTC_MIN
    effective_recency = _as_utc(getattr(row, "updated_at", None)) or created_at
    return effective_recency, created_at, getattr(row, "id", 0)


def _output_order_key(row: Any) -> tuple[dt.datetime, dt.datetime, Any]:
    return _selection_key(row)


def select_latest_substantive_reviews(rows: Iterable[Any]) -> list[Any]:
    """Select the latest substantive row per known reviewer.

    Anonymous rows remain distinct because their authors cannot be correlated.
    """

    latest_by_reviewer: dict[str, Any] = {}
    anonymous: list[Any] = []

    for row in rows:
        if not _is_substantive(row):
            continue

        identity = _reviewer_identity(row)
        if not identity:
            anonymous.append(row)
            continue

        current = latest_by_reviewer.get(identity)
        if current is None or _selection_key(row) > _selection_key(current):
            latest_by_reviewer[identity] = row

    return sorted([*latest_by_reviewer.values(), *anonymous], key=_output_order_key)


def _human_evidence(row: Any) -> dict[str, Any]:
    identity = _reviewer_identity(row)
    forbidden_values = (
        frozenset({identity.casefold()}) if isinstance(identity, str) else frozenset()
    )
    return {
        "source_id": f"human:{row.id}",
        "kind": _kind(row) or "note",
        "timestamp": _iso_utc(getattr(row, "updated_at", None) or getattr(row, "created_at", None)),
        "overall_score": getattr(row, "overall_score", None),
        "scores": _sanitize(
            _scores(row),
            forbidden_values,
            redact_human_text=True,
        ),
        "note": _redact_human_text(
            str(getattr(row, "notes", None) or "").strip(),
            forbidden_values,
        ),
    }


def _safe_list(value: Any) -> list[Any]:
    return _sanitize(value) if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _judge_evidence(row: Any) -> dict[str, Any]:
    scores = _scores(row)
    passed = scores.get("passed")
    return {
        "source_id": f"judge:{row.id}",
        "kind": "udl_judge",
        "timestamp": _iso_utc(getattr(row, "updated_at", None) or getattr(row, "created_at", None)),
        "overall_score": getattr(row, "overall_score", None),
        "passed": passed if isinstance(passed, bool) else None,
        "recommendations": _safe_list(scores.get("recommendations")),
        "correctness_notes": _safe_text(scores.get("correctness_notes")),
        "clarity_notes": _safe_text(scores.get("clarity_notes")),
        "checkpoint_scores": _safe_list(scores.get("checkpoint_scores")),
        "judge_prompt_version": getattr(row, "judge_prompt_version", None),
        "judge_model_version": getattr(row, "judge_model_version", None),
    }


def build_unit_evidence(
    curated: Any,
    human_rows: Iterable[Any],
    judge_row: Any | None,
) -> dict[str, Any]:
    """Build model context and normalized, identity-free review evidence."""

    evidence = [_human_evidence(row) for row in select_latest_substantive_reviews(human_rows)]
    if judge_row is not None:
        evidence.append(_judge_evidence(judge_row))

    return {
        "curriculum_unit_id": curated.curriculum_unit_id,
        "title": curated.title or "",
        "subtopic": curated.subtopic or "",
        "curation_prompt_version": curated.prompt_version or "",
        "curated_content": curated.curated_content_md or "",
        "evidence": evidence,
    }


def compute_source_hash(payload: dict[str, Any]) -> str:
    """Hash a payload using canonical, Unicode-preserving JSON."""

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _retry_validated(call, validate):
    """Call the model up to three times, backing off after invalid output."""

    last_error: Exception | None = None
    for attempt in range(1, _VALIDATION_ATTEMPTS + 1):
        try:
            return validate(call())
        except (ValidationError, ValueError) as exc:
            last_error = exc
            if attempt < _VALIDATION_ATTEMPTS:
                time.sleep(_VALIDATION_RETRY_BACKOFF**attempt)
    assert last_error is not None
    raise last_error


def _reject_unknown(referenced: set[str], known: set[str], label: str) -> None:
    unknown = sorted(referenced - known)
    if unknown:
        raise ValueError(f"unknown {label}(s): {', '.join(unknown)}")


def summarize_unit(payload: dict[str, Any], *, model: str) -> ContentWeaknessSummary:
    """Summarize one unit's review evidence into grounded weaknesses."""

    known_sources = {item["source_id"] for item in payload["evidence"]}

    def validate(raw: dict[str, Any]) -> ContentWeaknessSummary:
        result = ContentWeaknessSummary.model_validate(raw)
        referenced = {
            source_id
            for weakness in result.weaknesses
            for source_id in weakness.evidence_source_ids
        }
        _reject_unknown(referenced, known_sources, "evidence source")
        return result

    return _retry_validated(
        lambda: chat_completion_json(
            component="review_weakness_content",
            model=model,
            system=CONTENT_SUMMARY_SYSTEM_PROMPT,
            user=build_content_summary_user_prompt(payload),
            metadata={
                "curriculum_unit_id": payload["curriculum_unit_id"],
                "title": payload["title"],
                "subtopic": payload["subtopic"],
                "curation_prompt_version": payload["curation_prompt_version"],
            },
        ),
        validate,
    )


def summarize_rollup(
    summaries: list[dict[str, Any]],
    failed_unit_ids: list[str],
    *,
    model: str,
) -> WeaknessRollup:
    """Roll successful unit summaries into recurring, grounded weaknesses."""

    known_units = {summary["curriculum_unit_id"] for summary in summaries}
    known_sources = {
        source_id
        for summary in summaries
        for weakness in summary.get("weaknesses", [])
        for source_id in weakness.get("evidence_source_ids", [])
    }

    def validate(raw: dict[str, Any]) -> WeaknessRollup:
        result = WeaknessRollup.model_validate(raw)
        if result.excluded_failed_units != failed_unit_ids:
            raise ValueError("rollup changed excluded_failed_units")
        for item in result.recurring_weaknesses:
            _reject_unknown(set(item.affected_unit_ids), known_units, "affected unit")
            _reject_unknown(set(item.evidence_source_ids), known_sources, "evidence source")
        return result

    return _retry_validated(
        lambda: chat_completion_json(
            component="review_weakness_rollup",
            model=model,
            system=ROLLUP_SYSTEM_PROMPT,
            user=build_rollup_user_prompt(summaries, failed_unit_ids),
            metadata={"unit_count": len(summaries)},
        ),
        validate,
    )
