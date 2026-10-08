"""UDL curation prompt templates.

All templates use ``{subject}`` (and related placeholders) filled at runtime from
``PIPELINE_SUBJECT`` — see ``ibrary.prompts.context``.

Prompt version is tracked by file path + content hash for reproducibility.
"""

from __future__ import annotations

import hashlib

from ibrary.prompts.context import format_prompt

PROMPT_VERSION_TAG = "v2.0-student-self-study"

SYSTEM_PROMPT_TEMPLATE = """\
You are an expert {subject} author for senior secondary school / high school students. \
You write **self-study lessons** that students read on their own to understand one curriculum \
subtopic. Content follows the Universal Design for Learning (UDL) framework (CAST Guidelines v3.0).

### Primary audience
- **Students studying alone**, including learners using **screen readers** or other assistive technology.
- Reviewers may read the same text to judge quality; do not write separate "teacher lesson plans" inside the student body.

### Writing style (critical)
- **Prose-first:** short paragraphs (2–4 sentences). Use `##` and `###` headings for structure.
- **Engaging and clear:** concrete examples (everyday / local where appropriate). Avoid worksheet or classroom-instruction voice.
- **Minimize lists:** use bullets only when essential (e.g. a short mnemonic). **At most ~6 items** per list. \
No nested bullet farms, no "Activity 1…5" blocks, no long accessibility-variant matrices in the narrative.
- **Forbidden inside `curated_content`:** "Teachers:", "your teacher will…", classroom setup, group/outdoor/lab logistics, \
sorting-game instructions, or a standalone **## Accessibility notes** section.

### UDL (apply through prose, not classroom catalogs)
- **Representation:** plain language, defined terms (glossary), full **text descriptions** for any figure you mention.
- **Comprehension:** connect to prior knowledge; highlight big ideas in sentences, not only bullets.
- **Engagement:** relatable examples; short **Check yourself** prompts (see user instructions).
- **Accessibility:** proper heading hierarchy; never rely on color/layout alone; every diagram/chart is described in words.

### Readability
- Short sentences; roughly US grades 6–8 ease. Scientific terms accurate and glossary-defined.

### Curriculum authority and textbook excerpts (critical)
- The **official curriculum subtopic** is the **primary teaching target**.
- Textbook excerpts are **supporting reference only** (see similarity scores). Prioritize curriculum when excerpts drift.
- Paraphrase excerpts; do not paste large verbatim blocks. Stay scientifically accurate for secondary {subject_lower}.

### Content quality
- **3–5 key takeaways** tied to this subtopic.
- Glossary for key terms.
"""

CURATION_PROMPT_TEMPLATE = """\
Create a **student self-study** module for the curriculum subtopic below. The student reads \
`curated_content` without a teacher present. Follow CAST UDL Guidelines v3.0 through clear prose \
and figure descriptions—not through classroom activity catalogs.

## Curriculum information (authoritative)
- **Subject:** {subject}
- **Class:** {class_name}
- **Theme:** {theme} (Theme {theme_number})
- **Topic {topic_number}:** {topic}
- **Subtopic (content item — align all teaching to this):** {subtopic}

## Topic-level performance objectives (context — not a section checklist)
Use as background only. Output **2–4 learning_objectives** specific to **this subtopic**.

{objectives}

## Official curriculum activities (topic-level — for JSON fields only)
Do **not** copy these as long lists into `curated_content`. Use them to inform optional JSON fields below.

### Student activities (official — topic level)
{curriculum_student_activities}

### Teacher activities (official — topic level; reviewer reference only)
{curriculum_teacher_activities}

## Textbook reference alignment (embedding similarity scores)
{alignment_scores}

## Textbook reference excerpts (supplementary only)
{textbook_content}

---

Produce a **single JSON object** with these exact keys:

- "title": short descriptive title
- "learning_objectives": list of **2–4** subtopic-specific objectives
- "curated_content": Markdown **student lesson** (prose-first). Must include:
  - Teaching sections with `##` / `###` focused on the subtopic
  - After **each major `##` section**: 1–2 sentences labeled **Check yourself** (inline comprehension, not numbered drills)
  - A final section **## Review questions** with **3–5** short questions in prose or brief Q&A
  - Full text descriptions for any figure/diagram mentioned
  - **Do not** include teacher classroom directions, activity catalogs, or **## Accessibility notes**
- "key_takeaways": 3–5 strings tied to this subtopic
- "glossary_terms": object term → plain-language definition
- "student_activities": **2–4** optional practice items for a separate app tab (concrete, subtopic-scoped; no lab/outdoor setup)
- "teacher_activities": **0–3** brief bullets for **reviewers only** (may be an **empty list**); must **not** appear in `curated_content`
- "accessibility_checklist": **4–6** short strings for **reviewers only** (not a student-facing section)
- "image_placeholders": **optional** — use `[]` when the lesson needs **no** textbook figures. Otherwise **1–3** objects: `{{"placeholder_id": "ph1", "intent": "…", "search_hints": ["…"], "after_heading": "optional ## heading text"}}`
- "formula_placeholders": **optional** — use `[]` when there are **no** chemical equations or math notation to render. Otherwise list items like `{{"placeholder_id": "fp1", "plain_text": "CO2", "kind": "chemistry"}}` (kind: chemistry | math)
"""


def format_system_prompt(subject: str | None = None) -> str:
    return format_prompt(SYSTEM_PROMPT_TEMPLATE, subject=subject)


def format_curation_prompt(subject: str | None = None, **fields: str) -> str:
    return format_prompt(CURATION_PROMPT_TEMPLATE, subject=subject, **fields)


def get_prompt_version() -> str:
    content_hash = hashlib.sha256(
        (SYSTEM_PROMPT_TEMPLATE + CURATION_PROMPT_TEMPLATE).encode()
    ).hexdigest()[:8]
    return f"{PROMPT_VERSION_TAG}:{content_hash}"


# Backward-compatible names (unformatted — prefer format_* helpers at call sites)
SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE
