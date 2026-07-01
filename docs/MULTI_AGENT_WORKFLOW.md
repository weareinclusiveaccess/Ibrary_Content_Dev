# Multi-Agent Software Team Workflow

Cursor-facing roles for human-driven development. Runtime pipeline agents are separate (see below).

---

## Cursor agents

| Agent | Scope |
|-------|--------|
| **Project Owner** | Scope requests into a software delivery brief; goals, constraints, success criteria. |
| **Orchestrator** | Create step-by-step execution plans; align work with repo state and priorities. |
| **System Architect** | Propose structure (modules, files, config); reuse before reinventing. |
| **Designer** | Propose UX/UI direction when a feature touches user experience. |
| **Information Retriever** | Pull and summarize docs, configs, and codebase facts for decisions. |
| **Intern** | Inspect repository (structure, key files, patterns); report findings. |
| **Software Engineer** | Implement tasks per plan and architecture. |
| **Senior Software Engineer** | Review implementation (correctness, patterns, maintainability). |
| **Tester** | Validate behavior and coverage. |
| **Editor** | Improve docs, naming, and wording. |

---

## Rules

- **Stay in scope:** Only the active agent speaks; do not mix roles.
- **Handoff:** Every agent ends with a handoff to the next best agent.
- **Ground decisions:** Use the actual codebase, file structure, configs, and existing patterns.
- **Reuse before reinventing:** Prefer existing patterns under `src/ibrary/`.
- **Output:** Keep responses structured, concise, and actionable.

---

## Pipeline sub-agents (runtime, subject-agnostic)

Implemented in code — not Cursor chat roles.

| Module | Responsibility |
|--------|----------------|
| `src/ibrary/pipeline/` | `PipelineOrchestrator`, sub-agents, native DAG |
| `src/ibrary/judging/` | UDL v3 subtopic judge (CAST metrics PDF) |
| `src/ibrary/prompt_improvement/` | Compare prompt versions using judge scores |
| `src/ibrary/relevance/` | (planned) filter_relevance |
| `src/ibrary/curation/` | Text/media/formula curation |

Guide: `docs/PIPELINE_ORCHESTRATOR.md`  
Spec: `docs/superpowers/specs/2026-05-16-biology-pipeline-v2-design.md`

---

## References

- **Pipeline spec:** `docs/superpowers/specs/2026-05-16-biology-pipeline-v2-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-05-16-biology-pipeline-v2.md`
- **Setup:** `SETUP.md`, `README.md`
