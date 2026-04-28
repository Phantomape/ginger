"""exp-20260427-020: entry extension + weak follow-through audit.

This observed-only runner changes no production behavior. It tests whether the
entry-extension family from exp-20260427-015 becomes more useful when combined
with weak post-entry follow-through, while measuring winner collateral.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from statistics import mean


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
QUANT_DIR = os.path.join(ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260427-020"
OUT_DIR = os.path.join(ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(
    OUT_DIR,
    "exp_20260427_020_extension_weak_followthrough_audit.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20251023_20260421.json"),
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20250423_20251022.json"),
        "regime": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"),
        "regime": "mixed-to-weak older tape with lower win rate",
    }),
])


def load_snapshot(path: str) -> dict[str, list[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload["ohlcv"]


def _pct(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return (num / den) - 1


def _round(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if isinstance(value, (int, float)) else None


def _ticker_rows(snapshot: dict[str, list[dict]], ticker: str) -> list[dict]:
    return snapshot.get(ticker) or []


def _index_by_date(rows: list[dict]) -> dict[str, int]:
    return {row["Date"]: idx for idx, row in enumerate(rows)}


def _extension_features(rows: list[dict], entry_idx: int) -> dict:
    signal_idx = entry_idx - 1
    if signal_idx < 20:
        return {"data_status": "insufficient_history"}
    signal = rows[signal_idx]
    close = signal.get("Close")
    prior_5 = rows[signal_idx - 5].get("Close")
    prior_10 = rows[signal_idx - 10].get("Close")
    closes_10 = [row.get("Close") for row in rows[signal_idx - 9: signal_idx + 1]]
    closes_20 = [row.get("Close") for row in rows[signal_idx - 19: signal_idx + 1]]
    closes_10 = [v for v in closes_10 if isinstance(v, (int, float))]
    closes_20 = [v for v in closes_20 if isinstance(v, (int, float))]
    sma10 = mean(closes_10) if len(closes_10) == 10 else None
    sma20 = mean(closes_20) if len(closes_20) == 20 else None
    high20 = max(row.get("High") for row in rows[signal_idx - 19: signal_idx + 1])
    low20 = min(row.get("Low") for row in rows[signal_idx - 19: signal_idx + 1])
    range_pos_20d = (close - low20) / (high20 - low20) if high20 > low20 else None
    prior_5d_return = _pct(close, prior_5)
    prior_10d_return = _pct(close, prior_10)
    close_vs_sma10 = _pct(close, sma10)
    close_vs_sma20 = _pct(close, sma20)
    flags = {
        "entry_ge_12pct_prior_10d": (prior_10d_return or 0) >= 0.12,
        "entry_ge_8pct_above_sma20": (close_vs_sma20 or 0) >= 0.08,
        "entry_top_5pct_20d_and_above_sma10": (
            (range_pos_20d or 0) >= 0.95 and (close_vs_sma10 or 0) >= 0.04
        ),
    }
    return {
        "data_status": "ok",
        "signal_date": signal.get("Date"),
        "signal_close": close,
        "prior_5d_return": _round(prior_5d_return),
        "prior_10d_return": _round(prior_10d_return),
        "close_vs_sma10": _round(close_vs_sma10),
        "close_vs_sma20": _round(close_vs_sma20),
        "range_pos_20d": _round(range_pos_20d),
        "extension_flags": flags,
        "extended_entry": any(flags.values()),
    }


def _followthrough_features(
    rows: list[dict],
    spy_rows: list[dict],
    entry_idx: int,
    entry_date: str,
) -> dict:
    spy_idx = _index_by_date(spy_rows).get(entry_date)
    if entry_idx + 1 >= len(rows) or spy_idx is None or spy_idx + 1 >= len(spy_rows):
        return {"followthrough_status": "insufficient_forward"}
    entry = rows[entry_idx]
    next_day = rows[entry_idx + 1]
    spy_entry = spy_rows[spy_idx]
    spy_next = spy_rows[spy_idx + 1]
    ticker_entry_day_return = _pct(entry.get("Close"), entry.get("Open"))
    ticker_next_close_return = _pct(next_day.get("Close"), entry.get("Open"))
    spy_next_close_return = _pct(spy_next.get("Close"), spy_entry.get("Open"))
    rs_vs_spy_next = (
        ticker_next_close_return - spy_next_close_return
        if ticker_next_close_return is not None and spy_next_close_return is not None
        else None
    )
    flags = {
        "entry_day_red": (ticker_entry_day_return or 0) < 0,
        "next_close_below_entry_open": (ticker_next_close_return or 0) < 0,
        "next_day_rs_vs_spy_negative": (rs_vs_spy_next or 0) < 0,
    }
    return {
        "followthrough_status": "ok",
        "entry_day_return": _round(ticker_entry_day_return),
        "next_close_return_from_entry_open": _round(ticker_next_close_return),
        "spy_next_close_return": _round(spy_next_close_return),
        "rs_vs_spy_next_close": _round(rs_vs_spy_next),
        "weak_followthrough_flags": flags,
        "weak_followthrough": any(flags.values()),
    }


def _run_window(label: str, cfg: dict, universe: list[str]) -> dict:
    engine = BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        ohlcv_snapshot_path=cfg["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label}: {result['error']}")
    snapshot = load_snapshot(cfg["snapshot"])
    spy_rows = _ticker_rows(snapshot, "SPY")
    rows = []
    for trade in result.get("trades", []):
        ticker = trade.get("ticker")
        entry_date = trade.get("entry_date")
        ticker_rows = _ticker_rows(snapshot, ticker)
        idx = _index_by_date(ticker_rows).get(entry_date)
        if idx is None:
            features = {"data_status": "missing_entry_date"}
            follow = {"followthrough_status": "missing_entry_date"}
        else:
            features = _extension_features(ticker_rows, idx)
            follow = _followthrough_features(ticker_rows, spy_rows, idx, entry_date)
        pnl = trade.get("pnl") or 0.0
        extended = bool(features.get("extended_entry"))
        weak = bool(follow.get("weak_followthrough"))
        rows.append({
            "window": label,
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
            "entry_date": entry_date,
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": round(pnl, 2),
            "pnl_pct_net": trade.get("pnl_pct_net"),
            "is_loss": pnl <= 0,
            "extended_entry": extended,
            "weak_followthrough": weak,
            "family_match": extended and weak and pnl <= 0,
            "winner_collateral_match": extended and weak and pnl > 0,
            "extension_features": features,
            "followthrough_features": follow,
        })
    return {
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_pnl": result.get("total_pnl"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "win_rate": result.get("win_rate"),
            "trade_count": result.get("total_trades"),
            "survival_rate": result.get("survival_rate"),
        },
        "rows": rows,
    }


def _summary(rows: list[dict]) -> dict:
    pnls = [row["pnl"] for row in rows]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2),
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "strategy_counts": dict(sorted(Counter(row.get("strategy") for row in rows).items())),
        "sector_counts": dict(sorted(Counter(row.get("sector") for row in rows).items())),
        "window_counts": dict(sorted(Counter(row.get("window") for row in rows).items())),
    }


def main() -> int:
    universe = get_universe()
    windows = OrderedDict()
    all_rows = []
    for label, cfg in WINDOWS.items():
        payload = _run_window(label, cfg, universe)
        windows[label] = {
            "range": {"start": cfg["start"], "end": cfg["end"]},
            "regime": cfg["regime"],
            "metrics": payload["metrics"],
            "trade_count": len(payload["rows"]),
        }
        all_rows.extend(payload["rows"])

    losses = [row for row in all_rows if row["is_loss"]]
    wins = [row for row in all_rows if not row["is_loss"]]
    family = [row for row in all_rows if row["family_match"]]
    collateral = [row for row in all_rows if row["winner_collateral_match"]]
    extended_losses = [row for row in losses if row["extended_entry"]]
    extended_collateral = [row for row in wins if row["extended_entry"]]

    family_loss_pnl = sum(row["pnl"] for row in family)
    collateral_pnl = sum(row["pnl"] for row in collateral)
    naive_net = abs(family_loss_pnl) - collateral_pnl
    decision_hint = (
        "candidate_for_replay"
        if family and naive_net > 0 and len(collateral) <= len(family)
        else "observed_only_do_not_promote"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "change_type": "ranking_rule_observed_audit",
        "single_causal_variable": "entry extension plus weak next-day follow-through ranking penalty",
        "strategy_behavior_changed": False,
        "windows": windows,
        "definition": {
            "extended_entry": "signal-day close >=8% above SMA20, or prior 10d return >=12%, or top 5% of 20d range while >=4% above SMA10",
            "weak_followthrough": "entry day red, or next close below entry open, or next close RS vs SPY < 0",
            "note": "Weak follow-through is observed after entry; this audit does not define a pre-entry production rule.",
        },
        "aggregate": {
            "trade_count": len(all_rows),
            "loss_count": len(losses),
            "win_count": len(wins),
            "extended_loss_count": len(extended_losses),
            "extended_winner_count": len(extended_collateral),
            "family_loss_count": len(family),
            "family_loss_coverage_rate": round(len(family) / len(losses), 4) if losses else None,
            "winner_collateral_count": len(collateral),
            "winner_collateral_rate": round(len(collateral) / len(wins), 4) if wins else None,
            "family_loss_pnl_that_rule_would_avoid": round(abs(family_loss_pnl), 2),
            "winner_pnl_at_risk": round(collateral_pnl, 2),
            "naive_net_pnl_delta_estimate": round(naive_net, 2),
            "decision_hint": decision_hint,
        },
        "family_summary": _summary(family),
        "winner_collateral_summary": _summary(collateral),
        "family_rows": family,
        "winner_collateral_rows": collateral,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(json.dumps(payload["aggregate"], indent=2))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
