"""LLM judging against CAST UDL v3.0 — callable whenever text is available."""

from ibrary.judging.prompts import get_judge_prompt_version
from ibrary.judging.rubric import (
    CHECKPOINT_BY_ID,
    PRINCIPLE_DISPLAY,
    UDL_V3_CHECKPOINTS,
    export_rubric_json,
    get_checkpoint,
    rubric_summary_for_prompt,
)
from ibrary.judging.schemas import CheckpointScore, SubtopicJudgeInput, SubtopicJudgeResult
from ibrary.judging.subtopic_judge import (
    DEFAULT_PASS_THRESHOLD,
    append_evaluation_result,
    enrich_checkpoint_scores,
    evaluate_all_curated,
    evaluate_content,
    evaluate_subtopic,
    evaluate_subtopics,
    evaluate_text,
    load_evaluation_unit_ids,
    module_to_judge_input,
    save_evaluation_report,
)

__all__ = [
    "DEFAULT_PASS_THRESHOLD",
    "CHECKPOINT_BY_ID",
    "PRINCIPLE_DISPLAY",
    "UDL_V3_CHECKPOINTS",
    "CheckpointScore",
    "SubtopicJudgeInput",
    "SubtopicJudgeResult",
    "enrich_checkpoint_scores",
    "evaluate_content",
    "evaluate_subtopic",
    "evaluate_subtopics",
    "evaluate_all_curated",
    "append_evaluation_result",
    "load_evaluation_unit_ids",
    "evaluate_text",
    "export_rubric_json",
    "get_checkpoint",
    "module_to_judge_input",
    "rubric_summary_for_prompt",
    "save_evaluation_report",
]
