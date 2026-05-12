"""Observed-only entry-day adverse tape taxonomy for exp-20260512-102.

This runner does not change strategy behavior. It reads the accepted late
window backtest artifact and classifies already-executed trades by one
ex-post context variable: whether SPY and/or a sector proxy weakened on the
entry day after the simulated open fill.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260512-102"
ROOT = Path(__file__).resolve().parents[2]
BACKTEST_PATH = ROOT / "data" / "backtest_results_20260510.json"
SNAPSHOT_PATH = ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json"
OUT_PATH = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260512_102_entry_day_adverse_tape_taxonomy.json"
)

SECTOR_PROXY = {
    "Commodities": "GLD",
    "Communication Services": "QQQ",
    "Consumer Discretionary": "QQQ",
    "Energy": "XLE",
    "Financials": "SPY",
    "Healthcare": "XLV",
    "Industrials": "SPY",
    "Technology": "QQQ",
}


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    return _round(value)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_by_date(snapshot: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    ohlcv = snapshot.get("ohlcv", snapshot)
    return {
        ticker: {str(row.get("Date")): row for row in rows}
        for ticker, rows in ohlcv.items()
        if isinstance(rows, list)
    }


def _open_close_return(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    open_price = row.get("Open")
    close_price = row.get("Close")
    if open_price in (None, 0) or close_price is None:
        return None
    return float(close_price) / float(open_price) - 1.0


def _summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(trades)
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] < 0]
    total_pnl = sum(t["pnl"] for t in trades)
    loss_abs = -sum(t["pnl"] for t in losers)
    winner_pnl = sum(t["pnl"] for t in winners)
    return {
        "count": count,
        "winner_count": len(winners),
        "loser_count": len(losers),
        "win_rate": (len(winners) / count) if count else None,
        "total_pnl": total_pnl,
        "avg_pnl": (total_pnl / count) if count else None,
        "loss_abs": loss_abs,
        "winner_pnl": winner_pnl,
        "worst_pnl": min((t["pnl"] for t in trades), default=0.0),
    }


def _bucket(spy_ret: float | None, sector_ret: float | None) -> str:
    if spy_ret is None or sector_ret is None:
        return "missing_tape"
    if spy_ret < 0 and sector_ret < 0:
        return "spy_and_sector_negative"
    if spy_ret < 0:
        return "spy_negative_only"
    if sector_ret < 0:
        return "sector_negative_only"
    return "both_non_negative"


def _threshold_flags(spy_ret: float | None, sector_ret: float | None) -> list[str]:
    flags: list[str] = []
    if spy_ret is None or sector_ret is None:
        return ["missing_tape"]
    for threshold in (0.0, -0.005, -0.01):
        suffix = str(abs(threshold)).replace(".", "p")
        if spy_ret <= threshold:
            flags.append(f"spy_le_{suffix}")
        if sector_ret <= threshold:
            flags.append(f"sector_le_{suffix}")
        if spy_ret <= threshold and sector_ret <= threshold:
            flags.append(f"spy_and_sector_le_{suffix}")
    return flags


def _annotate_trades(
    trades: list[dict[str, Any]],
    market_rows: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    annotated = []
    for trade in trades:
        entry_date = str(trade.get("entry_date"))
        sector = str(trade.get("sector") or "Unknown")
        proxy = SECTOR_PROXY.get(sector, "SPY")
        spy_ret = _open_close_return(market_rows.get("SPY", {}).get(entry_date))
        proxy_ret = _open_close_return(market_rows.get(proxy, {}).get(entry_date))
        ticker_ret = _open_close_return(
            market_rows.get(str(trade.get("ticker")), {}).get(entry_date)
        )
        out = {
            "trade_key": trade.get("trade_key"),
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "sector": sector,
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": float(trade.get("pnl") or 0.0),
            "pnl_pct_net": float(trade.get("pnl_pct_net") or 0.0),
            "shares": trade.get("shares"),
            "actual_risk_pct": trade.get("actual_risk_pct"),
            "regime_exit_bucket": trade.get("regime_exit_bucket"),
            "regime_exit_score": trade.get("regime_exit_score"),
            "sector_proxy": proxy,
            "entry_day_spy_open_close_return": spy_ret,
            "entry_day_sector_proxy_open_close_return": proxy_ret,
            "entry_day_ticker_open_close_return": ticker_ret,
            "entry_day_tape_bucket": _bucket(spy_ret, proxy_ret),
            "entry_day_tape_flags": _threshold_flags(spy_ret, proxy_ret),
        }
        annotated.append(out)
    return annotated


def _group_by(trades: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(key))].append(trade)
    return {name: _summary(rows) for name, rows in sorted(grouped.items())}


def _flag_summary(trades: list[dict[str, Any]], total_loss_abs: float) -> dict[str, Any]:
    flags = sorted({flag for trade in trades for flag in trade["entry_day_tape_flags"]})
    out = {}
    for flag in flags:
        exposed = [t for t in trades if flag in t["entry_day_tape_flags"]]
        bad = [t for t in exposed if t["pnl"] < 0]
        good = [t for t in exposed if t["pnl"] > 0]
        bad_summary = _summary(bad)
        good_summary = _summary(good)
        out[flag] = {
            "exposed": _summary(exposed),
            "bad_slice": bad_summary,
            "good_trade_collateral_if_naive_filter": good_summary,
            "tail_loss_share_of_all_losses": (
                bad_summary["loss_abs"] / total_loss_abs if total_loss_abs else None
            ),
            "naive_filter_net_after_collateral": -(
                bad_summary["loss_abs"] + good_summary["winner_pnl"]
            ),
            "future_fix_would_likely_kill": {
                "winner_count": good_summary["winner_count"],
                "winner_pnl": good_summary["winner_pnl"],
                "note": "This is collateral from a naive rule using the observed flag; it is not a recommendation to filter.",
            },
        }
    return out


def main() -> None:
    backtest = _load_json(BACKTEST_PATH)
    snapshot = _load_json(SNAPSHOT_PATH)
    market_rows = _rows_by_date(snapshot)
    trades = _annotate_trades(backtest.get("trades") or [], market_rows)
    losers = [trade for trade in trades if trade["pnl"] < 0]
    total_loss_abs = -sum(trade["pnl"] for trade in losers)
    tail_n = max(1, math.ceil(len(losers) * 0.2)) if losers else 0
    tail_trades = sorted(losers, key=lambda trade: trade["pnl"])[:tail_n]

    primary_family = [
        trade for trade in trades if "sector_le_0p01" in trade["entry_day_tape_flags"]
    ]
    primary_bad = [trade for trade in primary_family if trade["pnl"] < 0]
    primary_good = [trade for trade in primary_family if trade["pnl"] > 0]

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "observed_only",
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "entry-day adverse tape taxonomy",
        "hypothesis": (
            "Accepted-stack bad trades in the late window may concentrate in an "
            "entry-day adverse tape family where SPY and/or the relevant sector "
            "proxy are already negative on the execution day."
        ),
        "backtest_protocol": {
            "window": "late_strong",
            "start": "2025-10-23",
            "end": "2026-04-21",
            "baseline_result_file": str(BACKTEST_PATH.relative_to(ROOT)),
            "snapshot": str(SNAPSHOT_PATH.relative_to(ROOT)),
        },
        "expected_value_score": backtest.get("expected_value_score"),
        "sharpe": backtest.get("sharpe"),
        "sharpe_daily": backtest.get("sharpe_daily"),
        "max_drawdown_pct": backtest.get("max_drawdown_pct"),
        "win_rate": backtest.get("win_rate"),
        "total_trades": backtest.get("total_trades"),
        "survival_rate": backtest.get("survival_rate"),
        "total_pnl": backtest.get("total_pnl"),
        "benchmarks": backtest.get("benchmarks") or {},
        "baseline_metrics": {
            "expected_value_score": backtest.get("expected_value_score"),
            "sharpe_daily": backtest.get("sharpe_daily"),
            "total_pnl": backtest.get("total_pnl"),
            "max_drawdown_pct": backtest.get("max_drawdown_pct"),
            "win_rate": backtest.get("win_rate"),
            "trade_count": backtest.get("total_trades"),
            "signals_generated": backtest.get("signals_generated"),
            "signals_survived": backtest.get("signals_survived"),
            "survival_rate": backtest.get("survival_rate"),
            "tail_loss_share": backtest.get("tail_loss_share"),
            "worst_trade_pct": backtest.get("worst_trade_pct"),
        },
        "sector_proxy_map": SECTOR_PROXY,
        "trade_summary": _summary(trades),
        "bad_trade_summary": _summary(losers),
        "entry_day_tape_bucket_summary": _group_by(trades, "entry_day_tape_bucket"),
        "entry_day_tape_flag_summary": _flag_summary(trades, total_loss_abs),
        "primary_family": {
            "definition": "Sector proxy had an entry-day open-to-close return <= -1%; SPY condition is not required.",
            "exposed": _summary(primary_family),
            "bad_slice": _summary(primary_bad),
            "good_trade_collateral_if_naive_filter": _summary(primary_good),
            "tail_loss_share_of_all_losses": (
                _summary(primary_bad)["loss_abs"] / total_loss_abs
                if total_loss_abs
                else None
            ),
            "overlap_with_tail_losses": {
                "tail_n": tail_n,
                "tail_trade_count_in_family": sum(
                    1
                    for trade in tail_trades
                    if "sector_le_0p01" in trade["entry_day_tape_flags"]
                ),
                "tail_loss_abs_in_family": -sum(
                    trade["pnl"]
                    for trade in tail_trades
                    if "sector_le_0p01" in trade["entry_day_tape_flags"]
                ),
            },
            "worst_bad_examples": sorted(primary_bad, key=lambda trade: trade["pnl"])[:5],
        },
        "tail_summary": {
            "loser_count": len(losers),
            "tail_n": tail_n,
            "total_loss_abs": total_loss_abs,
            "tail_loss_abs": -sum(trade["pnl"] for trade in tail_trades),
            "tail_loss_share": (
                -sum(trade["pnl"] for trade in tail_trades) / total_loss_abs
                if total_loss_abs
                else None
            ),
            "worst_trades": tail_trades,
        },
        "observed_future_candidate": {
            "candidate": "entry-day adverse tape hold-quality shadow triage",
            "why": (
                "The valid next test would be a forward/shadow attribution of "
                "whether adverse entry-day benchmark and sector proxy action "
                "predicts poor hold quality after the fill, not a same-sample "
                "entry filter."
            ),
            "must_measure_before_strategy_change": [
                "next-day or day-2 reclaim rate",
                "winner collateral from adverse-tape winners",
                "same-day replacement candidates",
                "news/event context for market-wide selloff days",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "decision": "observed_only",
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(_safe(artifact), indent=2), encoding="utf-8")
    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(OUT_PATH.relative_to(ROOT)),
        "primary_family": artifact["primary_family"],
        "decision": "observed_only",
    }), indent=2))


if __name__ == "__main__":
    main()
