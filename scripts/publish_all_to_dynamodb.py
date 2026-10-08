#!/usr/bin/env python3
"""Bulk-publish curated units from Postgres to DynamoDB.

Use when Postgres rows are already ``published`` but DynamoDB was never written
(e.g. portal had ``PORTAL_PUBLISH_ENABLED=false``). Unlike the portal publish
button, this re-writes ``published`` units instead of treating them as a no-op.

Prerequisites:
  - ``DATABASE_URL_REVIEW`` points at the review Postgres (Neon prod or local)
  - AWS credentials for the target account (``AWS_PROFILE`` or env keys)
  - ``AWS_DEFAULT_REGION`` set (default from config: eu-west-1)

Examples:
  # Preview what would be published (prod AWS — ignores .env local DynamoDB)
  uv run python scripts/publish_all_to_dynamodb.py --prod --dry-run

  # Backfill all published + verified units to prod DynamoDB
  uv run python scripts/publish_all_to_dynamodb.py --prod

  # Single unit
  uv run python scripts/publish_all_to_dynamodb.py --prod --unit bio_sss1_theme1_topic1_content0
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# --prod must be applied before config loads .env (which sets DYNAMODB_ENDPOINT_URL
# to http://localhost:8000 for local dev).
if "--prod" in sys.argv:
    os.environ["DYNAMODB_ENDPOINT_URL"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ibrary.config import AWS_DEFAULT_REGION, DYNAMODB_ENDPOINT_URL
from ibrary.review.service import DYNAMODB_BACKFILL_STATUSES, publish_all_units_to_dynamodb


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish curated units from Postgres to DynamoDB (bulk backfill).",
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Target AWS DynamoDB (ignore DYNAMODB_ENDPOINT_URL from .env).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching units without writing to DynamoDB.",
    )
    parser.add_argument(
        "--status",
        default=",".join(sorted(DYNAMODB_BACKFILL_STATUSES)),
        help=f"Comma-separated Postgres statuses to include (default: {','.join(sorted(DYNAMODB_BACKFILL_STATUSES))}).",
    )
    parser.add_argument(
        "--unit",
        action="append",
        dest="units",
        metavar="ID",
        help="Publish only this curriculum_unit_id (repeatable).",
    )
    parser.add_argument(
        "--allow-local",
        action="store_true",
        help="Allow publishing when DYNAMODB_ENDPOINT_URL is set (DynamoDB Local).",
    )
    args = parser.parse_args()

    statuses = frozenset(s.strip() for s in args.status.split(",") if s.strip())
    if not statuses:
        print("error: --status must include at least one status", file=sys.stderr)
        return 1

    endpoint = DYNAMODB_ENDPOINT_URL if DYNAMODB_ENDPOINT_URL else None
    if endpoint and not args.allow_local and not args.prod:
        print(
            f"error: DYNAMODB_ENDPOINT_URL is set ({endpoint}). "
            "Pass --prod for AWS DynamoDB, or --allow-local for DynamoDB Local.",
            file=sys.stderr,
        )
        return 1

    target = endpoint or f"AWS DynamoDB ({AWS_DEFAULT_REGION})"
    mode = "dry-run" if args.dry_run else "publish"
    print(f"mode={mode} target={target} statuses={','.join(sorted(statuses))}")

    try:
        published = publish_all_units_to_dynamodb(
            statuses=statuses,
            unit_ids=args.units,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not published:
        print("No matching units found.")
        return 0

    verb = "Would publish" if args.dry_run else "Published"
    print(f"{verb} {len(published)} unit(s):")
    for unit_id in published:
        print(f"  {unit_id}")
    if not args.dry_run:
        print(
            f"Done. Each unit wrote 2 DynamoDB items (TOPIC + SUBTOPIC) "
            f"to table CuratedContent."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
