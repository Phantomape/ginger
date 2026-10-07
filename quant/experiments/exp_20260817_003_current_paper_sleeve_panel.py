"""Materialize the 41-surface panel and rerun the core-plus-paper allocator."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

from quant import current_paper_core_allocator as allocator
from quant import historical_current_contract_reassessment as reassess
from quant.current_paper_sleeve_panel import (
    REPO_ROOT,
    build_panel,
    panel_identity,
    serializable_panel,
)


EXPERIMENT_ID = "exp-20260817-003"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _refinement_support(coarse: Mapping[str, Any]) -> tuple[str, ...]:
    selected = tuple(coarse["selected"]["weights"])
    if selected:
        return selected
    return tuple(
        sorted(
            set((coarse.get("best_nonzero_unconstrained") or {}).get("weights", {}))
            | set((coarse.get("best_pnl_nonzero") or {}).get("weights", {}))
        )
    )


def _search(
    names: Sequence[str],
    panel: Mapping[str, Any],
    *,
    walk_forward: bool,
) -> dict[str, Any]:
    returns = {name: panel["surface_returns"][name] for name in names}
    coarse = allocator.optimize_allocations(
        allocator.enumerate_coarse_allocations(names),
        labels=allocator.WINDOWS,
        core_returns=panel["core_returns"],
        surface_returns=returns,
    )
    support = _refinement_support(coarse)
    refined = allocator.optimize_allocations(
        allocator.enumerate_refined_allocations(support),
        labels=allocator.WINDOWS,
        core_returns=panel["core_returns"],
        surface_returns=returns,
    )
    return {
        "surface_count": len(names),
        "surfaces": list(names),
        "coarse": coarse,
        "refinement_support": list(support),
        "refined": refined,
        "walk_forward": (
            allocator._walk_forward(panel["core_returns"], returns)
            if walk_forward
            else None
        ),
    }


def _expanded_weights(weights: Mapping[str, float]) -> dict[str, float]:
    return {
        str(spec["surface"]): float(weights.get(str(spec["surface"]), 0.0))
        for spec in allocator.SURFACE_SPECS
    }


def run(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    if not output.is_absolute():
        output = REPO_ROOT / output
    output.mkdir(parents=True, exist_ok=True)

    panel = build_panel()
    serial = serializable_panel(panel)
    serial["panel_identity_sha256"] = panel_identity(serial)
    _write_json(output / "current_paper_sleeve_panel.json", serial)
    _write_json(
        output / "surface_inventory.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "summary": panel["summary"],
            "inventory": panel["inventory"],
            "research_diagnostics": panel["research_diagnostics"],
        },
    )

    research_names = tuple(panel["summary"]["research_combinable_surfaces"])
    current_names = tuple(panel["summary"]["current_enabled_combinable_surfaces"])
    research_search = _search(research_names, panel, walk_forward=False)
    current_search = _search(current_names, panel, walk_forward=True)

    manifest = allocator.write_coarse_combination_manifest(
        output / "research_39_surface_coarse_combination_manifest.jsonl",
        eligible=research_names,
        core_returns=panel["core_returns"],
        surface_returns=panel["surface_returns"],
    )
    if manifest["total_vector_count"] != research_search["coarse"]["scanned_vector_count"]:
        raise ValueError("research search and combination manifest counts differ")

    recent = allocator.recent_surface_diagnostics()
    recent_hindsight = allocator.optimize_recent(recent)
    classic_selected = current_search["refined"]["selected"]
    recent_check = allocator.selected_recent_check(classic_selected["weights"], recent)
    concentration = allocator.ticker_concentration(classic_selected["weights"], panel)
    walk_rows = current_search["walk_forward"] or []
    robust = (
        bool(classic_selected["weights"])
        and bool(classic_selected["feasible"])
        and all(bool(row["passed"]) for row in walk_rows)
        and bool(recent_check["nonnegative_vs_all"])
        and bool(concentration["passed"])
    )
    recommended_weights = dict(classic_selected["weights"]) if robust else {}
    recommended = allocator.evaluate_allocation(
        recommended_weights,
        labels=allocator.WINDOWS,
        core_returns=panel["core_returns"],
        surface_returns=panel["surface_returns"],
    )

    surface_metrics = {
        name: {
            window: reassess.current_return_metrics(panel["surface_returns"][name][window])
            for window in allocator.WINDOWS
        }
        for name in research_names
    }
    result = {
        "schema": "ginger.current_paper_sleeve_panel.v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "measurement_decision": "accepted_measurement_repair",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "production_changed": False,
        "panel_identity_sha256": serial["panel_identity_sha256"],
        "panel_summary": panel["summary"],
        "input_identity": panel["input_identity"],
        "surface_metrics": surface_metrics,
        "selection_contract": {
            "classic_windows": list(allocator.WINDOWS),
            "research_universe": "all canonical complete paths, including six currently disabled surfaces",
            "current_universe": "canonical complete and current paper_enabled paths",
            "total_paper_cap": allocator.TOTAL_PAPER_CAP,
            "surface_cap": allocator.SURFACE_CAP,
            "max_active_surfaces": allocator.MAX_ACTIVE_SURFACES,
            "coarse_levels": list(allocator.COARSE_LEVELS),
            "refined_step": allocator.REFINED_STEP,
            "conflict_edges": [sorted(edge) for edge in allocator.CONFLICT_EDGES],
            "recent_use": "settled replacement-value contradiction check only",
        },
        "research_39_surface_search": research_search,
        "research_coarse_combination_manifest": manifest,
        "current_enabled_33_surface_search": current_search,
        "recent_hindsight_search": recent_hindsight,
        "classic_selected_recent_check": recent_check,
        "ticker_concentration": concentration,
        "recommended_allocation": {
            **recommended,
            "all_41_weights": _expanded_weights(recommended_weights),
            "reason": (
                "all classic, walk-forward, recent, and concentration checks passed"
                if robust
                else "fail-closed to 100% core because at least one robustness check failed"
            ),
        },
        "robust_nonnull_allocation_passed": robust,
        "limitations": [
            "core_misfit is a counterfactual attribution ledger with three opposing tracks, not one capital return series.",
            "core_drawdown_flow_put has research-PIT partial history and cannot pass the three-window canonical contract.",
            "Classic windows are reused research windows, not untouched holdouts.",
            "Recent evidence covers settled rows for 21 surfaces and is not a full daily covariance panel.",
            "Research search may include six current paper-disabled surfaces and is never an execution recommendation.",
        ],
    }
    _write_json(output / "current_paper_sleeve_panel_result.json", result)

    before_windows = {
        window: reassess.current_return_metrics(panel["core_returns"][window])
        for window in allocator.WINDOWS
    }
    after_windows = {
        window: recommended["windows"][window]["combined_metrics"]
        for window in allocator.WINDOWS
    }
    before = {
        "schema": "ginger.current_paper_sleeve_panel.measurement.v1",
        "experiment_id": EXPERIMENT_ID,
        "role": "before_exp_20260817_002_artifact_only_panel",
        "classic_complete_surface_count": 21,
        "registered_surface_count": 41,
        "expected_value_score": sum(float(row["expected_value_score"]) for row in before_windows.values()),
        "total_pnl": sum(float(row["total_pnl"]) for row in before_windows.values()),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in before_windows.values()),
        "windows": before_windows,
    }
    after = {
        "schema": "ginger.current_paper_sleeve_panel.measurement.v1",
        "experiment_id": EXPERIMENT_ID,
        "role": "after_version_aware_41_surface_panel",
        "classic_complete_surface_count": len(research_names),
        "current_enabled_complete_surface_count": len(current_names),
        "registered_surface_count": 41,
        "expected_value_score": sum(float(row["expected_value_score"]) for row in after_windows.values()),
        "total_pnl": sum(float(row["total_pnl"]) for row in after_windows.values()),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in after_windows.values()),
        "windows": after_windows,
        "measurement_repair_passed": len(research_names) == 39,
        "recommended_weights": _expanded_weights(recommended_weights),
    }
    _write_json(output / "before_measurement.json", before)
    _write_json(output / "after_measurement.json", after)

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "measurement_decision": "accepted_measurement_repair",
        "registered_surface_count": 41,
        "classic_complete_surface_count": len(research_names),
        "current_enabled_complete_surface_count": len(current_names),
        "residual_blockers": panel["summary"]["unsupported_or_incomplete_surfaces"],
        "research_coarse_vectors_scanned": research_search["coarse"]["scanned_vector_count"],
        "current_coarse_vectors_scanned": current_search["coarse"]["scanned_vector_count"],
        "research_refined_weights": research_search["refined"]["selected"]["weights"],
        "current_refined_weights": classic_selected["weights"],
        "walk_forward_all_pass": all(bool(row["passed"]) for row in walk_rows),
        "recent_support_check": recent_check,
        "recent_hindsight_weights": (recent_hindsight.get("selected") or {}).get("weights", {}),
        "robust_nonnull_allocation_passed": robust,
        "recommended_weights": recommended_weights,
        "core_weight": recommended["core_weight"],
        "panel_identity_sha256": serial["panel_identity_sha256"],
        "result_artifact": str(
            (output / "current_paper_sleeve_panel_result.json").relative_to(REPO_ROOT)
        ).replace("\\", "/"),
    }
    _write_json(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", default=f"data/experiments/{EXPERIMENT_ID}"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), ensure_ascii=False, indent=2, sort_keys=True))
