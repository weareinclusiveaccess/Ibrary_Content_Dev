#!/usr/bin/env python3
"""Align curated_content.json image s3_urls with textbook_image_manifest / S3 layout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ibrary.config import PIPELINE_SUBJECT_SLUG, PROJECT_ROOT
from ibrary.curation.curated_postgres import upsert_curated_payloads
from ibrary.textbook.s3_paths import textbook_image_s3_url

_OLD_PREFIX = "s3://ibrary-content/textbook-images/"
_NEW_PREFIX = f"s3://ibrary-content/{PIPELINE_SUBJECT_SLUG}/textbook-images/"


def _load_manifest_map(manifest_path: Path) -> dict[str, dict]:
    if not manifest_path.is_file():
        return {}
    rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{manifest_path} must be a JSON array")
    return {r["image_id"]: r for r in rows if isinstance(r, dict) and r.get("image_id")}


def _canonical_url(image_id: str, by_id: dict[str, dict], fallback_ext: str) -> str:
    row = by_id.get(image_id)
    if row and row.get("s3_url"):
        return str(row["s3_url"])
    ext = (row or {}).get("ext") or fallback_ext
    return textbook_image_s3_url(image_id, ext)


def fix_curated_image_urls(
    *,
    subject_slug: str | None = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Return (images_fixed, modules_touched)."""
    slug = subject_slug or PIPELINE_SUBJECT_SLUG
    biology_dir = PROJECT_ROOT / "data" / "docs" / "extracted_source_content" / slug
    curated_path = biology_dir / "curated_content.json"
    manifest_path = biology_dir / "textbook_image_manifest.json"

    if not curated_path.is_file():
        raise FileNotFoundError(curated_path)

    data = json.loads(curated_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("curated_content.json must be a JSON array")

    by_id = _load_manifest_map(manifest_path)
    images_fixed = 0
    modules_touched = 0

    for module in data:
        if not isinstance(module, dict):
            continue
        module_fixes = 0
        for img in module.get("images") or []:
            if not isinstance(img, dict):
                continue
            image_id = img.get("image_id")
            if not image_id:
                continue
            old_url = img.get("s3_url", "")
            ext = "jpeg"
            if "." in old_url:
                ext = old_url.rsplit(".", 1)[-1]
            new_url = _canonical_url(image_id, by_id, ext)
            if old_url != new_url:
                img["s3_url"] = new_url
                images_fixed += 1
                module_fixes += 1
        if module_fixes:
            modules_touched += 1

    if dry_run:
        return images_fixed, modules_touched

    curated_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    upsert_curated_payloads(data)
    return images_fixed, modules_touched


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    p.add_argument("--subject", default=None, help=f"Subject slug (default: {PIPELINE_SUBJECT_SLUG})")
    args = p.parse_args()

    fixed, modules = fix_curated_image_urls(
        subject_slug=args.subject,
        dry_run=args.dry_run,
    )
    action = "would fix" if args.dry_run else "fixed"
    print(f"{action} {fixed} image URL(s) across {modules} module(s)")


if __name__ == "__main__":
    main()
