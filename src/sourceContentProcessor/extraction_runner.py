"""
Extraction runners for RTF/PDF and for biology notes (.md + .rtf/.pdf).

Notebooks can use:
    from sourceContentProcessor.extraction_runner import ExtractionRunner, extract_file
    from sourceContentProcessor.extraction_runner import extract_biology_notes, run_notes_extraction
"""

from pathlib import Path

from sourceContentProcessor.extractor.rtfExtractor import RTFExtractor, extract_rtf_to_json
from sourceContentProcessor.extractor.notesExtractor import extract_biology_notes

# Alias for backward compatibility
ExtractionRunner = RTFExtractor


def extract_file(
    file_path: str | Path,
    output_path: str | Path | None = None,
    base_dir: Path | None = None,
    **kwargs,
):
    """
    Extract content from a single file (RTF or PDF).
    Uses RTFExtractor for .rtf; for .pdf returns text via existing PDF extractor if needed.
    """
    runner = RTFExtractor()
    if base_dir is not None:
        runner.base_dir = Path(base_dir)
    return runner.extract(file_path, output_path=output_path, **kwargs)


def run_notes_extraction(
    md_path: str | Path | None = None,
    rtf_path: str | Path | None = None,
    pdf_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    base_dir: Path | None = None,
) -> dict:
    """
    Run biology notes extraction from .md with optional .rtf/.pdf for images.

    Default paths (when base_dir is None) use project root and:
      md_path: docs/extracted_source_content/Notes/1ST TERM S1 BIOLOGY.docx (1).md
      rtf_path: docs/extracted_source_content/Notes/1ST TERM S1 BIOLOGY.rtf
      output_dir: docs/extracted_source_content/biology/extracted_notes

    Returns the extracted structure (dict).
    """
    base = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent.parent
    docs = base / "docs" / "extracted_source_content"
    notes_dir = docs / "Notes"
    if md_path is None:
        md_path = notes_dir / "1ST TERM S1 BIOLOGY.docx (1).md"
    if rtf_path is None:
        rtf_path = notes_dir / "1ST TERM S1 BIOLOGY.rtf"
    if output_dir is None:
        output_dir = docs / "biology" / "extracted_notes"
    return extract_biology_notes(
        md_path=md_path,
        output_dir=output_dir,
        rtf_path=rtf_path,
        pdf_path=pdf_path,
    )


__all__ = [
    "ExtractionRunner",
    "extract_file",
    "extract_biology_notes",
    "run_notes_extraction",
]
