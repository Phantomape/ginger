"""exp-20260426-053 low-MFE stopout lifecycle exit replay.

Experiment-only, default-off replay. It does not modify production strategy
files. The replay asks whether a narrow in-trade state can exit positions
earlier when they never achieve 1% favorable excursion and close below entry
before the original exit.
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
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260426-053"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_053_low_mfe_exit_replay_results.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with weaker follow-through",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
LOW_MFE_PCT = 0.01
TRIGGER_CLOSE_RETURN_MAX = 0.0
INITIAL_CAPITAL = 100_000.0


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict]]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    return payload.get("ohlcv", payload)


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _value(row: dict, key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _trade_rows(snapshot: dict[str, list[dict]], trade: dict) -> list[dict]:
    rows = sorted(snapshot.get(trade.get("ticker"), []) or [], key=_date)
    entry = trade.get("entry_date")
    exit_ = trade.get("exit_date")
    return [row for row in rows if entry <= _date(row) <= exit_]


def _trigger(rows: list[dict], trade: dict) -> dict | None:
    entry = trade.get("entry_price")
    if not isinstance(entry, (int, float)) or entry <= 0:
        return None
    if len(rows) < 2:
        return None

    max_high = None
    for idx, row in enumerate(rows[:-1]):
        high = _value(row, "High")
        close = _value(row, "Close")
        if high is not None:
            max_high = high if max_high is None else max(max_high, high)
        if close is None or max_high is None:
            continue
        running_mfe = (max_high / entry) - 1.0
        close_return = (close / entry) - 1.0
        if running_mfe < LOW_MFE_PCT and close_return <= TRIGGER_CLOSE_RETURN_MAX:
            next_row = rows[idx + 1]
            raw_open = _value(next_row, "Open")
            if raw_open is None:
                return None
            exit_price = apply_slippage(raw_open, SLIPPAGE_BPS_TARGET, "sell")
            return {
                "trigger_date": _date(row),
                "exit_date": _date(next_row),
                "exit_raw_price": raw_open,
                "exit_price": exit_price,
                "running_mfe_pct": running_mfe,
                "trigger_close_return_pct": close_return,
            }
    return None


def _replayed_trade(trade: dict, trigger: dict | None) -> tuple[dict, dict | None]:
    if not trigger:
        return dict(trade), None

    entry = trade.get("entry_price")
    shares = trade.get("shares")
    exit_price = trigger["exit_price"]
    if not isinstance(entry, (int, float)) or not isinstance(shares, int):
        return dict(trade), None

    new_pnl = (exit_price - entry) * shares - exit_price * ROUND_TRIP_COST_PCT * shares
    old_pnl = float(trade.get("pnl") or 0.0)
    replayed = dict(trade)
    replayed.update({
        "exit_price": round(exit_price, 2),
        "exit_raw_price": round(trigger["exit_raw_price"], 4),
        "exit_reason": "exp_low_mfe_lifecycle_exit",
        "exit_date": trigger["exit_date"],
        "pnl": round(new_pnl, 2),
        "pnl_pct_net": round(((exit_price - entry) / entry) - ROUND_TRIP_COST_PCT, 6),
    })
    event = {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "original_exit_date": trade.get("exit_date"),
        "original_exit_reason": trade.get("exit_reason"),
        "trigger_date": trigger["trigger_date"],
        "replay_exit_date": trigger["exit_date"],
        "running_mfe_pct": round(trigger["running_mfe_pct"], 6),
        "trigger_close_return_pct": round(trigger["trigger_close_return_pct"], 6),
        "old_pnl": round(old_pnl, 2),
        "new_pnl": round(new_pnl, 2),
        "pnl_delta": round(new_pnl - old_pnl, 2),
        "winner_truncated": old_pnl > 0 and new_pnl < old_pnl,
    }
    return replayed, event


def _metrics_from_trades(before: dict, trades: list[dict]) -> dict:
    total_pnl = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
    wins = sum(1 for trade in trades if (trade.get("pnl") or 0.0) > 0)
    total = len(trades)
    total_return = round(total_pnl / INITIAL_CAPITAL, 4)
    after = dict(before)
    after.update({
        "trades": trades,
        "total_trades": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total, 4) if total else 0.0,
        "total_pnl": total_pnl,
        "benchmarks": {
            **(before.get("benchmarks") or {}),
            "strategy_total_return_pct": total_return,
        },
    })
    after["expected_value_score"] = compute_expected_value_score(after)
    return after


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
    }


def _delta(after: dict, before: dict) -> dict:
    return {
        key: (
            round((after.get(key) or 0.0) - (before.get(key) or 0.0), 6)
            if isinstance(before.get(key), (int, float)) or isinstance(after.get(key), (int, float))
            else None
        )
        for key in before
    }


def _run_window(label: str, cfg: dict, universe: list[str]) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    baseline = engine.run()
    snapshot = _load_snapshot(cfg["snapshot"])

    replayed = []
    events = []
    for trade in baseline.get("trades", []):
        rows = _trade_rows(snapshot, trade)
        trigger = _trigger(rows, trade)
        new_trade, event = _replayed_trade(trade, trigger)
        replayed.append(new_trade)
        if event:
            events.append(event)

    after = _metrics_from_trades(baseline, replayed)
    before_metrics = _metrics(baseline)
    after_metrics = _metrics(after)
    return {
        "window": label,
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "market_regime_summary": cfg["regime"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": _delta(after_metrics, before_metrics),
        "trigger_count": len(events),
        "winner_truncation_count": sum(1 for row in events if row["winner_truncated"]),
        "winner_truncation_pnl_delta": round(
            sum(row["pnl_delta"] for row in events if row["winner_truncated"]), 2
        ),
        "stopout_trigger_count": sum(
            1 for row in events if row["original_exit_reason"] == "stop"
        ),
        "events": events,
    }


def _decision_support(windows: list[dict]) -> dict:
    improved = [
        row["window"]
        for row in windows
        if (row["delta_metrics"].get("expected_value_score") or 0.0) > 0
    ]
    material_winner_truncation = [
        row["window"]
        for row in windows
        if row["winner_truncation_count"] > 0
        and abs(row["winner_truncation_pnl_delta"]) > 0.01 * abs(row["baseline_metrics"]["total_pnl"])
    ]
    accepted_candidate = len(improved) >= 2 and not material_winner_truncation
    return {
        "candidate_acceptance_rule": (
            "accepted_candidate iff majority-window EV improves and no window "
            "has material winner truncation above 1% of baseline PnL"
        ),
        "ev_improved_windows": improved,
        "material_winner_truncation_windows": material_winner_truncation,
        "accepted_candidate": accepted_candidate,
        "production_connection_justified": accepted_candidate,
        "production_connection_note": (
            "A separate production-path ticket would still be required."
            if accepted_candidate
            else "Do not connect to production; replay did not pass the shadow candidate gate."
        ),
    }


def _root_from_primary(windows: list[dict]) -> dict:
    primary = next(row for row in windows if row["window"] == "late_strong")
    metrics = primary["after_metrics"]
    return {
        "period": "2025-10-23 -> 2026-04-21",
        "total_trades": metrics["trade_count"],
        "win_rate": metrics["win_rate"],
        "total_pnl": metrics["total_pnl"],
        "sharpe": metrics["sharpe"],
        "sharpe_daily": metrics["sharpe_daily"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "survival_rate": metrics["survival_rate"],
        "expected_value_score": metrics["expected_value_score"],
        "benchmarks": {
            "strategy_total_return_pct": metrics["total_return_pct"],
        },
    }


def main() -> int:
    universe = get_universe()
    windows = [_run_window(label, cfg, universe) for label, cfg in WINDOWS.items()]
    for row in windows:
        print(
            f"[{row['window']}] EV {row['baseline_metrics']['expected_value_score']} -> "
            f"{row['after_metrics']['expected_value_score']} "
            f"delta={row['delta_metrics']['expected_value_score']} "
            f"triggers={row['trigger_count']} "
            f"winner_trunc={row['winner_truncation_count']}"
        )

    decision = _decision_support(windows)
    root = _root_from_primary(windows)
    root.update({
        "experiment_id": EXPERIMENT_ID,
        "status": "accepted_candidate" if decision["accepted_candidate"] else "rejected",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "The zero-winner-collateral low-MFE stopout family may support a "
            "narrow default-off lifecycle exit replay, distinct from rejected "
            "generic weak-hold exits."
        ),
        "single_causal_variable": "low-MFE stopout lifecycle exit replay trigger",
        "parameters": {
            "low_mfe_pct": LOW_MFE_PCT,
            "trigger_close_return_max": TRIGGER_CLOSE_RETURN_MAX,
            "execution": "next available open after trigger close, target-side sell slippage",
            "default_off": True,
            "note": (
                "This replay changes only exit timing for already-open trades; "
                "it does not refill freed slots or alter entries/ranking/sizing."
            ),
        },
        "windows": windows,
        "decision_support": decision,
        "production_promotion": False,
        "production_promotion_reason": decision["production_connection_note"],
    })

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(root, handle, indent=2)
        handle.write("\n")

    print(json.dumps({"decision_support": decision}, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
