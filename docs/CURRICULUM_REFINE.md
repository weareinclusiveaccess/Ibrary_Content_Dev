# Curriculum refinement agent

## Problem

`validate_curriculum` expands each **topic** into **subtopic units** but copies the same topic-level `performance_objectives`, `teachers_activities`, and `student_activities` onto every unit. Example: subtopic *Characteristics of living things* incorrectly includes *State complexity of organization in higher organisms*, which belongs to a later subtopic.

## Data sources

| Source | Path | Role |
|--------|------|------|
| Structured curriculum | `biology_curriculum_structured.json` | Raw NERDC extract (topic-level lists) |
| Validated units | `curriculum_validated.json` | One row per subtopic (`content_text`) |
| Textbook | `Biology2e-WEB.pdf` → Postgres `textbook_chunks` | Separate pipeline (extract/align) |

Refinement only fixes **curriculum** JSON; it does not read the textbook.

## Agent

Module: `src/ibrary/curriculum/refiner.py`

- Groups units by `(theme_number, topic_number)`
- One LLM call per topic (~14 calls for SSS1 topics 1–6)
- Assigns each pool item to the subtopic whose `content_text` it matches
- Writes `curriculum_refinement_report.json` with per-subtopic `rationale`

Config: `OPENAI_CURRICULUM_REFINE_MODEL` (default `gpt-4o-mini`)

## Commands

**Dry-run one topic (preview JSON, no save):**

```bash
python scripts/refine_curriculum.py --dry-run --topic 1
```

**Refine theme 1 topic 1 only:**

```bash
python scripts/refine_curriculum.py --topic 1
```

**Refine all topics in existing validated file:**

```bash
python scripts/refine_curriculum.py
```

**Pipeline (after validate):**

```bash
python scripts/run_pipeline.py --steps validate,refine_curriculum
# or
python scripts/run_pipeline.py --refine-curriculum --steps validate,align
```

## Expected result (topic 1)

| content_index | content_text | performance_objectives (example) |
|---------------|--------------|--------------------------------|
| 0 | Characteristics of living things | State the characteristics of living things |
| 1 | Differences between plants and animals | (subset or empty — not “complexity”) |
| 2 | Levels of organization… | Give examples of levels of organization… |
| 3 | Complexity of organization… | State complexity of organization… |

Teacher/student activities should align with specimens (cockroach/plant vs microscope vs heart/digestive).

## Review

1. Open `curriculum_refinement_report.json` — read `rationale` per subtopic.
2. Diff `curriculum_validated.json` for `bio_sss1_theme1_topic1_content0` — objectives list should shrink to subtopic-relevant items.
3. Re-run alignment/curation only if you depend on updated objectives in downstream prompts.
