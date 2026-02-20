r"""
Extract embedded images from RTF files (\pict groups) and save to disk.

Supports \pngblip and \jpegblip (hex-encoded data). Returns ordered list of
saved file paths for association with document structure.
"""

import binascii
import re
from pathlib import Path


def _find_pict_groups(rtf_content: str) -> list[tuple[int, int, str]]:
    """
    Find each \\pict... group in RTF. Returns list of (start, end, blob) where
    blob is the full group content including {\\pict... }.
    """
    # RTF groups: { ... } so we need to find {\pict and match braces to get the group
    result = []
    pos = 0
    while True:
        m = re.search(r"\{\\pict", rtf_content[pos:], re.I | re.DOTALL)
        if not m:
            break
        start = pos + m.start()
        depth = 1
        i = pos + m.end()
        while i < len(rtf_content) and depth > 0:
            if rtf_content[i] == "{":
                depth += 1
            elif rtf_content[i] == "}":
                depth -= 1
            i += 1
        end = i
        blob = rtf_content[start:end]
        result.append((start, end, blob))
        pos = end
    return result


def _extract_hex_from_pict(blob: str) -> tuple[bytes | None, str]:
    """
    Extract image bytes from a \\pict group. Returns (bytes, ext) or (None, '').
    Handles \\pngblip and \\jpegblip with hex data.
    """
    blob_lower = blob.lower()
    if "\\pngblip" in blob_lower:
        ext = "png"
        magic = "89504e47"  # PNG signature in hex
    elif "\\jpegblip" in blob_lower or "\\jpeggblip" in blob_lower:
        ext = "jpg"
        magic = "ffd8ff"  # JPEG signature in hex
    else:
        return None, ""

    # Find magic bytes in blob to locate start of hex payload (after control words)
    blob_hex_clean = re.sub(r"[^0-9a-fA-F]", "", blob)
    idx = blob_hex_clean.lower().find(magic)
    if idx < 0:
        # Fallback: take first long run of hex
        hex_match = re.search(r"([0-9a-fA-F]{2}\s*)+", blob)
        if not hex_match:
            return None, ""
        hex_str = re.sub(r"\s+", "", hex_match.group(0))
    else:
        # From magic to end of hex (all hex chars in blob after magic start)
        hex_str = blob_hex_clean[idx:]
    if len(hex_str) % 2 != 0:
        hex_str = hex_str[:-1]
    if len(hex_str) < 20:
        return None, ""
    try:
        data = binascii.unhexlify(hex_str)
    except binascii.Error:
        return None, ""
    if ext == "png" and not data.startswith(b"\x89PNG"):
        return None, ""
    if ext == "jpg" and not data.startswith(b"\xff\xd8\xff"):
        return None, ""
    return data, ext


def extract_rtf_images_to_dir(
    rtf_path: str | Path,
    output_dir: str | Path,
    name_prefix: str = "image",
) -> list[str]:
    """
    Extract all embedded images from an RTF file and save to output_dir.

    Args:
        rtf_path: Path to the .rtf file.
        output_dir: Directory to write image files (e.g. extracted_notes/img).
        name_prefix: Prefix for filenames (e.g. image_001.png).

    Returns:
        List of relative paths (e.g. ['image_001.png', 'image_002.jpg']) in document order.
    """
    rtf_path = Path(rtf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rtf_bytes = rtf_path.read_bytes()
    try:
        rtf_content = rtf_bytes.decode("cp1252", errors="replace")
    except Exception:
        rtf_content = rtf_bytes.decode("utf-8", errors="replace")

    pict_groups = _find_pict_groups(rtf_content)
    saved_paths: list[str] = []
    for i, (_start, _end, blob) in enumerate(pict_groups):
        data, ext = _extract_hex_from_pict(blob)
        if data is None:
            continue
        num = len(saved_paths) + 1
        filename = f"{name_prefix}_{num:03d}.{ext}"
        out_path = output_dir / filename
        out_path.write_bytes(data)
        saved_paths.append(filename)
    return saved_paths
