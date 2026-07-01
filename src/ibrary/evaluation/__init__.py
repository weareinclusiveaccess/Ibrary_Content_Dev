"""Deprecated: use ``ibrary.judging`` instead."""

from ibrary.judging import (
    evaluate_content,
    evaluate_subtopics,
    evaluate_text,
    save_evaluation_report,
)

evaluate_all = evaluate_subtopics
save_evaluation = save_evaluation_report

__all__ = [
    "evaluate_all",
    "evaluate_content",
    "evaluate_subtopics",
    "evaluate_text",
    "save_evaluation",
    "save_evaluation_report",
]
