"""Observed-only skipped-execution audit for strict day-2 add-ons.

This loss-attribution experiment keeps the default-off add-on candidate fixed:
day-2 unrealized >= 2%, RS vs SPY > 0, add 25% of original shares. It only
classifies scheduled add-ons that did not execute because hard constraints
blocked them. Production strategy code is not changed.
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


EXPERIMENT_ID = "exp-20260426-019"

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
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
}
CHECKPOINT_CAP_CONFIG = {
    **ADDON_CONFIG,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": True,
}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_019_addon_skipped_execution_audit.json",
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


def _event_key(event: dict) -> tuple:
    return (
        event.get("ticker"),
        event.get("strategy"),
        event.get("checkpoint_date"),
        event.get("scheduled_fill_date"),
    )


def _index_trades(result: dict) -> dict[tuple, dict]:
    return {_trade_key(t): t for t in result.get("trades", [])}


def _find_trade_for_event(result: dict, event: dict) -> dict | None:
    for trade in result.get("trades", []):
        if (
            trade.get("ticker") == event.get("ticker")
            and trade.get("strategy") == event.get("strategy")
            and trade.get("entry_date") <= event.get("checkpoint_date", "")
            and trade.get("exit_date") >= event.get("checkpoint_date", "")
        ):
            return trade
    return None


def _strength_bucket(unrealized: float | None) -> str:
    if unrealized is None:
        return "unknown_strength"
    if unrealized >= 0.08:
        return "very_hot_gt8"
    if unrealized >= 0.06:
        return "hot_6to8"
    if unrealized >= 0.04:
        return "strong_4to6"
    return "thin_2to4"


def _rs_bucket(rs_vs_spy: float | None) -> str:
    if rs_vs_spy is None:
        return "unknown_rs"
    if rs_vs_spy < 0.01:
        return "low_rs_edge"
    if rs_vs_spy < 0.03:
        return "clear_rs"
    return "high_rs"


def _sleeve(event: dict) -> str:
    sector = event.get("sector") or "Unknown"
    strategy = event.get("strategy") or "unknown_strategy"
    if sector == "Commodities":
        return f"{strategy}|Commodities"
    if sector in {"Energy", "Materials"}:
        return f"{strategy}|Cyclicals"
    return f"{strategy}|{sector}"


def _context_bucket(event: dict, trade: dict | None) -> str:
    exit_reason = (trade or {}).get("exit_reason") or "unknown_exit"
    return "|".join([
        _sleeve(event),
        _strength_bucket(event.get("unrealized_pct")),
        _rs_bucket(event.get("rs_vs_spy")),
        str(event.get("status") or "unknown_status"),
        exit_reason,
    ])


def _hypothetical_pnl(event: dict, trade: dict | None) -> float | None:
    if not trade:
        return None
    raw_open = event.get("raw_open")
    requested_shares = event.get("requested_shares")
    exit_price = trade.get("exit_price")
    if not raw_open or not requested_shares or not exit_price:
        return None
    entry_fill = raw_open * 1.0005
    cost = exit_price * ROUND_TRIP_COST_PCT * requested_shares
    return round((exit_price - entry_fill) * requested_shares - cost, 2)


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
        "addons_scheduled": addon.get("scheduled", 0),
        "addons_executed": addon.get("executed", 0),
        "addons_skipped": addon.get("skipped", 0),
        "addons_checkpoint_rejected": addon.get("checkpoint_rejected", 0),
    }


def _summarize(rows: list[dict], pnl_field: str = "hypothetical_skipped_pnl") -> dict:
    if not rows:
        return {"count": 0}
    pnls = [r[pnl_field] for r in rows if isinstance(r.get(pnl_field), (int, float))]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    return {
        "count": len(rows),
        "with_pnl_count": len(pnls),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "win_rate": round(len(winners) / len(pnls), 4) if pnls else None,
        "winner_count": len(winners),
        "loser_count": len(losers),
    }


def _group_summary(rows: list[dict], group_key: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row.get(group_key) or "unknown"].append(row)
    return {
        key: _summarize(group_rows)
        for key, group_rows in sorted(groups.items())
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


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    baseline_result = _run_window(universe, cfg, BASE_CONFIG)
    addon_result = _run_window(universe, cfg, ADDON_CONFIG)
    checkpoint_result = _run_window(universe, cfg, CHECKPOINT_CAP_CONFIG)

    baseline_metrics = _metrics(baseline_result)
    addon_metrics = _metrics(addon_result)
    checkpoint_metrics = _metrics(checkpoint_result)

    baseline_trades = _index_trades(baseline_result)
    rows = []
    skipped_events = [
        e for e in addon_result.get("addon_attribution", {}).get("events", [])
        if str(e.get("status", "")).startswith("skipped_")
    ]
    checkpoint_rejected = {
        (e.get("ticker"), e.get("strategy"), e.get("checkpoint_date")): e
        for e in checkpoint_result.get("addon_attribution", {}).get("events", [])
        if str(e.get("status", "")).startswith("rejected_checkpoint_")
    }

    for event in skipped_events:
        trade = _find_trade_for_event(addon_result, event)
        base_trade = baseline_trades.get(_trade_key(trade or {})) if trade else None
        rejected = checkpoint_rejected.get((
            event.get("ticker"),
            event.get("strategy"),
            event.get("checkpoint_date"),
        ))
        pnl = _hypothetical_pnl(event, trade)
        row = {
            "window": label,
            "event_key": _event_key(event),
            "ticker": event.get("ticker"),
            "strategy": event.get("strategy"),
            "sector": event.get("sector"),
            "checkpoint_date": event.get("checkpoint_date"),
            "scheduled_fill_date": event.get("scheduled_fill_date"),
            "status": event.get("status"),
            "checkpoint_rejected_status": (rejected or {}).get("status"),
            "requested_shares": event.get("requested_shares"),
            "original_shares": event.get("original_shares"),
            "raw_open": event.get("raw_open"),
            "unrealized_pct": event.get("unrealized_pct"),
            "rs_vs_spy": event.get("rs_vs_spy"),
            "exit_reason": (trade or {}).get("exit_reason"),
            "exit_date": (trade or {}).get("exit_date"),
            "baseline_trade_pnl": (base_trade or {}).get("pnl"),
            "addon_trade_pnl": (trade or {}).get("pnl"),
            "hypothetical_skipped_pnl": pnl,
            "opportunity_class": (
                "skipped_winner" if isinstance(pnl, (int, float)) and pnl > 0
                else "skipped_loser" if isinstance(pnl, (int, float))
                else "unpriced_skip"
            ),
        }
        row["sleeve"] = _sleeve(row)
        row["context_bucket"] = _context_bucket(row, trade)
        rows.append(row)

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "baseline_metrics": baseline_metrics,
        "addon_metrics": addon_metrics,
        "checkpoint_cap_metrics": checkpoint_metrics,
        "addon_delta_vs_baseline": _delta(addon_metrics, baseline_metrics),
        "checkpoint_cap_delta_vs_addon": _delta(checkpoint_metrics, addon_metrics),
        "skipped_summary": _summarize(rows),
        "by_status": _group_summary(rows, "status"),
        "by_sleeve": _group_summary(rows, "sleeve"),
        "by_opportunity_class": _group_summary(rows, "opportunity_class"),
        "by_context_bucket": _group_summary(rows, "context_bucket"),
        "skipped_events": rows,
    }


def main() -> int:
    universe = get_universe()
    windows = {
        label: _window_audit(label, cfg, universe)
        for label, cfg in WINDOWS.items()
    }
    skipped = [
        row
        for window in windows.values()
        for row in window["skipped_events"]
    ]

    priced_skips = [
        row for row in skipped
        if isinstance(row.get("hypothetical_skipped_pnl"), (int, float))
    ]
    top_positive = sorted(
        [r for r in priced_skips if r["hypothetical_skipped_pnl"] > 0],
        key=lambda r: r["hypothetical_skipped_pnl"],
        reverse=True,
    )[:8]
    top_negative = sorted(
        [r for r in priced_skips if r["hypothetical_skipped_pnl"] <= 0],
        key=lambda r: r["hypothetical_skipped_pnl"],
    )[:8]

    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Strict day-2 follow-through add-on skipped executions may cluster "
            "into reproducible cap/heat opportunity-loss or risk-avoidance "
            "families before any production promotion."
        ),
        "change_type": "failure_taxonomy",
        "single_causal_variable": "strict day2 follow-through addon skipped-execution taxonomy",
        "parameters": ADDON_CONFIG,
        "windows": windows,
        "aggregate": {
            "skipped_summary": _summarize(skipped),
            "by_status": _group_summary(skipped, "status"),
            "by_sleeve": _group_summary(skipped, "sleeve"),
            "by_opportunity_class": _group_summary(skipped, "opportunity_class"),
            "by_context_bucket": _group_summary(skipped, "context_bucket"),
            "top_positive_skipped_events": top_positive,
            "top_negative_skipped_events": top_negative,
        },
        "decision": "observed_only",
        "interpretation": (
            "This is attribution only. Positive skipped opportunity does not "
            "justify relaxing hard caps; it identifies where a future, separate "
            "capital-allocation experiment would need to prove materiality."
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
