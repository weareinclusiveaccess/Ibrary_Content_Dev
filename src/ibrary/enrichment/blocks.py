"""Markdown → content_blocks; inject images and formulas."""

from __future__ import annotations

import re
from typing import Any

from ibrary.curation.schemas import FormulaRef
from ibrary.enrichment.schemas import MediaAsset


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """Parse simple markdown into LearningModule v1 blocks."""
    blocks: list[dict[str, Any]] = []
    bid = 0
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("### "):
            blocks.append(
                {"id": f"b{bid}", "type": "heading", "level": 3, "text": line[4:].strip()}
            )
            bid += 1
            i += 1
            continue
        if line.startswith("## "):
            blocks.append(
                {"id": f"b{bid}", "type": "heading", "level": 2, "text": line[3:].strip()}
            )
            bid += 1
            i += 1
            continue
        if line.startswith("# "):
            blocks.append(
                {"id": f"b{bid}", "type": "heading", "level": 1, "text": line[2:].strip()}
            )
            bid += 1
            i += 1
            continue
        if re.match(r"^[-*]\s+", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                items.append(re.sub(r"^[-*]\s+", "", lines[i]).strip())
                i += 1
            blocks.append(
                {"id": f"b{bid}", "type": "list", "style": "bullet", "items": items}
            )
            bid += 1
            continue
        if line.strip() == "":
            i += 1
            continue
        para_lines = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
            if re.match(r"^[-*]\s+", lines[i]):
                break
            para_lines.append(lines[i])
            i += 1
        text = " ".join(p.strip() for p in para_lines if p.strip())
        if text:
            blocks.append({"id": f"b{bid}", "type": "paragraph", "text": text})
            bid += 1
    return blocks


def inject_image_blocks(
    blocks: list[dict[str, Any]],
    assets: list[MediaAsset],
    *,
    after_heading: str | None = None,
) -> list[dict[str, Any]]:
    if not assets:
        return blocks
    out: list[dict[str, Any]] = []
    inserted = False
    for block in blocks:
        out.append(block)
        if (
            not inserted
            and after_heading
            and block.get("type") == "heading"
            and after_heading.lower() in (block.get("text") or "").lower()
        ):
            for asset in assets:
                out.append(
                    {
                        "id": f"img_{asset.asset_id}",
                        "type": "image",
                        "asset_id": asset.asset_id,
                        "placement": "inline",
                    }
                )
            inserted = True
    if not inserted:
        out.append(
            {"id": "b_figures_h", "type": "heading", "level": 2, "text": "Figures"}
        )
        for asset in assets:
            out.append(
                {
                    "id": f"img_{asset.asset_id}",
                    "type": "image",
                    "asset_id": asset.asset_id,
                    "placement": "inline",
                }
            )
    return out


def inject_formula_blocks(
    blocks: list[dict[str, Any]],
    formulas: list[FormulaRef],
) -> list[dict[str, Any]]:
    """Insert block formulas after paragraphs that mention plain_text."""
    if not formulas:
        return blocks
    out: list[dict[str, Any]] = []
    for block in blocks:
        out.append(block)
        if block.get("type") != "paragraph":
            continue
        text = block.get("text") or ""
        for f in formulas:
            if f.plain_text and f.plain_text in text:
                out.append(
                    {
                        "id": f"formula_{f.formula_id}",
                        "type": "formula",
                        "formula_id": f.formula_id,
                        "display": "block",
                    }
                )
    return out


def apply_latex_to_markdown(markdown: str, formulas: list[FormulaRef]) -> str:
    """Replace plain_text tokens with inline LaTeX for student markdown export."""
    out = markdown
    for f in sorted(formulas, key=lambda x: -len(x.plain_text)):
        if not f.plain_text or f.plain_text not in out:
            continue
        if f.kind == "chemistry":
            replacement = f"${f.latex}$"
        else:
            replacement = f"${f.latex}$"
        out = out.replace(f.plain_text, replacement, 1)
    return out
