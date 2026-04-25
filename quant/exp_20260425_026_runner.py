"""exp-20260425-026 passive QQQ idle-cash overlay screen.

This is deliberately different from exp-20260425-025:
    025 made QQQ behave like another ATR-target trade and failed.
    026 screens a passive overlay on estimated idle cash, with no target/stop.

The output is a research screen, not production parity. If it is positive, the
next step is implementing a real overlay ledger in the backtester.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import OrderedDict

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


INITIAL_CAPITAL = 100_000.0
SLOT_CAPITAL_FRACTION = 0.20

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

VARIANTS = OrderedDict([
    ("overlay025_mom015", {"overlay_fraction": 0.25, "mom10_min": 0.015}),
    ("overlay050_mom015", {"overlay_fraction": 0.50, "mom10_min": 0.015}),
    ("overlay100_mom015", {"overlay_fraction": 1.00, "mom10_min": 0.015}),
    ("overlay025_mom025", {"overlay_fraction": 0.25, "mom10_min": 0.025}),
    ("overlay050_mom025", {"overlay_fraction": 0.50, "mom10_min": 0.025}),
    ("overlay100_mom025", {"overlay_fraction": 1.00, "mom10_min": 0.025}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_026_results.json")


def _load_snapshot_frame(snapshot_path: str, ticker: str) -> pd.DataFrame:
    with open(snapshot_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    rows = (payload.get("ohlcv") or {}).get(ticker)
    if not rows:
        raise ValueError(f"{ticker} missing from {snapshot_path}")
    frame = pd.DataFrame(rows)
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.set_index("Date").sort_index()
    return frame


def _active_count_by_day(trades: list[dict], days: list[pd.Timestamp]) -> dict[str, int]:
    counts = {str(day.date()): 0 for day in days}
    for trade in trades:
        try:
            entry = pd.Timestamp(trade.get("entry_date"))
            exit_ = pd.Timestamp(trade.get("exit_date"))
        except Exception:
            continue
        if pd.isna(entry) or pd.isna(exit_) or entry > exit_:
            continue
        for day in days:
            if entry <= day <= exit_:
                counts[str(day.date())] += 1
    return counts


def _sharpe_daily(equity_values: list[float]):
    returns = []
    for i in range(1, len(equity_values)):
        prev = equity_values[i - 1]
        if prev > 0:
            returns.append((equity_values[i] / prev) - 1)
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(var_r) if var_r > 0 else 0
    return round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else None


def _max_drawdown(equity_values: list[float]):
    peak = 0.0
    max_dd = 0.0
    for value in equity_values:
        peak = max(peak, value)
        dd = (peak - value) / peak if peak else 0.0
        max_dd = max(max_dd, dd)
    return round(max_dd, 4)


def _risk_on_series(qqq: pd.DataFrame, spy: pd.DataFrame, mom10_min: float):
    qqq = qqq.copy()
    spy = spy.copy()
    qqq["ma200"] = qqq["Close"].rolling(200).mean()
    qqq["mom10"] = qqq["Close"] / qqq["Close"].shift(10) - 1
    spy["mom10"] = spy["Close"] / spy["Close"].shift(10) - 1
    aligned = qqq.join(spy[["mom10"]].rename(columns={"mom10": "spy_mom10"}))
    return (
        (aligned["Close"] > aligned["ma200"])
        & (aligned["Close"] / aligned["ma200"] - 1 > 0.05)
        & (aligned["mom10"] >= mom10_min)
        & (aligned["mom10"] > aligned["spy_mom10"])
    )


def _apply_overlay(result: dict, cfg: dict, variant: dict) -> dict:
    snapshot = os.path.join(REPO_ROOT, cfg["snapshot"])
    qqq = _load_snapshot_frame(snapshot, "QQQ")
    spy = _load_snapshot_frame(snapshot, "SPY")

    equity_curve = [(pd.Timestamp(d), float(v)) for d, v in result["equity_curve"]]
    days = [d for d, _ in equity_curve]
    active_counts = _active_count_by_day(result.get("trades", []), days)
    risk_on = _risk_on_series(qqq, spy, variant["mom10_min"])

    overlay_pnl = 0.0
    overlay_days = 0
    overlay_notional_days = 0.0
    combined = [equity_curve[0][1]]
    for i in range(1, len(equity_curve)):
        day = equity_curve[i][0]
        prev_day = equity_curve[i - 1][0]
        base_value = equity_curve[i][1]
        prev_close = qqq["Close"].get(prev_day)
        close = qqq["Close"].get(day)
        if prev_close is None or close is None or prev_close <= 0:
            combined.append(base_value + overlay_pnl)
            continue
        if not bool(risk_on.get(prev_day, False)):
            combined.append(base_value + overlay_pnl)
            continue

        active = active_counts.get(str(prev_day.date()), 0)
        idle_fraction = max(0.0, 1.0 - active * SLOT_CAPITAL_FRACTION)
        notional = INITIAL_CAPITAL * idle_fraction * variant["overlay_fraction"]
        if notional <= 0:
            combined.append(base_value + overlay_pnl)
            continue
        daily_pnl = notional * ((close / prev_close) - 1)
        overlay_pnl += daily_pnl
        overlay_days += 1
        overlay_notional_days += notional / INITIAL_CAPITAL
        combined.append(base_value + overlay_pnl)

    total_pnl = result.get("total_pnl", 0.0) + overlay_pnl
    total_return = total_pnl / INITIAL_CAPITAL
    sharpe_daily = _sharpe_daily(combined)
    ev = round(total_return * sharpe_daily, 4) if sharpe_daily is not None else None
    spy_ret = (result.get("benchmarks") or {}).get("spy_buy_hold_return_pct")
    qqq_ret = (result.get("benchmarks") or {}).get("qqq_buy_hold_return_pct")
    return {
        "overlay_pnl": round(overlay_pnl, 2),
        "overlay_days": overlay_days,
        "avg_overlay_notional_fraction": (
            round(overlay_notional_days / overlay_days, 4) if overlay_days else 0.0
        ),
        "expected_value_score": ev,
        "sharpe_daily": sharpe_daily,
        "max_drawdown_pct": _max_drawdown(combined),
        "total_return_pct": round(total_return, 4),
        "strategy_vs_spy_pct": round(total_return - spy_ret, 4) if spy_ret is not None else None,
        "strategy_vs_qqq_pct": round(total_return - qqq_ret, 4) if qqq_ret is not None else None,
    }


def _baseline_summary(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": (result.get("benchmarks") or {}).get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": (result.get("benchmarks") or {}).get("strategy_vs_qqq_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "gross_slot_day_fraction": (result.get("capital_efficiency") or {}).get(
            "gross_slot_day_fraction"
        ),
    }


def main() -> int:
    universe = list(dict.fromkeys(list(get_universe()) + ["QQQ"]))
    results = []
    for label, cfg in WINDOWS.items():
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=os.path.join(REPO_ROOT, "data"),
            ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
        )
        baseline = engine.run()
        base = _baseline_summary(baseline)
        print(
            f"[{label} baseline] EV={base['expected_value_score']} "
            f"ret={base['total_return_pct']} vs_spy={base['strategy_vs_spy_pct']} "
            f"vs_qqq={base['strategy_vs_qqq_pct']} sharpe_d={base['sharpe_daily']} "
            f"dd={base['max_drawdown_pct']}"
        )
        results.append({"window": label, "variant": "baseline", **base})

        for variant_name, variant in VARIANTS.items():
            overlay = _apply_overlay(baseline, cfg, variant)
            row = {
                "window": label,
                "variant": variant_name,
                "overlay_fraction": variant["overlay_fraction"],
                "mom10_min": variant["mom10_min"],
                **overlay,
            }
            print(
                f"[{label} {variant_name}] EV={row['expected_value_score']} "
                f"ret={row['total_return_pct']} vs_spy={row['strategy_vs_spy_pct']} "
                f"vs_qqq={row['strategy_vs_qqq_pct']} sharpe_d={row['sharpe_daily']} "
                f"dd={row['max_drawdown_pct']} overlay_pnl={row['overlay_pnl']} "
                f"days={row['overlay_days']} notional={row['avg_overlay_notional_fraction']}"
            )
            results.append(row)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "passive_qqq_idle_cash_overlay",
                    "definition": (
                        "Research-only overlay: estimate idle capital as "
                        "1 - active_position_count*20%, then apply a fraction "
                        "of that idle capital to QQQ close-to-close returns when "
                        "QQQ is >5% above its 200dma, QQQ 10d momentum exceeds "
                        "the variant threshold, and QQQ 10d momentum exceeds SPY."
                    ),
                    "parity_warning": (
                        "This does not yet model production fills, financing, "
                        "or a real overlay ledger. Positive results require a "
                        "follow-up implementation experiment."
                    ),
                },
                "variants": VARIANTS,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
