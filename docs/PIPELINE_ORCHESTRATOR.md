# Content pipeline orchestrator

Subject-agnostic runtime sub-agents under **`src/ibrary/pipeline/`**.

## Framework

| Backend | Module | When to use |
|---------|--------|-------------|
| **Native Python DAG** (default) | `orchestrator.py` | Production batch pipeline — deterministic, idempotent |
| **OpenAI Agents SDK** | `pipeline/openai_agents/` | Specialist definitions, handoffs, manager orchestration |

No LangGraph. OpenAI Agents SDK docs: [Agent definitions](https://developers.openai.com/api/docs/guides/agents/define-agents?lang=python), [Orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration).

## Layout

```text
src/ibrary/pipeline/
  context.py           # PipelineContext
  subagents.py           # Relevance, TextCurator, MediaLinker, Formula, Assembler
  orchestrator.py        # PipelineOrchestrator

src/ibrary/judging/        # UDL v3 subtopic judge (CAST graphic organizer metrics)
src/ibrary/prompt_improvement/  # Compare prompt versions via judge
```

## Per-unit curation DAG

```text
TextCuratorAgent → MediaLinkerAgent ∥ FormulaAgent → ModuleAssemblerAgent
```

## Usage — native DAG

```python
from ibrary.pipeline import PipelineContext, create_orchestrator

orch = create_orchestrator()
ctx = PipelineContext(curriculum_unit_id="bio_sss1_theme1_topic1_content0")
ctx = orch.filter_relevance_unit(ctx, alignment_matches=[...])
ctx = orch.curate_unit(ctx)
```

## Usage — OpenAI Agents SDK

Install: `uv sync && uv pip install -e .` (includes `openai-agents`).

```python
from ibrary.pipeline.openai_agents import (
    relevance_scorer_agent,
    text_curator_agent,
    curation_pipeline_manager,
    run_agent_sync,
    run_curation_manager,
)

# Single specialist
result = run_agent_sync(
    relevance_scorer_agent,
    "Score relevance for subtopic 'Characteristics of living things' ...",
)
print(result.final_output)

# Manager (specialists as tools — manager keeps final answer)
result = run_curation_manager("bio_sss1_theme1_topic1_content0")
print(result.final_output)
```

CLI:

```bash
python scripts/run_openai_agent.py --list
python scripts/run_openai_agent.py --agent curriculum_refiner --message "Refine topic 1 units..."
python scripts/run_openai_agent.py --unit bio_sss1_theme1_topic1_content0
```

### Agent map

| Key | OpenAI `Agent` | Tools / pattern |
|-----|----------------|-----------------|
| `relevance_scorer` | Relevance Scorer | `score_chunk_relevance_tool` |
| `curriculum_refiner` | Curriculum Refiner | `refine_curriculum_topic_tool` |
| `text_curator` | Text Curator | `curate_subtopic_tool` |
| `media_linker` | Media Linker | stub (manifest linking TBD) |
| `formula` | Formula Agent | stub (LaTeX TBD) |
| `module_assembler` | Module Assembler | stub (schema merge TBD) |
| `udl_judge` | UDL Judge | `judge_subtopic_content_tool` |
| `curation_manager` | Curation Pipeline Manager | specialists via `.as_tool()` |
| `curation_triage` | Curation Triage | handoffs to refiner / relevance / curator / judge |

## Judging (`ibrary.judging`)

Standalone module — call whenever you have text, not only after curation or in prompt improvement.

```python
from ibrary.judging import evaluate_text, evaluate_content, SubtopicJudgeInput

# Minimal: body text only
result = evaluate_text("Living things share metabolism, growth, and reproduction…", subtopic="Characteristics of living things")

# Richer context
result = evaluate_content(SubtopicJudgeInput(content=markdown_body, subtopic="...", learning_objectives=[...]))

# After curation
from ibrary.judging import evaluate_subtopic, evaluate_subtopics
```

Rubric: all CAST UDL v3.0 checkpoints from `data/docs/udlg3-graphicorganizer-digital-numbers-a11y.pdf`.

## Prompt improvement

```python
from ibrary.prompt_improvement import compare_curated_files, save_improvement_report

report = compare_curated_files("eval/v1.3/curated.json", "eval/v1.4/curated.json")
save_improvement_report(report, "data/prompt_lab/eval")
print(report.improved, report.mean_delta)
```

Spec: `docs/superpowers/specs/2026-05-16-biology-pipeline-v2-design.md`
