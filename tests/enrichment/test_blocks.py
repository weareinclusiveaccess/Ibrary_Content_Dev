"""Tests for markdown blocks and formula heuristics."""

from ibrary.enrichment.blocks import apply_latex_to_markdown, markdown_to_blocks
from ibrary.enrichment.formula_resolver import _heuristic_formulas
from ibrary.curation.schemas import FormulaRef


def test_markdown_to_blocks_headings():
    md = "## Intro\n\nHello world.\n\n### Detail\n\nMore text."
    blocks = markdown_to_blocks(md)
    types = [b["type"] for b in blocks]
    assert "heading" in types
    assert "paragraph" in types


def test_heuristic_co2():
    formulas = _heuristic_formulas("Plants release CO2 during respiration.")
    assert any(f.plain_text == "CO2" and f.kind == "chemistry" for f in formulas)


def test_apply_latex_replaces_plain_text():
    formulas = [
        FormulaRef(
            formula_id="f001",
            kind="chemistry",
            latex=r"\ce{CO2}",
            plain_text="CO2",
        )
    ]
    out = apply_latex_to_markdown("Plants use CO2.", formulas)
    assert r"\ce{CO2}" in out
    assert "CO2" not in out or "$" in out
