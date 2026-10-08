# Review Weakness Summarization Design

## Goal

Create an offline batch workflow that reads all substantive human and automated
reviews associated with each curated biology content unit in Neon, uses OpenAI
to identify weaknesses evidenced by those reviews, and stores both per-content
and cross-content summaries in a versioned JSON artifact for later curation
prompt improvement.

## Scope

The workflow will:

- read curated content review data from Neon through the existing review
  database session;
- combine human notes and rubrics with automated UDL judge feedback;
- select the latest substantive human review per reviewer and content unit;
- exclude publish and audit-only rows;
- produce one structured weakness summary per content unit;
- produce one cross-content rollup from validated per-content summaries;
- persist only to JSON; and
- run offline through a standalone CLI.

It will not edit curation prompts automatically, add OpenAI calls to the
reviewer portal, change review submission behavior, or create a new database
table.

## Review Selection

For every curated content unit with review data, the workflow will collect:

- human notes;
- human rubric scores and accompanying feedback;
- human rejection feedback; and
- automated UDL judge recommendations, correctness notes, clarity notes,
  checkpoint notes, pass/fail state, and dimension scores.

When one reviewer has submitted multiple substantive reviews for the same
content unit, only that reviewer's latest row is used. Publish rows and other
audit-only rows are excluded. Reviewer identity is used only during selection
and is not written to the output artifact.

Each normalized evidence item retains its source type, source row ID, timestamp,
and feedback fields needed for traceability. Curated content text is supplied
only when needed to resolve what a review refers to and is not copied into the
result artifact.

## Architecture

### Review weakness module

`src/ibrary/prompt_improvement/review_weaknesses.py` will own:

- database queries and eager loading;
- substantive-review filtering;
- latest-per-reviewer selection;
- evidence normalization;
- deterministic source-data hashing;
- per-content summarization orchestration;
- incremental artifact updates; and
- cross-content rollup orchestration.

Functions will be separated so selection, normalization, hashing, model calls,
and persistence can be tested independently.

### Prompt module

`src/ibrary/prompt_improvement/review_weakness_prompts.py` will contain the
system and user prompt builders. Prompt versions will use the project's
file-content hash convention. The prompts will require the model to:

- report only weaknesses supported by supplied review evidence;
- preserve source evidence references;
- merge duplicate observations;
- distinguish correctness, clarity, pedagogy, UDL/accessibility, engagement,
  structure, and other justified categories;
- assign a bounded severity and occurrence count;
- produce concise, actionable prompt-instruction suggestions; and
- return the required JSON shape.

### CLI

`scripts/summarize_review_weaknesses.py` will expose the offline workflow. It
will support:

- an optional output path;
- an optional curriculum unit filter;
- an optional processing limit; and
- a force-refresh flag.

The default output will be:

`data/docs/extracted_source_content/biology/review_weakness_summaries.json`

This workflow remains separate from the main pipeline because human reviews
arrive after content generation and publishing workflows may run without an
OpenAI key.

## Data Flow

1. Query curated content units and their human and automated review rows from
   Neon.
2. Remove audit-only rows and select the latest substantive human row for each
   reviewer and unit.
3. Normalize the selected human evidence and UDL judge evidence.
4. Compute a deterministic hash of the normalized source data.
5. Skip a unit when its stored source hash and summarizer prompt version are
   unchanged, unless force-refresh is enabled.
6. Call OpenAI for each changed unit and validate the structured response.
7. Persist the artifact immediately after each unit.
8. Generate a cross-content rollup from all successfully validated per-content
   summaries.
9. Validate and persist the rollup with its input-summary hash.

## OpenAI Configuration

The summarizer will use `OPENAI_REVIEW_SUMMARY_MODEL` when set and fall back to
`OPENAI_MODEL`. It will reuse the central JSON completion client, tracing, and
three-attempt exponential-backoff behavior.

The per-content call is intentionally separate from the rollup call. This keeps
requests bounded, makes failures local to one unit, and allows unchanged units
to be reused on later runs.

## Output Artifact

The JSON document will include:

- schema version;
- generation and update timestamps;
- summarizer prompt version;
- model name;
- per-content summaries keyed by curriculum unit ID;
- source-data hash and source evidence references for each unit;
- status and error details for units marked `[Needs Review]`; and
- a cross-content rollup with its input-summary hash.

Each per-content summary will include:

- content identifiers and prompt version;
- categorized weaknesses;
- concise descriptions;
- severity;
- occurrence count;
- supporting review source references; and
- actionable curation prompt-instruction suggestions.

The rollup will include:

- recurring weakness themes;
- affected unit IDs and counts;
- aggregate priority;
- representative evidence references; and
- consolidated instruction themes suitable as input to the prompt feedback
  refinement workflow.

The artifact is updated by key rather than appended blindly, making reruns
idempotent. It contains no reviewer names, emails, or user IDs.

## Error Handling

- Database failures stop the run before model processing.
- Invalid or incomplete OpenAI responses are retried through the shared client.
- After retries are exhausted, the unit is retained with a `[Needs Review]`
  status and an error description.
- Successful prior summaries remain intact when another unit fails.
- The cross-content rollup uses only validated summaries and records excluded
  failed units.
- File writes use an atomic temporary-file replacement to avoid corrupting the
  artifact.
- An invalid existing artifact fails clearly rather than being overwritten
  silently.

## Testing

Unit tests will verify:

- substantive human review filtering;
- latest-per-reviewer selection;
- judge feedback normalization;
- stable source hashing;
- skipping unchanged units;
- force-refresh behavior;
- structured response validation;
- exhausted model-call failure handling;
- incremental and atomic JSON persistence;
- exclusion of reviewer identity;
- rollup inputs and failed-unit reporting; and
- model configuration fallback.

Integration-style tests with mocked database and OpenAI boundaries will verify
the end-to-end orchestration and CLI wiring without requiring Neon or OpenAI
network access.

## Success Criteria

- Every curated content unit with substantive human or judge review evidence is
  represented in the artifact.
- Multiple historical human reviews are reduced to the latest substantive row
  per reviewer and unit.
- Every reported weakness cites at least one supplied review source.
- Unchanged units do not incur new OpenAI calls on rerun.
- Partial failures are visible and do not discard successful summaries.
- The rollup clearly identifies recurring weaknesses and produces actionable
  instruction themes for the next curation prompt revision.
