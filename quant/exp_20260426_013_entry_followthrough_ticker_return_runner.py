"""exp-20260426-010 follow-through add-on trigger-quality shadow audit.

The accepted candidate trigger stays fixed:
day-2 unrealized >= +2%, RS vs SPY > 0, add 25% of original shares.

This runner tests one extra trigger-quality variable without touching the
shared backtester: require the ticker's entry-close to checkpoint-close return
to be positive. Because the backtester has no config hook for this condition
yet, this is an audit of the normal add-on event stream, not a production-path
counterfactual replay.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
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

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_013_entry_followthrough_ticker_return_results.json",
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


def _load_snapshot(path: str) -> dict:
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("ohlcv", raw)


def _close_by_date(snapshot: dict, ticker: str) -> dict:
    rows = snapshot.get(ticker) or []
    out = {}
    for row in rows:
        date = row.get("Date") or row.get("date")
        close = row.get("Close")
        if date is not None and close is not None:
            out[str(date)[:10]] = float(close)
    return out


def _entry_return(snapshot: dict, event: dict) -> float | None:
    closes = _close_by_date(snapshot, event["ticker"])
    checkpoint_date = event.get("checkpoint_date")
    entry_date = event.get("entry_date")
    if not entry_date:
        # Backtester add-on events do not currently expose entry_date. Infer it
        # from the checkpoint index and checkpoint_days in the OHLCV snapshot.
        rows = snapshot.get(event["ticker"]) or []
        dates = [str((row.get("Date") or row.get("date")))[:10] for row in rows]
        try:
            checkpoint_idx = dates.index(checkpoint_date)
        except ValueError:
            return None
        entry_idx = checkpoint_idx - int(event.get("checkpoint_days", 2))
        if entry_idx < 0:
            return None
        entry_date = dates[entry_idx]
    entry_close = closes.get(str(entry_date)[:10])
    checkpoint_close = closes.get(str(checkpoint_date)[:10])
    if not entry_close or checkpoint_close is None:
        return None
    return (checkpoint_close / entry_close) - 1.0


def _matching_trade(trades: list[dict], event: dict) -> dict | None:
    fill_date = event.get("scheduled_fill_date")
    candidates = [
        trade for trade in trades
        if trade.get("ticker") == event.get("ticker")
        and trade.get("addon_count", 0)
        and str(trade.get("exit_date", "")) >= str(fill_date)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda trade: str(trade.get("exit_date", "")))[0]


def _addon_forward_pnl(event: dict, trade: dict | None) -> float | None:
    if not trade or event.get("status") != "executed":
        return None
    shares = event.get("addon_shares")
    entry_fill = event.get("entry_fill")
    exit_price = trade.get("exit_price")
    if not all(isinstance(v, (int, float)) for v in [shares, entry_fill, exit_price]):
        return None
    return round((exit_price - entry_fill) * shares, 2)


def _audit_events(snapshot: dict, addon_result: dict) -> dict:
    events = addon_result.get("addon_attribution", {}).get("events", [])
    trades = addon_result.get("trades", [])
    audited = []
    groups = {
        "pass_positive_ticker_return": [],
        "fail_nonpositive_ticker_return": [],
        "unknown_ticker_return": [],
    }

    for event in events:
        ticker_ret = _entry_return(snapshot, event)
        trade = _matching_trade(trades, event)
        rec = {
            **event,
            "ticker_day2_return": round(ticker_ret, 6) if ticker_ret is not None else None,
            "passes_positive_ticker_return": ticker_ret is not None and ticker_ret > 0,
            "matched_exit_date": trade.get("exit_date") if trade else None,
            "matched_exit_reason": trade.get("exit_reason") if trade else None,
            "estimated_addon_forward_pnl": _addon_forward_pnl(event, trade),
        }
        audited.append(rec)
        if ticker_ret is None:
            groups["unknown_ticker_return"].append(rec)
        elif ticker_ret > 0:
            groups["pass_positive_ticker_return"].append(rec)
        else:
            groups["fail_nonpositive_ticker_return"].append(rec)

    def summarize(items: list[dict]) -> dict:
        executed = [item for item in items if item.get("status") == "executed"]
        scheduled = [item for item in items if item.get("scheduled_fill_date")]
        skipped = [item for item in items if str(item.get("status", "")).startswith("skipped_")]
        pnls = [
            item["estimated_addon_forward_pnl"] for item in executed
            if isinstance(item.get("estimated_addon_forward_pnl"), (int, float))
        ]
        return {
            "events": len(items),
            "scheduled": len(scheduled),
            "executed": len(executed),
            "skipped": len(skipped),
            "estimated_forward_pnl_sum": round(sum(pnls), 2),
            "estimated_forward_pnl_avg": round(sum(pnls) / len(pnls), 2) if pnls else None,
            "positive_forward_pnl_rate": (
                round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 4)
                if pnls else None
            ),
            "cap_or_heat_skips": sum(
                1 for item in skipped
                if "position_cap" in str(item.get("status"))
                or "portfolio_heat" in str(item.get("status"))
            ),
        }

    summary = {name: summarize(items) for name, items in groups.items()}
    summary["all_events"] = summarize(audited)
    pass_pnl = summary["pass_positive_ticker_return"]["estimated_forward_pnl_sum"]
    all_pnl = summary["all_events"]["estimated_forward_pnl_sum"]
    summary["retained_estimated_pnl_fraction"] = (
        round(pass_pnl / all_pnl, 4) if all_pnl else None
    )
    summary["retained_executed_fraction"] = (
        round(
            summary["pass_positive_ticker_return"]["executed"]
            / summary["all_events"]["executed"],
            4,
        )
        if summary["all_events"]["executed"] else None
    )
    return {"summary": summary, "events": audited}


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": "exp-20260426-017",
        "artifact_name": "exp_20260426_013_entry_followthrough_ticker_return_results",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hypothesis": (
            "For the strict day-2 follow-through add-on candidate, requiring "
            "positive ticker return over the same two-day checkpoint may improve "
            "trigger quality."
        ),
        "single_causal_variable": "require_positive_day2_ticker_return_for_followthrough_addon",
        "fixed_addon_config": ADDON_CONFIG,
        "parity_warning": (
            "Audit-only decomposition of normal add-on events. The shared "
            "BacktestEngine has no config hook for this filter, and ticket scope "
            "forbids modifying it in this run."
        ),
        "windows": {},
    }

    aggregate = {
        "normal_addon_ev_delta_sum": 0.0,
        "normal_addon_pnl_delta_sum": 0.0,
        "pass_executed": 0,
        "all_executed": 0,
        "pass_estimated_forward_pnl": 0.0,
        "all_estimated_forward_pnl": 0.0,
    }

    for label, cfg in WINDOWS.items():
        snapshot = _load_snapshot(cfg["snapshot"])
        baseline_result = _run_window(universe, cfg, BASE_CONFIG)
        addon_result = _run_window(universe, cfg, ADDON_CONFIG)
        baseline = _metrics(baseline_result)
        addon = _metrics(addon_result)
        delta = _delta(addon, baseline)
        audit = _audit_events(snapshot, addon_result)

        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "baseline": baseline,
            "normal_25pct_addon": addon,
            "normal_25pct_delta_vs_baseline": delta,
            "ticker_return_filter_audit": audit,
        }

        aggregate["normal_addon_ev_delta_sum"] += delta.get("expected_value_score") or 0.0
        aggregate["normal_addon_pnl_delta_sum"] += delta.get("total_pnl") or 0.0
        audit_summary = audit["summary"]
        aggregate["pass_executed"] += audit_summary["pass_positive_ticker_return"]["executed"]
        aggregate["all_executed"] += audit_summary["all_events"]["executed"]
        aggregate["pass_estimated_forward_pnl"] += audit_summary[
            "pass_positive_ticker_return"
        ]["estimated_forward_pnl_sum"]
        aggregate["all_estimated_forward_pnl"] += audit_summary[
            "all_events"
        ]["estimated_forward_pnl_sum"]

    aggregate["normal_addon_ev_delta_sum"] = round(
        aggregate["normal_addon_ev_delta_sum"],
        6,
    )
    aggregate["normal_addon_pnl_delta_sum"] = round(
        aggregate["normal_addon_pnl_delta_sum"],
        2,
    )
    aggregate["retained_executed_fraction"] = (
        round(aggregate["pass_executed"] / aggregate["all_executed"], 4)
        if aggregate["all_executed"] else None
    )
    aggregate["retained_estimated_pnl_fraction"] = (
        round(
            aggregate["pass_estimated_forward_pnl"]
            / aggregate["all_estimated_forward_pnl"],
            4,
        )
        if aggregate["all_estimated_forward_pnl"] else None
    )
    aggregate["pass_estimated_forward_pnl"] = round(
        aggregate["pass_estimated_forward_pnl"],
        2,
    )
    aggregate["all_estimated_forward_pnl"] = round(
        aggregate["all_estimated_forward_pnl"],
        2,
    )
    results["aggregate_summary"] = aggregate

    if (
        aggregate["retained_estimated_pnl_fraction"] is not None
        and aggregate["retained_estimated_pnl_fraction"] >= 0.95
        and aggregate["retained_executed_fraction"] is not None
        and aggregate["retained_executed_fraction"] < 1.0
    ):
        decision = "needs_real_replay_hook"
    else:
        decision = "rejected_filter_quality"
    results["decision"] = decision
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "Audit-only result; no production add-on trigger can be promoted without "
        "a dedicated backtester config hook and full equity-curve replay."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "aggregate_summary": results["aggregate_summary"],
        "decision": results["decision"],
    }, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
