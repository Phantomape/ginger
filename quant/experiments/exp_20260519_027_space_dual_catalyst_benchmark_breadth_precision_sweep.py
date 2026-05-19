"""exp-20260519-027: Space dual-catalyst benchmark-breadth precision sweep.

Tests one capital-allocation variable on the current accepted Space stack:
whether the accepted source-diverse dual-catalyst benchmark-breadth trend
scalar can be moved from 1.0125 toward the prior 1.025 drawdown boundary
without ratcheting through the original guardrail.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260516_029_space_dual_catalyst_benchmark_breadth_trend_risk as prior


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260519-027"
STEM = "space_dual_catalyst_benchmark_breadth_precision_sweep"
CURRENT_ACCEPTED_EXPERIMENT_ID = "exp-20260516-029"
CURRENT_ACCEPTED_SCALAR = 1.0125
ANCHOR_SCALAR = 1.0
SCALARS = (1.0, 1.0125, 1.015625, 1.01875, 1.021875, 1.025)

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    return prior._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metric_rows(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {label: row["metrics"] for label, row in variant["by_window"].items()}


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return prior.BASE._risk_distribution(variant)


def _gate_variant(
    variant: dict[str, Any],
    current: dict[str, Any],
    anchor: dict[str, Any],
) -> dict[str, Any]:
    current_delta = prior.BASE.exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        current["aggregate"],
    )
    anchor_delta = prior.BASE.exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        anchor["aggregate"],
    )
    by_window_delta = {
        label: prior.BASE.exp041.source_diversity_exp._delta(
            row["metrics"],
            current["by_window"][label]["metrics"],
        )
        for label, row in variant["by_window"].items()
    }
    ev_improved = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] < -1e-9
    }
    counts = variant.get("dual_catalyst_benchmark_breadth_counts") or {}
    by_window_counts = (
        variant.get("dual_catalyst_benchmark_breadth_counts_by_window") or {}
    )
    changed_count = int(counts.get(f"{prior.MARKER}_changed_signal", 0) or 0)
    eligible_count = int(counts.get(f"{prior.MARKER}_eligible_signal", 0) or 0)
    changed_tickers = prior._changed_tickers(counts)
    changed_windows = prior._changed_windows(by_window_counts)
    scalar = float(
        variant["parameters"]["space_dual_catalyst_benchmark_breadth_trend_scalar"]
    )
    anchor_drawdown_ok = (
        anchor_delta["max_drawdown_pct_max"]
        <= prior.BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
    )
    passed = bool(
        scalar != CURRENT_ACCEPTED_SCALAR
        and scalar > CURRENT_ACCEPTED_SCALAR
        and changed_count > 0
        and len(changed_tickers) >= prior.BASE.MIN_ADJUSTED_TICKERS
        and len(changed_windows) >= prior.BASE.MIN_ADJUSTED_WINDOWS
        and current_delta["expected_value_score_sum"] > 0.0
        and current_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and current_delta["max_drawdown_pct_max"]
        <= prior.BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and anchor_drawdown_ok
        and variant["aggregate"].get("min_survival_rate", 0.0)
        >= prior.BASE.MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0)
        >= prior.BASE.MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_current": current_delta,
        "aggregate_delta_vs_anchor": anchor_delta,
        "by_window_delta_vs_current": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "eligible_signal_count": eligible_count,
        "changed_signal_count": changed_count,
        "changed_tickers": changed_tickers,
        "changed_windows": changed_windows,
        "reasons": {
            "non_current_scalar": scalar != CURRENT_ACCEPTED_SCALAR,
            "only_upward_precision_sweep": scalar > CURRENT_ACCEPTED_SCALAR,
            "changed_signals": changed_count,
            "adjusted_ticker_count_ok": (
                len(changed_tickers) >= prior.BASE.MIN_ADJUSTED_TICKERS
            ),
            "adjusted_window_count_ok": (
                len(changed_windows) >= prior.BASE.MIN_ADJUSTED_WINDOWS
            ),
            "current_ev_delta_positive": current_delta[
                "expected_value_score_sum"
            ]
            > 0.0,
            "current_pnl_delta_positive": current_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "current_drawdown_delta_within_limit": (
                current_delta["max_drawdown_pct_max"]
                <= prior.BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "anchor_drawdown_delta_within_limit": anchor_drawdown_ok,
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= prior.BASE.MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= prior.BASE.MIN_TRADE_COUNT,
        },
    }


def _record(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload["current_variant"]
    anchor = payload["anchor_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    selected_scalar = best["parameters"][
        "space_dual_catalyst_benchmark_breadth_trend_scalar"
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": (
            "space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar"
        ),
        "parameters": {
            "scalars_tested": list(SCALARS),
            "current_accepted_scalar": CURRENT_ACCEPTED_SCALAR,
            "selected_scalar": selected_scalar,
            "drawdown_anchor_scalar": ANCHOR_SCALAR,
            "accepted_before_experiment": CURRENT_ACCEPTED_EXPERIMENT_ID,
            "target_strategy": prior.TARGET_STRATEGY,
            "target_profile_gate": "benchmark_breadth_gate",
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in prior.BASE.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": current["aggregate"],
        "anchor_metrics": anchor["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": _metric_rows(current),
        "by_window_after_metrics": _metric_rows(best),
        "by_window_delta": gate["by_window_delta_vs_current"],
        "expected_value_score_delta": gate["aggregate_delta_vs_current"].get(
            "expected_value_score_sum"
        ),
        "total_pnl_delta": gate["aggregate_delta_vs_current"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": _risk_distribution(current),
            "after": _risk_distribution(best),
        },
        "gate_answers": {
            "1_alpha_hypothesis": payload["hypothesis"],
            "2_prior_similar_experiments": [
                "exp-20260516-029 accepted 1.0125 but rejected 1.025 because drawdown drift was slightly above the original guardrail.",
                "exp-20260516-031 rejected target widening on the same current cohort because it changed no EV.",
                "exp-20260518-017 rejected VSAT isolated fallback; candidate-pool expansion remains fragile.",
            ],
            "3_single_causal_variable": (
                "Only the accepted dual-catalyst benchmark-breadth trend scalar "
                "is precision-swept; pool, entries, exits, ranking, event gates, "
                "LLM/news, and live Space slots stay fixed."
            ),
            "4_success_criteria": (
                "Positive EV/PnL versus current 1.0125, at least two improved "
                "windows, no EV-regressed windows, drawdown drift <= 0.5 pp "
                "versus current and the original 1.0 anchor, survival >= 5%, "
                "trade count >= 50, and adjusted cohort across at least two "
                "tickers and two windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260519_027_space_dual_catalyst_benchmark_breadth_precision_sweep.py"
            ),
        },
        "gate_results": gate,
        "gate_results_by_scalar": payload["gate_results_by_scalar"],
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: no precision scalar improved current EV/PnL while "
            "respecting window, survival, trade-count, and original-anchor "
            "drawdown guards."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry this benchmark-breadth scalar axis without new closed "
            "forward rows or a materially different production-visible field."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted scalar must be promoted through shared "
                "space_catalyst_sleeve.py policy and parity tests; live Space "
                "slots remain zero."
                if promoted
                else "Experiment-only wrapper; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, candidate-pool "
            "expansion has old-window and satcom fallback fragility, 20d "
            "durability was rejected, and target widening made no EV change. "
            "This run tests the highest-evidence remaining Space alpha: a "
            "single capital-allocation precision move inside the accepted "
            "source-diverse dual-catalyst benchmark-breadth cohort."
        ),
        "related_files": [
            "quant/experiments/exp_20260519_027_space_dual_catalyst_benchmark_breadth_precision_sweep.py",
            "data/experiments/exp-20260519-027/space_dual_catalyst_benchmark_breadth_precision_sweep.json",
            "experiments/logs/exp-20260519-027.json",
            "experiments/tickets/exp-20260519-027.json",
            "experiments/artifacts/exp-20260519-027_space_dual_catalyst_benchmark_breadth_precision_sweep.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    current = payload["current_variant"]
    anchor = payload["anchor_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space dual-catalyst benchmark-breadth precision sweep",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        "`space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar`.",
        "",
        "## Gate 1 Baseline",
        f"- current accepted scalar: `{CURRENT_ACCEPTED_SCALAR}` from `{CURRENT_ACCEPTED_EXPERIMENT_ID}`",
        f"- current aggregate EV: `{current['aggregate']['expected_value_score_sum']}`",
        f"- current aggregate PnL: `{current['aggregate']['total_pnl_sum']}`",
        f"- anchor scalar for drawdown ratchet check: `{ANCHOR_SCALAR}`",
        f"- anchor aggregate max drawdown pct max: `{anchor['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- dual catalyst profile field check passed: `{payload['dual_profile_field_check']['passed']}`",
        f"- benchmark-breadth field check passed: `{payload['benchmark_breadth_field_check']['passed']}`",
        f"- target tickers: `{payload['benchmark_breadth_field_check'].get('target_tickers')}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{current['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; this is a sizing-only scalar.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_current"].items():
        before_metrics = current["by_window"][label]["metrics"]
        after_metrics = best["by_window"][label]["metrics"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant",
            f"- scalar: `{best['parameters']['space_dual_catalyst_benchmark_breadth_trend_scalar']}`",
            f"- eligible signals: `{gate['eligible_signal_count']}`",
            f"- changed signals: `{gate['changed_signal_count']}`",
            f"- changed tickers: `{gate['changed_tickers']}`",
            f"- changed windows: `{gate['changed_windows']}`",
            f"- aggregate EV delta vs current: `{gate['aggregate_delta_vs_current']['expected_value_score_sum']}`",
            f"- aggregate PnL delta vs current: `{gate['aggregate_delta_vs_current']['total_pnl_sum']}`",
            f"- max drawdown delta vs current: `{gate['aggregate_delta_vs_current']['max_drawdown_pct_max']}`",
            f"- max drawdown delta vs anchor: `{gate['aggregate_delta_vs_anchor']['max_drawdown_pct_max']}`",
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            f"  backtester_adapter_changed: {str(promoted).lower()}",
            f"  run_adapter_changed: {str(promoted).lower()}",
            f"  replay_only: {str(not promoted).lower()}",
            f"  parity_test_added: {str(promoted).lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Precision Space benchmark-breadth scalar "
            f"{best['parameters']['space_dual_catalyst_benchmark_breadth_trend_scalar']} "
            f"changed {gate['changed_signal_count']} signals with EV delta "
            f"{gate['aggregate_delta_vs_current']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    prior.BASE.exp008._install_experiment_path_compat()
    gates = prior.BASE.exp021._collect_gates()
    field_check = prior.BASE.exp051._open_position_field_check()
    dual_profile_field_check = prior.BASE.exp014._field_check_dual_catalyst_profiles()
    benchmark_breadth_field_check = prior._benchmark_breadth_field_check(gates)
    if not field_check["passed"]:
        raise RuntimeError(f"Open-position field check failed: {field_check}")
    if not dual_profile_field_check["passed"]:
        raise RuntimeError(
            f"Dual-catalyst profile field check failed: {dual_profile_field_check}"
        )
    if not benchmark_breadth_field_check["passed"]:
        raise RuntimeError(
            "Benchmark-breadth profile field check failed: "
            f"{benchmark_breadth_field_check}"
        )

    variants = [
        prior._run_variant(benchmark_breadth_scalar=scalar, gates=gates)
        for scalar in SCALARS
    ]
    by_scalar = {
        float(
            variant["parameters"][
                "space_dual_catalyst_benchmark_breadth_trend_scalar"
            ]
        ): variant
        for variant in variants
    }
    current = by_scalar[CURRENT_ACCEPTED_SCALAR]
    anchor = by_scalar[ANCHOR_SCALAR]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, current, anchor)
    accepted = [variant for variant in variants if variant["gate"]["passed"]]
    if accepted:
        best = max(
            accepted,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_current"][
                    "expected_value_score_sum"
                ],
                item["gate"]["aggregate_delta_vs_current"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_current"][
                    "expected_value_score_sum"
                ],
                item["gate"]["aggregate_delta_vs_current"]["total_pnl_sum"],
            ),
        )

    decision = "accept" if best["gate"]["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "gates": gates,
        "field_check": field_check,
        "dual_profile_field_check": dual_profile_field_check,
        "benchmark_breadth_field_check": benchmark_breadth_field_check,
        "variants": variants,
        "anchor_variant": anchor,
        "current_variant": current,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][
                    "space_dual_catalyst_benchmark_breadth_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "hypothesis": (
            "The accepted source-diverse dual-catalyst benchmark-breadth Space "
            "trend cohort may be under-allocated at 1.0125; a finer scalar "
            "inside the prior 1.025 drawdown boundary could improve EV while "
            "keeping the original anchor drawdown guard intact."
        ),
        "changed_variable": (
            "space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar"
        ),
    }
    payload["experiment_log_record"] = _record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    payload = run()
    persist(payload)
    best = payload["best_variant"]
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_scalar": best["parameters"][
                        "space_dual_catalyst_benchmark_breadth_trend_scalar"
                    ],
                    "eligible_signals": gate["eligible_signal_count"],
                    "changed_signals": gate["changed_signal_count"],
                    "changed_tickers": gate["changed_tickers"],
                    "changed_windows": gate["changed_windows"],
                    "aggregate_ev_delta_vs_current": gate[
                        "aggregate_delta_vs_current"
                    ]["expected_value_score_sum"],
                    "aggregate_pnl_delta_vs_current": gate[
                        "aggregate_delta_vs_current"
                    ]["total_pnl_sum"],
                    "max_drawdown_delta_vs_current": gate[
                        "aggregate_delta_vs_current"
                    ]["max_drawdown_pct_max"],
                    "max_drawdown_delta_vs_anchor": gate[
                        "aggregate_delta_vs_anchor"
                    ]["max_drawdown_pct_max"],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                    "gate_reasons": gate["reasons"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
