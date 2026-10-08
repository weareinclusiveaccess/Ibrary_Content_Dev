"""
Orchestrate extraction of biology/scheme-of-work notes from .md + optional .rtf/.pdf.

Produces JSON matching extraction_template.json and saves images to output_dir/img/.
"""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from ..parser.notes_md_parser import parse_notes_md
from .rtfImageExtractor import extract_rtf_images_to_dir
from .pdfImageExtractor import extract_pdf_images_to_dir


def _collect_figure_slots(structure: dict) -> list[tuple[int, str, int, int]]:
    """
    Collect figure slots in document order: (week_idx, "subtopic"|"assignment", block_idx, figure_idx).
    Parser outputs figures per subtopic and per assignment; we flatten in order: subtopics then assignments per week.
    """
    slots: list[tuple[int, str, int, int]] = []
    for wi, week in enumerate(structure.get("weeks", [])):
        for si, sub in enumerate(week.get("subtopics", [])):
            for fi in range(len(sub.get("figures", []))):
                slots.append((wi, "subtopic", si, fi))
        for ai, assign in enumerate(week.get("assignments", [])):
            for fi in range(len(assign.get("figures", []))):
                slots.append((wi, "assignment", ai, fi))
    return slots


def _group_pdf_images_by_page(page_paths: list[tuple[int, str]]) -> list[list[str]]:
    """
    Group (page_index, filename) by page so images from the same page become one figure.
    E.g. page_21_image_0.png through page_21_image_8.png → one group; page_24_image_0 through page_24_image_7 → another.
    """
    by_page: dict[int, list[str]] = defaultdict(list)
    for page_idx, path in page_paths:
        by_page[page_idx].append(path)
    return [by_page[p] for p in sorted(by_page.keys())]


def _content_hash(path: Path) -> str:
    """SHA-256 hash of file contents for deduplication."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _deduplicate_images_by_content(
    paths: list[str],
    img_dir: Path,
) -> tuple[dict[str, str], list[str]]:
    """
    Deduplicate by file content. Returns (path_to_canonical, paths_to_delete).
    path_to_canonical: each path -> canonical path (first occurrence of that content).
    paths_to_delete: duplicate paths that can be removed from disk.
    """
    content_to_path: dict[str, str] = {}
    path_to_canonical: dict[str, str] = {}
    to_delete: list[str] = []
    for p in paths:
        full = img_dir / p
        if not full.exists():
            path_to_canonical[p] = p
            continue
        h = _content_hash(full)
        if h in content_to_path:
            path_to_canonical[p] = content_to_path[h]
            to_delete.append(p)
        else:
            content_to_path[h] = p
            path_to_canonical[p] = p
    return path_to_canonical, to_delete


def _apply_canonical_paths(
    image_groups: list[list[str]],
    path_to_canonical: dict[str, str],
) -> list[list[str]]:
    """Replace paths with canonical and uniq each group (same page can reference same image after dedup)."""
    out: list[list[str]] = []
    for group in image_groups:
        canonical = [path_to_canonical.get(p, p) for p in group]
        # Uniq preserving order
        seen = set()
        uniq = [p for p in canonical if p not in seen and not seen.add(p)]
        out.append(uniq)
    return out


def _populate_week_figures(structure: dict) -> None:
    """
    Set week["figures"] for each week: aggregate all figures from subtopics and assignments
    (including paths filled by _associate_image_groups_to_figures) so the figure list is visible at week level.
    """
    for week in structure.get("weeks", []):
        week_figures: list[dict] = []
        for s in week.get("subtopics", []):
            for f in s.get("figures", []):
                week_figures.append({**f, "source": f"subtopic: {s['subtopic']}"})
        for a in week.get("assignments", []):
            for f in a.get("figures", []):
                week_figures.append({**f, "source": f"assignment: {a['heading']}"})
        week["figures"] = week_figures


def _associate_image_groups_to_figures(
    structure: dict,
    image_groups: list[list[str]],
    img_prefix: str = "img",
) -> None:
    """
    Assign each group of image paths (e.g. all images from one page) to one figure slot in order.
    Slots are subtopic figures then assignment figures, in document order.
    Mutates structure in place: each figure gets "paths": [rel_path, ...].
    If parser created no figure slots, use first subtopic and create one figure per group.
    """
    slots = _collect_figure_slots(structure)
    if not slots and image_groups and structure.get("weeks"):
        wi = 0
        si = 0
        for fn in range(1, len(image_groups) + 1):
            structure["weeks"][wi]["subtopics"][si].setdefault("figures", []).append(
                {"figure_number": fn, "caption": ""}
            )
        slots = _collect_figure_slots(structure)
    for i, paths in enumerate(image_groups):
        rel_paths = [f"{img_prefix}/{p}" if img_prefix else p for p in paths]
        if i < len(slots):
            wi, block_type, bi, fi = slots[i]
            if block_type == "subtopic":
                structure["weeks"][wi]["subtopics"][bi]["figures"][fi]["paths"] = rel_paths
            else:
                structure["weeks"][wi]["assignments"][bi]["figures"][fi]["paths"] = rel_paths
        else:
            if slots:
                wi, block_type, bi, fi = slots[-1]
                if block_type == "subtopic":
                    structure["weeks"][wi]["subtopics"][bi]["figures"][fi].setdefault("paths", []).extend(rel_paths)
                else:
                    structure["weeks"][wi]["assignments"][bi]["figures"][fi].setdefault("paths", []).extend(rel_paths)


def extract_biology_notes(
    md_path: str | Path,
    output_dir: str | Path,
    rtf_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    output_basename: str | None = None,
) -> dict:
    """
    Extract biology notes to JSON matching extraction_template.json and save images.

    Steps:
      1. Parse .md to get full structure (subject, class, term, weeks with subtopics and assignments).
      2. Extract images from RTF and/or PDF to output_dir/img/.
      3. Associate images to subtopics (by figure-placeholder order).
      4. Write JSON to output_dir / <basename>.json.

    Args:
        md_path: Path to the markdown notes file.
        output_dir: Directory for output JSON and img/ (e.g. docs/.../biology/extracted_notes).
        rtf_path: Optional path to .rtf file for image extraction.
        pdf_path: Optional path to .pdf file for image extraction.
        output_basename: Base name for JSON file (default: stem of md_path).

    Returns:
        The extracted structure (dict) as written to JSON.
    """
    md_path = Path(md_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    img_dir = output_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    structure = parse_notes_md(md_path)
    raw_rtf_groups: list[list[str]] = []
    raw_pdf_groups: list[list[str]] = []

    if rtf_path and Path(rtf_path).exists():
        rtf_path = Path(rtf_path)
        paths = extract_rtf_images_to_dir(rtf_path, img_dir, name_prefix="image")
        raw_rtf_groups = [[p] for p in paths]

    if pdf_path and Path(pdf_path).exists():
        pdf_path = Path(pdf_path)
        page_paths = extract_pdf_images_to_dir(pdf_path, img_dir, name_prefix="page")
        raw_pdf_groups = _group_pdf_images_by_page(page_paths)

    all_paths: list[str] = []
    for g in raw_rtf_groups + raw_pdf_groups:
        all_paths.extend(g)
    if all_paths:
        path_to_canonical, paths_to_delete = _deduplicate_images_by_content(all_paths, img_dir)
        for p in paths_to_delete:
            (img_dir / p).unlink(missing_ok=True)
        image_groups = _apply_canonical_paths(raw_rtf_groups + raw_pdf_groups, path_to_canonical)
        _associate_image_groups_to_figures(structure, image_groups, img_prefix="img")
    _populate_week_figures(structure)

    basename = output_basename or md_path.stem
    # Sanitize basename (e.g. "1ST TERM S1 BIOLOGY.docx (1)" -> keep as-is or simplify)
    json_path = output_dir / f"{basename}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2, ensure_ascii=False)
    return structure
