"""exp-20260515-023: Space defense-budget early-RS60 trend risk.

Tests one risk-allocation variable on top of accepted exp-20260515-021:
whether official Space defense-budget same-theme winners that have not yet
entered the RS60 top-quintile state deserve a small extra default-off top-up.

This keeps entries, exits, ranking, ticker breadth, LLM authority, and live
Space slots unchanged.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260514_041_space_benchmark_breadth_trend_risk as exp041
import exp_20260514_051_space_defense_budget_delayed_benchmark_trend_risk as exp051
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-023"
STEM = "space_defense_budget_early_rs60_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260515-021"
BEFORE_STEM = "space_defense_budget_same_theme_winner_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
MARKER = "space_defense_budget_early_rs60_trend_risk"

ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR = 1.05
SCALARS = (1.0, 1.0125, 1.025, 1.05, 1.075)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(value: Any) -> Any:
    return exp051._safe(value)


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


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return False


def _extra_scale_and_record(
    *,
    signal: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    counts: Counter[str],
    adjustments: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> None:
    ticker = str(signal.get("ticker") or "").upper()
    shares_before = int(sizing.get("shares_to_buy") or 0)
    dollars_before = float(sizing.get("position_size_dollars") or 0.0)
    exp041.source_diversity_exp._scale_sizing(
        sizing,
        scalar,
        portfolio_value,
        MARKER,
    )
    shares_after = int(sizing.get("shares_to_buy") or 0)
    dollars_after = float(sizing.get("position_size_dollars") or 0.0)
    counts[f"{MARKER}_eligible_signal"] += 1
    counts[f"{MARKER}_eligible_{ticker}"] += 1
    if shares_after != shares_before:
        counts[f"{MARKER}_changed_signal"] += 1
        counts[f"{MARKER}_changed_{ticker}"] += 1
    adjustments.append(
        {
            "ticker": ticker,
            "strategy": signal.get("strategy"),
            "date": str(signal.get("date") or ""),
            "marker": MARKER,
            "scalar": scalar,
            "shares_before_scalar": shares_before,
            "shares_after_scalar": shares_after,
            "dollars_before_scalar": dollars_before,
            "dollars_after_scalar": dollars_after,
            "profile": profile,
            "rs60_top_quintile_state": signal.get("rs60_top_quintile_state"),
            "momentum_60d_pct": signal.get("momentum_60d_pct"),
            "rs60_top_quintile_cutoff": signal.get("rs60_top_quintile_cutoff"),
            "price_vs_200ma_pct": signal.get("price_vs_200ma_pct"),
            "price_vs_200ma_extension_state": signal.get(
                "price_vs_200ma_extension_state"
            ),
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_exp021_stack_variant(
    label: str,
    *,
    early_rs60_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_extra = exp021._extra_scale_and_record
    early_adjustments: list[dict[str, Any]] = []

    def patched_extra(
        *,
        signal: dict[str, Any],
        sizing: dict[str, Any],
        scalar: float,
        portfolio_value: float,
        counts: Counter[str],
        adjustments: list[dict[str, Any]],
        profile: dict[str, Any] | None,
    ) -> None:
        original_extra(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        if str(signal.get("strategy") or "") != TARGET_STRATEGY:
            return
        if not sizing:
            return
        if "rs60_top_quintile_state" not in signal:
            counts[f"{MARKER}_missing_rs60_top_quintile_state"] += 1
            return
        if _is_true(signal.get("rs60_top_quintile_state")):
            counts[f"{MARKER}_skipped_rs60_top_quintile"] += 1
            return
        _extra_scale_and_record(
            signal=signal,
            sizing=sizing,
            scalar=early_rs60_scalar,
            portfolio_value=portfolio_value,
            counts=counts,
            adjustments=early_adjustments,
            profile=profile,
        )
        signal["space_defense_budget_early_rs60_trend_bucket"] = True
        signal["space_defense_budget_early_rs60_trend_scalar"] = early_rs60_scalar
        signal["space_defense_budget_early_rs60_profile"] = profile

    exp021._extra_scale_and_record = patched_extra
    try:
        variant = exp021._run_exp051_stack_variant(
            label,
            defense_same_theme_winner_scalar=(
                ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
            ),
            gates=gates,
        )
    finally:
        exp021._extra_scale_and_record = original_extra

    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    by_window_counts = {
        name: {
            key: value
            for key, value in sorted(
                (row.get("source_diversity_trend_counts") or {}).items()
            )
            if MARKER in key
        }
        for name, row in variant["by_window"].items()
    }
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "accepted_defense_budget_same_theme_winner_trend_scalar": (
            ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
        ),
        "space_defense_budget_early_rs60_trend_scalar": early_rs60_scalar,
        "target_strategy": TARGET_STRATEGY,
        "requires_rs60_top_quintile_state": False,
        "defense_budget_same_theme_winner_target_tickers": gates[
            "defense_budget_same_theme_winner_gate"
        ]["target_tickers"],
    }
    variant["defense_budget_early_rs60_counts"] = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    variant["defense_budget_early_rs60_counts_by_window"] = by_window_counts
    variant["defense_budget_early_rs60_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(early_adjustments)
    )
    variant["defense_budget_early_rs60_adjustment_sample"] = early_adjustments[:25]
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        label: exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
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
    counts = variant.get("defense_budget_early_rs60_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    missing_count = int(counts.get(f"{MARKER}_missing_rs60_top_quintile_state", 0))
    scalar = float(
        variant["parameters"]["space_defense_budget_early_rs60_trend_scalar"]
    )
    passed = bool(
        scalar != 1.0
        and changed_count > 0
        and missing_count == 0
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "eligible_early_rs60_signal_count": eligible_count,
        "changed_early_rs60_signal_count": changed_count,
        "missing_rs60_top_quintile_state_count": missing_count,
        "reasons": {
            "non_identity_scalar": scalar != 1.0,
            "changed_signals": changed_count,
            "rs60_field_present": missing_count == 0,
            "aggregate_ev_delta_positive": aggregate_delta[
                "expected_value_score_sum"
            ]
            > 0.0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= MIN_TRADE_COUNT,
        },
    }


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            key: row["metrics"].get(key)
            for key in (
                "worst_trade_pct",
                "max_consecutive_losses",
                "tail_loss_share",
            )
        }
        for label, row in variant["by_window"].items()
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": (
            "Within accepted Space defense-budget same-theme winners, trend "
            "signals that have not yet reached RS60 top-quintile status may "
            "represent earlier catalyst continuation and deserve a small "
            "default-off allocation top-up."
        ),
        "change_type": "alpha_search",
        "changed_variable": "space_defense_budget_early_rs60_trend_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": best["parameters"][
                "space_defense_budget_early_rs60_trend_scalar"
            ],
            "target_strategy": TARGET_STRATEGY,
            "requires_rs60_top_quintile_state": False,
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_defense_budget_same_theme_winner_trend_scalar": (
                ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
            ),
            "target_tickers": payload["gates"][
                "defense_budget_same_theme_winner_gate"
            ]["target_tickers"],
            "target_profile_row_count": payload["gates"][
                "defense_budget_same_theme_winner_gate"
            ]["target_profile_row_count"],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec for label, spec in exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": {
            label: item["metrics"] for label, item in before["by_window"].items()
        },
        "by_window_after_metrics": {
            label: item["metrics"] for label, item in best["by_window"].items()
        },
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "total_pnl_delta": gate["aggregate_delta_vs_before"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": _risk_distribution(before),
            "after": _risk_distribution(best),
        },
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Risk allocation for Space defense-budget same-theme winner "
                "trend signals that are still below RS60 top-quintile."
            ),
            "2_prior_similar_experiments": [
                "exp-20260515-021 accepted a same-theme-winner defense-budget top-up.",
                "exp-20260515-020 rejected a broad RS60 x price-extension overlap top-up.",
                "exp-20260515-019 rejected Space theme-beta pool expansion.",
                "No prior Space experiment found that isolates the accepted defense-budget same-theme winner cohort by early RS60 state.",
            ],
            "3_single_causal_variable": (
                "extra scalar on accepted defense-budget same-theme winner "
                "signals only when rs60_top_quintile_state is false"
            ),
            "4_success_criteria": (
                "Aggregate EV and PnL positive, at least two EV-improved "
                "windows, no EV-regressed windows, max drawdown drift <= 0.5 "
                "pp, survival >= 5%, trade count >= 50, adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_023_space_defense_budget_early_rs60_trend_risk.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: selected early-RS60 scalar did not improve enough "
            "fixed windows without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Avoid another nearby defense-budget scalar retry until new closed "
            "Space rows or a different production-visible catalyst-quality "
            "field exists."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted helper must be promoted only through shared "
                "space_catalyst_sleeve.py policy and parity tests; live Space "
                "slots remain zero."
                if promoted
                else "Experiment-only monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited, recent Space candidate-pool "
            "expansion failed, and this isolates one production-visible "
            "catalyst-quality allocation state instead."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space defense-budget early-RS60 trend risk",
        "",
        "## Hypothesis",
        (
            "Accepted defense-budget same-theme winner `trend_long` signals "
            "that have not yet reached RS60 top-quintile status may deserve a "
            "small extra default-off allocation as earlier catalyst continuation."
        ),
        "",
        "## Single Changed Variable",
        (
            "`space_defense_budget_early_rs60_trend_scalar` on top of accepted "
            f"`{BEFORE_EXPERIMENT_ID}`."
        ),
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- missing runtime `rs60_top_quintile_state`: `{gate['missing_rs60_top_quintile_state_count']}`",
        f"- target tickers: `{payload['gates']['defense_budget_same_theme_winner_gate']['target_tickers']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; this is a sizing-only scalar.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
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
            f"- scalar: `{best['parameters']['space_defense_budget_early_rs60_trend_scalar']}`",
            f"- eligible signals: `{gate['eligible_early_rs60_signal_count']}`",
            f"- adjusted signals: `{gate['changed_early_rs60_signal_count']}`",
            f"- adjusted counts: `{best['defense_budget_early_rs60_counts']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- max drawdown pct max delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
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
            f"Defense-budget early-RS60 trend scalar "
            f"{best['parameters']['space_defense_budget_early_rs60_trend_scalar']} "
            f"changed {gate['changed_early_rs60_signal_count']} signals with "
            f"aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = exp021._collect_gates()
    variants = [
        _run_exp021_stack_variant(
            label=f"{STEM}_{str(scalar).replace('.', '_')}",
            early_rs60_scalar=scalar,
            gates=gates,
        )
        for scalar in SCALARS
    ]
    before = variants[0]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)
    accepted = [variant for variant in variants if variant["gate"]["passed"]]
    if accepted:
        best = max(
            accepted,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    field_check = exp051._open_position_field_check()
    decision = "accept" if best["gate"]["passed"] and field_check["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "core_baseline": core,
        "gates": gates,
        "field_check": field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][
                    "space_defense_budget_early_rs60_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "alpha_hypothesis": (
            "Defense-budget same-theme winner Space trend signals below RS60 "
            "top-quintile may merit a conservative default-off risk top-up."
        ),
        "changed_variable": "space_defense_budget_early_rs60_trend_scalar",
    }
    payload["experiment_log_record"] = _experiment_record(payload)
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
                        "space_defense_budget_early_rs60_trend_scalar"
                    ],
                    "eligible_signals": gate["eligible_early_rs60_signal_count"],
                    "adjusted_signals": gate["changed_early_rs60_signal_count"],
                    "missing_rs60_top_quintile_state": gate[
                        "missing_rs60_top_quintile_state_count"
                    ],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
