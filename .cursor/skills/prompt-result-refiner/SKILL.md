---
name: prompt-result-refiner
description: >-
  Refines prompts by diagnosing gaps between intended behavior and actual model
  outputs: bad samples, parse errors, rubric failures, hallucinations, or scope
  drift. Produces minimal prompt edits tied to each observed issue and a
  verification plan. Use when the user shares outputs, logs, screenshots, or
  evaluation results and asks to fix or improve the prompt that produced them.
---

# Prompt Result Refiner

Act as a **Prompt Result Refiner**: use **concrete outputs and failures** (not third-party review text) to improve prompts with **traceable, minimal changes**.

## When to use this skill vs. prompt-feedback-refiner

| Situation | Skill |
|-----------|--------|
| Bad sample output, wrong JSON shape, judge scores, run logs | **This skill** (`prompt-result-refiner`) |
| Pasted review, another model’s comments, doc/URL with feedback | `prompt-feedback-refiner` |

If both apply, merge: treat **observed output** as primary evidence and **external feedback** as extra constraints.

## Inputs to collect

1. **Target prompt**: file path (e.g. `src/ibrary/curation/prompts.py`) or pasted prompt text.
2. **Evidence** (one or more):
   - Representative **bad output** (full or redacted).
   - **Error messages** (API, JSON schema, validator).
   - **Scores or rubric breakdown** (e.g. UDL judge dimensions).
   - **Expected vs actual** for a fixed input (same chunk, same curriculum item).
3. **Context**: model name/settings if known; whether output is few-shot or zero-shot.

## Diagnosis workflow

1. **Reproduce the failure class** (without running code unless the user asks): label each issue using the taxonomy below.
2. **Hypothesize prompt cause**: which instruction was missing, weak, or contradicted? Prefer **one primary cause per issue**; note if multiple causes compete.
3. **Propose minimal edits**: add or tighten instructions; add **negative examples** or **format cages** only when the failure repeats structurally.
4. **Verification**: define a **small check** (one call, one fixture, or re-run judge on the same case).

Do **not** invent outputs the user did not provide. If evidence is thin, state assumptions and ask for one more example.

## Issue taxonomy (map output → prompt lever)

| Observed pattern | Likely prompt lever |
|------------------|---------------------|
| Wrong JSON / extra keys / markdown fences | Explicit “JSON only” schema block; forbid prose; example shape |
| Hallination or facts not in context | Stronger “use only provided context”; quote-or-abstain; cite passage |
| Ignores constraints (length, audience, locale) | Move constraints up; repeat in “before you answer”; checklist |
| Right topic, wrong depth | Add grade/audience line; “define terms” or “assume prior knowledge” |
| Mixes units, ambiguous terms | Glossary line or “use these terms only: …” |
| Inconsistent style across runs | Add role + output template; reduce optional phrasing |
| Judge dimension always low | Map dimension → one explicit bullet; add self-check sentence |
| Safe/PII concerns | Safety block; what to refuse; no real names |

## Editing principles

- **Minimal diff**: fix only what the evidence supports.
- **Preserve project conventions**: string style, sections, versioning (`PROMPT_VERSION_TAG`, path + hash, etc.); bump version when behavior changes.
- **No prompt stuffing**: prefer one clear rule over many vague bullets.
- **Traceability**: after edits, list **Issue → prompt change → how to verify**.

## Output format

Deliver in this order:

1. **Failure summary**: what went wrong in the outputs (bullet list).
2. **Root-cause table**: *observed symptom* → *likely missing/wrong instruction*.
3. **Proposed edits**: patches or code blocks ready to apply.
4. **Regression check**: exact steps to confirm the fix (same input, expected delta).
5. **Risks**: over-constraint, longer prompt, or new failure modes.

## IBrary-specific notes

- Curation and alignment prompts live under `src/ibrary/curation/` and related modules; respect UDL framing and idempotency from project rules.
- If outputs violate **curriculum IDs**, **chunk grounding**, or **schema** in `curation/schemas.py`, tie fixes to those artifacts explicitly.

## Example user message

> Here’s the curated JSON we got for unit X — learning objectives are generic and the activities ignore the textbook chunk. Here’s the chunk and the current system prompt. How should we change the prompt?

Proceed: classify issues → map to prompt sections → minimal edits → verification.
