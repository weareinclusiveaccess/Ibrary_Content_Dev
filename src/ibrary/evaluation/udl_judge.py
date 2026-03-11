"""UDL evaluation judge — scores curated content against UDL criteria."""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog

from ibrary.config import OPENAI_API_KEY, OPENAI_MODEL
from ibrary.curation.schemas import CuratedModule

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2

JUDGE_SYSTEM_PROMPT = """\
You are a UDL (Universal Design for Learning) content evaluator. \
Score the given educational content against the CAST UDL Guidelines v3.0.

Evaluate across three principles with the following checkpoints:

### Representation (Score 1-10)
1. Perception: Is content presented in multiple formats (text, headings, lists)?
2. Language & Symbols: Are key terms defined? Is vocabulary clear?
3. Comprehension: Does content connect to prior knowledge? Are patterns highlighted?

### Action & Expression (Score 1-10)
4. Physical Action: Is content accessible via multiple interaction modes?
5. Expression & Communication: Are diverse ways to demonstrate understanding suggested?
6. Executive Functions: Are learning objectives clear? Are reflection prompts included?

### Engagement (Score 1-10)
7. Recruiting Interest: Are relatable, everyday examples used?
8. Sustaining Effort: Is content broken into manageable sections?
9. Self-Regulation: Are reflection questions included?

Respond with a JSON object:
{
  "representation_score": <1-10>,
  "representation_notes": "<brief justification>",
  "action_expression_score": <1-10>,
  "action_expression_notes": "<brief justification>",
  "engagement_score": <1-10>,
  "engagement_notes": "<brief justification>",
  "overall_score": <1-10 average>,
  "recommendations": ["<improvement 1>", "<improvement 2>", ...]
}
"""

JUDGE_USER_TEMPLATE = """\
Evaluate the following UDL-curated biology content module:

**Title:** {title}
**Subtopic:** {subtopic}
**Learning Objectives:** {objectives}

**Content:**
{content}

**Key Takeaways:** {takeaways}
**Glossary Terms:** {glossary}
"""


def _call_judge(content_text: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": content_text},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:
            logger.warning("judge_retry", attempt=attempt, error=str(exc))
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF**attempt)
    return {}


def evaluate_module(module: CuratedModule) -> dict:
    """Run UDL evaluation on a single curated module."""
    user_prompt = JUDGE_USER_TEMPLATE.format(
        title=module.title,
        subtopic=module.subtopic,
        objectives="\n".join(f"- {o}" for o in module.learning_objectives),
        content=module.curated_content[:6000],
        takeaways="\n".join(f"- {t}" for t in module.key_takeaways),
        glossary=json.dumps(module.glossary_terms, indent=2),
    )
    try:
        result = _call_judge(user_prompt)
        result["curriculum_unit_id"] = module.curriculum_unit_id
        return result
    except Exception as exc:
        logger.error("judge_failed", unit_id=module.curriculum_unit_id, error=str(exc))
        return {
            "curriculum_unit_id": module.curriculum_unit_id,
            "overall_score": 0,
            "error": str(exc),
        }


def evaluate_all(
    modules: list[CuratedModule],
    threshold: float = 6.0,
) -> tuple[list[dict], list[str]]:
    """Evaluate all modules.  Returns (scores, flagged_unit_ids)."""
    scores: list[dict] = []
    flagged: list[str] = []
    for module in modules:
        result = evaluate_module(module)
        scores.append(result)
        overall = result.get("overall_score", 0)
        if overall < threshold:
            flagged.append(module.curriculum_unit_id)
            logger.warning(
                "below_threshold",
                unit_id=module.curriculum_unit_id,
                score=overall,
            )
    return scores, flagged


def save_evaluation(scores: list[dict], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "udl_evaluation_report.json"
    path.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    logger.info("evaluation_saved", path=str(path))
    return path
