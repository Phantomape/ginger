"""exp-20260720-004: entry-time cross-source slot arbitration, observed-only.

Observed-only attribution on already-settled artifacts. For every same-day
entry-slot conflict where an accepted default-off sleeve generated a candidate
on the exact date the cash-feasible champion executed a core entry, compare the
sleeve candidate's settled net return against a matched-horizon counterfactual
of the displaced core ticker over the sleeve's own entry/exit window.

No strategy, order, ranking, or sizing behavior changes. Reads committed
replay artifacts and warehouse OHLCV only.

Decision unit: one (window, core entry date, sleeve source) pair. Micro rows
(sleeve row x same-date core ticker) are averaged into their pair so multi-pick
sleeve days and multi-entry core days do not multiply evidence.

Acceptance rule (fixed at reserve time): lead only if mean AND median pair
replacement value are positive, at least 2 of 3 windows have positive mean,
and the max single-pair share of aggregate positive replacement value is
<= 50%. Otherwise rejected; the arbitration lane parks with a quantitative
forward-conflict reopen count.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260720-004"
RULE_VERSION = "entry_time_cross_source_slot_arbitration_matched_horizon_replacement_value_v1"
ROUND_TRIP_COST = 0.0035

CORE_WINDOWS = {
    "old_thin": REPO / "data/backtests/cash_feasible_20260715/old_thin_exp-20260715-010.json",
    "mid_weak": REPO / "data/backtests/cash_feasible_20260715/mid_weak_exp-20260715-010.json",
    "late_strong": REPO / "data/backtests/cash_feasible_20260715/late_strong_exp-20260715-010.json",
}

SLEEVE_ARTIFACTS = {
    "sbc_burden_improvement": REPO
    / "data/experiments/exp-20260616-015/exp_20260616_015_sbc_burden_improvement_shared_adapter.json",
    "supplier_financing_debt_relief": REPO
    / "data/experiments/exp-20260620-009/exp_20260620_009_supplier_financing_debt_relief_shared_4k_risk_scaled_adapter.json",
    "distribution_day_absorption": REPO
    / "data/experiments/exp-20260611-007/exp_20260611_007_distribution_day_absorption_shared_adapter.json",
    "move_rate_volatility_relief": REPO
    / "data/experiments/exp-20260711-004/exp_20260711_004_move_rate_volatility_relief_shared_paper.json",
}

WAREHOUSE = REPO / "data/warehouse/warehouse_main.sqlite"

OUT_DIR = REPO / "data/experiments" / EXPERIMENT_ID
OUT_PATH = OUT_DIR / "exp_20260720_004_cross_source_slot_arbitration_observed_only.json"


def load_core_entries() -> dict:
    """window -> entry_date -> [ticker, ...] from champion trade keys."""
    out = {}
    for window, path in CORE_WINDOWS.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        per_date = {}
        for trade in payload["trades"]:
            ticker, entry_date, _ = trade["trade_key"].split(":")
            per_date.setdefault(entry_date, []).append(ticker)
        out[window] = per_date
    return out


def load_sleeve_rows() -> dict:
    """window -> sleeve -> entry_date -> [row, ...]."""
    out = {}
    for sleeve, path in SLEEVE_ARTIFACTS.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_window = payload["target_trades_by_window"]
        for window, rows in by_window.items():
            for row in rows:
                entry_date = row.get("entry_date")
                if not entry_date:
                    continue
                out.setdefault(window, {}).setdefault(sleeve, {}).setdefault(
                    entry_date, []
                ).append(row)
    return out


class PriceReader:
    def __init__(self, db_path: Path):
        self.con = sqlite3.connect(str(db_path))

    def bar(self, ticker: str, date: str):
        row = self.con.execute(
            "select open, close from ohlcv where ticker=? and date=?",
            (ticker, date),
        ).fetchone()
        return row

    def window_return(self, ticker: str, entry_date: str, exit_date: str):
        """Next-open-to-close return over [entry_date open, exit_date close]."""
        entry = self.bar(ticker, entry_date)
        exit_ = self.bar(ticker, exit_date)
        if entry is None or exit_ is None:
            return None
        entry_open, _ = entry
        _, exit_close = exit_
        if not entry_open or not exit_close:
            return None
        return exit_close / entry_open - 1.0


def sleeve_row_ticker(row: dict) -> str:
    ticker = row.get("ticker")
    if ticker:
        return ticker
    decision_id = row.get("decision_id", "")
    parts = decision_id.split(":")
    return parts[3] if len(parts) >= 4 else "?"


def sleeve_row_return(row: dict):
    for key in ("pnl_pct_net", "net_return_pct"):
        value = row.get(key)
        if value is not None:
            return float(value)
    return None


def main() -> dict:
    core = load_core_entries()
    sleeves = load_sleeve_rows()
    prices = PriceReader(WAREHOUSE)

    pairs = []
    excluded = []
    for window, core_dates in core.items():
        sleeve_map = sleeves.get(window, {})
        for entry_date, core_tickers in sorted(core_dates.items()):
            for sleeve, sleeve_dates in sleeve_map.items():
                rows = sleeve_dates.get(entry_date)
                if not rows:
                    continue
                micro = []
                for row in rows:
                    s_ret = sleeve_row_return(row)
                    exit_date = row.get("exit_date")
                    if s_ret is None or not exit_date:
                        excluded.append(
                            {
                                "window": window,
                                "entry_date": entry_date,
                                "sleeve": sleeve,
                                "reason": "sleeve_row_missing_return_or_exit_date",
                                "sleeve_ticker": sleeve_row_ticker(row),
                            }
                        )
                        continue
                    spy_gross = prices.window_return("SPY", entry_date, exit_date)
                    for core_ticker in core_tickers:
                        c_gross = prices.window_return(core_ticker, entry_date, exit_date)
                        if c_gross is None:
                            excluded.append(
                                {
                                    "window": window,
                                    "entry_date": entry_date,
                                    "sleeve": sleeve,
                                    "reason": "core_counterfactual_price_missing",
                                    "core_ticker": core_ticker,
                                    "exit_date": exit_date,
                                }
                            )
                            continue
                        micro.append(
                            {
                                "sleeve_ticker": sleeve_row_ticker(row),
                                "core_ticker": core_ticker,
                                "exit_date": exit_date,
                                "hold_days": row.get("hold_days"),
                                "sleeve_net_return": s_ret,
                                "core_matched_net_return": c_gross - ROUND_TRIP_COST,
                                "spy_matched_net_return": (
                                    spy_gross - ROUND_TRIP_COST
                                    if spy_gross is not None
                                    else None
                                ),
                            }
                        )
                if not micro:
                    continue
                sleeve_ret = statistics.mean(m["sleeve_net_return"] for m in micro)
                core_ret = statistics.mean(m["core_matched_net_return"] for m in micro)
                spy_vals = [
                    m["spy_matched_net_return"]
                    for m in micro
                    if m["spy_matched_net_return"] is not None
                ]
                pairs.append(
                    {
                        "window": window,
                        "entry_date": entry_date,
                        "sleeve": sleeve,
                        "micro_rows": micro,
                        "sleeve_net_return": sleeve_ret,
                        "core_matched_net_return": core_ret,
                        "spy_matched_net_return": (
                            statistics.mean(spy_vals) if spy_vals else None
                        ),
                        "replacement_value": sleeve_ret - core_ret,
                    }
                )

    replacement = [p["replacement_value"] for p in pairs]
    by_window = {}
    for window in CORE_WINDOWS:
        vals = [p["replacement_value"] for p in pairs if p["window"] == window]
        by_window[window] = {
            "pair_count": len(vals),
            "mean_replacement_value": statistics.mean(vals) if vals else None,
            "median_replacement_value": statistics.median(vals) if vals else None,
        }

    positive_total = sum(v for v in replacement if v > 0)
    max_positive_share = (
        max((v for v in replacement if v > 0), default=0.0) / positive_total
        if positive_total > 0
        else None
    )

    mean_rv = statistics.mean(replacement) if replacement else None
    median_rv = statistics.median(replacement) if replacement else None
    windows_positive = sum(
        1
        for w in by_window.values()
        if w["mean_replacement_value"] is not None and w["mean_replacement_value"] > 0
    )

    lead = (
        mean_rv is not None
        and mean_rv > 0
        and median_rv > 0
        and windows_positive >= 2
        and (max_positive_share is None or max_positive_share <= 0.5)
    )

    sleeve_means = {}
    for sleeve in SLEEVE_ARTIFACTS:
        vals = [p["replacement_value"] for p in pairs if p["sleeve"] == sleeve]
        sleeve_means[sleeve] = {
            "pair_count": len(vals),
            "mean_replacement_value": statistics.mean(vals) if vals else None,
        }

    result = {
        "experiment_id": EXPERIMENT_ID,
        "rule_version": RULE_VERSION,
        "change_type": "observed_only_attribution",
        "alters_orders": False,
        "trade_enabled": False,
        "round_trip_cost_applied_to_counterfactuals": ROUND_TRIP_COST,
        "core_source": {
            window: str(path.relative_to(REPO)) for window, path in CORE_WINDOWS.items()
        },
        "sleeve_sources": {
            sleeve: str(path.relative_to(REPO))
            for sleeve, path in SLEEVE_ARTIFACTS.items()
        },
        "pair_count": len(pairs),
        "excluded_rows": excluded,
        "aggregate": {
            "mean_replacement_value": mean_rv,
            "median_replacement_value": median_rv,
            "windows_with_positive_mean": windows_positive,
            "max_single_pair_share_of_positive": max_positive_share,
            "mean_sleeve_net_return": (
                statistics.mean(p["sleeve_net_return"] for p in pairs) if pairs else None
            ),
            "mean_core_matched_net_return": (
                statistics.mean(p["core_matched_net_return"] for p in pairs)
                if pairs
                else None
            ),
            "mean_spy_matched_net_return": (
                statistics.mean(
                    p["spy_matched_net_return"]
                    for p in pairs
                    if p["spy_matched_net_return"] is not None
                )
                if pairs
                else None
            ),
        },
        "by_window": by_window,
        "by_sleeve": sleeve_means,
        "pairs": pairs,
        "acceptance_rule": (
            "Lead only if mean AND median matched-horizon replacement value are "
            "positive, at least 2 of 3 windows have positive mean, and max "
            "single-pair share of aggregate positive replacement value <=50%."
        ),
        "verdict": "lead_cross_source_slot_arbitration" if lead else "observed_only_rejected",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=False), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    summary = main()
    print(json.dumps({k: summary[k] for k in ("pair_count", "aggregate", "by_window", "by_sleeve", "verdict")}, indent=2))
    print(f"excluded: {len(summary['excluded_rows'])}")
    print(f"artifact: {OUT_PATH}")
