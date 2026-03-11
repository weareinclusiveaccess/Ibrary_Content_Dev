"""Extract textbook content from Biology2e-WEB.pdf into structured chunks.

The parser reads the PDF, identifies chapters/sections/subsections via the
table of contents, and yields TextbookChunkRecord objects ready for DB insert.
"""

from __future__ import annotations

import hashlib
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


# Biology2e TOC patterns
_CHAPTER_RE = re.compile(r"^Chapter\s+(\d+)", re.IGNORECASE)
_SECTION_RE = re.compile(r"^(\d+)\.(\d+)\s+(.+)")


def _make_chunk_id(book_id: str, ch: int, sec: int | None = None, sub: int | None = None) -> str:
    parts = [book_id, f"ch{ch}"]
    if sec is not None:
        parts.append(f"sec{sec}")
    if sub is not None:
        parts.append(f"sub{sub}")
    return "_".join(parts)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _first_paragraph(text: str) -> str:
    """Return the first meaningful paragraph as a summary fallback."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 50]
    return paragraphs[0] if paragraphs else text[:500]


def extract_biology2e(
    pdf_path: str | Path,
    book_id: str = "bio2e",
) -> tuple[list[TextbookChunkRecord], list[ExtractedImage]]:
    """Extract chapters and sections from Biology2e-WEB.pdf.

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
        level, title, start_page = entry["level"], entry["title"], entry["page"]
        end_page = entries[i + 1]["page"] - 1 if i + 1 < len(entries) else len(doc) - 1

        ch_num = entry.get("chapter")
        sec_num = entry.get("section")
        sub_num = entry.get("subsection")

        if ch_num is None:
            continue

        text_parts = []
        for pg in range(start_page, min(end_page + 1, len(doc))):
            text_parts.append(doc[pg].get_text("text"))
        content = "\n".join(text_parts).strip()

        if not content:
            continue

        chunk_id = _make_chunk_id(book_id, ch_num, sec_num, sub_num)
        summary = _first_paragraph(content)

        chunks.append(
            TextbookChunkRecord(
                chunk_id=chunk_id,
                book_id=book_id,
                chapter_num=ch_num,
                section_num=sec_num,
                subsection_num=sub_num,
                title=title,
                summary=summary,
                content=content,
                content_hash=_content_hash(content),
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
                        img_id = f"{chunk_id}_pg{pg}_img{img_idx}"
                        images.append(
                            ExtractedImage(
                                image_id=img_id,
                                chunk_id=chunk_id,
                                page_num=pg,
                                image_bytes=base_img["image"],
                                ext=base_img.get("ext", "png"),
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
