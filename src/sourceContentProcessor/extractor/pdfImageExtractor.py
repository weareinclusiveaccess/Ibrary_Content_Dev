"""
Extract embedded images from PDF files using PyMuPDF (fitz).

Saves images to a directory and returns (page_index, path) for association
with document structure by page.
"""

from pathlib import Path

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def extract_pdf_images_to_dir(
    pdf_path: str | Path,
    output_dir: str | Path,
    name_prefix: str = "page",
) -> list[tuple[int, str]]:
    """
    Extract all embedded images from a PDF and save to output_dir.

    Args:
        pdf_path: Path to the .pdf file.
        output_dir: Directory to write image files (e.g. extracted_notes/img).
        name_prefix: Prefix for filenames (e.g. page_07_image_0.png).

    Returns:
        List of (page_index_0based, filename) in document order, e.g.
        [(0, 'page_00_image_0.png'), (1, 'page_01_image_0.png')].
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError("PyMuPDF (fitz) is required for PDF image extraction. Install with: pip install pymupdf")

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result: list[tuple[int, str]] = []
    extracted_xrefs: dict[int, str] = {}  # xref -> filename, to avoid writing same image twice
    doc = fitz.open(pdf_path)
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                if xref in extracted_xrefs:
                    result.append((page_num, extracted_xrefs[xref]))
                    continue
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue
                img_bytes = base_image["image"]
                ext = base_image["ext"]
                if not ext or ext == "unknown":
                    ext = "png"
                filename = f"{name_prefix}_{page_num:02d}_image_{img_index}.{ext}"
                out_path = output_dir / filename
                out_path.write_bytes(img_bytes)
                extracted_xrefs[xref] = filename
                result.append((page_num, filename))
    finally:
        doc.close()
    return result
