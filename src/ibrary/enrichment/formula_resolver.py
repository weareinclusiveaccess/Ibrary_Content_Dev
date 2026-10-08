"""Extract and normalize LaTeX formulas (math + chemistry \\ce{})."""

from __future__ import annotations

import json
import re

import structlog

from ibrary.config import CURATION_MAX_FORMULAS, OPENAI_ENRICHMENT_MODEL, PIPELINE_SUBJECT
from ibrary.curation.schemas import FormulaRef
from ibrary.llm.client import chat_completion_json

logger = structlog.get_logger(__name__)

FORMULA_SYSTEM = """\
You extract scientific notation from lesson text for KaTeX rendering (with mhchem for chemistry).
Return JSON only.

Rules:
- **chemistry** kind: use `\\ce{...}` in latex (e.g. `\\ce{H2O}`, `\\ce{CO2}`, `\\ce{C6H12O12}`).
- **math** kind: standard LaTeX (ratios, scientific notation like `6.02 \\times 10^{23}`).
- plain_text: how it appears in the lesson before formatting.
- spoken_text: how a teacher would read it aloud for screen readers.
- Only include formulas/equations that appear in or are clearly implied by the lesson (max {max_formulas}).
- Do not invent chemistry not supported by the text.
"""

FORMULA_USER = """\
**Subject:** {subject}
**Subtopic:** {subtopic}

## Lesson markdown
{content}

Return JSON:
{{
  "formulas": [
    {{
      "formula_id": "f001",
      "kind": "chemistry",
      "latex": "\\\\ce{CO2}",
      "plain_text": "CO2",
      "spoken_text": "C O 2",
      "confidence": 0.9
    }}
  ]
}}
"""


# Quick pass for common biology tokens if LLM returns empty
_CHEM_PATTERNS = [
    (r"\bCO2\b", "chemistry", r"\ce{CO2}", "CO2"),
    (r"\bCO₂\b", "chemistry", r"\ce{CO2}", "CO₂"),
    (r"\bH2O\b", "chemistry", r"\ce{H2O}", "H2O"),
    (r"\bH₂O\b", "chemistry", r"\ce{H2O}", "H₂O"),
    (r"\bO2\b", "chemistry", r"\ce{O2}", "O2"),
    (r"\bO₂\b", "chemistry", r"\ce{O2}", "O₂"),
    (r"\bNH3\b", "chemistry", r"\ce{NH3}", "NH3"),
    (r"\bCH4\b", "chemistry", r"\ce{CH4}", "CH4"),
    (r"\bATP\b", "chemistry", r"\ce{ATP}", "ATP"),
    (r"\bDNA\b", "chemistry", r"\text{DNA}", "DNA"),
    (r"\bRNA\b", "chemistry", r"\text{RNA}", "RNA"),
]


def _heuristic_formulas(content: str) -> list[FormulaRef]:
    found: list[FormulaRef] = []
    seen: set[str] = set()
    for pattern, kind, latex, plain in _CHEM_PATTERNS:
        if re.search(pattern, content) and plain not in seen:
            seen.add(plain)
            fid = f"f{len(found) + 1:03d}"
            found.append(
                FormulaRef(
                    formula_id=fid,
                    kind=kind,
                    latex=latex,
                    plain_text=plain,
                    spoken_text=plain.replace("2", " two ").replace("3", " three "),
                    source="heuristic",
                    confidence=0.7,
                )
            )
            if len(found) >= CURATION_MAX_FORMULAS:
                break
    return found


def resolve_formulas(
    *,
    curriculum_unit_id: str,
    subtopic: str,
    curated_content: str,
    placeholders: list[dict] | None = None,
    allow_heuristic: bool = False,
) -> tuple[list[FormulaRef], list[dict]]:
    """Extract formulas from lesson body (+ optional placeholders)."""
    if not placeholders and not allow_heuristic:
        return [], []

    content = curated_content[:10000]
    formulas: list[FormulaRef] = []

    try:
        raw = chat_completion_json(
            component="formula_resolver",
            model=OPENAI_ENRICHMENT_MODEL,
            system=FORMULA_SYSTEM.format(max_formulas=CURATION_MAX_FORMULAS),
            user=FORMULA_USER.format(
                subject=PIPELINE_SUBJECT,
                subtopic=subtopic,
                content=content,
            ),
            metadata={"curriculum_unit_id": curriculum_unit_id},
        )
        for i, item in enumerate(raw.get("formulas", [])[:CURATION_MAX_FORMULAS]):
            kind = item.get("kind", "math")
            latex = (item.get("latex") or "").strip()
            if kind == "chemistry" and latex and not latex.startswith("\\ce"):
                inner = latex.removeprefix("\\ce{").removesuffix("}")
                latex = f"\\ce{{{inner}}}"
            formulas.append(
                FormulaRef(
                    formula_id=item.get("formula_id") or f"f{i + 1:03d}",
                    kind=kind,
                    latex=latex,
                    plain_text=item.get("plain_text", ""),
                    spoken_text=item.get("spoken_text", ""),
                    source="generated",
                    confidence=float(item.get("confidence", 0.85)),
                )
            )
    except Exception as exc:
        logger.warning("formula_llm_failed", unit_id=curriculum_unit_id, error=str(exc))

    if not formulas and allow_heuristic:
        formulas = _heuristic_formulas(content)

    resolution = [{"formula_id": f.formula_id, "kind": f.kind, "source": f.source} for f in formulas]
    logger.info("formula_resolver_done", unit_id=curriculum_unit_id, count=len(formulas))
    return formulas, resolution
