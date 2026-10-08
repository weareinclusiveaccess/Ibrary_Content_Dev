"""CAST UDL Guidelines v3.0 checkpoints (source: udlg3 graphic organizer PDF).

Reference: data/docs/udlg3-graphicorganizer-digital-numbers-a11y.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UdlCheckpoint:
    """Single scorable UDL v3 design option."""

    id: str
    principle: str
    category: str
    label: str
    cast_guideline: str  # top-level guideline number: 1–9


# Human-readable CAST principle names (three UDL principles)
PRINCIPLE_DISPLAY: dict[str, str] = {
    "engagement": "Engagement",
    "representation": "Representation",
    "action_expression": "Action & Expression",
}

# Organized by principle → category per CAST v3.0
UDL_V3_CHECKPOINTS: tuple[UdlCheckpoint, ...] = (
    UdlCheckpoint("7.1", "engagement", "recruiting_interest", "Optimize choice and autonomy", "7"),
    UdlCheckpoint("7.2", "engagement", "recruiting_interest", "Optimize relevance, value, and authenticity", "7"),
    UdlCheckpoint("7.3", "engagement", "recruiting_interest", "Nurture joy and play", "7"),
    UdlCheckpoint("7.4", "engagement", "recruiting_interest", "Address biases, threats, and distractions", "7"),
    UdlCheckpoint("8.1", "engagement", "sustaining_effort", "Clarify the meaning and purpose of goals", "8"),
    UdlCheckpoint("8.2", "engagement", "sustaining_effort", "Optimize challenge and support", "8"),
    UdlCheckpoint("8.3", "engagement", "sustaining_effort", "Foster collaboration and collective learning", "8"),
    UdlCheckpoint("8.4", "engagement", "sustaining_effort", "Foster belonging and community", "8"),
    UdlCheckpoint("8.5", "engagement", "sustaining_effort", "Offer action-oriented feedback", "8"),
    UdlCheckpoint("9.1", "engagement", "emotional_capacity", "Recognize expectations, beliefs, and motivations", "9"),
    UdlCheckpoint("9.2", "engagement", "emotional_capacity", "Develop awareness of self and others", "9"),
    UdlCheckpoint("9.3", "engagement", "emotional_capacity", "Promote individual and collective reflection", "9"),
    UdlCheckpoint("9.4", "engagement", "emotional_capacity", "Cultivate empathy and restorative practices", "9"),
    UdlCheckpoint("1.1", "representation", "perception", "Customize the display of information", "1"),
    UdlCheckpoint("1.2", "representation", "perception", "Support multiple ways to perceive information", "1"),
    UdlCheckpoint("1.3", "representation", "perception", "Represent diverse perspectives and identities", "1"),
    UdlCheckpoint("2.1", "representation", "language_symbols", "Clarify vocabulary, symbols, and language structures", "2"),
    UdlCheckpoint("2.2", "representation", "language_symbols", "Support decoding of text, math notation, and symbols", "2"),
    UdlCheckpoint("2.3", "representation", "language_symbols", "Cultivate understanding across languages and dialects", "2"),
    UdlCheckpoint("2.4", "representation", "language_symbols", "Address biases in language and symbols", "2"),
    UdlCheckpoint("2.5", "representation", "language_symbols", "Illustrate through multiple media", "2"),
    UdlCheckpoint("3.1", "representation", "building_knowledge", "Connect prior knowledge to new learning", "3"),
    UdlCheckpoint("3.2", "representation", "building_knowledge", "Highlight patterns, critical features, and big ideas", "3"),
    UdlCheckpoint("3.3", "representation", "building_knowledge", "Cultivate multiple ways of knowing", "3"),
    UdlCheckpoint("3.4", "representation", "building_knowledge", "Maximize transfer and generalization", "3"),
    UdlCheckpoint("4.1", "action_expression", "interaction", "Vary methods for response, navigation, and movement", "4"),
    UdlCheckpoint("4.2", "action_expression", "interaction", "Optimize assistive technologies and accessible tools", "4"),
    UdlCheckpoint("5.1", "action_expression", "expression", "Use multiple media for communication", "5"),
    UdlCheckpoint("5.2", "action_expression", "expression", "Use multiple tools for construction and creativity", "5"),
    UdlCheckpoint("5.3", "action_expression", "expression", "Build fluencies with graduated support", "5"),
    UdlCheckpoint("5.4", "action_expression", "expression", "Address biases in modes of expression", "5"),
    UdlCheckpoint("6.1", "action_expression", "strategy", "Set meaningful goals", "6"),
    UdlCheckpoint("6.2", "action_expression", "strategy", "Anticipate and plan for challenges", "6"),
    UdlCheckpoint("6.3", "action_expression", "strategy", "Organize information and resources", "6"),
    UdlCheckpoint("6.4", "action_expression", "strategy", "Enhance capacity for monitoring progress", "6"),
    UdlCheckpoint("6.5", "action_expression", "strategy", "Challenge exclusionary practices", "6"),
)


def _checkpoint_entry(cp: UdlCheckpoint) -> dict[str, str]:
    return {
        "checkpoint_id": cp.id,
        "principle": cp.principle,
        "principle_display": PRINCIPLE_DISPLAY[cp.principle],
        "cast_guideline": cp.cast_guideline,
        "category": cp.category,
        "measures": cp.label,
    }


# Lookup: checkpoint_id → metadata (principle, what it measures, CAST guideline)
CHECKPOINT_BY_ID: dict[str, dict[str, str]] = {
    cp.id: _checkpoint_entry(cp) for cp in UDL_V3_CHECKPOINTS
}


def get_checkpoint(checkpoint_id: str) -> dict[str, str] | None:
    """Return rubric metadata for a CAST checkpoint id (e.g. ``\"2.1\"``)."""
    return CHECKPOINT_BY_ID.get(checkpoint_id)


def rubric_summary_for_prompt() -> str:
    """Compact checklist text for LLM judge system prompt."""
    lines = ["CAST UDL Guidelines v3.0 — score each checkpoint 1–10 (present & quality):"]
    current_principle = ""
    for cp in UDL_V3_CHECKPOINTS:
        if cp.principle != current_principle:
            current_principle = cp.principle
            lines.append(f"\n## {PRINCIPLE_DISPLAY[cp.principle]}")
        lines.append(
            f"- [{cp.id}] (Guideline {cp.cast_guideline}) {cp.label}"
        )
    return "\n".join(lines)


def export_rubric_json() -> list[dict[str, Any]]:
    """Full rubric as JSON-serializable rows (for docs, APIs, UI)."""
    return [dict(_checkpoint_entry(cp)) for cp in UDL_V3_CHECKPOINTS]
