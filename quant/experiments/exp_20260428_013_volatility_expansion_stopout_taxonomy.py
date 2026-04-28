"""exp-20260428-013: post-entry volatility expansion stopout taxonomy.

Observed-only loss attribution runner. It changes no production strategy
behavior and only writes the experiment artifact declared in the ticket.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-013"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_013_volatility_expansion_stopout_taxonomy.json"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "regime": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "regime": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "regime": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

PRE_ENTRY_RANGE_DAYS = 10
MIN_HOLD_AVG_RANGE_EXPANSION = 1.5
MIN_MAX_RANGE_EXPANSION = 2.0
MIN_MFE_PCT_TO_AVOID_LOW_MFE_REPEAT = 0.01
MAX_MFE_R = 1.0


def _safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None or not isinstance(value, (int, float)) or math.isnan(value):
        return None
    return round(float(value), digits)


def _safe_mean(values: list[float]) -> float | None:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return mean(clean) if clean else None


def _safe_median(values: list[float]) -> float | None:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return median(clean) if clean else None


def _load_frames(snapshot_path: str) -> dict[str, pd.DataFrame]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8"))
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _range_pct(row: pd.Series) -> float | None:
    close = row.get("Close")
    high = row.get("High")
    low = row.get("Low")
    if not all(isinstance(v, (int, float)) for v in [close, high, low]) or close == 0:
        return None
    return float(high - low) / float(close)


def _trade_features(trade: dict, df: pd.DataFrame) -> dict:
    entry_date = pd.Timestamp(trade["entry_date"])
    exit_date = pd.Timestamp(trade["exit_date"])
    if entry_date not in df.index or exit_date not in df.index:
        return {"feature_status": "missing_trade_dates"}

    entry_loc = int(df.index.get_loc(entry_date))
    exit_loc = int(df.index.get_loc(exit_date))
    if entry_loc < PRE_ENTRY_RANGE_DAYS:
        return {"feature_status": "insufficient_pre_entry_history"}

    pre_rows = df.iloc[entry_loc - PRE_ENTRY_RANGE_DAYS : entry_loc]
    hold_rows = df.iloc[min(entry_loc, exit_loc) : max(entry_loc, exit_loc) + 1]
    pre_ranges = [v for v in (_range_pct(row) for _, row in pre_rows.iterrows()) if v is not None]
    hold_ranges = [v for v in (_range_pct(row) for _, row in hold_rows.iterrows()) if v is not None]
    entry_price = trade.get("entry_price")
    stop_price = trade.get("stop_price")
    highs = [float(v) for v in hold_rows["High"].tolist() if isinstance(v, (int, float))]
    lows = [float(v) for v in hold_rows["Low"].tolist() if isinstance(v, (int, float))]
    if not pre_ranges or not hold_ranges or not isinstance(entry_price, (int, float)):
        return {"feature_status": "missing_price_path"}

    pre_avg = _safe_mean(pre_ranges)
    hold_avg = _safe_mean(hold_ranges)
    max_hold_range = max(hold_ranges)
    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    risk_pct = trade.get("initial_risk_pct")
    if not isinstance(risk_pct, (int, float)) and isinstance(stop_price, (int, float)):
        risk_pct = (entry_price - stop_price) / entry_price
    mfe_pct = ((max_high / entry_price) - 1) if max_high else None
    mae_pct = ((min_low / entry_price) - 1) if min_low else None
    mfe_r = mfe_pct / risk_pct if mfe_pct is not None and risk_pct else None
    hold_avg_expansion = hold_avg / pre_avg if pre_avg else None
    max_range_expansion = max_hold_range / pre_avg if pre_avg else None

    is_family = (
        trade.get("exit_reason") == "stop"
        and isinstance(hold_avg_expansion, (int, float))
        and isinstance(max_range_expansion, (int, float))
        and isinstance(mfe_pct, (int, float))
        and isinstance(mfe_r, (int, float))
        and hold_avg_expansion >= MIN_HOLD_AVG_RANGE_EXPANSION
        and max_range_expansion >= MIN_MAX_RANGE_EXPANSION
        and mfe_pct >= MIN_MFE_PCT_TO_AVOID_LOW_MFE_REPEAT
        and mfe_r < MAX_MFE_R
    )
    collateral_match = (
        isinstance(hold_avg_expansion, (int, float))
        and isinstance(max_range_expansion, (int, float))
        and isinstance(mfe_pct, (int, float))
        and isinstance(mfe_r, (int, float))
        and hold_avg_expansion >= MIN_HOLD_AVG_RANGE_EXPANSION
        and max_range_expansion >= MIN_MAX_RANGE_EXPANSION
        and mfe_pct >= MIN_MFE_PCT_TO_AVOID_LOW_MFE_REPEAT
        and mfe_r < MAX_MFE_R
    )

    return {
        "feature_status": "ok",
        "pre_entry_avg_range_pct": _safe_round(pre_avg),
        "hold_avg_range_pct": _safe_round(hold_avg),
        "hold_max_range_pct": _safe_round(max_hold_range),
        "hold_avg_range_expansion": _safe_round(hold_avg_expansion),
        "hold_max_range_expansion": _safe_round(max_range_expansion),
        "mfe_pct": _safe_round(mfe_pct),
        "mae_pct": _safe_round(mae_pct),
        "mfe_r": _safe_round(mfe_r),
        "holding_days": int(len(hold_rows)),
        "volatility_expansion_stopout_family": bool(is_family),
        "oracle_collateral_match": bool(collateral_match),
    }


def _summarize(rows: list[dict]) -> dict:
    pnl = [float(r["pnl"]) for r in rows]
    return {
        "count": len(rows),
        "pnl_sum": _safe_round(sum(pnl), 2) if pnl else 0,
        "avg_pnl": _safe_round(_safe_mean(pnl), 2),
        "median_pnl": _safe_round(_safe_median(pnl), 2),
        "window_counts": dict(Counter(r["window"] for r in rows)),
        "strategy_counts": dict(Counter(r.get("strategy") for r in rows)),
        "sector_counts": dict(Counter(r.get("sector") for r in rows)),
        "tickers": sorted(set(r.get("ticker") for r in rows)),
    }


def _bucketize(rows: list[dict]) -> dict:
    buckets = OrderedDict(
        [
            ("avg_expansion_gte_1_25", []),
            ("avg_expansion_gte_1_50", []),
            ("max_expansion_gte_2_00", []),
            ("mfe_between_1pct_and_1r", []),
            ("all_except_mfe_floor", []),
            ("all_except_avg_expansion", []),
        ]
    )
    for row in rows:
        avg_exp = row.get("hold_avg_range_expansion")
        max_exp = row.get("hold_max_range_expansion")
        mfe_pct = row.get("mfe_pct")
        mfe_r = row.get("mfe_r")
        if isinstance(avg_exp, (int, float)) and avg_exp >= 1.25:
            buckets["avg_expansion_gte_1_25"].append(row)
        if isinstance(avg_exp, (int, float)) and avg_exp >= 1.50:
            buckets["avg_expansion_gte_1_50"].append(row)
        if isinstance(max_exp, (int, float)) and max_exp >= 2.00:
            buckets["max_expansion_gte_2_00"].append(row)
        if (
            isinstance(mfe_pct, (int, float))
            and isinstance(mfe_r, (int, float))
            and mfe_pct >= 0.01
            and mfe_r < 1.0
        ):
            buckets["mfe_between_1pct_and_1r"].append(row)
        if (
            isinstance(avg_exp, (int, float))
            and isinstance(max_exp, (int, float))
            and isinstance(mfe_r, (int, float))
            and avg_exp >= MIN_HOLD_AVG_RANGE_EXPANSION
            and max_exp >= MIN_MAX_RANGE_EXPANSION
            and mfe_r < MAX_MFE_R
        ):
            buckets["all_except_mfe_floor"].append(row)
        if (
            isinstance(max_exp, (int, float))
            and isinstance(mfe_pct, (int, float))
            and isinstance(mfe_r, (int, float))
            and max_exp >= MIN_MAX_RANGE_EXPANSION
            and mfe_pct >= MIN_MFE_PCT_TO_AVOID_LOW_MFE_REPEAT
            and mfe_r < MAX_MFE_R
        ):
            buckets["all_except_avg_expansion"].append(row)
    return {
        name: {
            "count": len(members),
            "loss_pnl_abs": _safe_round(sum(abs(float(r["pnl"])) for r in members), 2),
            "summary": _summarize(members),
        }
        for name, members in buckets.items()
    }


def _tail_losses(loss_rows: list[dict]) -> list[dict]:
    if not loss_rows:
        return []
    losses = sorted(loss_rows, key=lambda r: r["pnl"])
    n = max(1, math.ceil(len(losses) * 0.25))
    return losses[:n]


def run() -> dict:
    universe = get_universe()
    all_trades = []
    window_results = {}

    for window_name, spec in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        ).run()
        frames = _load_frames(spec["snapshot"])
        window_results[window_name] = {
            "range": {"start": spec["start"], "end": spec["end"]},
            "regime": spec["regime"],
            "metrics": _metrics(result),
        }
        for trade in result.get("trades") or []:
            df = frames.get(str(trade.get("ticker", "")).upper())
            features = _trade_features(trade, df) if df is not None else {"feature_status": "missing_ticker_frame"}
            all_trades.append({**trade, **features, "window": window_name})

    losses = [t for t in all_trades if t.get("pnl", 0) < 0]
    winners = [t for t in all_trades if t.get("pnl", 0) > 0]
    family_losses = [t for t in losses if t.get("volatility_expansion_stopout_family")]
    collateral_winners = [t for t in winners if t.get("oracle_collateral_match")]
    tail = _tail_losses(losses)
    tail_family = [t for t in tail if t.get("volatility_expansion_stopout_family")]
    total_loss_abs = sum(abs(float(t["pnl"])) for t in losses)
    family_loss_abs = sum(abs(float(t["pnl"])) for t in family_losses)
    tail_loss_abs = sum(abs(float(t["pnl"])) for t in tail)
    tail_family_abs = sum(abs(float(t["pnl"])) for t in tail_family)
    collateral_pnl = sum(float(t["pnl"]) for t in collateral_winners)

    rows_for_artifact = []
    for trade in family_losses + collateral_winners:
        rows_for_artifact.append(
            {
                key: trade.get(key)
                for key in [
                    "window",
                    "ticker",
                    "strategy",
                    "sector",
                    "entry_date",
                    "exit_date",
                    "exit_reason",
                    "pnl",
                    "pnl_pct_net",
                    "initial_risk_pct",
                    "holding_days",
                    "pre_entry_avg_range_pct",
                    "hold_avg_range_pct",
                    "hold_max_range_pct",
                    "hold_avg_range_expansion",
                    "hold_max_range_expansion",
                    "mfe_pct",
                    "mae_pct",
                    "mfe_r",
                    "volatility_expansion_stopout_family",
                    "oracle_collateral_match",
                ]
            }
        )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "post-entry volatility expansion stopout taxonomy",
        "strategy_behavior_changed": False,
        "history_guardrails": {
            "does_not_add_filter": True,
            "does_not_change_strategy_logic": True,
            "distinct_from_low_mfe": "requires MFE >= +1% and MFE < 1R, so it is not the zero-MFE stopout family",
            "distinct_from_gap_down": "uses high-low range expansion, not overnight gap",
            "distinct_from_extension": "uses post-entry realized range, not pre-entry extension or next-day followthrough",
        },
        "taxonomy_definition": {
            "name": "post_entry_volatility_expansion_stopout",
            "criteria": {
                "exit_reason": "stop",
                "hold_avg_range_expansion_gte": MIN_HOLD_AVG_RANGE_EXPANSION,
                "hold_max_range_expansion_gte": MIN_MAX_RANGE_EXPANSION,
                "mfe_pct_gte": MIN_MFE_PCT_TO_AVOID_LOW_MFE_REPEAT,
                "mfe_r_lt": MAX_MFE_R,
                "pre_entry_range_days": PRE_ENTRY_RANGE_DAYS,
            },
            "interpretation": "The trade made some progress, but post-entry realized range expanded sharply before it ever earned 1R; future fixes should be lifecycle sizing/monitoring candidates, not entry filters.",
        },
        "windows": window_results,
        "aggregate": {
            "trade_count": len(all_trades),
            "loss_count": len(losses),
            "win_count": len(winners),
            "total_loss_abs": _safe_round(total_loss_abs, 2),
            "family_loss_count": len(family_losses),
            "family_loss_abs": _safe_round(family_loss_abs, 2),
            "family_loss_frequency_share": _safe_round(len(family_losses) / len(losses) if losses else None, 4),
            "family_loss_dollar_share": _safe_round(family_loss_abs / total_loss_abs if total_loss_abs else None, 4),
            "tail_loss_count": len(tail),
            "tail_loss_abs": _safe_round(tail_loss_abs, 2),
            "tail_family_count": len(tail_family),
            "tail_family_abs": _safe_round(tail_family_abs, 2),
            "tail_loss_share_explained": _safe_round(tail_family_abs / tail_loss_abs if tail_loss_abs else None, 4),
            "winner_collateral_count": len(collateral_winners),
            "winner_collateral_pnl": _safe_round(collateral_pnl, 2),
            "oracle_avoid_loss_minus_winner_collateral": _safe_round(family_loss_abs - collateral_pnl, 2),
        },
        "family_loss_summary": _summarize(family_losses),
        "winner_collateral_summary": _summarize(collateral_winners),
        "loss_sensitivity_diagnostics": _bucketize(losses),
        "future_candidate_fix_shape": {
            "candidate_type": "observed-only lifecycle risk monitor or position-size decay, not a hard entry filter",
            "why": "The condition is only knowable after entry and has measurable winner collateral, so direct veto would be an oracle rule.",
            "next_test": "Default-off replay that halves remaining risk only after two in-position days with range expansion >=1.5x and MFE <1R, then compare with winner collateral.",
            "risk": "May cut noisy eventual winners before target, especially in trend regimes with volatility expansion that resolves upward.",
        },
        "audit_rows": rows_for_artifact,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(OUT_JSON),
        "aggregate": result["aggregate"],
    }, indent=2))
