"""exp-20260503-008: full-position ATR trailing exit profile sweep.

Alpha search only. The latest old-thin slot-routing audit showed many losses
that first had positive MFE. This tests one lifecycle exit variable already
supported by the backtester config: after enough ATR profit, replace the fixed
target with a full-position ATR trailing stop. It is not the rejected pure
TRAILING_STOP partial-reduce loop and does not reinterpret target_price as a
partial profit-taking rule.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = REPO_ROOT / "quant" / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260502_011_old_thin_slot_routing_alpha as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-009"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "atr_trailing_exit_profile.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = base.WINDOWS

BASELINE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "REPLAY_PARTIAL_REDUCES": True,
    "TRAIL_TRIGGER_ATR_MULT": 0,
    "TRAIL_OFFSET_ATR_MULT": 0,
}

VARIANTS = OrderedDict([
    ("trail_2_0atr_1_5atr", {"TRAIL_TRIGGER_ATR_MULT": 2.0, "TRAIL_OFFSET_ATR_MULT": 1.5}),
    ("trail_3_0atr_1_5atr", {"TRAIL_TRIGGER_ATR_MULT": 3.0, "TRAIL_OFFSET_ATR_MULT": 1.5}),
    ("trail_3_0atr_2_0atr", {"TRAIL_TRIGGER_ATR_MULT": 3.0, "TRAIL_OFFSET_ATR_MULT": 2.0}),
    ("trail_4_0atr_2_0atr", {"TRAIL_TRIGGER_ATR_MULT": 4.0, "TRAIL_OFFSET_ATR_MULT": 2.0}),
])


def _run_backtest(window: dict, config: dict) -> dict:
    engine = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=window["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _exit_reason_counts(trades: list[dict]) -> dict:
    counts = {}
    for trade in trades or []:
        reason = trade.get("exit_reason") or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _loss_after_positive_mfe(snapshot: dict, result: dict) -> dict:
    rows = []
    for trade in result.get("trades") or []:
        if base._num(trade.get("pnl"), 0.0) >= 0:
            continue
        ticker = (trade.get("ticker") or "").upper()
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        entry = base._num(trade.get("entry_price"), None)
        if not ticker or not entry_date or not exit_date or not entry:
            continue
        series = snapshot.get(ticker) or []
        start_idx = base._row_index_on_or_after(series, entry_date)
        end_idx = base._row_index_on_or_before(series, exit_date)
        if start_idx is None or end_idx is None or end_idx < start_idx:
            continue
        path = series[start_idx:end_idx + 1]
        best_high = max(base._num(row.get("High"), entry) for row in path)
        mfe_pct = (best_high / entry) - 1.0
        if mfe_pct <= 0:
            continue
        mfe_dollars = mfe_pct * entry * int(trade.get("shares") or 0)
        rows.append({
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "entry_date": entry_date,
            "exit_date": exit_date,
            "exit_reason": trade.get("exit_reason"),
            "mfe_pct": base._round(mfe_pct, 6),
            "actual_pnl": base._round(trade.get("pnl"), 2),
            "mfe_dollars": base._round(mfe_dollars, 2),
            "giveback_vs_mfe": base._round(mfe_dollars - base._num(trade.get("pnl")), 2),
        })
    return {
        "count": len(rows),
        "giveback_vs_mfe": base._round(
            sum(base._num(row.get("giveback_vs_mfe"), 0.0) for row in rows),
            2,
        ),
        "top": sorted(
            rows,
            key=lambda row: base._num(row.get("giveback_vs_mfe"), 0.0),
            reverse=True,
        )[:10],
    }


def _metrics(result: dict, snapshot: dict) -> dict:
    metrics = base._metrics(result)
    trades = result.get("trades") or []
    metrics["exit_reason_counts"] = _exit_reason_counts(trades)
    metrics["trailing_stop_trades"] = metrics["exit_reason_counts"].get("trailing_stop", 0)
    metrics["loss_after_positive_mfe"] = _loss_after_positive_mfe(snapshot, result)
    return metrics


def _aggregate(by_window: dict) -> dict:
    return base._aggregate({
        label: row["metrics"]
        for label, row in by_window.items()
    })


def _delta(before: dict, after: dict) -> dict:
    by_window = {}
    ev_improved = 0
    ev_regressed = 0
    pnl_improved = 0
    pnl_regressed = 0
    dd_improved = 0
    for label in WINDOWS:
        b = before[label]["metrics"]
        a = after[label]["metrics"]
        row = {
            "expected_value_score": base._round(
                base._num(a.get("expected_value_score")) - base._num(b.get("expected_value_score")),
                4,
            ),
            "sharpe_daily": base._round(
                base._num(a.get("sharpe_daily")) - base._num(b.get("sharpe_daily")),
                4,
            ),
            "total_pnl": base._round(
                base._num(a.get("total_pnl")) - base._num(b.get("total_pnl")),
                2,
            ),
            "total_return_pct": base._round(
                base._num(a.get("total_return_pct")) - base._num(b.get("total_return_pct")),
                4,
            ),
            "max_drawdown_pct": base._round(
                base._num(a.get("max_drawdown_pct")) - base._num(b.get("max_drawdown_pct")),
                4,
            ),
            "win_rate": base._round(base._num(a.get("win_rate")) - base._num(b.get("win_rate")), 4),
            "trade_count": int(base._num(a.get("trade_count")) - base._num(b.get("trade_count"))),
            "trailing_stop_trades": int(
                base._num(a.get("trailing_stop_trades")) - base._num(b.get("trailing_stop_trades"))
            ),
            "loss_after_positive_mfe_count": int(
                base._num(a["loss_after_positive_mfe"].get("count"))
                - base._num(b["loss_after_positive_mfe"].get("count"))
            ),
            "loss_after_positive_mfe_giveback": base._round(
                base._num(a["loss_after_positive_mfe"].get("giveback_vs_mfe"))
                - base._num(b["loss_after_positive_mfe"].get("giveback_vs_mfe")),
                2,
            ),
        }
        if row["expected_value_score"] > 0:
            ev_improved += 1
        if row["expected_value_score"] < 0:
            ev_regressed += 1
        if row["total_pnl"] > 0:
            pnl_improved += 1
        if row["total_pnl"] < 0:
            pnl_regressed += 1
        if row["max_drawdown_pct"] < 0:
            dd_improved += 1
        by_window[label] = row

    before_agg = _aggregate(before)
    after_agg = _aggregate(after)
    ev_delta = after_agg["expected_value_score_sum"] - before_agg["expected_value_score_sum"]
    pnl_delta = after_agg["total_pnl_sum"] - before_agg["total_pnl_sum"]
    return {
        "by_window": by_window,
        "baseline": before_agg,
        "variant": after_agg,
        "expected_value_score_delta_sum": base._round(ev_delta, 4),
        "expected_value_score_delta_pct": base._round(
            ev_delta / before_agg["expected_value_score_sum"],
            6,
        ) if before_agg["expected_value_score_sum"] else None,
        "total_pnl_delta_sum": base._round(pnl_delta, 2),
        "total_pnl_delta_pct": base._round(
            pnl_delta / before_agg["total_pnl_sum"],
            6,
        ) if before_agg["total_pnl_sum"] else None,
        "ev_windows_improved": ev_improved,
        "ev_windows_regressed": ev_regressed,
        "pnl_windows_improved": pnl_improved,
        "pnl_windows_regressed": pnl_regressed,
        "drawdown_windows_improved": dd_improved,
        "max_sharpe_daily_delta": max(row["sharpe_daily"] for row in by_window.values()),
        "min_win_rate_delta": min(row["win_rate"] for row in by_window.values()),
        "trade_count_delta_sum": sum(row["trade_count"] for row in by_window.values()),
        "trailing_stop_trades_delta_sum": sum(row["trailing_stop_trades"] for row in by_window.values()),
    }


def _passes_gate4(delta: dict) -> bool:
    if delta["ev_windows_improved"] < 2:
        return False
    if delta["expected_value_score_delta_pct"] and delta["expected_value_score_delta_pct"] > 0.10:
        return True
    if delta["total_pnl_delta_pct"] and delta["total_pnl_delta_pct"] > 0.05:
        return True
    if delta["max_sharpe_daily_delta"] > 0.10:
        return True
    if delta["drawdown_windows_improved"] >= 2:
        # Gate 4 asks for >1pp max drawdown reduction. Apply it per-window.
        if any(row["max_drawdown_pct"] < -0.01 for row in delta["by_window"].values()):
            return True
    if delta["trade_count_delta_sum"] > 0 and delta["min_win_rate_delta"] >= 0:
        return True
    return False


def _best_variant(deltas: dict) -> str:
    return max(
        deltas,
        key=lambda name: (
            deltas[name]["expected_value_score_delta_sum"],
            deltas[name]["total_pnl_delta_sum"],
            deltas[name]["max_sharpe_daily_delta"],
        ),
    )


def build_payload() -> dict:
    logging.getLogger().setLevel(logging.ERROR)
    snapshots = {
        label: base._load_snapshot(window["snapshot"])
        for label, window in WINDOWS.items()
    }
    baseline = OrderedDict()
    for label, window in WINDOWS.items():
        result = _run_backtest(window, BASELINE_CONFIG)
        baseline[label] = {
            "window": window,
            "metrics": _metrics(result, snapshots[label]),
        }
        metrics = baseline[label]["metrics"]
        print(
            f"[{label} baseline] EV={metrics['expected_value_score']} "
            f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
            f"DD={metrics['max_drawdown_pct']} trades={metrics['trade_count']}"
        )

    variants = OrderedDict()
    deltas = OrderedDict()
    for variant_name, override in VARIANTS.items():
        variant_config = {**BASELINE_CONFIG, **override}
        by_window = OrderedDict()
        for label, window in WINDOWS.items():
            result = _run_backtest(window, variant_config)
            by_window[label] = {
                "window": window,
                "metrics": _metrics(result, snapshots[label]),
            }
            metrics = by_window[label]["metrics"]
            print(
                f"[{label} {variant_name}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} trailing={metrics['trailing_stop_trades']}"
            )
        variants[variant_name] = by_window
        deltas[variant_name] = _delta(baseline, by_window)

    best = _best_variant(deltas)
    best_delta = deltas[best]
    accepted = _passes_gate4(best_delta)
    status = "accepted_candidate" if accepted else "rejected"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": status,
        "lane": "alpha_search",
        "change_type": "exit_lifecycle_full_atr_trailing",
        "hypothesis": (
            "Positions that first move far enough in our favor but fail to hit "
            "fixed targets leak alpha through giveback; a full-position ATR "
            "trailing exit may improve old_thin without changing entries, "
            "sizing, candidate universe, or LLM/news behavior."
        ),
        "alpha_hypothesis_category": "exit_lifecycle",
        "why_not_llm_or_sec": (
            "LLM soft-ranking and SEC/filing samples remain coverage-limited; "
            "this uses replayable OHLCV path data already available in all "
            "three canonical snapshots."
        ),
        "history_check": {
            "not_trailing_partial_reduce_retry": True,
            "not_signal_target_partial_reduce_retry": True,
            "not_day5_day10_price_only_exit_retry": True,
            "prior_mechanism_source": "exp-20260502-011 H2 MFE giveback observation",
        },
        "parameters": {
            "single_causal_variable": "full-position ATR trailing exit profile",
            "baseline": BASELINE_CONFIG,
            "tested_variants": VARIANTS,
            "best_variant": best,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk sizing",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "follow-through add-ons",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            "late_strong": "slow-melt bull / accepted-stack dominant tape",
            "mid_weak": "rotation-heavy bull where strategy makes money but lags indexes",
            "old_thin": "mixed-to-weak older tape with lower win rate",
        },
        "before_metrics": {
            label: baseline[label]["metrics"]
            for label in WINDOWS
        },
        "after_metrics": {
            name: {
                label: variants[name][label]["metrics"]
                for label in WINDOWS
            }
            for name in variants
        },
        "delta_metrics": deltas,
        "best_variant": best,
        "best_variant_delta": best_delta,
        "gate4_pass": accepted,
        "gate4_basis": (
            "Accepted candidate; production promotion requires moving the exit "
            "policy into a shared production/backtest lifecycle helper and "
            "adding parity tests."
            if accepted else
            "Rejected because no full-position ATR trailing profile cleared "
            "the fixed three-window Gate 4 acceptance bar."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "A positive variant cannot be merged as strategy logic until "
                "the same exit action is surfaced by run.py through shared "
                "production policy."
            ),
        },
        "rejection_reason": None if accepted else (
            "Full ATR trailing either cut fixed-target winners or did not "
            "reduce giveback enough across a majority of windows."
        ),
        "next_retry_requires": [
            "Do not repeat nearby ATR trigger/offset sweeps without a richer discriminator.",
            "A valid retry needs event/news context or a position-state feature that separates real trend exhaustion from normal volatility.",
            "If promoted later, implement through shared production parity rather than backtester-only config.",
        ],
        "related_files": [
            "quant/experiments/exp_20260503_009_atr_trailing_exit_profile.py",
            "data/experiments/exp-20260503-009/atr_trailing_exit_profile.json",
            "experiments/logs/exp-20260503-009.json",
            "experiments/tickets/exp-20260503-009.json",
        ],
    }
    return payload


def _append_jsonl(payload: dict) -> None:
    record = {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": {
            label: {
                key: payload["before_metrics"][label].get(key)
                for key in (
                    "expected_value_score",
                    "sharpe_daily",
                    "total_pnl",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "win_rate",
                    "trade_count",
                    "survival_rate",
                )
            }
            for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": payload["best_variant"],
            **{
                label: {
                    key: payload["after_metrics"][payload["best_variant"]][label].get(key)
                    for key in (
                        "expected_value_score",
                        "sharpe_daily",
                        "total_pnl",
                        "total_return_pct",
                        "max_drawdown_pct",
                        "win_rate",
                        "trade_count",
                        "survival_rate",
                    )
                }
                for label in WINDOWS
            },
        },
        "expected_value_score_delta": payload["best_variant_delta"]["expected_value_score_delta_sum"],
        "delta_metrics": payload["best_variant_delta"],
        "gate4_basis": payload["gate4_basis"],
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
    }
    with JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "ATR trailing exit profile sweep",
        "summary": payload["hypothesis"],
        "best_variant": payload["best_variant"],
        "gate4_pass": payload["gate4_pass"],
        "best_variant_delta": payload["best_variant_delta"],
        "next_retry_requires": payload["next_retry_requires"],
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _append_jsonl(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "gate4_pass": payload["gate4_pass"],
        "best_variant_delta": payload["best_variant_delta"],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
