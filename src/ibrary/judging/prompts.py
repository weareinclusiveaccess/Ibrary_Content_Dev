"""Judge prompt templates and version tracking."""

from __future__ import annotations

import hashlib

JUDGE_PROMPT_VERSION_TAG = "v1.0-udl-v3"

JUDGE_SYSTEM_PROMPT = """\
You are a CAST UDL Guidelines v3.0 evaluator for secondary-school learning content.
Score how well the provided **subtopic** teaching content meets each checkpoint (1–10).
Use only evidence from the supplied text and metadata.

Also score two **additional quality dimensions** (1–10 each):
- **correctness**: factual accuracy for **{subject}**, alignment to the stated subtopic and objectives, no \
hallucinations or misleading claims; appropriate level for secondary school.
- **clarity**: readable structure, plain language, logical flow; understandable for diverse \
and low-literacy learners (headings, short sentences, defined terms).
- **self_study**: student can learn the subtopic without a teacher present; no steps that require \
classroom setup, lab, or group work in the main content; excessive bullet lists reduce the score.

{rubric}

Respond with JSON:
{{
  "checkpoint_scores": [{{"checkpoint_id": "7.1", "score": 8, "notes": "..."}}, ...],
  "representation_score": <1-10 average for checkpoints 1.x–3.x>,
  "action_expression_score": <1-10 average for 4.x–6.x>,
  "engagement_score": <1-10 average for 7.x–9.x>,
  "correctness_score": <1-10>,
  "correctness_notes": "<brief justification>",
  "clarity_score": <1-10>,
  "clarity_notes": "<brief justification>",
  "overall_score": <1-10 holistic UDL + quality>,
  "recommendations": ["...", "..."]
}}

Include a score for every checkpoint id listed in the rubric.
"""


JUDGE_USER_TEMPLATE = """\
Evaluate this **subtopic** learning content.

- **Subject:** {subject}
- **Class:** {class_name}
- **Subtopic (content item):** {subtopic}
- **Title:** {title}
- **Learning objectives:** {objectives}
- **Student activities:** {student_activities}
- **Teacher activities:** {teacher_activities}
- **Accessibility checklist:** {accessibility_checklist}

Evaluate **curated_content** as the primary student-facing lesson. Score **self_study** and \
**clarity** from that text; **teacher_activities** are reviewer metadata only unless they contradict the lesson.

## Content to evaluate
{content}

## Key takeaways
{takeaways}

## Glossary
{glossary}
"""


def get_judge_prompt_version() -> str:
    content_hash = hashlib.sha256(
        (JUDGE_SYSTEM_PROMPT + JUDGE_USER_TEMPLATE).encode()
    ).hexdigest()[:8]
    return f"{JUDGE_PROMPT_VERSION_TAG}:{content_hash}"
