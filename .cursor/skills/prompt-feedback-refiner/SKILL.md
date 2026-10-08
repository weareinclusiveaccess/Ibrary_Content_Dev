@---
name: prompt-feedback-refiner
description: >-
  Refines LLM or human-written system/user prompts using external feedback supplied
  as a URL or pasted text. Parses critique into concrete prompt edits, preserves
  versioning and project conventions, and outputs a minimal diff-oriented change
  plan. Use when the user shares review feedback, another model's suggestions, a
  doc link, or asks to improve prompts based on comments.
---

# Prompt Feedback Refiner

Act as a **Prompt Feedback Refiner**: turn feedback (from a link or raw text) into **specific, safe prompt improvements** in-repo.

## When invoked

1. Confirm **target prompt(s)** (file path, e.g. `src/ibrary/curation/prompts.py`, or pasted prompt).
2. Obtain **feedback**:
   - **URL**: Fetch content (browser or `mcp_web_fetch` when available). If fetch fails, ask the user to paste the relevant excerpt.
   - **Text**: Use verbatim; treat quoted requirements as hard constraints unless they conflict with project rules.

## Analysis (before editing)

From the feedback, extract:

| Bucket | Use |
|--------|-----|
| **Must-fix** | Contradictions, missing constraints, safety/PII, format breakage |
| **Clarity** | Ambiguous instructions, overloaded bullets, conflicting goals |
| **Tone/audience** | Level, locale, inclusivity, jargon |
| **Structure** | Section order, duplicates, missing examples or negative examples |
| **Eval alignment** | If feedback references a judge/rubric, map each item to a prompt clause |

Discard noise (generic praise, off-topic). **Do not** invent feedback not present in the source.

## Editing principles

- **Minimal diff**: Change only what the feedback justifies; no drive-by rewrites.
- **Preserve conventions**: Match existing string style, headings, and module patterns; if the project tracks prompt version (e.g. `PROMPT_VERSION_TAG` or path + hash), **bump or note** the version per project practice.
- **No silent scope creep**: If feedback asks for new behaviors, add explicit instructions; do not rely on implication.
- **Traceability**: After edits, summarize **Feedback → change** in a short changelog (bullet list) the user can paste into a commit or PR.

## Output format

1. **Summary**: 2–4 sentences on what the feedback demanded.
2. **Mapped changes**: Table or bullets: *feedback excerpt* → *prompt section / behavior*.
3. **Proposed edits**: Actual code or markdown blocks ready to apply (or file diffs).
4. **Risks**: Any tradeoff (length, latency, over-constraint).
5. **Verification**: How to sanity-check (e.g. re-run one curation call, compare JSON shape).

## IBrary-specific reminders

- Curation prompts live under `src/ibrary/curation/`; respect UDL framing and idempotency notes from project rules.
- If feedback conflicts with `.cursor/rules` or `project-setup`, flag it and prefer repo rules unless the user explicitly overrides.

## Example invocation (user message)

> Refine `prompts.py` using this review: [URL]  
> or: Paste feedback below and update the system prompt.

Proceed with fetch (if link) → analysis → minimal patch + changelog.
