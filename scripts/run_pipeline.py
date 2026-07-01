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
SETUP_STEPS_V1 = ["extract", "validate", "align"]
SETUP_STEPS_V2 = ["extract", "validate", "align", "filter_relevance"]
REFINE_CURRICULUM_STEP = "refine_curriculum"
EXTENSION_STEPS = ["curate", "judge", "publish"]


def _all_steps(pipeline_version: int, *, include_refine: bool = False) -> list[str]:
    setup = SETUP_STEPS_V2 if pipeline_version >= 2 else SETUP_STEPS_V1
    steps = list(setup)
    if include_refine and REFINE_CURRICULUM_STEP not in steps:
        idx = steps.index("validate") + 1
        steps.insert(idx, REFINE_CURRICULUM_STEP)
    return steps + EXTENSION_STEPS

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "docs" / "extracted_source_content" / "biology"
OUTPUT_DIR = DATA_DIR
TEXTBOOK_PDF = Path(os.environ.get("TEXTBOOK_PDF", "")) if os.environ.get("TEXTBOOK_PDF") else (DATA_DIR / "Biology2e-WEB.pdf")
CURRICULUM_JSON = DATA_DIR / "biology_curriculum_structured.json"


def _parse_steps_list(spec: str, pipeline_version: int, *, include_refine: bool = False) -> list[str]:
    """Parse comma-separated step names; order follows pipeline step list."""
    all_steps = _all_steps(pipeline_version, include_refine=include_refine)
    raw = [p.strip().lower() for p in spec.split(",") if p.strip()]
    if not raw:
        raise ValueError("empty --steps")
    unknown = [p for p in raw if p not in all_steps]
    if unknown:
        raise ValueError(f"unknown step(s): {unknown}; valid: {all_steps}")
    order = {name: i for i, name in enumerate(all_steps)}
    return sorted(set(raw), key=lambda s: order[s])


def _resolve_selected_steps(
    args: argparse.Namespace,
    pipeline_version: int,
    *,
    include_refine: bool = False,
) -> list[str]:
    all_steps = _all_steps(pipeline_version, include_refine=include_refine)
    if args.steps is not None:
        return _parse_steps_list(args.steps, pipeline_version, include_refine=include_refine)
    if args.full:
        return list(all_steps)
    setup = SETUP_STEPS_V2 if pipeline_version >= 2 else SETUP_STEPS_V1
    steps = list(setup)
    if include_refine and REFINE_CURRICULUM_STEP not in steps:
        steps.insert(steps.index("validate") + 1, REFINE_CURRICULUM_STEP)
    return steps


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


def step_refine_curriculum(validated):
    from ibrary.curriculum.refiner import refine_validated_curriculum, save_refinement_outputs

    logger.info("step_refine_curriculum")
    refined, report = refine_validated_curriculum(validated)
    save_refinement_outputs(refined, report, OUTPUT_DIR)
    return refined


def step_filter_relevance(validated, alignment):
    from ibrary.relevance import filter_relevance_for_units, save_relevance_json

    logger.info("step_filter_relevance")
    reports = filter_relevance_for_units(validated.units, alignment)
    save_relevance_json(reports, OUTPUT_DIR)
    return reports


def step_align(validated):
    from ibrary.alignment.aligner import align_all, save_alignment
    from ibrary.alignment.embedder import embed_textbook_chunks
    from ibrary.alignment.embedding_text import resolve_embedding_storage_version

    topics = validated.topics
    if not topics:
        from ibrary.curriculum.validator import validate_curriculum

        topics = validate_curriculum(CURRICULUM_JSON).topics
        logger.info("alignment_topics_from_structured", count=len(topics))

    storage_version = resolve_embedding_storage_version()
    logger.info("step_align", embedding_model_version=storage_version)
    embedded = embed_textbook_chunks(storage_version)
    logger.info("embedding_done", new_embeddings=embedded, model_version=storage_version)

    alignment = align_all(
        validated.units,
        storage_version=storage_version,
        topics=topics,
    )
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
        load_curated_unit_ids,
        select_units_for_curation,
    )

    from ibrary.config import PIPELINE_VERSION, USE_CURATION_ORCHESTRATOR

    logger.info(
        "step_curate",
        curate_theme=curate_theme,
        curate_topic=curate_topic,
        curate_units=curate_units,
        replace_curated=replace_curated,
        pipeline_version=int(os.getenv("PIPELINE_VERSION", str(PIPELINE_VERSION))),
        use_orchestrator=USE_CURATION_ORCHESTRATOR,
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
    resume_from = load_curated_unit_ids(curated_path) if not replace_curated else set()
    if resume_from:
        logger.info("resuming_curation", already_done=len(resume_from))

    saved = curate_all(
        units_to_curate,
        alignment,
        resume_from=resume_from,
        output_dir=OUTPUT_DIR,
        merge_existing=not replace_curated,
    )
    logger.info(
        "step_curate_complete",
        saved=saved,
        units_in_run=len(units_to_curate),
        skipped_resume=len(resume_from),
    )
    return saved


def step_judge(*, replace_evaluation: bool = False):
    from ibrary.judging.subtopic_judge import evaluate_all_curated, load_evaluation_unit_ids

    eval_path = OUTPUT_DIR / "udl_subtopic_evaluation.json"
    resume_from = load_evaluation_unit_ids(eval_path) if not replace_evaluation else set()

    logger.info("step_judge", replace_evaluation=replace_evaluation, skipped_resume=len(resume_from))
    judged, flagged = evaluate_all_curated(
        OUTPUT_DIR,
        resume_from=resume_from,
        merge_existing=not replace_evaluation,
        replace_evaluation=replace_evaluation,
    )
    logger.info("step_judge_complete", judged=judged, flagged=flagged)
    return judged, flagged


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
    parser.add_argument(
        "--pipeline-version",
        type=int,
        choices=[1, 2],
        default=None,
        help="Pipeline v2 adds filter_relevance and excerpt-based curation (default: PIPELINE_VERSION env or 1).",
    )
    parser.add_argument(
        "--refine-curriculum",
        action="store_true",
        help=f"Include {REFINE_CURRICULUM_STEP} after validate (LLM assigns POs/activities per subtopic).",
    )
    args = parser.parse_args()

    from ibrary.config import PIPELINE_VERSION as ENV_PIPELINE_VERSION

    pipeline_version = (
        args.pipeline_version if args.pipeline_version is not None else ENV_PIPELINE_VERSION
    )
    os.environ["PIPELINE_VERSION"] = str(pipeline_version)
    all_steps = _all_steps(pipeline_version, include_refine=args.refine_curriculum)

    if args.full and args.steps is not None:
        parser.error("use either --full or --steps, not both")

    try:
        steps_to_run = _resolve_selected_steps(
            args, pipeline_version, include_refine=args.refine_curriculum
        )
    except ValueError as e:
        parser.error(str(e))

    if args.resume_from is not None:
        if args.resume_from not in all_steps:
            parser.error(f"--resume-from must be one of {all_steps}")
        if args.resume_from not in steps_to_run:
            print(
                f"error: --resume-from {args.resume_from!r} is not in the selected steps {steps_to_run}.\n"
                "  For curation or later, use: python scripts/run_pipeline.py --full --resume-from "
                f"{args.resume_from}",
                file=sys.stderr,
            )
            sys.exit(1)
        steps_to_run = steps_to_run[steps_to_run.index(args.resume_from) :]

    logger.info("pipeline_start", steps=steps_to_run, pipeline_version=pipeline_version)

    validated = None
    alignment = None
    modules = None

    for step_name in steps_to_run:
        logger.info("step_begin", step=step_name)

        if step_name == "extract":
            step_extract()

        elif step_name == "validate":
            validated = step_validate()

        elif step_name == "refine_curriculum":
            if validated is None:
                from ibrary.curriculum.validator import load_validated

                validated_path = OUTPUT_DIR / "curriculum_validated.json"
                if validated_path.exists():
                    validated = load_validated(validated_path)
                else:
                    validated = step_validate()
            validated = step_refine_curriculum(validated)

        elif step_name == "align":
            if validated is None:
                from ibrary.curriculum.validator import validate_curriculum

                validated = validate_curriculum(CURRICULUM_JSON)
            alignment = step_align(validated)

        elif step_name == "filter_relevance":
            if pipeline_version < 2:
                logger.error("filter_relevance_requires_v2")
                sys.exit(1)
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
            step_filter_relevance(validated, alignment)

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
            step_curate(
                validated,
                alignment,
                curate_theme=args.curate_theme,
                curate_topic=args.curate_topic,
                curate_units=cu,
                replace_curated=args.replace_curated,
            )
            modules = None

        elif step_name == "judge":
            if args.skip_judge:
                logger.info("judge_skipped")
                continue
            step_judge()

        elif step_name == "publish":
            step_publish()

        logger.info("step_complete", step=step_name)

    logger.info("pipeline_complete")


if __name__ == "__main__":
    main()
