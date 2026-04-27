"""Observed-only loss attribution for strict day-2 follow-through add-ons.

This audit keeps the accepted add-on candidate fixed and asks where adverse
outcomes come from. It does not change production strategy code.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402


EXPERIMENT_ID = "exp-20260426-016"

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
ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_UNREALIZED_PCT": 0.02,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_013_addon_loss_attribution.json",
)


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


def _trade_key(trade: dict) -> tuple:
    return (
        trade.get("ticker"),
        trade.get("strategy"),
        trade.get("entry_date"),
    )


def _index_trades(result: dict) -> dict[tuple, dict]:
    return {_trade_key(t): t for t in result.get("trades", [])}


def _event_key(event: dict) -> tuple:
    return (
        event.get("ticker"),
        event.get("strategy"),
        event.get("checkpoint_date"),
        event.get("scheduled_fill_date"),
    )


def _context_bucket(event: dict, trade: dict | None) -> str:
    strategy = event.get("strategy") or "unknown_strategy"
    sector = event.get("sector") or (trade or {}).get("sector") or "Unknown"
    unrealized = event.get("unrealized_pct")
    rs = event.get("rs_vs_spy")
    exit_reason = (trade or {}).get("exit_reason") or "unknown_exit"

    if sector == "Commodities":
        context = "commodity_followthrough"
    elif sector in {"Energy", "Materials"}:
        context = "cyclical_followthrough"
    elif strategy == "breakout_long":
        context = "breakout_followthrough"
    elif strategy == "trend_long":
        context = "trend_followthrough"
    else:
        context = strategy

    if unrealized is not None and unrealized >= 0.06:
        strength = "hot_gt6"
    elif unrealized is not None and unrealized >= 0.04:
        strength = "strong_4to6"
    else:
        strength = "thin_2to4"

    if rs is not None and rs < 0.01:
        rs_bucket = "low_rs_edge"
    else:
        rs_bucket = "clear_rs"

    return f"{context}|{strength}|{rs_bucket}|{exit_reason}"


def _summarize(rows: list[dict], pnl_field: str) -> dict:
    if not rows:
        return {"count": 0}
    pnls = [r[pnl_field] for r in rows if isinstance(r.get(pnl_field), (int, float))]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "win_rate": round(len(winners) / len(pnls), 4) if pnls else None,
        "loser_count": len(losers),
        "winner_count": len(winners),
    }


def _hypothetical_skipped_pnl(event: dict, trade: dict | None) -> float | None:
    if not trade:
        return None
    raw_open = event.get("raw_open")
    shares = event.get("requested_shares")
    exit_price = trade.get("exit_price")
    if not raw_open or not shares or not exit_price:
        return None
    # Existing add-on implementation uses entry slippage; this approximation
    # intentionally attributes only skipped opportunity cost by final exit.
    entry_fill = raw_open * 1.0005
    cost = exit_price * ROUND_TRIP_COST_PCT * shares
    return round((exit_price - entry_fill) * shares - cost, 2)


def _attribution_for_window(label: str, cfg: dict, universe: list[str]) -> dict:
    baseline = _run_window(universe, cfg, BASE_CONFIG)
    addon = _run_window(universe, cfg, ADDON_CONFIG)
    base_trades = _index_trades(baseline)
    addon_trades = _index_trades(addon)
    addon_events = addon.get("addon_attribution", {}).get("events", [])

    executed_rows = []
    skipped_rows = []
    for event in addon_events:
        matching_trade = next(
            (
                t for t in addon.get("trades", [])
                if t.get("ticker") == event.get("ticker")
                and t.get("strategy") == event.get("strategy")
            ),
            None,
        )
        status = event.get("status")
        if status == "executed":
            trade = matching_trade
            if not trade:
                continue
            base_trade = base_trades.get(_trade_key(trade))
            pnl_delta = None
            if base_trade:
                pnl_delta = round(trade.get("pnl", 0.0) - base_trade.get("pnl", 0.0), 2)
            row = {
                "event_key": _event_key(event),
                "ticker": event.get("ticker"),
                "strategy": event.get("strategy"),
                "sector": event.get("sector"),
                "checkpoint_date": event.get("checkpoint_date"),
                "scheduled_fill_date": event.get("scheduled_fill_date"),
                "unrealized_pct": event.get("unrealized_pct"),
                "rs_vs_spy": event.get("rs_vs_spy"),
                "addon_shares": event.get("addon_shares"),
                "exit_reason": trade.get("exit_reason"),
                "exit_date": trade.get("exit_date"),
                "baseline_pnl": base_trade.get("pnl") if base_trade else None,
                "addon_trade_pnl": trade.get("pnl"),
                "addon_pnl_delta": pnl_delta,
                "context_bucket": _context_bucket(event, trade),
            }
            row["adverse"] = pnl_delta is not None and pnl_delta <= 0
            executed_rows.append(row)
        elif status and status.startswith("skipped_"):
            trade = matching_trade or addon_trades.get((
                event.get("ticker"),
                event.get("strategy"),
                None,
            ))
            hypothetical = _hypothetical_skipped_pnl(event, matching_trade)
            skipped_rows.append({
                "event_key": _event_key(event),
                "ticker": event.get("ticker"),
                "strategy": event.get("strategy"),
                "sector": event.get("sector"),
                "checkpoint_date": event.get("checkpoint_date"),
                "scheduled_fill_date": event.get("scheduled_fill_date"),
                "status": status,
                "requested_shares": event.get("requested_shares"),
                "unrealized_pct": event.get("unrealized_pct"),
                "rs_vs_spy": event.get("rs_vs_spy"),
                "hypothetical_skipped_pnl": hypothetical,
                "context_bucket": _context_bucket(event, trade),
            })

    adverse_by_context = defaultdict(list)
    all_executed_by_context = defaultdict(list)
    skipped_by_context = defaultdict(list)
    for row in executed_rows:
        all_executed_by_context[row["context_bucket"]].append(row)
        if row["adverse"]:
            adverse_by_context[row["context_bucket"]].append(row)
    for row in skipped_rows:
        skipped_by_context[row["context_bucket"]].append(row)

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "baseline_metrics": {
            "expected_value_score": baseline.get("expected_value_score"),
            "total_pnl": baseline.get("total_pnl"),
            "trade_count": baseline.get("total_trades"),
            "win_rate": baseline.get("win_rate"),
        },
        "addon_metrics": {
            "expected_value_score": addon.get("expected_value_score"),
            "total_pnl": addon.get("total_pnl"),
            "trade_count": addon.get("total_trades"),
            "win_rate": addon.get("win_rate"),
            "addon": addon.get("addon_attribution", {}),
        },
        "delta_metrics": {
            "expected_value_score": round(addon.get("expected_value_score", 0) - baseline.get("expected_value_score", 0), 6),
            "total_pnl": round(addon.get("total_pnl", 0) - baseline.get("total_pnl", 0), 2),
        },
        "executed_summary": _summarize(executed_rows, "addon_pnl_delta"),
        "skipped_summary": _summarize(skipped_rows, "hypothetical_skipped_pnl"),
        "adverse_contexts": {
            k: _summarize(v, "addon_pnl_delta")
            for k, v in sorted(adverse_by_context.items())
        },
        "executed_contexts": {
            k: _summarize(v, "addon_pnl_delta")
            for k, v in sorted(all_executed_by_context.items())
        },
        "skipped_contexts": {
            k: _summarize(v, "hypothetical_skipped_pnl")
            for k, v in sorted(skipped_by_context.items())
        },
        "executed_events": executed_rows,
        "skipped_events": skipped_rows,
    }


def main() -> int:
    universe = get_universe()
    windows = {
        label: _attribution_for_window(label, cfg, universe)
        for label, cfg in WINDOWS.items()
    }

    executed = [
        row
        for window in windows.values()
        for row in window["executed_events"]
    ]
    skipped = [
        row
        for window in windows.values()
        for row in window["skipped_events"]
    ]
    adverse = [row for row in executed if row["adverse"]]

    adverse_by_context = defaultdict(list)
    for row in adverse:
        adverse_by_context[row["context_bucket"]].append(row)

    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Strict day-2 follow-through add-on adverse outcomes cluster into "
            "reproducible contexts that can be counted before production promotion."
        ),
        "change_type": "failure_taxonomy",
        "single_causal_variable": "strict day2 follow-through addon adverse outcome taxonomy",
        "parameters": ADDON_CONFIG,
        "windows": windows,
        "aggregate": {
            "executed_summary": _summarize(executed, "addon_pnl_delta"),
            "adverse_summary": _summarize(adverse, "addon_pnl_delta"),
            "skipped_summary": _summarize(skipped, "hypothetical_skipped_pnl"),
            "adverse_contexts": {
                k: _summarize(v, "addon_pnl_delta")
                for k, v in sorted(adverse_by_context.items())
            },
            "top_adverse_events": sorted(
                adverse,
                key=lambda r: r.get("addon_pnl_delta") or 0,
            )[:8],
        },
        "decision": "observed_only",
        "next_candidate": (
            "If add-on promotion is revisited, first test whether the repeated "
            "adverse context can be excluded without losing the larger positive "
            "executed add-on contexts."
        ),
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps(results["aggregate"], indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
