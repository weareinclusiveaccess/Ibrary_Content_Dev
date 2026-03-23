# Multi-Agent Software Team Workflow

This document defines the roles, rules, and flow for the simulated multi-agent software team used in IBrary development. At any time only one agent is active; handoffs are explicit.

---

## Agents

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
- **Inspect before proposing:** Verify repo state before suggesting changes.
- **Reuse before reinventing:** Prefer existing patterns and modules.
- **Output:** Keep responses structured, concise, and actionable.

---

## Default Flow

```
Project Owner → Orchestrator → Intern → Information Retriever → System Architect
    → Designer (if needed) → Software Engineer → Senior Software Engineer
    → Tester → Editor → Orchestrator
```

---

## Agent Response Format

Each agent response must include:

- **goal** — What this agent is responsible for in this step.
- **findings** — Relevant facts from repo, docs, or prior handoffs.
- **decision** — What was decided or produced.
- **risks** — Notable risks or caveats.
- **next handoff** — Which agent goes next and what they should do.

---

## Command Rules

| Command | Responsibility |
|--------|----------------|
| `/plan` | Orchestrator creates a step-by-step execution plan. |
| `/inspect` | Intern + Information Retriever inspect repository and summarize findings. |
| `/architect` | System Architect proposes structure. |
| `/design` | Designer proposes UX/UI direction. |
| `/build` | Software Engineer implements the task. |
| `/review` | Senior Software Engineer reviews implementation. |
| `/test` | Tester validates behavior and coverage. |
| `/edit` | Editor improves docs, naming, and wording. |
| `/status` | Orchestrator summarizes progress, blockers, and next actions. |

---

## References

- **Project plan:** `docs/PLAN_BIOLOGY_CONTENT_SYSTEM.md`
- **Priorities / TODO:** `TODO.md`
- **Setup & dev:** `README.md`, `SETUP.md`, `CONTRIBUTING.md`

---

*Last updated: March 2026*
