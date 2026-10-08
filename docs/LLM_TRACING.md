# LLM tracing and logs

All OpenAI **chat** and **embedding** calls in the pipeline go through `src/ibrary/llm/client.py`, which records structured traces for analysis.

## What is logged

Each call writes:

| Field | Description |
|-------|-------------|
| `trace_id` | UUID |
| `component` | `curation`, `relevance`, `judge`, `curriculum_refine`, `embedder`, `openai_agents` |
| `operation` | `chat_completion` or `embedding` |
| `model` | Model id |
| `latency_ms` | Wall time |
| `prompt_tokens` / `completion_tokens` | From API usage when available |
| `metadata` | e.g. `curriculum_unit_id`, `chunk_id`, `theme_number` |

## Outputs

1. **Structlog** — console lines with event `llm_call` (set `LOG_LEVEL=INFO`).
2. **JSONL file** — default `data/logs/llm_traces.jsonl` (gitignored under `logs/`).
3. **LangSmith** (optional) — set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`; view at [smith.langchain.com](https://smith.langchain.com).

## Configuration (`.env`)

```bash
LLM_TRACE_ENABLED=true
LLM_TRACE_JSONL_PATH=data/logs/llm_traces.jsonl
LLM_TRACE_LOG_PROMPTS=false   # true = store prompt/response previews in JSONL
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=ibrary-pipeline
```

## Analyze JSONL

```bash
# Count calls by component
python -c "
import json
from collections import Counter
c = Counter()
for line in open('data/logs/llm_traces.jsonl'):
    r = json.loads(line)
    c[r['component']] += 1
print(c)
"

# Total tokens
python -c "
import json
t = 0
for line in open('data/logs/llm_traces.jsonl'):
    r = json.loads(line)
    t += r.get('total_tokens') or 0
print('total_tokens', t)
"
```

## Components covered

| Module | `component` value |
|--------|-------------------|
| `curation/curation_service.py` | `curation` |
| `relevance/scorer.py` | `relevance` |
| `judging/subtopic_judge.py` | `judge` |
| `curriculum/refiner.py` | `curriculum_refine` |
| `alignment/embedder.py` | `embedder` / `embedder_query` |
| `pipeline/openai_agents/runner.py` | `openai_agents` |
