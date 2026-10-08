"""
Parse biology/scheme-of-work markdown notes into JSON.

Rules:
  - #  = week (week title is the rest of the line)
  - ## = subtopic_title; subtopic content = everything after that line until the next ## (or next #)
  - Markdown tables (| a | b | \\n| ----- | ----- |\\n| c | d |) are parsed to list of dicts (headers as keys),
    numbered as tables, and replaced in content with "table-placeholder: N".
  - Lines that are figure/image headings (### DIAGRAM ..., ### FIGURE ..., etc.) are replaced in content with
    "figure-placeholder: N"; each subtopic has a "figures" list of {"figure_number": N}.
  - ## headers that contain ASSIGNMENT and WEEK are assignment blocks (level-2); they are not subtopics but
    go into week["assignments"] as {heading, content, tables, figures}. Week one has no assignment when
    the assignment is merged (e.g. "ASSIGNMENT WEEK ONE AND TWO" appears in week 2's body).

Skips TABLE OF CONTENTS. Strips trailing page numbers (tab + digits) from titles.
"""

import re
from pathlib import Path


# --- Markdown table detection and parsing ---

def _is_table_row(line: str) -> bool:
    """True if line looks like a markdown table row: starts with | and has at least one more |."""
    s = line.strip()
    return len(s) >= 2 and s.startswith("|") and "|" in s[1:]


def _is_separator_line(line: str) -> bool:
    """True if line is a table separator: only |, spaces, dashes, colons."""
    s = line.strip()
    if not s.startswith("|") or not s.endswith("|"):
        return False
    # Each cell (between |) should be only spaces, dashes, colons
    cells = _parse_table_cells(line)
    return all(c and all(ch in " \t-:" for ch in c) for c in cells)


def _parse_table_cells(line: str) -> list[str]:
    """Split a table row into cell strings (strip each). | a | b | c | -> ['a','b','c']."""
    s = line.strip()
    if not s.startswith("|"):
        return []
    parts = s.split("|")
    # parts: ['', ' a ', ' b ', ' c ', ''] -> [1:-1], strip each
    return [p.strip() for p in parts[1:-1]] if len(parts) >= 3 else []


def _parse_table_block(lines: list[str]) -> list[dict] | None:
    """
    Parse a block of lines that form one markdown table.
    First line = header, second = separator, rest = data rows.
    Returns list of dicts with headers as keys, or None if not a valid table.
    """
    if len(lines) < 3:
        return None
    if not _is_separator_line(lines[1]):
        return None
    headers = _parse_table_cells(lines[0])
    if not headers:
        return None
    rows = []
    for i in range(2, len(lines)):
        cells = _parse_table_cells(lines[i])
        if not cells:
            continue
        # Align to header count: pad with '' or truncate
        while len(cells) < len(headers):
            cells.append("")
        row = dict(zip(headers, cells[: len(headers)]))
        rows.append(row)
    return rows


def _extract_tables_from_content(content: str) -> tuple[str, list[dict]]:
    """
    Find all markdown tables in content, parse each to list of dicts, replace with table-placeholder: N.
    Returns (new_content, tables) where tables is [{"table_number": 1, "data": [{"col": "val"}, ...]}, ...].
    """
    if not content.strip():
        return content, []
    lines = content.split("\n")
    tables: list[dict] = []
    result_lines: list[str] = []
    table_number = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _is_table_row(line):
            result_lines.append(line)
            i += 1
            continue
        # Start of a potential table: collect consecutive table rows
        block = [line]
        j = i + 1
        while j < len(lines) and _is_table_row(lines[j]):
            block.append(lines[j])
            j += 1
        parsed = _parse_table_block(block)
        if parsed is not None:
            table_number += 1
            tables.append({"table_number": table_number, "data": parsed})
            result_lines.append(f"table-placeholder: {table_number}")
            i = j
        else:
            result_lines.append(line)
            i += 1
    new_content = "\n".join(result_lines)
    return new_content, tables


# --- Figure/image placeholder detection (### DIAGRAM ..., ### FIGURE ..., etc.) ---

_FIGURE_HEADING_KEYWORDS = ("diagram", "figure", "fig.", "image", "picture", "photo")


def _is_figure_heading_line(line: str) -> bool:
    """True if line is a ### (or more) heading whose text indicates a figure/image."""
    s = line.strip()
    if not s.startswith("###"):
        return False
    rest = _figure_heading_to_caption(line)
    return any(kw in rest.lower() for kw in _FIGURE_HEADING_KEYWORDS)


def _figure_heading_to_caption(line: str) -> str:
    """Extract caption text from a ### figure heading (strip #, anchor, **)."""
    s = line.strip()
    rest = re.sub(r"^#+\s*", "", s)
    rest = re.sub(r"\s*\{#[^}]+\}\s*$", "", rest)
    rest = re.sub(r"\*+", "", rest).strip()
    return rest


def _extract_figures_from_content(content: str) -> tuple[str, list[dict]]:
    """
    Find lines that are figure/image headings (### DIAGRAM ..., ### FIGURE ..., etc.),
    replace each with "figure-placeholder: N", and return (new_content, figures).
    figures is [{"figure_number": 1, "caption": "DIAGRAM OF A MICROSCOPE"}, ...].
    """
    if not content.strip():
        return content, []
    lines = content.split("\n")
    result_lines: list[str] = []
    figures: list[dict] = []
    figure_number = 0
    for line in lines:
        if _is_figure_heading_line(line):
            figure_number += 1
            caption = _figure_heading_to_caption(line)
            figures.append({"figure_number": figure_number, "caption": caption})
            result_lines.append(f"figure-placeholder: {figure_number}")
        else:
            result_lines.append(line)
    return "\n".join(result_lines), figures


# Week title to number (word or digit)
_WEEK_WORDS = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
    "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10,
    "ELEVEN": 11, "TWELVE": 12,
}


def _week_title_to_number(title: str) -> int:
    """Map 'WEEK ONE' / 'Week 1' to week number."""
    upper = title.upper().strip()
    for word, n in _WEEK_WORDS.items():
        if word in upper:
            return n
    m = re.search(r"WEEK\s*(\d+)", upper, re.I)
    if m:
        return int(m.group(1))
    return 0


def _strip_page_number_and_extra(text: str) -> str:
    """Remove trailing tab + page number and extra whitespace."""
    if not text:
        return text
    text = text.strip()
    text = re.sub(r"\t\s*\d+\s*$", "", text)
    return text.strip()


def _clean_heading_text(line: str) -> str:
    """Remove leading #/##, markdown bold, and anchor from heading."""
    line = line.strip()
    # Remove leading # and spaces
    line = re.sub(r"^#+\s*", "", line)
    # Remove {#anchor}
    line = re.sub(r"\s*\{#[^}]+\}\s*$", "", line)
    # Remove **
    line = re.sub(r"\*+", "", line).strip()
    return _strip_page_number_and_extra(line)


def _parse_metadata(lines: list[str]) -> tuple[str, str, str]:
    """Infer subject, class, term from first ~50 lines."""
    subject, class_name, term = "Biology", "SSS 1", "1"
    chunk = "\n".join(lines[:50])
    m = re.search(r"(\w+)\s+SCHEME\s+OF\s+WORK", chunk, re.I)
    if m:
        subject = m.group(1).strip().capitalize()
    m = re.search(r"Class\s*:\s*([^\n*]+)", chunk, re.I)
    if m:
        class_name = re.sub(r"\*+", "", m.group(1).strip())
    m = re.search(r"Term\s*:\s*(\d+)", chunk, re.I)
    if m:
        term = m.group(1).strip()
    return subject, class_name, term


def _is_toc_line(line: str) -> bool:
    """True if line is a TOC link [text](#anchor)."""
    return bool(re.match(r"^\s*\[.+\]\(#.+\)", line.strip()))


def _find_first_week_line(lines: list[str]) -> int:
    """Index of first line that is a week heading: # WEEK N or # WEEK ONE etc."""
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or _is_toc_line(line):
            continue
        if re.match(r"^#\s+\**\**?WEEK\s+(?:\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE)", s, re.I):
            return i
    return 0


def _extract_week_title_from_heading(line: str) -> str:
    """From '# **WEEK 1: BIOLOGY AND INQUIRY** {#...}' get 'BIOLOGY AND INQUIRY'."""
    cleaned = _clean_heading_text(line)
    m = re.match(r"WEEK\s+(?:\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE)\s*[:\-]\s*(.+)", cleaned, re.I)
    if m:
        return m.group(1).strip()
    return cleaned


def _is_assignment_heading(title: str) -> bool:
    """True if this ## header is an assignment (contains ASSIGNMENT and WEEK)."""
    upper = title.upper()
    return "ASSIGNMENT" in upper and "WEEK" in upper


def parse_notes_md(md_path: str | Path) -> dict:
    """
    Parse markdown into JSON: # = week + week title, ## = subtopic_title, content = text until next ##.

    Returns dict with: subject, class, term, weeks[].
    Each week: week_number, week_topic, subtopics[] where each subtopic has subtopic (title) and content.
    """
    path = Path(md_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    start_idx = _find_first_week_line(lines)
    subject, class_name, term = _parse_metadata(lines)

    # Split full content by lines that are week headings: # WEEK N or # WEEK ONE etc. (not every # line)
    week_starts: list[int] = []
    for i in range(start_idx, len(lines)):
        s = lines[i].strip()
        if not s.startswith("# ") or s.startswith("## "):
            continue
        if re.search(r"WEEK\s+(?:\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE)", s, re.I):
            week_starts.append(i)

    weeks_out = []
    for w in range(len(week_starts)):
        start = week_starts[w]
        end = week_starts[w + 1] if w + 1 < len(week_starts) else len(lines)
        week_lines = lines[start:end]

        if not week_lines:
            continue

        # First line is week heading
        week_heading = week_lines[0]
        week_num = _week_title_to_number(week_heading)
        week_topic = _extract_week_title_from_heading(week_heading)

        # Rest of week = body (may contain ## subtopics)
        week_body_lines = week_lines[1:]
        week_body = "\n".join(week_body_lines)

        # Split week body by "## " (double hash + space): each ## starts a subtopic; content = until next ##
        # Pattern: start of line, optional whitespace, ##, space, rest = title. Content = from next line to next ##
        pattern = re.compile(r"(?m)^(##\s+)(.+)$")
        matches = list(pattern.finditer(week_body))

        # Content after # title and before first ## = introduction (empty if no content or no ##)
        introduction = ""
        introduction_tables: list[dict] = []
        if matches:
            introduction = week_body[: matches[0].start()].strip()
        else:
            introduction = week_body.strip()
        if introduction:
            introduction, introduction_tables = _extract_tables_from_content(introduction)

        subtopics_list = []
        assignments_list: list[dict] = []
        for mi, m in enumerate(matches):
            title_raw = m.group(2).strip()
            title_clean = _clean_heading_text("## " + title_raw)
            content_end = matches[mi + 1].start() if mi + 1 < len(matches) else len(week_body)
            content = week_body[m.end() : content_end].strip()
            content, tables = _extract_tables_from_content(content)
            content, figures = _extract_figures_from_content(content)
            if _is_assignment_heading(title_clean):
                assignments_list.append({
                    "heading": title_clean,
                    "content": content,
                    "tables": tables,
                    "figures": figures,
                })
            else:
                subtopics_list.append({
                    "subtopic": title_clean,
                    "content": content,
                    "tables": tables,
                    "figures": figures,
                })

        week_subtopic_titles = [s["subtopic"] for s in subtopics_list]
        week_obj = {
            "week_number": week_num,
            "week_topic": week_topic,
            "introduction": introduction,
            "assignments": assignments_list,
            "week_subtopics": week_subtopic_titles,
            "subtopics": subtopics_list,
        }
        if introduction_tables:
            week_obj["introduction_tables"] = introduction_tables
        weeks_out.append(week_obj)

    return {
        "subject": subject,
        "class": class_name,
        "term": term,
        "weeks": weeks_out,
    }
