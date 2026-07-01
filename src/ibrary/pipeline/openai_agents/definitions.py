"""OpenAI Agents SDK definitions for IBrary pipeline specialists.

See:
- https://developers.openai.com/api/docs/guides/agents/define-agents
- https://developers.openai.com/api/docs/guides/agents/orchestration

Install: ``uv add openai-agents`` or ``pip install openai-agents``
"""

from __future__ import annotations

from agents import Agent

from ibrary.config import (
    OPENAI_CURATION_MODEL,
    OPENAI_CURRICULUM_REFINE_MODEL,
    OPENAI_MODEL,
    OPENAI_RELEVANCE_MODEL,
)
from ibrary.pipeline.openai_agents.tools import (
    curate_subtopic_tool,
    judge_subtopic_content_tool,
    list_pipeline_agent_roles,
    refine_curriculum_topic_tool,
    score_chunk_relevance_tool,
)
from ibrary.prompts.context import resolve_subject


def _subject() -> str:
    return resolve_subject()


# --- Specialists (single responsibility each) ---

relevance_scorer_agent = Agent(
    name="Relevance Scorer",
    handoff_description=(
        "Scores whether each textbook chunk supports a specific curriculum subtopic "
        "and extracts teachable excerpts."
    ),
    instructions=(
        f"You are a {_subject()} curriculum designer for senior secondary school. "
        "Given a subtopic and textbook chunk, decide relevance and extract only the "
        "sentences that teach the subtopic. Use the score_chunk_relevance tool; "
        "return structured JSON only."
    ),
    model=OPENAI_RELEVANCE_MODEL,
    tools=[score_chunk_relevance_tool],
)

curriculum_refiner_agent = Agent(
    name="Curriculum Refiner",
    handoff_description=(
        "Fixes topic-level performance objectives and activities copied to every "
        "subtopic — assigns each item to the correct content_text."
    ),
    instructions=(
        f"You refine {_subject()} curriculum records for "
        f"Nigerian Senior Secondary School. Each topic has multiple subtopics; "
        "assign performance_objectives, teachers_activities, and student_activities "
        "to the subtopic they belong to. Use refine_curriculum_topic_tool with a "
        "JSON array of units for one topic."
    ),
    model=OPENAI_CURRICULUM_REFINE_MODEL,
    tools=[refine_curriculum_topic_tool],
)

text_curator_agent = Agent(
    name="Text Curator",
    handoff_description=(
        "Creates UDL-aligned teaching content for one subtopic from curriculum "
        "and textbook excerpts."
    ),
    instructions=(
        f"You are an expert {_subject()} teacher following CAST UDL Guidelines v3.0. "
        "Produce accessible secondary-level modules: clear headings, glossary, "
        "alt text for visuals, and activities with accessible alternatives. "
        "Use curate_subtopic_tool with unit JSON and alignment matches JSON."
    ),
    model=OPENAI_CURATION_MODEL,
    tools=[curate_subtopic_tool],
)

media_linker_agent = Agent(
    name="Media Linker",
    handoff_description="Resolves image placeholders to textbook S3 assets or OpenStax web URLs.",
    instructions=(
        f"For {_subject()} learning modules, map image placeholders to textbook "
        "images (S3 manifest first, OpenStax web fallback). Return assets[] with "
        "url, alt_text, caption, and source. (Implementation pending — describe plan.)"
    ),
    model=OPENAI_CURATION_MODEL,
    tools=[list_pipeline_agent_roles],
)

formula_agent = Agent(
    name="Formula Agent",
    handoff_description="Extracts and normalizes LaTeX formulas including chemistry \\ce{} notation.",
    instructions=(
        f"For {_subject()} modules, convert formula placeholders to LaTeX in "
        "formulas[] (use \\ce{{}} for chemistry). KaTeX + mhchem compatible. "
        "(Implementation pending — describe plan.)"
    ),
    model=OPENAI_CURATION_MODEL,
    tools=[list_pipeline_agent_roles],
)

module_assembler_agent = Agent(
    name="Module Assembler",
    handoff_description="Merges content blocks, assets, and formulas into LearningModule v1 JSON.",
    instructions=(
        "Assemble content_blocks, assets[], and formulas[] into a single "
        "LearningModule v1 document with curriculum_unit_id and metadata. "
        "(Implementation pending — validate schema.)"
    ),
    model=OPENAI_CURATION_MODEL,
    tools=[list_pipeline_agent_roles],
)

udl_judge_agent = Agent(
    name="UDL Judge",
    handoff_description=(
        "Evaluates subtopic teaching content against CAST UDL v3 checkpoints plus "
        "correctness and clarity."
    ),
    instructions=(
        f"You evaluate {_subject()} learning content for secondary students. "
        "Use judge_subtopic_content_tool with the full markdown body and subtopic label."
    ),
    model=OPENAI_MODEL,
    tools=[judge_subtopic_content_tool],
)

# --- Orchestrator (manager keeps control; specialists as tools) ---

curation_pipeline_manager = Agent(
    name="Curation Pipeline Manager",
    instructions=(
        f"You coordinate {_subject()} subtopic curation for IBrary. "
        "For each unit: (1) ensure relevance filtering on aligned chunks, "
        "(2) run text curation on excerpts only, (3) resolve media and formulas, "
        "(4) assemble LearningModule v1. "
        "Call specialist tools in that order. Pass JSON outputs between steps. "
        "Do not skip curriculum authority — subtopic scope is strict."
    ),
    model=OPENAI_CURATION_MODEL,
    tools=[
        relevance_scorer_agent.as_tool(
            tool_name="score_chunk_relevance",
            tool_description=relevance_scorer_agent.handoff_description,
        ),
        text_curator_agent.as_tool(
            tool_name="curate_subtopic",
            tool_description=text_curator_agent.handoff_description,
        ),
        media_linker_agent.as_tool(
            tool_name="link_media",
            tool_description=media_linker_agent.handoff_description,
        ),
        formula_agent.as_tool(
            tool_name="resolve_formulas",
            tool_description=formula_agent.handoff_description,
        ),
        module_assembler_agent.as_tool(
            tool_name="assemble_module",
            tool_description=module_assembler_agent.handoff_description,
        ),
        list_pipeline_agent_roles,
    ],
)

# --- Handoff triage (alternative: delegate ownership per branch) ---

curation_triage_agent = Agent(
    name="Curation Triage",
    handoff_description="Routes work to curriculum, relevance, curation, or judging specialists.",
    instructions=(
        f"Route {_subject()} pipeline tasks to the right specialist. "
        "Use handoffs for full ownership; use tools only for bounded subtasks."
    ),
    model=OPENAI_CURATION_MODEL,
    handoffs=[
        curriculum_refiner_agent,
        relevance_scorer_agent,
        text_curator_agent,
        udl_judge_agent,
    ],
)

ALL_AGENTS: dict[str, Agent] = {
    "relevance_scorer": relevance_scorer_agent,
    "curriculum_refiner": curriculum_refiner_agent,
    "text_curator": text_curator_agent,
    "media_linker": media_linker_agent,
    "formula": formula_agent,
    "module_assembler": module_assembler_agent,
    "udl_judge": udl_judge_agent,
    "curation_manager": curation_pipeline_manager,
    "curation_triage": curation_triage_agent,
}
