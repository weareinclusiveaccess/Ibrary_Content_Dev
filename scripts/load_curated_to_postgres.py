#!/usr/bin/env python3
"""Bulk-load curated modules and UDL judge results from JSON into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ibrary.config import PROJECT_ROOT
from ibrary.curation.curated_postgres import upsert_curated_payloads
from ibrary.curation.curation_service import load_curated_json_array
from ibrary.judging.judge_postgres import upsert_judge_result
from ibrary.judging.schemas import SubtopicJudgeResult


def _default_curated_path() -> Path:
    return (
        PROJECT_ROOT
        / "data"
        / "docs"
        / "extracted_source_content"
        / "biology"
        / "curated_content.json"
    )


def _default_judgments_path() -> Path:
    return (
        PROJECT_ROOT
        / "data"
        / "docs"
        / "extracted_source_content"
        / "biology"
        / "udl_subtopic_evaluation.json"
    )


def _load_judgments(path: Path) -> list[SubtopicJudgeResult]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must be a JSON array")
    return [SubtopicJudgeResult.model_validate(item) for item in raw]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--curated",
        type=Path,
        default=_default_curated_path(),
        help="Path to curated_content.json",
    )
    parser.add_argument(
        "--judgments",
        type=Path,
        default=_default_judgments_path(),
        help="Path to udl_subtopic_evaluation.json",
    )
    parser.add_argument("--curated-only", action="store_true", help="Skip judge file")
    parser.add_argument("--judgments-only", action="store_true", help="Skip curated file")
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write")
    args = parser.parse_args()

    curated_count = 0
    judge_count = 0

    if not args.judgments_only:
        if not args.curated.is_file():
            print(f"Curated file not found: {args.curated}", file=sys.stderr)
            return 1
        payloads = load_curated_json_array(args.curated)
        curated_count = len(payloads)
        if args.dry_run:
            print(f"[dry-run] Would upsert {curated_count} curated module(s)")
        else:
            upsert_curated_payloads(payloads)
            print(f"Upserted {curated_count} curated module(s) to Postgres")

    if not args.curated_only:
        if not args.judgments.is_file():
            print(f"Judgments file not found: {args.judgments}", file=sys.stderr)
            return 1
        results = _load_judgments(args.judgments)
        judge_count = len(results)
        if args.dry_run:
            print(f"[dry-run] Would upsert {judge_count} judge result(s)")
        else:
            for result in results:
                upsert_judge_result(result)
            print(f"Upserted {judge_count} judge result(s) to Postgres")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
