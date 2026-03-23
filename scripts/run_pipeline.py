#!/usr/bin/env python3
"""IBrary biology content pipeline — run setup steps, curation, or any subset.

By default runs **setup only** (extract → validate → align): PDF + DB + embeddings +
curriculum↔textbook alignment. Curation and later steps depend on LLM prompts/models
and are opt-in via ``--full`` or ``--steps``.

Usage examples:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --steps extract
    python scripts/run_pipeline.py --steps extract,validate,align
    python scripts/run_pipeline.py --full
    python scripts/run_pipeline.py --full --resume-from curate
    python scripts/run_pipeline.py --resume-from validate
    python scripts/run_pipeline.py --full --skip-judge
    python scripts/run_pipeline.py --steps curate --curate-topic 1
    python scripts/run_pipeline.py --steps curate --curate-theme 1 --curate-topic 1
    python scripts/run_pipeline.py --steps curate --curate-unit bio_sss1_theme1_topic1_content0
"""

from __future__ import annotations

import argparse
import json
import os
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

logger = structlog.get_logger("pipeline")

# Default ``python scripts/run_pipeline.py``: ingest + validate + align (no LLM curation).
SETUP_STEPS = ["extract", "validate", "align"]
EXTENSION_STEPS = ["curate", "judge", "publish"]
ALL_STEPS = SETUP_STEPS + EXTENSION_STEPS

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "docs" / "extracted_source_content" / "biology"
OUTPUT_DIR = DATA_DIR
TEXTBOOK_PDF = Path(os.environ.get("TEXTBOOK_PDF", "")) if os.environ.get("TEXTBOOK_PDF") else (DATA_DIR / "Biology2e-WEB.pdf")
CURRICULUM_JSON = DATA_DIR / "biology_curriculum_structured.json"


def _parse_steps_list(spec: str) -> list[str]:
    """Parse comma-separated step names; order follows ALL_STEPS."""
    raw = [p.strip().lower() for p in spec.split(",") if p.strip()]
    if not raw:
        raise ValueError("empty --steps")
    unknown = [p for p in raw if p not in ALL_STEPS]
    if unknown:
        raise ValueError(f"unknown step(s): {unknown}; valid: {ALL_STEPS}")
    order = {name: i for i, name in enumerate(ALL_STEPS)}
    return sorted(set(raw), key=lambda s: order[s])


def _resolve_selected_steps(args: argparse.Namespace) -> list[str]:
    if args.steps is not None:
        return _parse_steps_list(args.steps)
    if args.full:
        return list(ALL_STEPS)
    return list(SETUP_STEPS)


def step_extract():
    from ibrary.config import S3_BUCKET
    from ibrary.textbook.openstax_biology2e import (
        extract_openstax_biology_2e,
        write_textbook_image_manifest,
    )
    from ibrary.textbook.loader import (
        save_images_locally,
        save_images_to_s3,
        upsert_chunks,
        upsert_textbook,
    )

    logger.info("step_extract", pdf=str(TEXTBOOK_PDF))
    upsert_textbook(
        book_id="bio2e",
        title="Biology 2e (OpenStax)",
        edition="2e",
        source_path=str(TEXTBOOK_PDF),
        subject="biology",
    )

    chunks, images = extract_openstax_biology_2e(TEXTBOOK_PDF, book_id="bio2e")
    upserted = upsert_chunks(chunks)
    logger.info("chunks_loaded", total=len(chunks), upserted=upserted)

    if images:
        try:
            save_images_to_s3(images, S3_BUCKET)
            write_textbook_image_manifest(
                images, OUTPUT_DIR / "textbook_image_manifest.json", s3_bucket=S3_BUCKET
            )
        except Exception:
            logger.warning("s3_unavailable_saving_locally")
            save_images_locally(images, OUTPUT_DIR / "textbook_images")
            write_textbook_image_manifest(images, OUTPUT_DIR / "textbook_image_manifest.json")

    return chunks


def step_validate():
    from ibrary.curriculum.validator import save_validated, validate_curriculum

    logger.info("step_validate", json=str(CURRICULUM_JSON))
    result = validate_curriculum(CURRICULUM_JSON)
    save_validated(result, OUTPUT_DIR)
    return result


def step_align(validated):
    from ibrary.alignment.aligner import align_all, save_alignment
    from ibrary.alignment.embedder import embed_textbook_chunks

    logger.info("step_align")
    embedded = embed_textbook_chunks()
    logger.info("embedding_done", new_embeddings=embedded)

    alignment = align_all(validated.units)
    save_alignment(alignment, OUTPUT_DIR)
    return alignment


def step_curate(
    validated,
    alignment,
    *,
    curate_theme: int | None = None,
    curate_topic: int | None = None,
    curate_units: list[str] | None = None,
    replace_curated: bool = False,
):
    from ibrary.curation.curation_service import (
        curate_all,
        load_curated_json_array,
        save_curated,
        select_units_for_curation,
    )
    from ibrary.curation.schemas import CuratedModule

    logger.info(
        "step_curate",
        curate_theme=curate_theme,
        curate_topic=curate_topic,
        curate_units=curate_units,
        replace_curated=replace_curated,
    )

    try:
        units_to_curate = select_units_for_curation(
            validated.units,
            curate_theme=curate_theme,
            curate_topic=curate_topic,
            curate_unit_ids=curate_units,
        )
    except ValueError as e:
        logger.error("curate_filter_error", error=str(e))
        sys.exit(1)

    curated_path = OUTPUT_DIR / "curated_content.json"
    existing = load_curated_json_array(curated_path)
    resume_from = {m["curriculum_unit_id"] for m in existing if isinstance(m, dict)}
    if resume_from:
        logger.info("resuming_curation", already_done=len(resume_from))

    new_modules = curate_all(units_to_curate, alignment, resume_from=resume_from)
    save_curated(new_modules, OUTPUT_DIR, merge_existing=not replace_curated)

    data = load_curated_json_array(curated_path)
    return [CuratedModule.model_validate(m) for m in data]


def step_judge(modules):
    from ibrary.evaluation.udl_judge import evaluate_all, save_evaluation

    logger.info("step_judge")
    scores, flagged = evaluate_all(modules)
    save_evaluation(scores, OUTPUT_DIR)
    logger.info("judge_complete", total=len(scores), flagged=len(flagged))
    return scores, flagged


def step_publish():
    from ibrary.serving.dynamodb_writer import create_table, publish_curated_content

    logger.info("step_publish")
    create_table()
    curated_path = OUTPUT_DIR / "curated_content.json"
    if not curated_path.exists():
        logger.error("no_curated_content")
        return 0
    count = publish_curated_content(str(curated_path))
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "IBrary pipeline: default is setup (extract, validate, align). "
            "Use --full or --steps for curation and publishing."
        ),
    )
    parser.add_argument(
        "--steps",
        metavar="LIST",
        default=None,
        help=(
            "Comma-separated steps to run, in pipeline order e.g. extract,validate or curate,judge. "
            "Overrides default setup and --full."
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run all steps through publish (includes LLM curation and judge).",
    )
    parser.add_argument(
        "--resume-from",
        choices=ALL_STEPS,
        default=None,
        help="Start at this step and run through the end of the selected step list.",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip the UDL judge step when it appears in the selected steps.",
    )
    parser.add_argument(
        "--curate-theme",
        type=int,
        default=None,
        metavar="N",
        help=(
            "With curate: only units in theme N. Combined with --curate-topic for one topic within "
            "that theme. Ignored when --curate-unit is set."
        ),
    )
    parser.add_argument(
        "--curate-topic",
        type=int,
        default=None,
        metavar="N",
        help=(
            "With curate: filter by curriculum topic_number across all themes, unless "
            "--curate-theme is also set (then both must match)."
        ),
    )
    parser.add_argument(
        "--curate-unit",
        action="append",
        default=None,
        dest="curate_units",
        metavar="UNIT_ID",
        help=(
            "With curate: only this curriculum_unit_id (repeatable). Overrides "
            "--curate-theme and --curate-topic."
        ),
    )
    parser.add_argument(
        "--replace-curated",
        action="store_true",
        help=(
            "With curate: write only this run's modules to curated_content.json (no merge). "
            "Default merges new/updated modules into an existing file."
        ),
    )
    args = parser.parse_args()

    if args.full and args.steps is not None:
        parser.error("use either --full or --steps, not both")

    try:
        steps_to_run = _resolve_selected_steps(args)
    except ValueError as e:
        parser.error(str(e))

    if args.resume_from is not None:
        if args.resume_from not in steps_to_run:
            print(
                f"error: --resume-from {args.resume_from!r} is not in the selected steps {steps_to_run}.\n"
                "  For curation or later, use: python scripts/run_pipeline.py --full --resume-from "
                f"{args.resume_from}",
                file=sys.stderr,
            )
            sys.exit(1)
        steps_to_run = steps_to_run[steps_to_run.index(args.resume_from) :]

    logger.info("pipeline_start", steps=steps_to_run)

    validated = None
    alignment = None
    modules = None

    for step_name in steps_to_run:
        logger.info("step_begin", step=step_name)

        if step_name == "extract":
            step_extract()

        elif step_name == "validate":
            validated = step_validate()

        elif step_name == "align":
            if validated is None:
                from ibrary.curriculum.validator import validate_curriculum

                validated = validate_curriculum(CURRICULUM_JSON)
            alignment = step_align(validated)

        elif step_name == "curate":
            if validated is None:
                from ibrary.curriculum.validator import validate_curriculum

                validated = validate_curriculum(CURRICULUM_JSON)
            if alignment is None:
                alignment_path = OUTPUT_DIR / "curriculum_textbook_alignment.json"
                if alignment_path.exists():
                    alignment = json.loads(alignment_path.read_text())
                else:
                    logger.error("no_alignment_file")
                    sys.exit(1)
            cu = args.curate_units or None
            modules = step_curate(
                validated,
                alignment,
                curate_theme=args.curate_theme,
                curate_topic=args.curate_topic,
                curate_units=cu,
                replace_curated=args.replace_curated,
            )

        elif step_name == "judge":
            if args.skip_judge:
                logger.info("judge_skipped")
                continue
            if modules is None:
                from ibrary.curation.curation_service import load_curated_json_array
                from ibrary.curation.schemas import CuratedModule

                curated_path = OUTPUT_DIR / "curated_content.json"
                data = load_curated_json_array(curated_path)
                if not data:
                    logger.error("no_curated_content_for_judge")
                    continue
                modules = [CuratedModule.model_validate(m) for m in data]
            step_judge(modules)

        elif step_name == "publish":
            step_publish()

        logger.info("step_complete", step=step_name)

    logger.info("pipeline_complete")


if __name__ == "__main__":
    main()
