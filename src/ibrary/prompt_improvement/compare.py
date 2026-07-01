"""Compare prompt versions using the UDL subtopic judge."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from ibrary.curation.schemas import CuratedModule
from ibrary.judging import DEFAULT_PASS_THRESHOLD, evaluate_content, module_to_judge_input
from ibrary.prompt_improvement.schemas import PromptImprovementReport, PromptVersionComparison

logger = structlog.get_logger(__name__)


def _load_modules_by_unit(path: Path) -> dict[str, CuratedModule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array in {path}")
    out: dict[str, CuratedModule] = {}
    for item in data:
        m = CuratedModule.model_validate(item)
        out[m.curriculum_unit_id] = m
    return out


def compare_prompt_versions(
    baseline_modules: list[CuratedModule],
    candidate_modules: list[CuratedModule],
    *,
    threshold: float = DEFAULT_PASS_THRESHOLD,
    min_delta: float = 0.25,
) -> PromptImprovementReport:
    """Judge baseline vs candidate modules per subtopic; decide if quality improved.

    ``improved`` on the report is True when mean candidate score exceeds baseline
    by at least ``min_delta``.
    """
    base_by_id = {m.curriculum_unit_id: m for m in baseline_modules}
    cand_by_id = {m.curriculum_unit_id: m for m in candidate_modules}
    unit_ids = sorted(set(base_by_id) & set(cand_by_id))

    if not unit_ids:
        raise ValueError("no overlapping curriculum_unit_id between baseline and candidate")

    baseline_pv = baseline_modules[0].prompt_version if baseline_modules else ""
    candidate_pv = candidate_modules[0].prompt_version if candidate_modules else ""

    comparisons: list[PromptVersionComparison] = []
    improved_count = 0
    regressed_count = 0
    base_scores: list[float] = []
    cand_scores: list[float] = []

    for uid in unit_ids:
        b_mod, c_mod = base_by_id[uid], cand_by_id[uid]
        b_res = evaluate_content(module_to_judge_input(b_mod), threshold=threshold)
        c_res = evaluate_content(module_to_judge_input(c_mod), threshold=threshold)
        b_score = float(b_res.overall_score or 0)
        c_score = float(c_res.overall_score or 0)
        delta = c_score - b_score
        unit_improved = delta >= min_delta
        if unit_improved:
            improved_count += 1
        elif delta < 0:
            regressed_count += 1
        base_scores.append(b_score)
        cand_scores.append(c_score)
        comparisons.append(
            PromptVersionComparison(
                curriculum_unit_id=uid,
                baseline_prompt_version=b_mod.prompt_version or baseline_pv,
                candidate_prompt_version=c_mod.prompt_version or candidate_pv,
                baseline_score=b_score,
                candidate_score=c_score,
                delta_overall=delta,
                improved=unit_improved,
                baseline=b_res,
                candidate=c_res,
            )
        )

    mean_b = sum(base_scores) / len(base_scores)
    mean_c = sum(cand_scores) / len(cand_scores)
    mean_delta = mean_c - mean_b

    report = PromptImprovementReport(
        baseline_prompt_version=baseline_pv,
        candidate_prompt_version=candidate_pv,
        comparisons=comparisons,
        mean_baseline=mean_b,
        mean_candidate=mean_c,
        mean_delta=mean_delta,
        improved=mean_delta >= min_delta,
        units_improved=improved_count,
        units_regressed=regressed_count,
    )
    logger.info(
        "prompt_comparison_complete",
        improved=report.improved,
        mean_delta=mean_delta,
        units=len(unit_ids),
    )
    return report


def compare_curated_files(
    baseline_path: str | Path,
    candidate_path: str | Path,
    **kwargs,
) -> PromptImprovementReport:
    """Load two ``curated_content.json`` files and compare via judge."""
    base_mods = list(_load_modules_by_unit(Path(baseline_path)).values())
    cand_mods = list(_load_modules_by_unit(Path(candidate_path)).values())
    return compare_prompt_versions(base_mods, cand_mods, **kwargs)


def save_improvement_report(report: PromptImprovementReport, output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"prompt_improvement_{report.baseline_prompt_version}_vs_{report.candidate_prompt_version}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path
