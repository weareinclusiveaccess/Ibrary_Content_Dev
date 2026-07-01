#!/usr/bin/env python3
"""Refine curriculum_validated.json — assign POs and activities per subtopic via LLM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger("refine_curriculum")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "docs" / "extracted_source_content" / "biology"
STRUCTURED_JSON = DATA_DIR / "biology_curriculum_structured.json"
VALIDATED_JSON = DATA_DIR / "curriculum_validated.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Assign performance_objectives, teachers_activities, and student_activities "
            "to the correct subtopic using an LLM (fixes topic-level copy bug)."
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=VALIDATED_JSON,
        help="curriculum_validated.json path (default: biology output dir)",
    )
    parser.add_argument(
        "--structured",
        type=Path,
        default=STRUCTURED_JSON,
        help="Re-run validate from structured JSON if --input missing",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DATA_DIR,
        help="Directory for curriculum_validated.json and refinement report",
    )
    parser.add_argument(
        "--topic",
        type=int,
        action="append",
        dest="topics",
        metavar="N",
        help="Only refine topic_number N (repeatable). Default: all topics in file.",
    )
    parser.add_argument(
        "--theme",
        type=int,
        default=1,
        help="theme_number when using --topic (default: 1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print one topic refinement sample without saving",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip topics already in curriculum_refinement_report.json (use after a failed run).",
    )
    args = parser.parse_args()

    from ibrary.curriculum.refiner import (
        refine_topic_units,
        refine_validated_curriculum,
        save_refinement_outputs,
    )
    from ibrary.curriculum.validator import load_validated, save_validated, validate_curriculum

    if args.input.is_file():
        validated = load_validated(args.input)
        logger.info("loaded_validated", path=str(args.input), units=len(validated.units))
    elif args.structured.is_file():
        logger.info("validating_from_structured", path=str(args.structured))
        validated = validate_curriculum(args.structured)
    else:
        parser.error(f"Neither --input ({args.input}) nor --structured ({args.structured}) found")

    topic_keys = None
    if args.topics:
        topic_keys = [(args.theme, t) for t in args.topics]

    if args.dry_run:
        from ibrary.curriculum.refiner import group_units_by_topic

        groups = group_units_by_topic(validated.units)
        key = topic_keys[0] if topic_keys else sorted(groups.keys())[0]
        units = groups[key]
        result = refine_topic_units(units)
        print(result.model_dump_json(indent=2))
        return

    refined, report = refine_validated_curriculum(
        validated,
        topic_keys=topic_keys,
        output_dir=args.output_dir,
        resume=args.resume,
    )
    save_refinement_outputs(refined, report, args.output_dir)
    logger.info(
        "refine_complete",
        topics=report.topics_refined,
        units=report.units_updated,
    )


if __name__ == "__main__":
    main()
