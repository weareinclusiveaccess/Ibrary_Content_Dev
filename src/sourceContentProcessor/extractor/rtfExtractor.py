"""
Extract content from RTF files (e.g. scheme of work / term notes) into a structured JSON.

Output format:
  subject, class, term, weeks[]
  each week: week_topic, subtopics[{ title, content }], images[], tables[]
"""

import json
import re
from pathlib import Path


def _rtf_to_plain_text(rtf_content: str, encoding: str = "cp1252") -> str:
    """Convert RTF byte/string content to plain text using striprtf."""
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError as e:
        raise ImportError(
            "striprtf is required for RTF extraction. Install with: pip install striprtf"
        ) from e

    if isinstance(rtf_content, bytes):
        rtf_content = rtf_content.decode(encoding, errors="replace")
    return rtf_to_text(rtf_content, encoding=encoding, errors="replace")


def _infer_metadata_from_filename(path: Path) -> tuple[str, str, str]:
    """Infer subject, class, term from filename like '1ST TERM S1 BIOLOGY.rtf'."""
    stem = path.stem.upper()
    subject = "Biology"
    class_name = "SSS 1"
    term = "1"

    # Term: "1ST TERM" -> 1, "2ND TERM" -> 2, "3RD TERM" -> 3
    term_match = re.search(r"(1ST|2ND|3RD|FIRST|SECOND|THIRD|1|2|3)\s*TERM", stem, re.I)
    if term_match:
        t = term_match.group(1).upper()
        if t in ("1ST", "FIRST"):
            term = "1"
        elif t in ("2ND", "SECOND"):
            term = "2"
        elif t in ("3RD", "THIRD"):
            term = "3"

    # Class: S1, SSS 1, SS1, etc.
    class_match = re.search(r"\b(S\d|SSS\s*\d|SS\s*\d)\b", stem, re.I)
    if class_match:
        class_name = class_match.group(1).replace(" ", "").upper()
        if class_name.startswith("S") and len(class_name) <= 3:
            class_name = "SSS " + class_name[-1] if class_name[-1].isdigit() else class_name

    # Subject: often at end, e.g. BIOLOGY
    for subj in ("BIOLOGY", "CHEMISTRY", "PHYSICS", "MATHEMATICS", "ENGLISH"):
        if subj in stem:
            subject = subj.capitalize()
            break

    return subject, class_name, term


def _parse_header_for_metadata(plain_text: str) -> tuple[str | None, str | None, str | None]:
    """Parse first ~1500 chars for 'Subject:', 'Class:', 'Term:' or scheme header."""
    header = plain_text[:1500]
    subject = class_name = term = None

    # "Class : SSS 1" or "Class: SSS 1"
    m = re.search(r"Class\s*:\s*([^\n]+)", header, re.I)
    if m:
        class_name = m.group(1).strip()
    # "Term : 1" or "Term: 1"
    m = re.search(r"Term\s*:\s*(\d+)", header, re.I)
    if m:
        term = m.group(1).strip()
    # Subject often in title "BIOLOGY SCHEME OF WORK"
    m = re.search(r"(\w+)\s+SCHEME\s+OF\s+WORK", header, re.I)
    if m:
        subject = m.group(1).strip().capitalize()

    return subject, class_name, term


def _week_title_to_number(title: str) -> int:
    """Map 'WEEK ONE' / 'Week 1' to week number."""
    title = title.upper().strip()
    # "WEEK ONE", "WEEK TWO", ...
    words = {
        "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
        "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10,
        "ELEVEN": 11, "TWELVE": 12,
    }
    for w, n in words.items():
        if w in title:
            return n
    m = re.search(r"WEEK\s*(\d+)", title, re.I)
    if m:
        return int(m.group(1))
    return 0


def _split_by_weeks(plain_text: str) -> list[tuple[int, str, str]]:
    """Split document into (week_number, week_heading, content) blocks."""
    # Match "WEEK ONE", "WEEK TWO", ... or "Week 1", "Week 2"
    week_pattern = re.compile(
        r"(WEEK\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|\d+)(?:\s*[-–]\s*[^\n]+)?)",
        re.IGNORECASE,
    )
    parts = []
    last_end = 0
    for match in week_pattern.finditer(plain_text):
        start = match.start()
        if start > last_end:
            # Content before first week (e.g. table of content) - attach to week 0 or skip
            pass
        heading = match.group(1).strip()
        week_num = _week_title_to_number(heading)
        # Content runs until next week match or end
        next_match = week_pattern.search(plain_text, match.end())
        if next_match:
            content = plain_text[match.end() : next_match.start()].strip()
        else:
            content = plain_text[match.end() :].strip()
        parts.append((week_num, heading, content))
        last_end = match.end() if not next_match else next_match.start()
    return parts


def _split_week_into_subtopics(content: str) -> list[dict]:
    """Split week content into subtopics with title and content."""
    subtopics = []
    # Split by double newline; first line may be a subtitle/topic
    blocks = re.split(r"\n\s*\n", content)
    current_title = ""
    current_content: list[str] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        first_line = lines[0].strip()
        # Heuristic: short first line (e.g. < 70 chars) and no trailing period = topic title
        if len(first_line) < 70 and not first_line.endswith(".") and len(lines) > 1:
            if current_title or current_content:
                subtopics.append({
                    "subtopic": current_title or "Content",
                    "content": "\n\n".join(current_content).strip(),
                })
            current_title = first_line
            current_content = [("\n".join(lines[1:])).strip()] if len(lines) > 1 else []
        else:
            if current_title:
                current_content.append(block)
            else:
                current_content.append(block)
    if current_title or current_content:
        subtopics.append({
            "subtopic": current_title or "Content",
            "content": "\n\n".join(current_content).strip(),
        })
    return subtopics if subtopics else [{"subtopic": "Content", "content": content}]


def _count_rtf_images_and_tables(rtf_content: str) -> tuple[list[str], list[str]]:
    """Scan RTF source for \\pict (images) and \\trowd (tables). Return placeholders."""
    images: list[str] = []
    tables: list[str] = []

    # Count \pict groups (images)
    pict_starts = [m.start() for m in re.finditer(r"\\pict", rtf_content, re.I)]
    for i, _ in enumerate(pict_starts):
        images.append(f"image_{i + 1}")

    # Count table rows \trowd (each table has at least one)
    trowd_count = len(re.findall(r"\\trowd", rtf_content, re.I))
    for i in range(trowd_count):
        tables.append(f"table_{i + 1}")

    return images, tables


def extract_rtf_to_json(
    rtf_path: str | Path,
    output_json_path: str | Path | None = None,
    encoding: str = "cp1252",
) -> dict:
    """
    Extract content from an RTF file into a structured JSON.

    Output structure:
      subject, class, term, weeks[]
      each week: week_number, week_topic, week_topics (list), subtopics[{ subtopic, content }], images[], tables[]

    Args:
        rtf_path: Path to the .rtf file.
        output_json_path: If provided, write the JSON to this path.
        encoding: Encoding for reading the RTF file (default cp1252).

    Returns:
        The extracted structure as a dict.
    """
    rtf_path = Path(rtf_path)
    if not rtf_path.exists():
        raise FileNotFoundError(f"RTF file not found: {rtf_path}")

    rtf_content = rtf_path.read_bytes()
    plain_text = _rtf_to_plain_text(rtf_content, encoding=encoding)

    # Metadata: prefer header, fallback to filename
    subj_h, class_h, term_h = _parse_header_for_metadata(plain_text)
    subj_f, class_f, term_f = _infer_metadata_from_filename(rtf_path)
    subject = subj_h or subj_f
    class_name = class_h or class_f
    term = term_h or term_f

    # Week blocks
    week_blocks = _split_by_weeks(plain_text)
    if not week_blocks and plain_text.strip():
        # No week headings found: treat whole document as one week
        week_blocks = [(1, "Week 1", plain_text.strip())]

    # Images/tables from raw RTF (whole document for now)
    rtf_str = rtf_content.decode(encoding, errors="replace")
    images_global, tables_global = _count_rtf_images_and_tables(rtf_str)

    weeks_out = []
    for week_num, week_heading, content in week_blocks:
        # Week topic: text after "WEEK N - " or the full heading
        week_topic_match = re.search(r"WEEK\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|\d+)\s*[-–]\s*(.+)", week_heading, re.I)
        week_topic = week_topic_match.group(1).strip() if week_topic_match else week_heading
        week_topics = [week_topic] if week_topic else []

        subtopics = _split_week_into_subtopics(content)
        # Per-week we don't have image/table positions; use empty or proportional placeholder
        weeks_out.append({
            "week_number": week_num,
            "week_topic": week_topic,
            "week_topics": week_topics,
            "subtopics": subtopics,
            "images": [],
            "tables": [],
        })

    # If we only have global images/tables, attach to first week or leave at root
    result = {
        "subject": subject,
        "class": class_name,
        "term": term,
        "weeks": weeks_out,
        "images": images_global,
        "tables": tables_global,
    }

    if output_json_path is not None:
        out_path = Path(output_json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


# ---------------------------------------------------------------------------
# Extraction runner: paths and single entry point (RTF + PDF) for notebooks
# ---------------------------------------------------------------------------

from typing import Any

_DEFAULT_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class RTFExtractor:
    """Holds base paths and runs extraction for a given file (PDF or RTF)."""

    base_dir: Path = _DEFAULT_BASE_DIR

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is not None:
            self.base_dir = Path(base_dir)

    def resolve_path(self, path: Path | str) -> Path:
        """Resolve a path against base_dir if it is not absolute."""
        p = Path(path)
        return (self.base_dir / p) if not p.is_absolute() else p

    def extract(
        self,
        file_path: Path | str,
        output_path: Path | str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Extract content from a file. Dispatches by extension.

        - .rtf -> extract to JSON (subject, class, term, weeks with subtopics, images, tables).
          Writes to output_path or same dir as file with .json suffix. Returns the extracted dict.
         Args:
            file_path: Path to the file to extract (relative to base_dir or absolute).
            output_path: For RTF, path of the output JSON; default is file_path with .json.
            **kwargs: Passed to the underlying extractor (e.g. encoding for RTF).

        Returns:
            For RTF: dict (subject, class, term, weeks, images, tables).
            For PDF: list of Document.
        """
        path = self.resolve_path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".rtf":
            out = Path(output_path) if output_path else path.with_suffix(".json")
            return extract_rtf_to_json(path, output_json_path=out, **kwargs)


