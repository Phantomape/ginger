from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260511-004"
EXPERIMENT_SLUG = "entry_ranking_continuation_proximity"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import signal_engine  # noqa: E402


WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}


RESULT_KEYS = [
    "expected_value_score",
    "total_pnl",
    "total_return_pct",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "trade_count",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 6)
    return value


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {key: round_value(result.get(key)) for key in RESULT_KEYS}
    benchmarks = result.get("benchmarks") or {}
    summary["total_return_pct"] = round_value(
        benchmarks.get("strategy_total_return_pct", summary.get("total_return_pct"))
    )
    summary["trade_count"] = round_value(result.get("total_trades", summary.get("trade_count")))
    summary["spy_buy_hold_return_pct"] = round_value(benchmarks.get("spy_buy_hold_return_pct"))
    summary["qqq_buy_hold_return_pct"] = round_value(benchmarks.get("qqq_buy_hold_return_pct"))
    if "convergence" in result:
        convergence = result.get("convergence") or {}
        summary["converged"] = bool(convergence.get("converged", False))
    return summary


def audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for section in ("positions", "observations"):
        for row in payload.get(section, []):
            rows.append((section, row))

    missing: list[dict[str, Any]] = []
    for section, row in rows:
        ticker = row.get("ticker")
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"section": section, "ticker": ticker, "field": field})

    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def condition_value(signal: dict[str, Any], field: str, default: float = float("-inf")) -> float:
    conditions = signal.get("conditions_met") or {}
    value = conditions.get(field)
    if value is None:
        value = signal.get(field)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def all_signal_52w_proximity_rank(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        list(signals),
        key=lambda signal: (
            condition_value(signal, "pct_from_52w_high"),
            float(signal.get("confidence_score") or 0.0),
        ),
        reverse=True,
    )


def run_window(label: str, *, variant: bool) -> dict[str, Any]:
    spec = WINDOWS[label]
    universe = get_universe()
    original_ranker = signal_engine.rank_signals_for_allocation
    if variant:
        signal_engine.rank_signals_for_allocation = all_signal_52w_proximity_rank
    try:
        engine = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        signal_engine.rank_signals_for_allocation = original_ranker

    if result.get("error"):
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    return summarize_result(result)


def metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key in RESULT_KEYS:
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float)):
            deltas[key] = round_value(after[key] - before[key])
    return deltas


def aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()), 6
        ),
        "total_pnl_sum": round(sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()), 2),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "max_drawdown_pct_max": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()), 6
        ),
        "survival_rate_min": round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()), 6
        ),
    }


def aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            deltas[key] = round_value(after_value - before_value)
    return deltas


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_experiment_log(entry: dict[str, Any]) -> None:
    path = REPO_ROOT / "docs" / "experiment_log.jsonl"
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    kept: list[str] = []
    for line in lines:
        try:
            if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                continue
        except json.JSONDecodeError:
            pass
        kept.append(line)
    kept.append(json.dumps(entry, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{value * 100:.2f}%"


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    baseline = payload["before_metrics"]
    after = payload["after_metrics"]
    deltas = payload["delta_metrics"]["by_window"]
    rows = [
        "| Window | EV before | EV after | EV delta | PnL before | PnL after | Survival after | Trade count after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        rows.append(
            "| {label} | {ev_b:.4f} | {ev_a:.4f} | {ev_d:.4f} | ${pnl_b:,.2f} | ${pnl_a:,.2f} | {surv} | {trades} |".format(
                label=label,
                ev_b=baseline[label]["expected_value_score"],
                ev_a=after[label]["expected_value_score"],
                ev_d=deltas[label]["expected_value_score"],
                pnl_b=baseline[label]["total_pnl"],
                pnl_a=after[label]["total_pnl"],
                surv=pct(after[label]["survival_rate"]),
                trades=after[label]["trade_count"],
            )
        )

    text = f"""# {EXPERIMENT_ID} Entry Ranking Continuation Proximity

Hypothesis: ranking all same-day entry candidates by proximity to the 52-week high should allocate scarce slots to stronger continuation setups than the current breakout-only proximity ordering.

Decision: rejected. The all-signal ranking reduced EV and PnL in all three standard windows.

{chr(10).join(rows)}

Protocol: `docs/backtesting.md` standard three non-overlapping windows with fixed OHLCV snapshots.

Single causal variable: replace the current breakout-only 52-week proximity re-ranking with an all-signal 52-week proximity ranking during same-day allocation.

Production impact: no promoted strategy code. A positive result would have required a shared policy change because `rank_signals_for_allocation` is used by both backtest and production paths. This rejected scout leaves production behavior unchanged.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    timestamp = utc_now()
    gate2 = audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2['missing_required_fields']}")

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    for label in WINDOWS:
        before_metrics[label] = run_window(label, variant=False)
        after_metrics[label] = run_window(label, variant=True)

    by_window_delta = {
        label: metric_delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    aggregate_before = aggregate(before_metrics)
    aggregate_after = aggregate(after_metrics)
    aggregate_metric_delta = aggregate_delta(aggregate_after, aggregate_before)

    ev_improved_windows = sum(
        1
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    )
    ev_regressed_windows = sum(
        1
        for label in WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "rejected",
        "lane": "alpha_search",
        "alpha_hypothesis_category": "entry_ranking",
        "hypothesis": (
            "Allocating scarce entry slots by 52-week-high proximity across all signals may favor "
            "the strongest continuation candidates better than the current breakout-only ordering."
        ),
        "change_type": "entry_ranking_scout",
        "changed_variable": "same-day allocation ranking key",
        "parameters": {
            "single_causal_variable": (
                "extend pct_from_52w_high re-ranking from breakout_long candidates to all entry candidates"
            ),
            "ranking_key": ["pct_from_52w_high", "confidence_score"],
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "position sizing",
                "exits",
                "add-ons",
                "LLM/news replay",
            ],
        },
        "protocol_answers": {
            "alpha_hypothesis": (
                "entry/ranking: all-signal 52-week proximity ranking should improve slot allocation."
            ),
            "history_check": (
                "Existing code only re-ranks breakout candidates by 52-week proximity. Recent "
                "state-surface and slot-retune experiments were rejected or made observe-only, so this "
                "tests a narrower shared ranking variable rather than another data-limited LLM surface."
            ),
            "single_independent_variable": "same-day allocation ordering key",
            "acceptance_criteria": (
                "Pass only if aggregate EV/PnL improves, at least two windows improve EV with no EV-regressed "
                "window, drawdown/tail risk do not worsen materially, trade count remains meaningful, and "
                "survival rate stays above 5%."
            ),
            "reproducibility": "This script reruns baseline and variant across all three standard windows.",
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md standard three-window fixed-snapshot protocol",
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_metric_delta,
            "ev_improved_windows": ev_improved_windows,
            "ev_regressed_windows": ev_regressed_windows,
        },
        "expected_value_score_delta": aggregate_metric_delta["expected_value_score_sum"],
        "gate_results": {
            "gate1": "baseline rerun with accepted exp-20260510-015 three-window protocol",
            "gate2": gate2,
            "gate3": {
                "new_filter_added": False,
                "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
                "passed": aggregate_after["survival_rate_min"] >= 0.05,
            },
            "gate4": {
                "passed": False,
                "reason": "EV and PnL regressed in all three standard windows.",
            },
        },
        "risk_distribution": {
            label: {
                key: after_metrics[label].get(key)
                for key in ("worst_trade_pct", "max_consecutive_losses", "tail_loss_share")
            }
            for label in WINDOWS
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_behavior_changed": False,
            "positive_result_required_shared_policy": True,
        },
        "decision": "rejected",
        "rejection_reason": (
            "All-signal 52-week proximity ranking over-prioritized near-high candidates and reduced "
            "expected_value_score/PnL across late_strong, mid_weak, and old_thin."
        ),
        "next_action": (
            "Do not generalize breakout proximity ranking to all signals. Prefer more selective "
            "replacement-value or event-conditioned ranking evidence before changing shared allocation order."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }

    artifact_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    markdown_path = (
        REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Reject all-signal 52-week proximity ranking",
        "status": "rejected",
        "lane": "alpha_search",
        "decision": payload["decision"],
        "reason": payload["rejection_reason"],
        "artifacts": payload["related_files"][1:5],
        "next_action": payload["next_action"],
    }

    write_json(artifact_path, payload)
    write_json(log_path, payload)
    write_json(ticket_path, ticket)
    write_markdown(markdown_path, payload)
    append_experiment_log(payload)
    print(json.dumps(payload["delta_metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
