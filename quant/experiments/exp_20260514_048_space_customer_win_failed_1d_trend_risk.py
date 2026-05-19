"""exp-20260514-048: Space customer-win failed 1d trend risk.

Tests one causal variable on top of accepted exp-20260514-047: whether
official Space benchmark-breadth trend signals should receive a small default-
off risk downscale when closed customer-win event rows already failed the 1d
follow-through test versus cash, same-theme replacement, SPY, QQQ, UFO, and
ARKX.

This is an alpha/risk-allocation search, not a ticker expansion, LLM change,
filter, lifecycle change, or live Space slot change.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (str(QUANT_DIR), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260514_041_space_benchmark_breadth_trend_risk as exp041
import exp_20260514_047_space_benchmark_same_theme_strength_trend_risk as exp047


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-048"
STEM = "space_customer_win_failed_1d_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-047"

ACCEPTED_SAME_THEME_STRENGTH_SCALAR = 1.025
CUSTOMER_WIN_FAILED_1D_SCALARS = (1.0, 0.975, 0.95, 0.925, 0.90)
TARGET_STRATEGY = "trend_long"
MARKER = "space_customer_win_failed_1d_trend_risk"

MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
MIN_TARGET_PROFILE_ROWS = 2


def _safe(payload: Any) -> Any:
    return exp041._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    exp041._write_json(path, payload)


def _append_jsonl_for_this_experiment(path: Path, entry: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    continue
            except json.JSONDecodeError:
                pass
            lines.append(line)
    lines.append(json.dumps(_safe(entry), separators=(",", ":"), sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _contains_customer_win(fields: Any) -> bool:
    if isinstance(fields, list):
        return "customer_win" in {str(field) for field in fields}
    return "customer_win" in str(fields or "")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _customer_win_failed_1d_gate() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped: Counter[str] = Counter()
    official_tickers = set(exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)

    for row in exp041._latest_closed_rows(path):
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in official_tickers:
            skipped["not_official_space_ticker"] += 1
            continue
        if row.get("closed_decision") is not True:
            skipped["not_closed_decision"] += 1
            continue
        if str(row.get("semantic_bucket") or "") == "attention_only":
            skipped["attention_only"] += 1
            continue
        if not _contains_customer_win(row.get("event_fields")):
            skipped["not_customer_win"] += 1
            continue
        h1 = exp041._horizon(row, "1d")
        if h1 is None:
            skipped["missing_mature_1d"] += 1
            continue
        fields = {
            "1d_cash_relative_pnl": exp041._as_float(h1.get("cash_relative_pnl")),
            "1d_same_theme_replacement_value": exp041._as_float(
                h1.get("same_theme_replacement_value")
            ),
            "1d_spy_relative_value": exp041._as_float(h1.get("spy_relative_value")),
            "1d_qqq_relative_value": exp041._as_float(h1.get("qqq_relative_value")),
            "1d_ufo_relative_value": exp041._as_float(h1.get("ufo_relative_value")),
            "1d_arkx_relative_value": exp041._as_float(h1.get("arkx_relative_value")),
        }
        if any(value is None for value in fields.values()):
            skipped["missing_1d_values"] += 1
            continue
        failed_1d = all(float(value) < 0.0 for value in fields.values())
        rows_by_ticker[ticker].append(
            {
                "ticker": ticker,
                "event_id": row.get("event_id"),
                "event_date": row.get("event_date"),
                "source_type": row.get("source_type"),
                "semantic_bucket": row.get("semantic_bucket"),
                "theme_segment": row.get("theme_segment"),
                "event_fields": row.get("event_fields"),
                "failed_customer_win_1d": failed_1d,
                **fields,
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    target_tickers: list[str] = []
    target_profile_row_count = 0
    for ticker, rows in sorted(rows_by_ticker.items()):
        failure_rows = [row for row in rows if row["failed_customer_win_1d"]]
        avg_fields = {
            field: _avg([float(row[field]) for row in rows])
            for field in (
                "1d_cash_relative_pnl",
                "1d_same_theme_replacement_value",
                "1d_spy_relative_value",
                "1d_qqq_relative_value",
                "1d_ufo_relative_value",
                "1d_arkx_relative_value",
            )
        }
        passed = bool(failure_rows)
        profiles[ticker] = {
            "ticker": ticker,
            "passed_customer_win_failed_1d": passed,
            "mature_customer_win_1d_row_count": len(rows),
            "failed_customer_win_1d_row_count": len(failure_rows),
            "avg_fields": avg_fields,
            "rows": rows,
        }
        if passed:
            target_tickers.append(ticker)
            target_profile_row_count += len(failure_rows)

    return {
        "passed": bool(target_tickers),
        "target_tickers": sorted(target_tickers),
        "target_profile_row_count": target_profile_row_count,
        "profiles": profiles,
        "skipped": dict(sorted(skipped.items())),
        "thresholds": {
            "required_event_field": "customer_win",
            "required_horizon": "1d",
            "required_failed_values": [
                "cash_relative_pnl < 0",
                "same_theme_replacement_value < 0",
                "spy_relative_value < 0",
                "qqq_relative_value < 0",
                "ufo_relative_value < 0",
                "arkx_relative_value < 0",
            ],
        },
    }


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


def _run_exp047_stack_variant(
    label: str,
    *,
    customer_win_failed_1d_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_extra = exp041._scale_and_record_extra
    failure_gate = gates["customer_win_failed_1d_gate"]
    target_tickers = set(failure_gate["target_tickers"])
    profiles = failure_gate["profiles"]
    failure_adjustments: list[dict[str, Any]] = []

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
        if ticker not in target_tickers:
            return
        _extra_scale_and_record(
            signal=signal,
            sizing=sizing,
            scalar=customer_win_failed_1d_scalar,
            portfolio_value=portfolio_value,
            counts=counts,
            adjustments=failure_adjustments,
            profile=profiles.get(ticker),
        )
        signal["space_customer_win_failed_1d_trend_bucket"] = True
        signal["space_customer_win_failed_1d_trend_scalar"] = (
            customer_win_failed_1d_scalar
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
    failure_counts = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
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
        "accepted_same_theme_strength_trend_scalar": (
            ACCEPTED_SAME_THEME_STRENGTH_SCALAR
        ),
        "space_customer_win_failed_1d_trend_scalar": (
            customer_win_failed_1d_scalar
        ),
        "customer_win_failed_1d_target_tickers": sorted(target_tickers),
        "customer_win_failed_1d_target_profile_row_count": failure_gate[
            "target_profile_row_count"
        ],
        "target_strategy": TARGET_STRATEGY,
    }
    variant["customer_win_failed_1d_counts"] = failure_counts
    variant["customer_win_failed_1d_counts_by_window"] = by_window_counts
    variant["customer_win_failed_1d_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(failure_adjustments)
    )
    variant["customer_win_failed_1d_adjustment_sample"] = failure_adjustments[:25]
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        name: exp041.source_diversity_exp._delta(
            payload["metrics"],
            before["by_window"][name]["metrics"],
        )
        for name, payload in variant["by_window"].items()
    }
    ev_regressions = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] < -1e-9
    }
    ev_improvements = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] > 1e-9
    }
    counts = variant.get("customer_win_failed_1d_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    scalar = float(
        variant["parameters"]["space_customer_win_failed_1d_trend_scalar"]
    )
    target_profile_row_count = int(
        variant["parameters"]["customer_win_failed_1d_target_profile_row_count"]
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "eligible_customer_win_failed_1d_signal_count": eligible_count,
        "changed_customer_win_failed_1d_signal_count": changed_count,
        "target_profile_row_count": target_profile_row_count,
        "sample_guard_passed": target_profile_row_count >= MIN_TARGET_PROFILE_ROWS,
        "accepted": bool(
            scalar != 1.0
            and changed_count > 0
            and target_profile_row_count >= MIN_TARGET_PROFILE_ROWS
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and aggregate_delta["max_drawdown_pct_max"]
            <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE
            and variant["aggregate"]["trade_count_sum"] >= MIN_TRADE_COUNT
        ),
    }


def _collect_gates() -> dict[str, Any]:
    gates = exp047._collect_gates()
    gates["customer_win_failed_1d_gate"] = _customer_win_failed_1d_gate()
    return gates


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space customer-win failed 1d trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_customer_win_failed_1d_trend_scalar` for official Space "
            "`trend_long` benchmark-breadth signals whose closed customer-win "
            "event profile failed 1d against cash, same-theme replacement, "
            "SPY, QQQ, UFO, and ARKX. Candidate pool, LLM/news, ranking, "
            "targets, stops, accepted exp047 stack, and live Space slots stay "
            "fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        f"- Best scalar: `{best['parameters']['space_customer_win_failed_1d_trend_scalar']}`",
        (
            "- Aggregate delta vs exp047: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Customer-win failed-1d signals changed: "
            f"`{gate['changed_customer_win_failed_1d_signal_count']}` of "
            f"`{gate['eligible_customer_win_failed_1d_signal_count']}` eligible"
        ),
        (
            "- Target tickers: "
            f"`{', '.join(best['parameters']['customer_win_failed_1d_target_tickers'])}`"
        ),
        "",
        "## Three-Window Deltas vs Exp047",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        counts = best["customer_win_failed_1d_counts_by_window"][name]
        adjusted = counts.get(f"{MARKER}_changed_signal", 0)
        lines.append(
            "| {name} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {trades} | {survival:.6f} | {adjusted} |".format(
                name=name,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            "## Gate Checks",
            f"- Gate 2 passed: `{payload['gate2_field_checks']['passed']}`",
            f"- Gate 3 survival passed: `{payload['gate3']['passed']}`",
            f"- Sample guard passed: `{gate['sample_guard_passed']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "best_parameters": payload["best_variant"]["parameters"],
        "aggregate_delta_vs_before": payload["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
    }


def run() -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc).isoformat()
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = _collect_gates()
    variants = [
        _run_exp047_stack_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            customer_win_failed_1d_scalar=scalar,
            gates=gates,
        )
        for scalar in CUSTOMER_WIN_FAILED_1D_SCALARS
    ]
    before = variants[0]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

    accepted_variants = [variant for variant in variants if variant["gate"]["accepted"]]
    if accepted_variants:
        best = max(
            accepted_variants,
            key=lambda variant: (
                variant["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda variant: (
                variant["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    runtime_gate = {
        "passed": best["gate"]["eligible_customer_win_failed_1d_signal_count"] > 0,
        "eligible_signal_count": best["gate"][
            "eligible_customer_win_failed_1d_signal_count"
        ],
        "required_runtime_fields": [
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.1d",
            "horizons.1d.same_theme_replacement_value",
            "horizons.1d.spy_relative_value",
            "horizons.1d.qqq_relative_value",
            "horizons.1d.ufo_relative_value",
            "horizons.1d.arkx_relative_value",
            "event_fields customer_win",
            "signal.strategy",
            "signal.sizing.shares_to_buy",
        ],
        "sample_rows": best.get("customer_win_failed_1d_adjustment_sample", [])[:10],
    }
    gate2 = {
        "open_positions": exp041.source_diversity_exp._gate2_open_positions(),
        "benchmark_breadth_profile": gates["benchmark_breadth_gate"],
        "customer_win_failed_1d_profile": gates["customer_win_failed_1d_gate"],
        "customer_win_failed_1d_runtime_state": runtime_gate,
    }
    gate2["passed"] = all(
        [
            gate2["open_positions"]["passed"],
            gates["benchmark_breadth_gate"]["passed"],
            gates["customer_win_failed_1d_gate"]["passed"],
            runtime_gate["passed"],
        ]
    )

    decision = "accepted" if best["gate"]["accepted"] else "rejected"
    status = (
        "accepted_default_off_space_customer_win_failed_1d_trend_risk"
        if decision == "accepted"
        else "rejected_space_customer_win_failed_1d_trend_risk"
    )
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "The customer-win failed-1d downscale did not clear Gate 4 versus "
            "the accepted exp047 stack. Do not retry this exact scalar on the "
            "same frozen snapshots without new closed customer-win rows or a "
            "materially different production-visible catalyst-quality field."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "Space customer-win events that immediately fail 1d follow-through "
            "against cash, same-theme replacement, SPY, QQQ, UFO, and ARKX may "
            "be lower-quality continuation catalysts, so benchmark-breadth "
            "trend signals for those tickers may deserve a conservative "
            "default-off risk downscale."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_customer_win_failed_1d_trend_scalar",
        "single_causal_variable": (
            "extra risk scalar for benchmark-breadth trend signals whose "
            "closed customer-win profile failed 1d versus every benchmark; "
            "accepted exp047 stack stays fixed"
        ),
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md core multi-window protocol plus Space "
                "frozen snapshots"
            ),
            "windows": exp041.source_diversity_exp.WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"]
                for label, window in exp041.source_diversity_exp.WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "risk allocation: failed 1d customer-win follow-through may "
                "identify weaker Space continuation catalysts inside the "
                "benchmark-breadth trend cohort."
            ),
            "q2_prior_experiments": [
                "exp-20260514-041 accepted benchmark-breadth trend risk at 1.025x.",
                "exp-20260514-044 accepted benchmark-breadth peer-nonleader trend risk at 1.025x.",
                "exp-20260514-047 accepted benchmark-breadth same-theme strength trend risk at 1.025x.",
                "exp-20260514-033 rejected delayed low-same-theme benchmark breadth due to no signal effect.",
                "exp-20260514-036 rejected early confirmation due to no runtime coverage.",
                "exp-20260514-042 rejected 20d durability due to no signal effect.",
            ],
            "q3_single_causal_variable": (
                "Only this customer-win failed-1d trend scalar changes."
            ),
            "q4_acceptance_standard": (
                "Same three Space windows; require positive aggregate EV/PnL, "
                "at least two EV-improved windows, no EV-regressed windows, max "
                "DD damage <= 0.5pp, survival >= 5%, >=50 trades, >=2 mature "
                "failed customer-win profile rows, and nonzero changed target "
                "signals."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best["aggregate"]["min_survival_rate"],
            "passed": best["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "tested_scalars": list(CUSTOMER_WIN_FAILED_1D_SCALARS),
            "selected_scalar": best["parameters"][
                "space_customer_win_failed_1d_trend_scalar"
            ],
            "customer_win_failed_1d_target_tickers": gates[
                "customer_win_failed_1d_gate"
            ]["target_tickers"],
            "customer_win_failed_1d_target_profile_row_count": gates[
                "customer_win_failed_1d_gate"
            ]["target_profile_row_count"],
            "accepted_same_theme_strength_trend_scalar": (
                ACCEPTED_SAME_THEME_STRENGTH_SCALAR
            ),
            "anti_js": "No JavaScript was used.",
            "locked_variables": [
                "official Space candidate pool",
                "all accepted Space scalars through exp047",
                "entry filters",
                "candidate ranking",
                "targets/stops",
                "MAX_POSITIONS",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best,
        "best_variant_gate": best["gate"],
        "decision": decision,
        "status": status,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only with shared Space metadata/helper and parity tests; "
            "live Space slots remain zero."
            if decision == "accepted"
            else (
                "Needs new closed customer-win rows, especially the pending "
                "RKLB 2026-05-07 company-release row after 10d maturity, before "
                "retesting this direction."
            )
        ),
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": decision == "accepted",
            "shared_policy_changed": decision == "accepted",
            "backtester_adapter_changed": False,
            "daily_report_metadata_changed": decision == "accepted",
            "run_adapter_changed": decision == "accepted",
            "replay_only": True,
            "parity_test_added": decision == "accepted",
            "live_slots": 0,
            "live_slots_changed": False,
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains sparse; broad ticker expansion, 5d early "
            "confirmation, 20d durability, and nearby RKLB-only benchmark "
            "scalar retunes were already accepted/rejected or data-limited. "
            "This tests a different production-visible catalyst-quality "
            "asymmetry without adding noisy Space tickers."
        ),
        "known_risks": [
            "Space remains default-off; this does not authorize live Space slots.",
            "The customer-win failed-1d slice is narrow and must not be widened into a filter without fresh evidence.",
        ],
        "llm_metrics": {"used_llm": False},
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    logs_dir = PROJECT_ROOT / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "experiments" / "artifacts"
    for directory in (exp_dir, logs_dir, tickets_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    artifact = _artifact_markdown(payload)
    payload["artifact_markdown"] = artifact
    _write_json(exp_dir / f"{STEM}.json", payload)
    _write_json(logs_dir / f"{EXPERIMENT_ID}.json", payload)
    _write_json(tickets_dir / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (artifacts_dir / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        artifact,
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": payload["experiment_id"],
            "timestamp": payload["run_finished_at"],
            "lane": payload["lane"],
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "parameters": payload["parameters"],
            "date_range": payload["backtest_protocol"]["windows"],
            "before_metrics": payload["before"]["by_window"],
            "after_metrics": payload["best_variant"]["by_window"],
            "delta_metrics": payload["best_variant_gate"],
            "expected_value_score_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["expected_value_score_sum"],
            "total_pnl_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["total_pnl_sum"],
            "production_impact": payload["production_impact"],
            "decision": payload["decision"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "related_files": [
                f"quant/experiments/{Path(__file__).name}",
                f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
                f"experiments/logs/{EXPERIMENT_ID}.json",
                f"experiments/tickets/{EXPERIMENT_ID}.json",
                f"experiments/artifacts/{EXPERIMENT_ID}_{STEM}.md",
                "docs/experiment_log.jsonl",
            ],
        },
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    summary = {
        "experiment_id": result["experiment_id"],
        "status": result["status"],
        "decision": result["decision"],
        "selected_scalar": result["parameters"]["selected_scalar"],
        "target_tickers": result["parameters"][
            "customer_win_failed_1d_target_tickers"
        ],
        "target_profile_row_count": result["parameters"][
            "customer_win_failed_1d_target_profile_row_count"
        ],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "eligible_customer_win_failed_1d_signal_count": result["best_variant_gate"][
            "eligible_customer_win_failed_1d_signal_count"
        ],
        "changed_customer_win_failed_1d_signal_count": result["best_variant_gate"][
            "changed_customer_win_failed_1d_signal_count"
        ],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
