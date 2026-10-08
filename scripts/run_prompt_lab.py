#!/usr/bin/env python3
"""Compare curation prompt versions on golden curriculum units using the judge."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

GOLDEN_UNITS = [
    "bio_sss1_theme1_topic1_content0",
    "bio_sss1_theme1_topic1_content1",
    "bio_sss1_theme1_topic1_content2",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "docs" / "extracted_source_content" / "biology"


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt lab: compare curated outputs via judge.")
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline curated_content.json")
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate curated_content.json")
    parser.add_argument(
        "--units",
        nargs="*",
        default=GOLDEN_UNITS,
        help="curriculum_unit_ids to compare (default: theme1 topic1 content 0-2)",
    )
    args = parser.parse_args()

    import json

    from ibrary.curation.schemas import CuratedModule
    from ibrary.prompt_improvement.compare import compare_prompt_versions

    def _modules_for_units(path: Path, unit_ids: list[str]) -> list[CuratedModule]:
        data = json.loads(path.read_text(encoding="utf-8"))
        by_id = {m["curriculum_unit_id"]: CuratedModule.model_validate(m) for m in data}
        missing = [u for u in unit_ids if u not in by_id]
        if missing:
            raise SystemExit(f"units not in {path}: {missing}")
        return [by_id[u] for u in unit_ids]

    report = compare_prompt_versions(
        _modules_for_units(args.baseline, args.units),
        _modules_for_units(args.candidate, args.units),
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
