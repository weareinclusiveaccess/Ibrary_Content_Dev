"""OpenStax *Biology 2e* PDF extraction (Biology2e-WEB.pdf).

Parses the embedded TOC, splits learning objectives, main body, chapter-summary
recaps, and end-of-chapter ancillary material, and yields records for PostgreSQL.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


@dataclass
class TextbookChunkRecord:
    chunk_id: str
    book_id: str
    chapter_num: int
    section_num: int | None = None
    subsection_num: int | None = None
    title: str = ""
    summary: str = ""
    content: str = ""
    learning_objectives: str = ""
    ancillary_content: str = ""
    content_hash: str = ""
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class ExtractedImage:
    image_id: str
    chunk_id: str
    page_num: int
    image_bytes: bytes = field(repr=False)
    ext: str = "png"
    caption: str = ""
    alt_text: str = ""


# OpenStax Biology 2e — TOC heading patterns in exported text
_CHAPTER_RE = re.compile(r"^Chapter\s+(\d+)", re.IGNORECASE)
_SECTION_RE = re.compile(r"^(\d+)\.(\d+)\s+(.+)")
_FIGURE_CAPTION_RE = re.compile(r"FIGURE\s+(\d+\.\d+)", re.IGNORECASE)


def _make_chunk_id(book_id: str, ch: int, sec: int | None = None, sub: int | None = None) -> str:
    parts = [book_id, f"ch{ch}"]
    if sec is not None:
        parts.append(f"sec{sec}")
    if sub is not None:
        parts.append(f"sub{sub}")
    return "_".join(parts)


def _content_hash(parts: list[str]) -> str:
    joined = "\n---\n".join(p for p in parts if p is not None)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _first_paragraph(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 50]
    return paragraphs[0] if paragraphs else text[:500]


def _is_running_header_or_footer(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.isdigit() and len(s) <= 3:
        return True
    if "access for free at openstax.org" in s.lower():
        return True
    if re.match(r"^\d+\s*•\s+", s):
        return True
    if re.match(r"^\d+\s+•\s+", s):
        return True
    return False


def _anchor_section_start(
    text: str,
    chapter_num: int,
    section_num: int | None,
    subsection_num: int | None,
    title: str,
) -> str:
    """Drop prior-section spillover by anchoring at this chunk's section heading."""
    if section_num is None:
        return text
    if subsection_num is not None and title.strip():
        esc = re.escape(title.strip())[:100]
        m = re.search(rf"(?m)^\s*{esc}\s*$", text)
        if m:
            return text[m.start() :].strip()

    sec_pat = re.compile(rf"(?m)^\s*{chapter_num}\.{section_num}\s+[^\n]+\s*$")
    m = sec_pat.search(text)
    if m:
        return text[m.start() :].strip()

    bullet_pat = re.compile(rf"(?m)^\s*{chapter_num}\s*•\s*[^\n]+$")
    for m in bullet_pat.finditer(text):
        if title.strip()[:15].lower() in m.group(0).lower():
            return text[m.start() :].strip()
    m = bullet_pat.search(text)
    if m:
        return text[m.start() :].strip()
    return text


def _split_learning_objectives(text: str) -> tuple[str, str]:
    """Extract LEARNING OBJECTIVES block; return (lo, remainder)."""
    lines = text.split("\n")
    start_idx: int | None = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "learning objectives" in low and "chapter" not in low:
            start_idx = i
            break
    if start_idx is None:
        return "", text

    collected: list[str] = []
    i = start_idx
    while i < len(lines):
        collected.append(lines[i])
        i += 1
        blob = "\n".join(collected).lower()
        if "by the end of this section" in blob:
            break
        if i - start_idx > 12:
            break

    while i < len(lines):
        s = lines[i].strip()
        if _is_running_header_or_footer(lines[i]) and s == "":
            collected.append(lines[i])
            i += 1
            continue
        if not s:
            collected.append(lines[i])
            i += 1
            continue
        if s == "•" or s.startswith("•"):
            collected.append(lines[i])
            i += 1
            continue
        if collected and collected[-1].strip() == "•" and len(s) < 160 and not s.startswith("•"):
            collected.append(lines[i])
            i += 1
            continue
        if len(s) > 50 and not s.startswith("•"):
            break
        collected.append(lines[i])
        i += 1

    lo_text = "\n".join(collected).strip()
    rest = "\n".join(lines[i:]).strip()
    return lo_text, rest


def _section_key(ch: int, sec: int) -> tuple[int, int]:
    return (ch, sec)


def _find_earliest_split(
    text: str,
    chapter_num: int,
    section_num: int,
) -> int | None:
    """Index where main body ends (Key Terms, Chapter Summary, or next section)."""
    candidates: list[int] = []

    for m in re.finditer(r"(?m)^Key Terms\s*$", text):
        candidates.append(m.start())

    for m in re.finditer(r"(?m)^Chapter Summary\s*$", text):
        candidates.append(m.start())

    for m in re.finditer(r"(?m)^(\d+)\.(\d+)\s+\S", text):
        ch, sec = int(m.group(1)), int(m.group(2))
        if _section_key(ch, sec) > _section_key(chapter_num, section_num):
            candidates.append(m.start())

    if not candidates:
        return None
    return min(candidates)


def _split_body_ancillary(
    text: str,
    chapter_num: int,
    section_num: int | None,
) -> tuple[str, str]:
    if section_num is None:
        split = None
        for m in re.finditer(r"(?m)^Key Terms\s*$", text):
            split = m.start() if split is None else min(split, m.start())
        if split is None:
            for m in re.finditer(r"(?m)^Chapter Summary\s*$", text):
                split = m.start() if split is None else min(split, m.start())
        if split is not None:
            return text[:split].strip(), text[split:].strip()
        return text.strip(), ""

    idx = _find_earliest_split(text, chapter_num, section_num)
    if idx is None:
        return text.strip(), ""
    return text[:idx].strip(), text[idx:].strip()


def _extract_chapter_summary_for_section(
    ancillary: str,
    chapter_num: int,
    section_num: int,
) -> str:
    """Pull the Chapter Summary subsection for e.g. 1.2 from ancillary text."""
    if not ancillary.strip():
        return ""
    m = re.search(r"(?ms)^Chapter Summary\s*\n(.*)$", ancillary)
    if not m:
        return ""
    region = m.group(1)
    sec_line = re.compile(rf"(?m)^{chapter_num}\.{section_num}\s+[^\n]+\s*$")
    sm = sec_line.search(region)
    if not sm:
        return ""
    start = sm.start()
    tail = region[start:]
    lines = tail.split("\n", 1)
    first_line = lines[0]
    body = lines[1] if len(lines) > 1 else ""

    end_patterns = [
        r"(?m)^Visual Connection Questions\s*$",
        r"(?m)^Review Questions\s*$",
    ]
    end_idx = len(body)
    for pat in end_patterns:
        em = re.search(pat, body)
        if em:
            end_idx = min(end_idx, em.start())

    next_sec = re.compile(r"(?m)^(\d+)\.(\d+)\s+\S")
    for em in next_sec.finditer(body):
        ch, sec = int(em.group(1)), int(em.group(2))
        if _section_key(ch, sec) > _section_key(chapter_num, section_num):
            end_idx = min(end_idx, em.start())
            break

    snippet = (first_line + "\n" + body[:end_idx]).strip()
    return snippet


def _structure_openstax_section(
    raw: str,
    chapter_num: int,
    section_num: int | None,
    subsection_num: int | None,
    title: str,
) -> tuple[str, str, str, str]:
    """Return (learning_objectives, content, summary, ancillary_content)."""
    anchored = _anchor_section_start(raw, chapter_num, section_num, subsection_num, title)
    lo, after_lo = _split_learning_objectives(anchored)

    if section_num is not None:
        body, ancillary = _split_body_ancillary(after_lo, chapter_num, section_num)
        summary = _extract_chapter_summary_for_section(ancillary, chapter_num, section_num)
        if not summary.strip():
            summary = _first_paragraph(body) if body.strip() else _first_paragraph(after_lo)
    else:
        body, ancillary = _split_body_ancillary(after_lo, chapter_num, section_num)
        summary = _first_paragraph(body) if body.strip() else _first_paragraph(anchored)

    return lo.strip(), body.strip(), summary.strip(), ancillary.strip()


def _collect_text_blocks(page: fitz.Page) -> list[tuple[float, float, float, float, str]]:
    """Sorted (x0, y0, x1, y1, text) for text blocks."""
    d = page.get_text("dict")
    out: list[tuple[float, float, float, float, str]] = []
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
        parts: list[str] = []
        for line in block.get("lines", []):
            line_parts = [sp.get("text", "") for sp in line.get("spans", [])]
            parts.append("".join(line_parts))
        t = "\n".join(parts).strip()
        if t:
            out.append((x0, y0, x1, y1, t))
    out.sort(key=lambda b: (b[1], b[0]))
    return out


def _caption_for_image(page: fitz.Page, xref: int) -> tuple[str, str]:
    """Find FIGURE caption near image bbox; return (caption, alt_text)."""
    try:
        rects = page.get_image_rects(xref)
    except Exception:
        rects = []
    if not rects:
        return "", ""
    ir = rects[0]
    blocks = _collect_text_blocks(page)
    candidates: list[tuple[float, str]] = []

    for x0, y0, x1, y1, t in blocks:
        if not _FIGURE_CAPTION_RE.search(t):
            continue
        if x1 < ir.x0 - 50 or x0 > ir.x1 + 50:
            continue
        dist_below = y0 - ir.y1
        dist_above = ir.y0 - y1
        if -8 <= dist_below < 160:
            candidates.append((dist_below, t))
        elif -5 <= dist_above < 100:
            candidates.append((dist_above + 500.0, t))

    if not candidates:
        return "", ""

    candidates.sort(key=lambda x: x[0])
    cap = candidates[0][1].strip()
    fm = _FIGURE_CAPTION_RE.search(cap)
    fig_id = fm.group(1) if fm else ""
    alt = f"Figure {fig_id}: {cap[:200]}" if fig_id else cap[:240]
    return cap, alt


def write_textbook_image_manifest(
    images: list[ExtractedImage],
    path: str | Path,
    *,
    s3_bucket: str | None = None,
) -> Path:
    """Write JSON table of images for reference (caption, ids, optional s3 URL)."""
    path = Path(path)
    rows: list[dict] = []
    for img in images:
        row = {
            "image_id": img.image_id,
            "chunk_id": img.chunk_id,
            "page_num": img.page_num,
            "caption": img.caption,
            "alt_text": img.alt_text,
            "ext": img.ext,
        }
        if s3_bucket:
            from ibrary.textbook.s3_paths import textbook_image_s3_url

            row["s3_url"] = textbook_image_s3_url(
                img.image_id, img.ext, bucket=s3_bucket
            )
        rows.append(row)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    logger.info("image_manifest_written", path=str(path), count=len(rows))
    return path


def extract_openstax_biology_2e(
    pdf_path: str | Path,
    book_id: str = "bio2e",
) -> tuple[list[TextbookChunkRecord], list[ExtractedImage]]:
    """Extract structured chunks and images from OpenStax Biology 2e (Biology2e-WEB.pdf).

    Returns (chunks, images).
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install pymupdf")

    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))

    toc = doc.get_toc(simple=True)
    if not toc:
        logger.warning("no_toc_found", path=str(pdf_path))
        toc = _build_toc_from_pages(doc)

    chunks: list[TextbookChunkRecord] = []
    images: list[ExtractedImage] = []

    entries = _normalize_toc(toc)

    for i, entry in enumerate(entries):
        title, start_page = entry["title"], entry["page"]
        end_page = entries[i + 1]["page"] - 1 if i + 1 < len(entries) else len(doc) - 1

        ch_num = entry.get("chapter")
        sec_num = entry.get("section")
        sub_num = entry.get("subsection")

        if ch_num is None:
            continue

        text_parts = []
        for pg in range(start_page, min(end_page + 1, len(doc))):
            text_parts.append(doc[pg].get_text("text"))
        raw = "\n".join(text_parts).strip()

        if not raw:
            continue

        chunk_id = _make_chunk_id(book_id, ch_num, sec_num, sub_num)

        lo, body, summary, ancillary = _structure_openstax_section(
            raw, ch_num, sec_num, sub_num, title
        )
        if not body:
            body = raw.strip()
        if not summary:
            summary = _first_paragraph(body)

        h = _content_hash([body, lo, summary, ancillary])

        chunks.append(
            TextbookChunkRecord(
                chunk_id=chunk_id,
                book_id=book_id,
                chapter_num=ch_num,
                section_num=sec_num,
                subsection_num=sub_num,
                title=title,
                summary=summary,
                content=body,
                learning_objectives=lo,
                ancillary_content=ancillary,
                content_hash=h,
                page_start=start_page,
                page_end=end_page,
            )
        )

        for pg in range(start_page, min(end_page + 1, len(doc))):
            page = doc[pg]
            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                try:
                    base_img = doc.extract_image(xref)
                    if base_img and base_img["image"]:
                        cap, alt = _caption_for_image(page, xref)
                        img_id = f"{chunk_id}_pg{pg}_img{img_idx}"
                        images.append(
                            ExtractedImage(
                                image_id=img_id,
                                chunk_id=chunk_id,
                                page_num=pg,
                                image_bytes=base_img["image"],
                                ext=base_img.get("ext", "png"),
                                caption=cap,
                                alt_text=alt,
                            )
                        )
                except Exception:
                    logger.debug("image_extraction_failed", xref=xref, page=pg)

    doc.close()
    logger.info("extraction_complete", chunks=len(chunks), images=len(images))
    return chunks, images


def _normalize_toc(toc_entries: list) -> list[dict]:
    """Convert raw PyMuPDF TOC into normalized entries with chapter/section."""
    result: list[dict] = []
    current_chapter: int | None = None

    for level, title, page_num in toc_entries:
        page_idx = max(0, page_num - 1)
        title_clean = title.strip()

        ch_match = _CHAPTER_RE.match(title_clean)
        sec_match = _SECTION_RE.match(title_clean)

        if ch_match:
            current_chapter = int(ch_match.group(1))
            result.append({
                "level": level,
                "title": title_clean,
                "page": page_idx,
                "chapter": current_chapter,
                "section": None,
                "subsection": None,
            })
        elif sec_match and current_chapter is not None:
            ch = int(sec_match.group(1))
            sec = int(sec_match.group(2))
            sec_title = sec_match.group(3).strip()
            if ch != current_chapter:
                current_chapter = ch
            result.append({
                "level": level,
                "title": sec_title,
                "page": page_idx,
                "chapter": ch,
                "section": sec,
                "subsection": None,
            })
        elif current_chapter is not None and level >= 3:
            result.append({
                "level": level,
                "title": title_clean,
                "page": page_idx,
                "chapter": current_chapter,
                "section": result[-1].get("section") if result else None,
                "subsection": level - 2,
            })

    return result


def _build_toc_from_pages(doc) -> list:
    """Fallback: scan pages for chapter headings when PDF has no embedded TOC."""
    toc = []
    for pg_num in range(len(doc)):
        text = doc[pg_num].get_text("text")
        for line in text.split("\n")[:5]:
            line = line.strip()
            ch_match = _CHAPTER_RE.match(line)
            if ch_match:
                toc.append((1, line, pg_num + 1))
                break
            sec_match = _SECTION_RE.match(line)
            if sec_match:
                toc.append((2, line, pg_num + 1))
                break
    return toc
