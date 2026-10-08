# Subject configuration (multi-discipline prompts)

All LLM prompts use **`{subject}`** placeholders filled at runtime from environment variables.

## Variables

| Variable | Default | Used in |
|----------|---------|---------|
| `PIPELINE_SUBJECT` | `Biology` | Curation, relevance, judge, curriculum refiner prompts |
| `PIPELINE_SUBJECT_SLUG` | `biology` | Storage keys, paths (future unit-id prefixes) |
| `EDUCATION_SYSTEM_LABEL` | `Nigerian Senior Secondary School` | Curriculum refinement system prompt |

## Switch subject (e.g. Chemistry)

```bash
# .env
PIPELINE_SUBJECT=Chemistry
PIPELINE_SUBJECT_SLUG=chemistry
```

Restart the shell and re-run pipeline steps. Curated modules will carry `subject: "Chemistry"`.

## Prompt modules

| Module | Placeholders |
|--------|----------------|
| `ibrary.curation.prompts` | `{subject}`, `{subject_lower}` |
| `ibrary.relevance.scorer` | `{subject}` |
| `ibrary.curriculum.refiner` | `{subject}`, `{education_system}` |
| `ibrary.judging.subtopic_judge` | `{subject}` (user + system correctness line) |

Shared helper: `ibrary.prompts.context.format_prompt(template, subject=..., **fields)`.

## OpenAI Agents SDK

Specialists are defined in `src/ibrary/pipeline/openai_agents/` using `{subject}` in instructions via `resolve_subject()`. Install with `uv sync` (`openai-agents` in `pyproject.toml`).

## Not yet parameterized

- DynamoDB partition keys in `serving/api.py` and `dynamodb_writer.py` (hardcoded `SUBJECT#Biology`)
- Unit id prefix `bio_` in `curriculum/validator.py`
- Textbook extractor `openstax_biology2e.py` (Biology-specific PDF)

Those are infrastructure/book choices, not LLM prompts.
