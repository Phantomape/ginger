"""Shadow audit for entry-high confirmed strict day-2 add-on triggers.

The research candidate stays fixed:
day-2 unrealized >= +2%, RS vs SPY > 0, add 25% of original shares.

This runner changes one variable only in shadow mode: trigger quality. It keeps
an already scheduled add-on only when the checkpoint close is above the original
entry-day high. Shared production strategy modules are not modified.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260426-038"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / AI-beta continuation",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with crowding risk",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak macro tape",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
NORMAL_ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_UNREALIZED_PCT": 0.02,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_038_entry_followthrough_entry_high_trigger_results.json",
)


def _load_snapshot(path: str) -> dict:
    with open(os.path.join(REPO_ROOT, path), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {
        ticker: {row["Date"]: row for row in rows}
        for ticker, rows in raw.get("ohlcv", {}).items()
    }


def _run_window(universe: list[str], cfg: dict, config: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _metrics(result: dict) -> dict:
    addon = result.get("addon_attribution", {})
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "addons_scheduled": addon.get("scheduled"),
        "addons_executed": addon.get("executed"),
        "addons_skipped": addon.get("skipped"),
        "addons_checkpoint_rejected": addon.get("checkpoint_rejected"),
    }


def _delta(after: dict, before: dict) -> dict:
    fields = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "addons_scheduled",
        "addons_executed",
        "addons_skipped",
    ]
    out = {}
    for field in fields:
        a = after.get(field)
        b = before.get(field)
        out[field] = (
            round(a - b, 6)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else None
        )
    return out


def _find_trade_for_event(event: dict, trades: list[dict], entry_date: str | None) -> dict | None:
    for trade in trades:
        if (
            trade.get("ticker") == event.get("ticker")
            and trade.get("strategy") == event.get("strategy")
            and (entry_date is None or trade.get("entry_date") == entry_date)
        ):
            return trade
    return None


def _row_value(snapshot: dict, ticker: str, date: str | None, field: str) -> float | None:
    if not date:
        return None
    row = snapshot.get(ticker, {}).get(date)
    if not row:
        return None
    value = row.get(field)
    return float(value) if isinstance(value, (int, float)) else None


def _entry_date(event: dict, snapshot: dict) -> str | None:
    rows = snapshot.get(event.get("ticker"), {})
    dates = sorted(rows)
    checkpoint = event.get("checkpoint_date")
    if checkpoint not in rows:
        return None
    idx = dates.index(checkpoint)
    entry_idx = idx - int(event.get("checkpoint_days", 2))
    return dates[entry_idx] if entry_idx >= 0 else None


def _entry_high_state(event: dict, trade: dict | None, snapshot: dict) -> dict:
    ticker = event.get("ticker")
    entry = _entry_date(event, snapshot)
    checkpoint = event.get("checkpoint_date")
    entry_high = _row_value(snapshot, ticker, entry, "High")
    entry_close = _row_value(snapshot, ticker, entry, "Close")
    day2_close = _row_value(snapshot, ticker, checkpoint, "Close")
    entry_price = trade.get("entry_price") if trade else None

    if not all(isinstance(v, (int, float)) and v > 0 for v in [
        entry_high,
        entry_close,
        day2_close,
        entry_price,
    ]):
        return {
            "entry_date": entry,
            "has_state": False,
            "keep_entry_high_trigger": False,
        }

    close_vs_entry_high = (day2_close - entry_high) / entry_high
    close_vs_entry_close = (day2_close - entry_close) / entry_close
    unrealized = (day2_close - entry_price) / entry_price
    keep = day2_close > entry_high

    return {
        "entry_date": entry,
        "has_state": True,
        "entry_day_high": round(entry_high, 6),
        "entry_day_close": round(entry_close, 6),
        "day2_close": round(day2_close, 6),
        "day2_unrealized_pct": round(unrealized, 6),
        "day2_close_vs_entry_high_pct": round(close_vs_entry_high, 6),
        "day2_close_vs_entry_close_pct": round(close_vs_entry_close, 6),
        "keep_entry_high_trigger": keep,
    }


def _addon_contribution(event: dict, trade: dict | None) -> float:
    if event.get("status") != "executed" or trade is None:
        return 0.0
    shares = event.get("addon_shares")
    fill = event.get("entry_fill")
    exit_price = trade.get("exit_price")
    if not all(isinstance(v, (int, float)) for v in [shares, fill, exit_price]):
        return 0.0
    return float(shares) * (float(exit_price) - float(fill))


def _shadow_filtered_metrics(
    baseline: dict,
    normal: dict,
    kept_contribution: float,
    kept_executed: int,
    kept_scheduled: int,
) -> dict:
    total_pnl = round((baseline.get("total_pnl") or 0.0) + kept_contribution, 2)
    total_return = round(total_pnl / 100000.0, 6)
    sharpe_daily = normal.get("sharpe_daily")
    ev = (
        round(total_return * sharpe_daily, 4)
        if isinstance(sharpe_daily, (int, float))
        else None
    )
    return {
        "expected_value_score": ev,
        "sharpe_daily": sharpe_daily,
        "total_pnl": total_pnl,
        "total_return_pct": total_return,
        "max_drawdown_pct": normal.get("max_drawdown_pct"),
        "trade_count": normal.get("total_trades"),
        "win_rate": normal.get("win_rate"),
        "addons_scheduled": kept_scheduled,
        "addons_executed": kept_executed,
        "addons_skipped": 0,
        "addons_checkpoint_rejected": 0,
    }


def _summarize_window(label: str, cfg: dict, baseline: dict, normal: dict) -> dict:
    snapshot = _load_snapshot(cfg["snapshot"])
    trades = normal.get("trades", [])
    events = normal.get("addon_attribution", {}).get("events", [])
    baseline_metrics = _metrics(baseline)
    normal_metrics = _metrics(normal)

    rows = []
    kept_contribution = 0.0
    normal_contribution = 0.0
    kept_executed = 0
    kept_scheduled = 0

    for event in events:
        entry = _entry_date(event, snapshot)
        trade = _find_trade_for_event(event, trades, entry)
        state = _entry_high_state(event, trade, snapshot)
        contribution = round(_addon_contribution(event, trade), 2)
        normal_contribution += contribution
        keep = bool(state.get("keep_entry_high_trigger"))
        if keep:
            kept_scheduled += 1
            kept_contribution += contribution
            if event.get("status") == "executed":
                kept_executed += 1
        rows.append({
            **event,
            **state,
            "matched_exit_date": trade.get("exit_date") if trade else None,
            "matched_exit_reason": trade.get("exit_reason") if trade else None,
            "matched_trade_pnl": trade.get("pnl") if trade else None,
            "estimated_addon_pnl_contribution": contribution,
            "kept_by_entry_high_trigger": keep,
        })

    filtered_metrics = _shadow_filtered_metrics(
        baseline,
        normal,
        kept_contribution,
        kept_executed,
        kept_scheduled,
    )
    executed = [row for row in rows if row.get("status") == "executed"]
    removed_executed = [row for row in executed if not row.get("kept_by_entry_high_trigger")]
    kept_executed_rows = [row for row in executed if row.get("kept_by_entry_high_trigger")]
    normal_delta_pnl = (normal.get("total_pnl") or 0.0) - (baseline.get("total_pnl") or 0.0)

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "baseline": baseline_metrics,
        "normal_25pct_addon": normal_metrics,
        "entry_high_trigger_shadow": filtered_metrics,
        "normal_25pct_delta_vs_baseline": _delta(normal_metrics, baseline_metrics),
        "entry_high_trigger_delta_vs_normal_25pct_addon": _delta(
            filtered_metrics,
            normal_metrics,
        ),
        "normal_addon_contribution_reconciliation": {
            "estimated_addon_pnl_sum": round(normal_contribution, 2),
            "actual_normal_minus_baseline_pnl": round(normal_delta_pnl, 2),
            "difference": round(normal_contribution - normal_delta_pnl, 2),
            "note": (
                "Contribution is event-level shadow attribution and may differ "
                "from full replay PnL because add-ons affect average entry and "
                "cash path inside BacktestEngine."
            ),
        },
        "trigger_quality_counts": {
            "scheduled_normal": len(events),
            "scheduled_kept": kept_scheduled,
            "executed_normal": len(executed),
            "executed_kept": kept_executed,
            "executed_removed": len(removed_executed),
        },
        "trigger_quality_pnl": {
            "kept_executed_estimated_pnl": round(
                sum(row["estimated_addon_pnl_contribution"] for row in kept_executed_rows),
                2,
            ),
            "removed_executed_estimated_pnl": round(
                sum(row["estimated_addon_pnl_contribution"] for row in removed_executed),
                2,
            ),
        },
        "events": rows,
    }


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Strict day-2 follow-through add-ons may become more selective if "
            "the day-2 close exceeds the entry-day high."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": (
            "strict day2 follow-through add-on trigger quality via close above "
            "entry-day high"
        ),
        "fixed_addon_config": NORMAL_ADDON_CONFIG,
        "shadow_rule": {
            "name": "day2_close_above_entry_day_high",
            "definition": (
                "Keep a normal strict day-2 add-on only when the checkpoint "
                "close is above the original entry-day high."
            ),
        },
        "parity_warning": (
            "Shadow audit only. The runner filters add-on attribution events "
            "from normal BacktestEngine output and estimates the PnL effect; "
            "it does not modify BacktestEngine scheduling behavior."
        ),
        "windows": {},
        "aggregate": {
            "ev_delta_vs_normal_addon_sum": 0.0,
            "pnl_delta_vs_normal_addon_sum": 0.0,
            "windows_improved_ev": 0,
            "windows_regressed_ev": 0,
            "normal_executed_addons": 0,
            "kept_executed_addons": 0,
            "removed_executed_addons": 0,
            "removed_executed_estimated_pnl": 0.0,
        },
    }
    normal_ev_sum = 0.0
    normal_pnl_sum = 0.0
    normal_return_sum = 0.0
    normal_trades = 0
    normal_wins = 0.0
    normal_max_drawdown = 0.0
    normal_survival_sum = 0.0
    filtered_ev_sum = 0.0
    filtered_pnl_sum = 0.0
    filtered_return_sum = 0.0

    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, BASE_CONFIG)
        normal = _run_window(universe, cfg, NORMAL_ADDON_CONFIG)
        window = _summarize_window(label, cfg, baseline, normal)
        delta = window["entry_high_trigger_delta_vs_normal_25pct_addon"]
        counts = window["trigger_quality_counts"]
        pnl = window["trigger_quality_pnl"]
        normal_metrics = window["normal_25pct_addon"]
        filtered_metrics = window["entry_high_trigger_shadow"]

        ev_delta = delta.get("expected_value_score") or 0.0
        pnl_delta = delta.get("total_pnl") or 0.0
        agg = results["aggregate"]
        agg["ev_delta_vs_normal_addon_sum"] += ev_delta
        agg["pnl_delta_vs_normal_addon_sum"] += pnl_delta
        agg["windows_improved_ev"] += 1 if ev_delta > 0 else 0
        agg["windows_regressed_ev"] += 1 if ev_delta < 0 else 0
        agg["normal_executed_addons"] += counts["executed_normal"]
        agg["kept_executed_addons"] += counts["executed_kept"]
        agg["removed_executed_addons"] += counts["executed_removed"]
        agg["removed_executed_estimated_pnl"] += pnl["removed_executed_estimated_pnl"]
        results["windows"][label] = window

        normal_ev_sum += normal_metrics.get("expected_value_score") or 0.0
        normal_pnl_sum += normal_metrics.get("total_pnl") or 0.0
        normal_return_sum += normal_metrics.get("total_return_pct") or 0.0
        normal_trades += normal_metrics.get("trade_count") or 0
        normal_wins += (
            (normal_metrics.get("win_rate") or 0.0)
            * (normal_metrics.get("trade_count") or 0)
        )
        normal_max_drawdown = max(
            normal_max_drawdown,
            normal_metrics.get("max_drawdown_pct") or 0.0,
        )
        normal_survival_sum += normal.get("survival_rate") or 0.0
        filtered_ev_sum += filtered_metrics.get("expected_value_score") or 0.0
        filtered_pnl_sum += filtered_metrics.get("total_pnl") or 0.0
        filtered_return_sum += filtered_metrics.get("total_return_pct") or 0.0

    for key in [
        "ev_delta_vs_normal_addon_sum",
        "pnl_delta_vs_normal_addon_sum",
        "removed_executed_estimated_pnl",
    ]:
        results["aggregate"][key] = round(results["aggregate"][key], 4)

    agg = results["aggregate"]
    results["decision"] = (
        "candidate_needs_real_replay_review"
        if (
            agg["windows_improved_ev"] >= 2
            and agg["windows_regressed_ev"] == 0
            and agg["pnl_delta_vs_normal_addon_sum"] > 0
        )
        else "rejected_shadow_trigger_quality"
    )
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "No production promotion from event-level shadow attribution. A passing "
        "result would still require a scoped BacktestEngine config hook and "
        "normal judge comparison."
    )
    results["expected_value_score"] = round(filtered_ev_sum, 4)
    results["sharpe"] = None
    results["sharpe_daily"] = None
    results["benchmarks"] = {
        "strategy_total_return_pct": round(filtered_return_sum, 4),
    }
    results["max_drawdown_pct"] = round(normal_max_drawdown, 4)
    results["win_rate"] = round(normal_wins / normal_trades, 4) if normal_trades else None
    results["total_trades"] = normal_trades
    results["wins"] = round(normal_wins, 4)
    results["total_pnl"] = round(filtered_pnl_sum, 2)
    results["survival_rate"] = round(normal_survival_sum / len(WINDOWS), 4)
    results["aggregation_note"] = (
        "Three-window shadow aggregate for judge compatibility. The after "
        "metrics are estimated by filtering normal add-on attribution events; "
        "per-window details and reconciliation are under windows."
    )
    results["normal_25pct_addon_aggregate"] = {
        "expected_value_score": round(normal_ev_sum, 4),
        "total_pnl": round(normal_pnl_sum, 2),
        "total_return_pct": round(normal_return_sum, 4),
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "aggregate": results["aggregate"],
        "decision": results["decision"],
        "wrote": OUT_JSON,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
