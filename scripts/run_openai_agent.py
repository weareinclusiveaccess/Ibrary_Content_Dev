#!/usr/bin/env python3
"""CLI to run an IBrary OpenAI Agents SDK specialist or manager.

Examples:
    python scripts/run_openai_agent.py --agent relevance_scorer --message "Score chunk ..."
    python scripts/run_openai_agent.py --agent curation_manager --unit bio_sss1_theme1_topic1_content0
    python scripts/run_openai_agent.py --agent udl_judge --message "Evaluate this content: ..."
    python scripts/run_openai_agent.py --list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run IBrary OpenAI Agents SDK agent.")
    parser.add_argument("--list", action="store_true", help="List agent names")
    parser.add_argument("--agent", type=str, default="curation_manager", help="Agent key from ALL_AGENTS")
    parser.add_argument("--message", type=str, default="", help="User message / task")
    parser.add_argument(
        "--unit",
        type=str,
        default="",
        help="Shorthand: curate this curriculum_unit_id (sets message for curation_manager)",
    )
    args = parser.parse_args()

    try:
        from ibrary.pipeline.openai_agents import ALL_AGENTS, run_agent_sync, run_curation_manager
    except ImportError as exc:
        print("Install OpenAI Agents SDK: uv add openai-agents", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.list:
        for key in sorted(ALL_AGENTS):
            agent = ALL_AGENTS[key]
            desc = getattr(agent, "handoff_description", "") or ""
            print(f"  {key}: {agent.name} — {desc[:80]}")
        return

    if args.unit:
        result = run_curation_manager(args.unit)
        print(result.final_output)
        return

    message = args.message or "List pipeline roles and explain your job."
    agent = ALL_AGENTS.get(args.agent)
    if agent is None:
        print(f"Unknown agent {args.agent!r}. Use --list.", file=sys.stderr)
        sys.exit(1)
    result = run_agent_sync(agent, message)
    print(result.final_output)


if __name__ == "__main__":
    main()
