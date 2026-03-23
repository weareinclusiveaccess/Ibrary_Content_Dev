#!/usr/bin/env python3
"""Curate one theme, topic, or unit — wrapper around ``run_pipeline.py --steps curate``.

Examples (from repo root):

  uv run python scripts/curate_subset.py --topic 1
  uv run python scripts/curate_subset.py --theme 1 --topic 1
  uv run python scripts/curate_subset.py --unit bio_sss1_theme1_topic1_content0
  uv run python scripts/curate_subset.py --unit bio_sss1_theme1_topic1_content0 \\
      --unit bio_sss1_theme1_topic1_content1

By default, new modules are merged into ``curated_content.json``. Use ``--replace``
to overwrite the file with only this run's output.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    pipeline = root / "scripts" / "run_pipeline.py"

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--theme", type=int, default=None, metavar="N", help="Curriculum theme_number")
    p.add_argument("--topic", type=int, default=None, metavar="N", help="Curriculum topic_number")
    p.add_argument(
        "--unit",
        action="append",
        default=None,
        dest="units",
        metavar="UNIT_ID",
        help="curriculum_unit_id (repeatable); overrides --theme/--topic",
    )
    p.add_argument(
        "--replace",
        action="store_true",
        help="Pass --replace-curated to run_pipeline (no merge)",
    )
    args = p.parse_args()

    cmd = [sys.executable, str(pipeline), "--steps", "curate"]
    if args.theme is not None:
        cmd.extend(["--curate-theme", str(args.theme)])
    if args.topic is not None:
        cmd.extend(["--curate-topic", str(args.topic)])
    for u in args.units or []:
        cmd.extend(["--curate-unit", u])
    if args.replace:
        cmd.append("--replace-curated")

    if args.units is None and args.theme is None and args.topic is None:
        p.error("specify --unit and/or --topic and/or --theme")

    raise SystemExit(subprocess.call(cmd, cwd=str(root)))


if __name__ == "__main__":
    main()
