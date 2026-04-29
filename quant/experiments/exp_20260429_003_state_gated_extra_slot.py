"""exp-20260429-003: state-gated sixth slot allocation replay.

Alpha search. Global MAX_POSITIONS sweeps were rejected, but the playbook
still leaves room for state-specific allocation. This runner tests one causal
variable: allow a sixth slot only when both SPY and QQQ are sufficiently above
their 200-day moving averages. Production code is unchanged unless the replay
passes fixed-window Gate 4.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260429-003"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260429_003_state_gated_extra_slot.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("baseline_5_slots", None),
    ("extra_slot_min_index_5pct", 0.05),
    ("extra_slot_min_index_8pct", 0.08),
    ("extra_slot_min_index_10pct", 0.10),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    cap_eff = result.get("capital_efficiency") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "pnl_per_trade_usd": cap_eff.get("pnl_per_trade_usd"),
        "pnl_per_calendar_slot_day_usd": cap_eff.get("pnl_per_calendar_slot_day_usd"),
        "entry_reason_counts": entry.get("reason_counts", {}),
        "by_strategy": result.get("by_strategy", {}),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict, threshold: float | None) -> dict:
    original_filter = backtester_module.filter_entry_signal_candidates
    audit_counts = {"extra_slot_blocked_days": 0, "extra_slot_allowed_days": 0}

    def state_gated_extra_slot(signals, *args, **kwargs):
        planned, audit = original_filter(signals, *args, **kwargs)
        if threshold is None:
            return planned, audit

        active_count = len(kwargs.get("active_tickers") or [])
        spy_pct = kwargs.get("spy_pct_from_ma")
        qqq_pct = kwargs.get("qqq_pct_from_ma")
        min_index_pct = None
        if spy_pct is not None and qqq_pct is not None:
            min_index_pct = min(spy_pct, qqq_pct)

        audit["state_gated_extra_slot_threshold"] = threshold
        audit["state_gated_extra_slot_min_index_pct"] = min_index_pct
        if active_count < 5:
            return planned, audit
        if min_index_pct is not None and min_index_pct >= threshold:
            audit_counts["extra_slot_allowed_days"] += 1
            audit["state_gated_extra_slot_allowed"] = True
            return planned, audit

        audit_counts["extra_slot_blocked_days"] += 1
        audit["state_gated_extra_slot_allowed"] = False
        audit["state_gated_extra_slot_blocked_signals"] = len(planned)
        return [], audit

    try:
        backtester_module.filter_entry_signal_candidates = state_gated_extra_slot
        result = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "MAX_POSITIONS": 5 if threshold is None else 6,
            },
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        ).run()
    finally:
        backtester_module.filter_entry_signal_candidates = original_filter

    if "error" in result:
        raise RuntimeError(result["error"])
    metrics = _metrics(result)
    metrics["extra_slot_audit"] = audit_counts
    return metrics


def run_experiment() -> dict:
    logging.getLogger().setLevel(logging.WARNING)
    universe = sorted(get_universe())
    rows = []
    for window, cfg in WINDOWS.items():
        for variant, threshold in VARIANTS.items():
            metrics = _run_window(universe, cfg, threshold)
            rows.append({
                "window": window,
                "variant": variant,
                "threshold": threshold,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "metrics": metrics,
            })
            print(
                f"[{window} {variant}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} WR={metrics['win_rate']} "
                f"trades={metrics['trade_count']} audit={metrics['extra_slot_audit']}"
            )

    baseline_rows = {
        window: next(
            row for row in rows
            if row["window"] == window and row["variant"] == "baseline_5_slots"
        )
        for window in WINDOWS
    }
    summary = OrderedDict()
    for variant, threshold in VARIANTS.items():
        if threshold is None:
            continue
        by_window = OrderedDict()
        for window in WINDOWS:
            before = baseline_rows[window]["metrics"]
            after = next(
                row["metrics"] for row in rows
                if row["window"] == window and row["variant"] == variant
            )
            by_window[window] = {
                "before": before,
                "after": after,
                "delta": _delta(after, before),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "threshold": threshold,
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
                ),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
                "extra_slot_allowed_days": sum(
                    v["after"]["extra_slot_audit"]["extra_slot_allowed_days"]
                    for v in by_window.values()
                ),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["windows_improved"] >= 2
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "state_specific_capital_allocation_replay",
        "hypothesis": (
            "A sixth slot may add alpha only in strongly risk-on index states, "
            "without reopening the rejected global slot-count sweep."
        ),
        "why_tested": (
            "LLM soft ranking remains sample-limited, sector-persistence entries "
            "were rejected, and the playbook calls for state-specific allocation "
            "signals rather than global capacity changes."
        ),
        "parameters": {
            "single_causal_variable": "state-gated sixth position slot",
            "baseline_max_positions": 5,
            "trial_max_positions": 6,
            "thresholds_tested_min_spy_qqq_pct_from_200ma": [0.05, 0.08, 0.10],
            "locked_variables": [
                "A/B signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT=0.40",
                "MAX_PORTFOLIO_HEAT=0.08",
                "MAX_PER_SECTOR=2",
                "upside/adverse gap cancels",
                "day-2 add-on trigger/fraction/cap",
                "all exits",
                "scarce-slot breakout deferral",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            name: cfg["state_note"] for name, cfg in WINDOWS.items()
        },
        "before_metrics": {
            window: baseline_rows[window]["metrics"] for window in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            **{
                window: best_summary["by_window"][window]["after"]
                for window in WINDOWS
            },
        },
        "delta_metrics": {
            **{
                window: best_summary["by_window"][window]["delta"]
                for window in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted by fixed-window Gate 4." if accepted
                else "Rejected because the best state-gated extra-slot variant did not improve a majority of windows without regression."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data is still insufficient, so this tested a deterministic, production-replayable allocation alpha instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_global_slot_count": True,
            "not_repeating_global_candidate_ordering": True,
            "not_repeating_sector_persistence_entry": True,
            "mechanism_family": "state-specific slot allocation",
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": None if accepted else (
            "State-gated sixth-slot allocation did not pass multi-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby SPY/QQQ pct-from-MA thresholds as a sixth-slot gate without a new state source.",
            "A valid allocation retry needs breadth, dispersion, event context, or forward/paper evidence.",
            "If a future variant is accepted, implement the gate in shared production/backtest policy before promotion.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path in (OUT_JSON, LOG_JSON, TICKET_JSON):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run_experiment()
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "best_variant": result["after_metrics"]["best_variant"],
        "aggregate": result["delta_metrics"]["aggregate"],
    }, indent=2))
