#!/usr/bin/env python3
"""End-to-end pipeline orchestrator for the IBrary biology content system.

Usage:
    python scripts/run_pipeline.py [--resume-from STEP] [--skip-judge]

Steps (in order):
    extract   — Extract textbook PDF → PostgreSQL
    validate  — Validate curriculum JSON (topics 1-6)
    align     — Embed + align curriculum ↔ textbook
    curate    — Generate UDL content via LLM (RAG)
    judge     — Run UDL evaluation judge
    publish   — Publish approved content to DynamoDB
"""

from __future__ import annotations

import argparse
import json
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

STEPS = ["extract", "validate", "align", "curate", "judge", "publish"]

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "docs" / "extracted_source_content" / "biology"
OUTPUT_DIR = DATA_DIR
TEXTBOOK_PDF = DATA_DIR / "Biology2e-WEB.pdf"
CURRICULUM_JSON = DATA_DIR / "biology_curriculum_structured.json"


def step_extract():
    from ibrary.config import S3_BUCKET
    from ibrary.textbook.extractor import extract_biology2e
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
    )

    chunks, images = extract_biology2e(TEXTBOOK_PDF, book_id="bio2e")
    upserted = upsert_chunks(chunks)
    logger.info("chunks_loaded", total=len(chunks), upserted=upserted)

    if images:
        try:
            save_images_to_s3(images, S3_BUCKET)
        except Exception:
            logger.warning("s3_unavailable_saving_locally")
            save_images_locally(images, OUTPUT_DIR / "textbook_images")

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


def step_curate(validated, alignment):
    from ibrary.curation.curation_service import curate_all, save_curated

    logger.info("step_curate")

    resume_from: set[str] = set()
    curated_path = OUTPUT_DIR / "curated_content.json"
    if curated_path.exists():
        existing = json.loads(curated_path.read_text())
        resume_from = {m["curriculum_unit_id"] for m in existing}
        logger.info("resuming_curation", already_done=len(resume_from))

    modules = curate_all(validated.units, alignment, resume_from=resume_from)
    save_curated(modules, OUTPUT_DIR)
    return modules


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


def main():
    parser = argparse.ArgumentParser(description="IBrary biology content pipeline")
    parser.add_argument(
        "--resume-from",
        choices=STEPS,
        default=None,
        help="Resume pipeline from this step (skips earlier steps)",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip the UDL judge evaluation step",
    )
    args = parser.parse_args()

    start_idx = STEPS.index(args.resume_from) if args.resume_from else 0
    steps_to_run = STEPS[start_idx:]

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
            modules = step_curate(validated, alignment)

        elif step_name == "judge":
            if args.skip_judge:
                logger.info("judge_skipped")
                continue
            if modules is None:
                curated_path = OUTPUT_DIR / "curated_content.json"
                if curated_path.exists():
                    from ibrary.curation.schemas import CuratedModule
                    data = json.loads(curated_path.read_text())
                    modules = [CuratedModule.model_validate(m) for m in data]
                else:
                    logger.error("no_curated_content_for_judge")
                    continue
            step_judge(modules)

        elif step_name == "publish":
            step_publish()

        logger.info("step_complete", step=step_name)

    logger.info("pipeline_complete")


if __name__ == "__main__":
    main()
