"""Prompt contract tests for v2.0-student-self-study curation."""

from ibrary.curation.prompts import (
    CURATION_PROMPT_TEMPLATE,
    PROMPT_VERSION_TAG,
    format_curation_prompt,
    format_system_prompt,
)


def test_prompt_version_tag():
    assert PROMPT_VERSION_TAG == "v2.0-student-self-study"


def test_system_prompt_self_study_audience():
    s = format_system_prompt("Biology").lower()
    assert "self-study" in s or "studying alone" in s
    assert "accessibility notes" in s or "do not" in s


def test_curation_prompt_requires_review_and_check_yourself():
    user = format_curation_prompt(
        "Biology",
        class_name="SSS 1",
        theme="Life",
        theme_number="1",
        topic_number="1",
        topic="Topic",
        subtopic="Subtopic",
        objectives="- obj",
        curriculum_student_activities="(none)",
        curriculum_teacher_activities="(none)",
        alignment_scores="- x: 0.5",
        textbook_content="excerpt",
    )
    lower = user.lower()
    assert "review questions" in lower
    assert "check yourself" in lower


def test_curation_prompt_teacher_activities_cap():
    assert "0–3" in CURATION_PROMPT_TEMPLATE or "0-3" in CURATION_PROMPT_TEMPLATE


def test_curation_prompt_image_and_formula_placeholders():
    lower = CURATION_PROMPT_TEMPLATE.lower()
    assert "image_placeholders" in lower
    assert "formula_placeholders" in lower
