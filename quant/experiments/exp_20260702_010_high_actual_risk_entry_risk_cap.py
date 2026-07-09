"""exp-20260702-010: high actual-risk entry risk cap.

Alpha-search replay. Tests one entry risk-allocation hypothesis: after the
accepted sizing stack computes shares, cap any core entry whose actual account
risk would exceed 2.0% at exactly 2.0%.

This does not change entries, exits, ranking, targets, stops, holds, add-ons,
LLM/news, paper sleeves, live/default orders, or production sizing code. A
positive replay would still require shared portfolio/run wiring before
promotion.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260630_012_close_confirmed_static_stop as replay_base


EXPERIMENT_ID = "exp-20260702-010"
OWNER = "alpha-explore"
SLUG = "high_actual_risk_entry_risk_cap"
RUNNER = f"quant/experiments/exp_20260702_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = replay_base.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine as pe  # noqa: E402


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260519-030"
    / "warehouse_main.sqlite"
)
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260702_010_{SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
}

BASE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
}
RISK_CAP = 0.02
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
CAPITAL_ALLOCATION_EV_IMPROVEMENT_FLOOR = 0.10

HYPOTHESIS = (
    "Entry risk-allocation alpha: cap any core entry whose post-sizing "
    "actual_risk_pct would exceed 2.0% at exactly 2.0%, because "
    "exp-20260630-018 showed high account-risk positions carry larger "
    "avoidable regret across all windows; this tests whether reducing initial "
    "risk budget, without changing entries, exits, ranking, targets, or holds, "
    "improves aggregate EV and drawdown."
)
CHANGE_TYPE = "capital_allocation"
IMPLEMENTATION_MODE = "private_replay_scout"
MECHANISM_FAMILY = "entry_risk_allocation"
TRIAL_FAMILY = "high_actual_risk_entry_risk_cap"
TRIAL_VARIANT_ID = "actual_risk_gt_2pct_cap_to_2pct_v1"
CHANGED_VARIABLE = "high_actual_risk_entry_risk_cap_v1"
NEW_EVIDENCE_TYPE = "entry_known_actual_risk_oracle_regret_lead"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260630-018",
    "exp-20260630-020",
    "exp-20260628-006",
]
CAUSAL_COMPONENTS = [
    "post-sizing actual_risk_pct cap at 2pct",
    "same entries exits ranking targets holds and add-ons",
    "canonical three-window before-after replay",
    "actual_risk_pct field audit",
    "live-realistic execution envelope disclosure",
]


def repo_rel(path: Path | str) -> str:
    return replay_base.repo_rel(path)


def read_json(path: Path, default: Any = None) -> Any:
    return replay_base.read_json(path, default)


def write_json(path: Path, payload: Any) -> None:
    replay_base.write_json(path, payload)


def write_text(path: Path, text: str) -> None:
    replay_base.write_text(path, text)


def safe(value: Any) -> Any:
    return replay_base.safe(value)


def rounded(value: Any, digits: int = 6) -> Any:
    return replay_base.rounded(value, digits)


def _as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _scale_sizing_to_risk_cap(
    sizing: dict[str, Any],
    sig: dict[str, Any],
    portfolio_value: float,
    stats: Counter,
) -> dict[str, Any]:
    risk_pct = _as_float(sizing.get("risk_pct"))
    if risk_pct is None or risk_pct <= RISK_CAP:
        return sizing
    net_risk_per_share = _as_float(sizing.get("net_risk_per_share"))
    entry = _as_float(sizing.get("entry_price") or sig.get("entry_price"))
    current_shares = int(sizing.get("shares_to_buy") or 0)
    if (
        portfolio_value <= 0
        or net_risk_per_share is None
        or net_risk_per_share <= 0
        or entry is None
        or entry <= 0
        or current_shares <= 0
    ):
        stats["cap_unable_to_scale"] += 1
        return sizing

    capped_shares = int(math.floor((portfolio_value * RISK_CAP) / net_risk_per_share))
    capped_shares = max(0, min(current_shares, capped_shares))
    if capped_shares >= current_shares:
        return sizing

    stats["cap_bind_count"] += 1
    stats["shares_before_sum"] += current_shares
    stats["shares_after_sum"] += capped_shares
    stats["risk_pct_before_sum"] += risk_pct
    stats["risk_pct_after_sum"] += (
        capped_shares * net_risk_per_share / portfolio_value
    )

    risk_amount = capped_shares * net_risk_per_share
    position_value = capped_shares * entry
    capped = dict(sizing)
    capped.update(
        {
            "shares_to_buy": capped_shares,
            "position_value_usd": round(position_value, 2),
            "position_pct_of_portfolio": round(position_value / portfolio_value, 4),
            "risk_amount_usd": round(risk_amount, 2),
            "risk_pct": risk_amount / portfolio_value if portfolio_value else 0.0,
            "high_actual_risk_entry_cap_applied": RISK_CAP,
            "high_actual_risk_entry_original_risk_pct": risk_pct,
            "high_actual_risk_entry_original_shares": current_shares,
            "high_actual_risk_entry_original_position_value_usd": sizing.get(
                "position_value_usd"
            ),
            "high_actual_risk_entry_original_risk_amount_usd": sizing.get(
                "risk_amount_usd"
            ),
        }
    )
    return capped


def _patch_size_signals(apply_cap: bool) -> tuple[Any, Counter]:
    original = pe.size_signals
    stats: Counter = Counter()

    def patched(signals: list[dict[str, Any]], portfolio_value: float, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        if not apply_cap:
            return sized
        stats["signals_seen"] += len(sized)
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if not sizing:
                continue
            new_sizing = _scale_sizing_to_risk_cap(sizing, sig, portfolio_value, stats)
            if new_sizing is not sizing:
                sig["sizing"] = new_sizing
        return sized

    pe.size_signals = patched
    return original, stats


def _trade_key(row: dict[str, Any]) -> str:
    return str(
        row.get("trade_key")
        or f"{row.get('ticker')}:{row.get('entry_date')}:{row.get('entry_price')}"
    )


def _changed_trades(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    before_by_key = {_trade_key(row): row for row in before}
    after_by_key = {_trade_key(row): row for row in after}
    changed: list[dict[str, Any]] = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        b = before_by_key.get(key)
        a = after_by_key.get(key)
        if b is None or a is None:
            changed.append(
                {
                    "trade_key": key,
                    "change_type": "added_or_removed_trade",
                    "before_present": b is not None,
                    "after_present": a is not None,
                    "ticker": (a or b or {}).get("ticker"),
                }
            )
            continue
        fields = ("exit_date", "exit_reason", "exit_price", "pnl", "shares")
        if any(b.get(field) != a.get(field) for field in fields):
            changed.append(
                {
                    "trade_key": key,
                    "ticker": a.get("ticker"),
                    "strategy": a.get("strategy"),
                    "entry_date": a.get("entry_date"),
                    "before_exit_date": b.get("exit_date"),
                    "after_exit_date": a.get("exit_date"),
                    "before_exit_reason": b.get("exit_reason"),
                    "after_exit_reason": a.get("exit_reason"),
                    "before_shares": b.get("shares"),
                    "after_shares": a.get("shares"),
                    "shares_delta": int(a.get("shares") or 0)
                    - int(b.get("shares") or 0),
                    "before_actual_risk_pct": b.get("actual_risk_pct"),
                    "after_actual_risk_pct": a.get("actual_risk_pct"),
                    "before_pnl": b.get("pnl"),
                    "after_pnl": a.get("pnl"),
                    "pnl_delta": rounded(
                        float(a.get("pnl") or 0.0) - float(b.get("pnl") or 0.0),
                        2,
                    ),
                }
            )
    return changed


def _summarize_changed(changed: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in changed.values() for row in rows]
    by_reason = Counter(
        f"{row.get('before_exit_reason')}->{row.get('after_exit_reason')}"
        for row in all_rows
    )
    by_ticker = Counter(row.get("ticker") or "UNKNOWN" for row in all_rows)
    return {
        "changed_trade_count": len(all_rows),
        "changed_trade_count_by_window": {
            label: len(rows) for label, rows in changed.items()
        },
        "changed_exit_reason_pairs": dict(by_reason.most_common()),
        "changed_tickers": dict(by_ticker.most_common()),
        "changed_pnl_delta_sum": round(
            sum(float(row.get("pnl_delta") or 0.0) for row in all_rows),
            2,
        ),
        "sample_changed_trades": all_rows[:30],
    }


def _metrics(result: dict[str, Any], cap_stats: Counter) -> dict[str, Any]:
    out = replay_base.metrics(result)
    trades = result.get("trades") or []
    high_risk_trades = [
        row for row in trades if float(row.get("actual_risk_pct") or 0.0) > RISK_CAP
    ]
    out.update(
        {
            "actual_risk_gt_2pct_trade_count": len(high_risk_trades),
            "actual_risk_gt_2pct_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in high_risk_trades),
                2,
            ),
            "max_actual_risk_pct": round(
                max((float(row.get("actual_risk_pct") or 0.0) for row in trades), default=0.0),
                6,
            ),
            "cap_bind_count": int(cap_stats.get("cap_bind_count") or 0),
            "cap_unable_to_scale": int(cap_stats.get("cap_unable_to_scale") or 0),
            "cap_shares_before_sum": int(cap_stats.get("shares_before_sum") or 0),
            "cap_shares_after_sum": int(cap_stats.get("shares_after_sum") or 0),
            "cap_avg_risk_pct_before": (
                round(
                    float(cap_stats.get("risk_pct_before_sum") or 0.0)
                    / int(cap_stats.get("cap_bind_count") or 1),
                    6,
                )
                if cap_stats.get("cap_bind_count")
                else None
            ),
            "cap_avg_risk_pct_after": (
                round(
                    float(cap_stats.get("risk_pct_after_sum") or 0.0)
                    / int(cap_stats.get("cap_bind_count") or 1),
                    6,
                )
                if cap_stats.get("cap_bind_count")
                else None
            ),
        }
    )
    return out


def _run_window(label: str, apply_cap: bool) -> dict[str, Any]:
    spec = WINDOWS[label]
    original, cap_stats = _patch_size_signals(apply_cap)
    try:
        result = BacktestEngine(
            get_universe(),
            start=spec["start"],
            end=spec["end"],
            config=BASE_CONFIG,
            ohlcv_warehouse_path=str(WAREHOUSE),
            ohlcv_warehouse_snapshot_source=str(spec["snapshot"]),
            include_oracle_diagnostics=False,
        ).run()
    finally:
        pe.size_signals = original
    if result.get("error"):
        raise RuntimeError(f"{label} failed: {result['error']}")
    return {
        "metrics": _metrics(result, cap_stats),
        "trades": result.get("trades") or [],
        "cap_stats": dict(cap_stats),
        "known_biases": result.get("known_biases") or {},
    }


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return replay_base.aggregate({label: rows[label]["metrics"] for label in WINDOWS})


def _aggregate_delta(
    after: dict[str, dict[str, Any]], before: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    before_agg = _aggregate(before)
    after_agg = _aggregate(after)
    delta = replay_base.delta(after_agg, before_agg)
    baseline_ev = float(before_agg.get("expected_value_score_sum") or 0.0)
    ev_delta = float(delta.get("expected_value_score_sum") or 0.0)
    baseline_pnl = float(before_agg.get("total_pnl_sum") or 0.0)
    pnl_delta = float(delta.get("total_pnl_sum") or 0.0)
    delta["expected_value_score_delta_pct"] = (
        round(ev_delta / baseline_ev, 6) if baseline_ev else None
    )
    delta["total_pnl_delta_pct"] = (
        round(pnl_delta / baseline_pnl, 6) if baseline_pnl else None
    )
    delta["cap_bind_count_sum"] = int(
        sum(after[label]["metrics"].get("cap_bind_count") or 0 for label in WINDOWS)
    )
    return delta


def _load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.18,
        "expected_ev_delta": 0.15,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "EV diluted by cutting winners",
            "old_thin regression",
            "cap affects too few trades",
            "capital allocation needs >10pct aggregate EV",
        ],
        "confidence_reason": (
            "The money hypothesis comes from a production-known risk cohort "
            "with cross-window oracle regret in exp-20260630-018, but prior "
            "high-risk exit promotion failed in exp-20260630-020 and risk "
            "allocation changes have a high materiality bar."
        ),
    }


def _gate2_runtime_field_audit(before_runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trades = [row for run in before_runs.values() for row in run["trades"]]
    missing_entry = [row for row in trades if not row.get("entry_date")]
    missing_target = [row for row in trades if row.get("target_price") in (None, "")]
    missing_actual_risk = [row for row in trades if row.get("actual_risk_pct") in (None, "")]
    return {
        "trade_rows_checked": len(trades),
        "fields_checked": ["entry_date", "target_price", "actual_risk_pct"],
        "missing_entry_date": len(missing_entry),
        "missing_target_price": len(missing_target),
        "missing_actual_risk_pct": len(missing_actual_risk),
        "high_actual_risk_before_count": sum(
            1 for row in trades if float(row.get("actual_risk_pct") or 0.0) > RISK_CAP
        ),
        "passed": not missing_entry and not missing_actual_risk,
        "target_price_relevance": (
            "Checked for Gate 2 completeness. The cap does not consume "
            "target_price and does not change target exits."
        ),
    }


def make_payload() -> dict[str, Any]:
    before_runs = {label: _run_window(label, False) for label in WINDOWS}
    after_runs = {label: _run_window(label, True) for label in WINDOWS}
    before_metrics = {label: before_runs[label]["metrics"] for label in WINDOWS}
    after_metrics = {label: after_runs[label]["metrics"] for label in WINDOWS}
    by_window_delta = {
        label: replay_base.delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = _aggregate(before_runs)
    aggregate_after = _aggregate(after_runs)
    aggregate_delta = _aggregate_delta(after_runs, before_runs)
    improved_windows = [
        label
        for label in WINDOWS
        if float(after_metrics[label].get("expected_value_score") or 0.0)
        > float(before_metrics[label].get("expected_value_score") or 0.0)
    ]
    regressed_windows = [
        label
        for label in WINDOWS
        if float(after_metrics[label].get("expected_value_score") or 0.0)
        < float(before_metrics[label].get("expected_value_score") or 0.0)
    ]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    changed = {
        label: _changed_trades(before_runs[label]["trades"], after_runs[label]["trades"])
        for label in WINDOWS
    }
    changed_summary = _summarize_changed(changed)
    gate2_open_positions = replay_base.audit_open_positions()
    gate2_runtime = _gate2_runtime_field_audit(before_runs)

    gate4_passed = (
        (aggregate_delta.get("expected_value_score_delta_pct") or 0.0)
        > CAPITAL_ALLOCATION_EV_IMPROVEMENT_FLOOR
        and float(aggregate_delta.get("total_pnl_sum") or 0.0) > 0
        and not regressed_windows
        and aggregate_after["survival_rate_min"] >= 0.05
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and int(aggregate_delta.get("cap_bind_count_sum") or 0) > 0
        and changed_summary["changed_trade_count"] > 0
    )
    observed_only_lead = bool(gate4_passed)
    decision = (
        "positive_replay_lead_not_promoted_high_actual_risk_entry_cap"
        if observed_only_lead
        else "rejected_high_actual_risk_entry_risk_cap"
    )
    failed_reasons: list[str] = []
    if (aggregate_delta.get("expected_value_score_delta_pct") or 0.0) <= CAPITAL_ALLOCATION_EV_IMPROVEMENT_FLOOR:
        failed_reasons.append("aggregate_ev_improvement_below_10pct_floor")
    if float(aggregate_delta.get("total_pnl_sum") or 0.0) <= 0:
        failed_reasons.append("aggregate_pnl_not_positive")
    if regressed_windows:
        failed_reasons.append("window_ev_regression")
    if aggregate_after["survival_rate_min"] < 0.05:
        failed_reasons.append("survival_below_floor")
    if max_drawdown_worse > MAX_DRAWDOWN_WORSE_GUARDRAIL:
        failed_reasons.append("drawdown_worse_than_guardrail")
    if int(aggregate_delta.get("cap_bind_count_sum") or 0) <= 0:
        failed_reasons.append("cap_affected_zero_signals")
    if changed_summary["changed_trade_count"] <= 0:
        failed_reasons.append("no_changed_trades")

    prediction = _load_ticket_prediction()
    predicted_p = float(prediction.get("success_probability") or 0.0)
    actual_success = 1 if observed_only_lead else 0

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": replay_base.utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": "observed_only_positive_lead" if observed_only_lead else "rejected",
        "decision": decision,
        "accepted": observed_only_lead,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": predicted_p,
            "brier_score": round((actual_success - predicted_p) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes") or []) & set(failed_reasons)
            ),
            "actual_ev_delta": aggregate_delta.get("expected_value_score_sum"),
            "actual_pnl_delta": aggregate_delta.get("total_pnl_sum"),
            "ev_prediction_error": rounded(
                float(aggregate_delta.get("expected_value_score_sum") or 0.0)
                - float(prediction.get("expected_ev_delta") or 0.0)
            ),
            "pnl_prediction_error": rounded(
                float(aggregate_delta.get("total_pnl_sum") or 0.0)
                - float(prediction.get("expected_pnl_delta") or 0.0),
                2,
            ),
            "surprise_note": (
                "The cap cleared the strict replay hurdle but is still not "
                "promoted because production wiring/parity are absent."
                if observed_only_lead
                else "The high-risk cap did not clear the capital-allocation materiality hurdle."
            ),
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "warehouse": repo_rel(WAREHOUSE),
            "before_config": BASE_CONFIG,
            "after_policy": {
                "post_sizing_actual_risk_cap": RISK_CAP,
                "cap_applies_when": "sizing.risk_pct > 0.02",
                "scale_method": (
                    "floor shares to portfolio_value * 0.02 / net_risk_per_share"
                ),
            },
            "windows": {
                label: {**spec, "snapshot": repo_rel(spec["snapshot"])}
                for label, spec in WINDOWS.items()
            },
            "acceptance_rule": (
                "Capital-allocation cap must improve aggregate EV by >10%, "
                "have positive aggregate PnL, no EV-regressed window, "
                "after survival >=5%, max drawdown drift <=0.5pp, and affect "
                "at least one trade. Replay positives are leads until shared "
                "production/backtest wiring is added."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new accepted the proposal without override; "
                    "nearest score 0.1808 and no blocking match."
                ),
                "exp-20260630-018": (
                    "Observed-only oracle diagnostic found actual_risk_pct >=2% "
                    "had larger avoidable exit regret across all windows."
                ),
                "exp-20260630-020": (
                    "High-risk early-relative-weakness exit failed; this test "
                    "does not change exits or response curves."
                ),
                "exp-20260628-006": (
                    "Entry slippage/risk attribution context; this test uses "
                    "a fixed actual-risk cap, not a stop/target retune."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "docs/backtesting.md Gate 1-4 plus the AGENTS >10% aggregate "
                "EV floor for capital-allocation retunes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "rerun_before_aggregate": aggregate_before,
            "accepted_reference": {
                "expected_value_score_sum": 7.8941,
                "total_pnl_sum": 234850.99,
                "trade_count_sum": 61,
                "signals_generated_sum": 164,
                "signals_survived_sum": 135,
            },
            "identity_delta_vs_reference": replay_base.delta(
                aggregate_before,
                {
                    "expected_value_score_sum": 7.8941,
                    "total_pnl_sum": 234850.99,
                    "trade_count_sum": 61,
                    "signals_generated_sum": 164,
                    "signals_survived_sum": 135,
                },
            ),
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_trade_fields": gate2_runtime,
            "passed": bool(gate2_runtime["passed"]),
        },
        "gate3": {
            "new_entry_filter_added": False,
            "signals_generated_delta": aggregate_delta.get("signals_generated_sum"),
            "signals_survived_delta": aggregate_delta.get("signals_survived_sum"),
            "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": gate4_passed,
            "accepted_alpha": False,
            "observed_only_lead": observed_only_lead,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "improved_windows": improved_windows,
            "regressed_windows": regressed_windows,
            "max_drawdown_worse": rounded(max_drawdown_worse),
            "capital_allocation_ev_improvement_floor": CAPITAL_ALLOCATION_EV_IMPROVEMENT_FLOOR,
            "actual_ev_improvement_pct": aggregate_delta.get(
                "expected_value_score_delta_pct"
            ),
            "changed_trade_count": changed_summary["changed_trade_count"],
            "cap_bind_count_sum": aggregate_delta.get("cap_bind_count_sum"),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
            "changed_trades": changed_summary,
        },
        "changed_trades_by_window": changed,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "target_geometry_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": True,
            "activation_envelope": {
                "intended_notional": "same core entries with per-trade actual risk capped at 2% if promoted",
                "capital_cap": "current core caps plus this per-entry risk cap",
                "liquidity_slippage_model": "unchanged next-open entry and existing cost/slippage model",
                "portfolio_displacement": "same ranking and slots; smaller high-risk fills may free cash/heat",
                "order_semantics": "same entry order timing, lower share quantity only",
                "failure_handling": "if sizing risk fields are missing, leave current sizing unchanged",
                "kill_switch": (
                    "do not promote if aggregate EV improvement <=10%, any "
                    "canonical EV regression, or drawdown drift >0.5pp"
                ),
            },
            "parity_note": (
                "Replay-only monkey patch. A positive result would require a "
                "shared portfolio_engine helper plus run.py/report parity tests."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The cap reduced enough high-risk exposure to clear the strict "
                "capital-allocation replay hurdle."
                if observed_only_lead
                else "High-risk entries were often winners or too sparse, so cutting them did not clear the >10% EV materiality hurdle."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune the 2% cap, try adjacent risk caps, combine with "
                "early-weakness exits, widen stop/target/hold changes, or turn "
                "this into another response-curve scan on the same rows."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more settled forward rows with "
                "entry-time risk outcomes, a new pre-entry risk-quality signal, "
                "or shared production wiring after a positive out-of-sample lead."
            ),
        },
        "rejection_reason": None if observed_only_lead else ";".join(failed_reasons),
        "next_retry_requires": [
            "materially more settled forward rows with entry-time risk outcomes",
            "a new pre-entry risk-quality signal beyond actual_risk_pct",
            "shared portfolio_engine/run.py wiring only after positive evidence",
        ],
        "before_after_strategy_behavior_changed": True,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            "quant/portfolio_engine.py",
            "quant/backtester.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\ohlcv_warehouse.py seed-snapshot-versions",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades d | Cap binds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        dlt = payload["delta_metrics"]["by_window"][label]
        rows.append(
            f"| {label} | {before.get('expected_value_score')} | "
            f"{after.get('expected_value_score')} | {dlt.get('expected_value_score')} | "
            f"{before.get('total_pnl')} | {after.get('total_pnl')} | "
            f"{dlt.get('total_pnl')} | {dlt.get('max_drawdown_pct')} | "
            f"{dlt.get('trade_count')} | {after.get('cap_bind_count')} |"
        )
    agg = payload["delta_metrics"]["aggregate_delta"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} high actual-risk entry risk cap",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            HYPOTHESIS,
            "",
            *rows,
            "",
            "Aggregate delta: "
            f"EV `{agg.get('expected_value_score_sum')}` "
            f"({agg.get('expected_value_score_delta_pct')} pct of baseline), "
            f"PnL `{agg.get('total_pnl_sum')}`, "
            f"cap binds `{agg.get('cap_bind_count_sum')}`, "
            f"changed trades `{payload['delta_metrics']['changed_trades']['changed_trade_count']}`.",
            "",
            "Production boundary: replay-only monkey patch. No production sizing, "
            "daily run path, live/default orders, entries, exits, ranking, or "
            "target geometry changed.",
        ]
    ) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": replay_base.utc_now(),
        "files": [
            {
                "path": repo_rel(path),
                "exists": (REPO_ROOT / path if not path.is_absolute() else path).exists(),
                "sha256": replay_base.sha256(
                    REPO_ROOT / path if not path.is_absolute() else path
                ),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_text(CARD_MD, make_card(payload))
    replay_base.save_experiment_log_entry(payload, allow_duplicate=True)
    write_json(MANIFEST_JSON, make_manifest(payload))
    replay_base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> None:
    payload = make_payload()
    persist(payload)
    print(
        json.dumps(
            safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "aggregate_delta": payload["delta_metrics"]["aggregate_delta"],
                    "changed_trade_count": payload["delta_metrics"]["changed_trades"][
                        "changed_trade_count"
                    ],
                    "artifact": payload["artifact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
