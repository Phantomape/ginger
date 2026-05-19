"""exp-20260514-053: Space benchmark-breadth IWM-leader trend risk.

Tests one risk-allocation variable on top of the accepted exp-20260514-051
Space stack: whether official Space trend signals with broad closed 10d
benchmark confirmation deserve another small default-off top-up when IWM 20d
momentum leads SPY.

This does not change entries, exits, ranking, ticker breadth, LLM authority, or
live Space slots.
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
import exp_20260514_047_space_benchmark_same_theme_strength_trend_risk as exp047
import exp_20260514_051_space_defense_budget_delayed_benchmark_trend_risk as exp051


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260514-053"
STEM = "space_benchmark_breadth_iwm_leader_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-051"
BEFORE_STEM = "space_defense_budget_delayed_benchmark_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
TARGET_IWM_STATE = "smallcap_leader"
MARKER = "space_benchmark_breadth_iwm_leader_trend_risk"

ACCEPTED_SAME_THEME_STRENGTH_SCALAR = 1.025
ACCEPTED_DEFENSE_BUDGET_DELAYED_BENCHMARK_SCALAR = 1.025
SCALARS = (1.0, 1.0125, 1.025, 1.05, 1.075)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(value: Any) -> Any:
    return exp051._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    exp051._write_json(path, payload)


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    exp051._append_jsonl_for_this_experiment(path, payload)


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
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_exp051_stack_variant(
    label: str,
    *,
    iwm_leader_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_extra = exp041._scale_and_record_extra
    benchmark_tickers = set(gates["benchmark_breadth_gate"]["target_tickers"])
    benchmark_profiles = gates["benchmark_breadth_gate"]["profiles"]
    defense_tickers = set(gates["defense_budget_delayed_benchmark_gate"]["target_tickers"])
    defense_profiles = gates["defense_budget_delayed_benchmark_gate"]["profiles"]
    iwm_adjustments: list[dict[str, Any]] = []

    def patched_extra(
        *,
        signal: dict[str, Any],
        sizing: dict[str, Any],
        scalar: float,
        portfolio_value: float,
        marker: str,
        counts: Counter[str],
        adjustments: list[dict[str, Any]],
        profile: dict[str, Any] | None,
    ) -> None:
        original_extra(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=marker,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        if marker != "space_benchmark_breadth_trend_risk":
            return
        if str(signal.get("strategy") or "") != TARGET_STRATEGY:
            return
        if not sizing:
            return
        ticker = str(signal.get("ticker") or "").upper()
        if ticker in defense_tickers:
            exp051._extra_scale_and_record(
                signal=signal,
                sizing=sizing,
                scalar=ACCEPTED_DEFENSE_BUDGET_DELAYED_BENCHMARK_SCALAR,
                portfolio_value=portfolio_value,
                counts=counts,
                adjustments=adjustments,
                profile=defense_profiles.get(ticker),
            )
            signal["space_defense_budget_delayed_benchmark_trend_bucket"] = True
            signal["space_defense_budget_delayed_benchmark_trend_scalar"] = (
                ACCEPTED_DEFENSE_BUDGET_DELAYED_BENCHMARK_SCALAR
            )
            signal["space_defense_budget_delayed_benchmark_profile"] = (
                defense_profiles.get(ticker)
            )
        if (
            ticker in benchmark_tickers
            and str(signal.get("space_iwm_relative_state") or "") == TARGET_IWM_STATE
        ):
            _extra_scale_and_record(
                signal=signal,
                sizing=sizing,
                scalar=iwm_leader_scalar,
                portfolio_value=portfolio_value,
                counts=counts,
                adjustments=iwm_adjustments,
                profile=benchmark_profiles.get(ticker),
            )
            signal["space_benchmark_breadth_iwm_leader_trend_bucket"] = True
            signal["space_benchmark_breadth_iwm_leader_trend_scalar"] = (
                iwm_leader_scalar
            )

    exp041._scale_and_record_extra = patched_extra
    try:
        variant = exp047._run_exp044_stack_variant(
            label,
            same_theme_strength_scalar=ACCEPTED_SAME_THEME_STRENGTH_SCALAR,
            gates=gates,
        )
    finally:
        exp041._scale_and_record_extra = original_extra

    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    iwm_counts = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    defense_counts = {
        key: value
        for key, value in sorted(counts.items())
        if exp051.MARKER in key
    }
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
        "accepted_benchmark_breadth_same_theme_strength_trend_scalar": (
            ACCEPTED_SAME_THEME_STRENGTH_SCALAR
        ),
        "accepted_defense_budget_delayed_benchmark_trend_scalar": (
            ACCEPTED_DEFENSE_BUDGET_DELAYED_BENCHMARK_SCALAR
        ),
        "space_benchmark_breadth_iwm_leader_trend_scalar": iwm_leader_scalar,
        "target_strategy": TARGET_STRATEGY,
        "target_iwm_relative_state": TARGET_IWM_STATE,
        "benchmark_breadth_target_tickers": sorted(benchmark_tickers),
    }
    variant["benchmark_breadth_iwm_leader_counts"] = iwm_counts
    variant["benchmark_breadth_iwm_leader_counts_by_window"] = by_window_counts
    variant["benchmark_breadth_iwm_leader_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(iwm_adjustments)
    )
    variant["benchmark_breadth_iwm_leader_adjustment_sample"] = iwm_adjustments[:25]
    variant["defense_budget_delayed_benchmark_counts"] = defense_counts
    variant["defense_budget_delayed_benchmark_adjusted_signal_count"] = counts.get(
        f"{exp051.MARKER}_changed_signal",
        0,
    )
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
    counts = variant.get("benchmark_breadth_iwm_leader_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    scalar = float(variant["parameters"]["space_benchmark_breadth_iwm_leader_trend_scalar"])
    passed = bool(
        scalar != 1.0
        and changed_count > 0
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
        "eligible_iwm_leader_signal_count": eligible_count,
        "changed_iwm_leader_signal_count": changed_count,
        "reasons": {
            "non_identity_scalar": scalar != 1.0,
            "changed_signals": changed_count,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"] > 0.0,
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


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    decision = payload["decision"]
    promoted = decision == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": (
            "Official Space trend signals with broad 10d benchmark confirmation "
            "deserve a small extra default-off allocation when IWM 20d momentum "
            "leads SPY."
        ),
        "change_type": "alpha_search",
        "changed_variable": "space_benchmark_breadth_iwm_leader_trend_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": best["parameters"][
                "space_benchmark_breadth_iwm_leader_trend_scalar"
            ],
            "target_strategy": TARGET_STRATEGY,
            "target_iwm_relative_state": TARGET_IWM_STATE,
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_defense_budget_delayed_benchmark_trend_scalar": (
                ACCEPTED_DEFENSE_BUDGET_DELAYED_BENCHMARK_SCALAR
            ),
            "accepted_benchmark_breadth_same_theme_strength_trend_scalar": (
                ACCEPTED_SAME_THEME_STRENGTH_SCALAR
            ),
            "benchmark_breadth_target_tickers": payload["gates"][
                "benchmark_breadth_gate"
            ]["target_tickers"],
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
            "before": {
                label: {
                    key: row["metrics"].get(key)
                    for key in (
                        "worst_trade_pct",
                        "max_consecutive_losses",
                        "tail_loss_share",
                    )
                }
                for label, row in before["by_window"].items()
            },
            "after": {
                label: {
                    key: row["metrics"].get(key)
                    for key in (
                        "worst_trade_pct",
                        "max_consecutive_losses",
                        "tail_loss_share",
                    )
                }
                for label, row in best["by_window"].items()
            },
        },
        "gate_results": gate,
        "decision": decision,
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: selected scalar did not improve enough fixed "
            "windows without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "New closed Space forward rows or a materially different "
            "benchmark-breadth tape-participation discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promoted,
            "replay_only": True,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted helper should be promoted to shared "
                "space_catalyst_sleeve.py metadata/risk-scalar path; live Space "
                "slots remain zero."
                if promoted
                else "Experiment-only monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited, and recent Space ticker "
            "expansion plus timing retests failed. This keeps the candidate set "
            "fixed and tests one production-visible tape participation state."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space benchmark-breadth IWM-leader trend risk",
        "",
        "## Hypothesis",
        (
            "Official Space `trend_long` signals with broad 10d confirmation "
            "versus cash, SPY, QQQ, UFO, and ARKX may deserve a small extra "
            "default-off allocation when IWM 20d momentum leads SPY."
        ),
        "",
        "## Single Changed Variable",
        (
            "`space_benchmark_breadth_iwm_leader_trend_scalar` on top of the "
            f"accepted `{BEFORE_EXPERIMENT_ID}` Space stack."
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
        f"- benchmark-breadth gate passed: `{payload['gates']['benchmark_breadth_gate']['passed']}`",
        f"- target IWM state: `{TARGET_IWM_STATE}`",
        f"- benchmark-breadth target tickers: `{payload['gates']['benchmark_breadth_gate']['target_tickers']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; trade count and survival should not decline except through sizing-side effects.",
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
            f"- scalar: `{best['parameters']['space_benchmark_breadth_iwm_leader_trend_scalar']}`",
            f"- eligible signals: `{gate['eligible_iwm_leader_signal_count']}`",
            f"- adjusted signals: `{gate['changed_iwm_leader_signal_count']}`",
            f"- adjusted counts: `{best['benchmark_breadth_iwm_leader_counts']}`",
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
            "  backtester_adapter_changed: false",
            f"  run_adapter_changed: {str(promoted).lower()}",
            "  replay_only: true",
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
            f"Benchmark-breadth IWM-leader trend scalar "
            f"{best['parameters']['space_benchmark_breadth_iwm_leader_trend_scalar']} "
            f"changed {gate['changed_iwm_leader_signal_count']} signals with "
            f"aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = exp051._collect_gates()
    variants = [
        _run_exp051_stack_variant(
            label=f"{STEM}_{str(scalar).replace('.', '_')}",
            iwm_leader_scalar=scalar,
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
                    "space_benchmark_breadth_iwm_leader_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "alpha_hypothesis": (
            "Benchmark-breadth Space trend signals with smallcap tape leadership "
            "deserve a conservative default-off risk top-up."
        ),
        "changed_variable": "space_benchmark_breadth_iwm_leader_trend_scalar",
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
                        "space_benchmark_breadth_iwm_leader_trend_scalar"
                    ],
                    "eligible_signals": gate["eligible_iwm_leader_signal_count"],
                    "adjusted_signals": gate["changed_iwm_leader_signal_count"],
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
