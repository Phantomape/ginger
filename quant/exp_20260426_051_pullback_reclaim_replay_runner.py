"""exp-20260426-051 production-path replay for pullback reclaim continuation.

This is an experiment-only runner. It does not edit production strategy files.
The runner reuses the exp-20260426-047 shadow entry definition, injects the
candidate source at runtime, then lets the normal BacktestEngine apply risk
enrichment, sizing, sector caps, slot competition, next-open fills, and exits.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from statistics import mean


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402
import feature_layer as fl_module  # noqa: E402
import signal_engine as se_module  # noqa: E402


EXPERIMENT_ID = "exp-20260426-051"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_051_pullback_reclaim_replay_results.json",
)

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
FAST_MA_DAYS = 10
MID_MA_DAYS = 50
SLOW_MA_DAYS = 100
PULLBACK_LOOKBACK_DAYS = 10
RECENT_HIGH_LOOKBACK_DAYS = 20
MIN_PULLBACK_FROM_HIGH = -0.15
MAX_PULLBACK_FROM_HIGH = -0.03
MIN_CANDIDATE_RS_VS_SPY = 0.0
MIN_DOLLAR_VOLUME = 25_000_000
EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

_runtime = {
    "mode": "baseline_ab",
    "candidate_by_date": {},
    "candidate_count": 0,
    "signals_added": 0,
    "signals_blocked_duplicate": 0,
}


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
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    return None


def _series(snapshot: dict[str, list[dict]], ticker: str) -> list[dict]:
    return sorted(snapshot.get(ticker) or [], key=_date)


def _row_index(rows: list[dict]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows)}


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if isinstance(value, (int, float))]
    return mean(clean) if clean else None


def _moving_average(rows: list[dict], end_idx: int, days: int) -> float | None:
    if end_idx - days < 0:
        return None
    return _avg([_value(row, "Close") for row in rows[end_idx - days:end_idx]])


def _close_return(rows: list[dict], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _value(rows[start_idx], "Close")
    end_close = _value(rows[end_idx], "Close")
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _trading_dates(snapshot: dict[str, list[dict]]) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY")]


def _candidate_rows(snapshot: dict[str, list[dict]], ticker: str, dates: list[str]) -> list[dict]:
    rows = _series(snapshot, ticker)
    min_history = max(SLOW_MA_DAYS, RECENT_HIGH_LOOKBACK_DAYS, PULLBACK_LOOKBACK_DAYS) + 2
    if len(rows) < min_history:
        return []

    idx_by_date = _row_index(rows)
    spy_rows = _series(snapshot, "SPY")
    spy_idx_by_date = _row_index(spy_rows)
    out = []
    for date in dates:
        idx = idx_by_date.get(date)
        spy_idx = spy_idx_by_date.get(date)
        if idx is None or spy_idx is None or idx < min_history or spy_idx < 1:
            continue

        cur = rows[idx]
        prev = rows[idx - 1]
        cur_close = _value(cur, "Close")
        cur_volume = _value(cur, "Volume")
        prev_high = _value(prev, "High")
        prev_close = _value(prev, "Close")
        if None in (cur_close, cur_volume, prev_high, prev_close):
            continue
        dollar_volume = cur_close * cur_volume
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue

        fast_ma = _moving_average(rows, idx, FAST_MA_DAYS)
        mid_ma = _moving_average(rows, idx, MID_MA_DAYS)
        slow_ma = _moving_average(rows, idx, SLOW_MA_DAYS)
        prev_fast_ma = _moving_average(rows, idx - 1, FAST_MA_DAYS)
        if None in (fast_ma, mid_ma, slow_ma, prev_fast_ma):
            continue
        if not (cur_close > fast_ma and cur_close > mid_ma and mid_ma > slow_ma):
            continue

        recent_high_values = [
            value for value in (
                _value(row, "High")
                for row in rows[idx - RECENT_HIGH_LOOKBACK_DAYS:idx]
            )
            if value is not None
        ]
        if len(recent_high_values) < RECENT_HIGH_LOOKBACK_DAYS:
            continue
        recent_high = max(recent_high_values)
        if cur_close > recent_high:
            continue

        pullback_values = [
            value for value in (
                _value(row, "Close")
                for row in rows[idx - PULLBACK_LOOKBACK_DAYS:idx]
            )
            if value is not None
        ]
        if len(pullback_values) < PULLBACK_LOOKBACK_DAYS:
            continue
        pullback_from_high = (min(pullback_values) / recent_high) - 1.0
        if pullback_from_high < MIN_PULLBACK_FROM_HIGH:
            continue
        if pullback_from_high > MAX_PULLBACK_FROM_HIGH:
            continue

        dipped_below_fast_ma = any(
            (_value(rows[i], "Close") is not None)
            and (_moving_average(rows, i, FAST_MA_DAYS) is not None)
            and (_value(rows[i], "Close") < _moving_average(rows, i, FAST_MA_DAYS))
            for i in range(idx - PULLBACK_LOOKBACK_DAYS, idx)
        )
        if not dipped_below_fast_ma:
            continue
        if prev_close > prev_fast_ma and cur_close <= prev_high:
            continue

        candidate_ret = _close_return(rows, idx - 1, idx)
        spy_candidate_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
        if candidate_ret is None or spy_candidate_ret is None:
            continue
        rs_vs_spy = candidate_ret - spy_candidate_ret
        if rs_vs_spy <= MIN_CANDIDATE_RS_VS_SPY:
            continue

        out.append({
            "date": date,
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "close": round(cur_close, 4),
            "pullback_from_20d_high": round(pullback_from_high, 6),
            "pct_above_10d_ma": round((cur_close / fast_ma) - 1.0, 6),
            "pct_above_50d_ma": round((cur_close / mid_ma) - 1.0, 6),
            "candidate_day_return": round(candidate_ret, 6),
            "candidate_day_spy_return": round(spy_candidate_ret, 6),
            "candidate_day_rs_vs_spy": round(rs_vs_spy, 6),
            "dollar_volume": round(dollar_volume, 2),
        })
    return out


def _build_candidate_map(snapshot: dict[str, list[dict]], cfg: dict, universe: list[str]) -> dict[str, dict[str, dict]]:
    dates = [
        date for date in _trading_dates(snapshot)
        if cfg["start"] <= date <= cfg["end"]
    ]
    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in EXCLUDED_TICKERS:
            continue
        for row in _candidate_rows(snapshot, ticker, dates):
            by_date[row["date"]][ticker] = row
    return {date: dict(rows) for date, rows in by_date.items()}


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pullback_signal(ticker: str, features: dict, row: dict) -> dict | None:
    close = features.get("close")
    atr = features.get("atr")
    if not close or not atr:
        return None
    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 3:
        return None
    if atr / close > 0.07:
        return None

    momentum_10d = _safe_float(features.get("momentum_10d_pct"))
    trend_score = _safe_float(features.get("trend_score"))
    rs_vs_spy = _safe_float(row.get("candidate_day_rs_vs_spy"))
    confidence = se_module._confidence([
        (features.get("above_200ma"), 1.0),
        (momentum_10d >= 0, 1.0),
        (trend_score >= 0.40, 0.5),
        (rs_vs_spy > 0, 0.5),
        (row.get("pct_above_10d_ma", 0) > 0, 0.5),
        (row.get("pct_above_50d_ma", 0) > 0, 0.5),
    ])
    entry = float(close)
    stop = round(entry - ATR_STOP_MULT * float(atr), 2)
    return {
        "ticker": ticker,
        "strategy": "pullback_reclaim_long",
        "entry_price": round(entry, 2),
        "stop_price": stop,
        "confidence_score": confidence,
        "entry_note": "Execute next-day open; experiment-only pullback reclaim replay",
        "conditions_met": {
            "pullback_from_20d_high": row.get("pullback_from_20d_high"),
            "candidate_day_rs_vs_spy": row.get("candidate_day_rs_vs_spy"),
            "pct_above_10d_ma": row.get("pct_above_10d_ma"),
            "pct_above_50d_ma": row.get("pct_above_50d_ma"),
            "dollar_volume": row.get("dollar_volume"),
            "momentum_10d_pct": features.get("momentum_10d_pct"),
            "trend_score": features.get("trend_score"),
        },
    }


def _pullback_signals(features_dict: dict[str, dict]) -> list[dict]:
    rows = _runtime["candidate_by_date"]
    signals = []
    for ticker, features in features_dict.items():
        if not features:
            continue
        date = features.get("_exp051_date")
        row = (rows.get(date) or {}).get(ticker)
        if not row:
            continue
        sig = _pullback_signal(ticker, features, row)
        if sig:
            signals.append(sig)
    return sorted(
        signals,
        key=lambda s: (
            s.get("confidence_score", 0),
            (s.get("conditions_met") or {}).get("candidate_day_rs_vs_spy", 0),
        ),
        reverse=True,
    )


def _patched_compute_features(ticker, ohlcv_data, earnings_data):
    features = _original_compute_features(ticker, ohlcv_data, earnings_data)
    if features is None or ohlcv_data is None or len(ohlcv_data) == 0:
        return features
    last_idx = ohlcv_data.index[-1]
    features["_exp051_date"] = str(last_idx.date() if hasattr(last_idx, "date") else last_idx)[:10]
    return features


def _patched_generate_signals(
    features_dict,
    market_context=None,
    enabled_strategies=None,
    breakout_max_pullback_from_52w_high=None,
):
    base = _original_generate_signals(
        features_dict,
        market_context=market_context,
        enabled_strategies=enabled_strategies,
        breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
    )
    if _runtime["mode"] == "baseline_ab":
        return base

    pullbacks = _pullback_signals(features_dict)
    _runtime["candidate_count"] += len(pullbacks)
    if _runtime["mode"] == "pullback_only":
        _runtime["signals_added"] += len(pullbacks)
        return pullbacks

    base_tickers = {signal.get("ticker") for signal in base}
    additions = [signal for signal in pullbacks if signal.get("ticker") not in base_tickers]
    _runtime["signals_blocked_duplicate"] += len(pullbacks) - len(additions)
    _runtime["signals_added"] += len(additions)
    return sorted(
        base + additions,
        key=lambda signal: signal.get("confidence_score", 0),
        reverse=True,
    )


@contextmanager
def _runtime_patches(candidate_by_date: dict[str, dict[str, dict]], mode: str):
    global _original_compute_features, _original_generate_signals
    _runtime["mode"] = mode
    _runtime["candidate_by_date"] = candidate_by_date
    _runtime["candidate_count"] = 0
    _runtime["signals_added"] = 0
    _runtime["signals_blocked_duplicate"] = 0
    _original_compute_features = fl_module.compute_features
    _original_generate_signals = se_module.generate_signals
    fl_module.compute_features = _patched_compute_features
    se_module.generate_signals = _patched_generate_signals
    try:
        yield
    finally:
        fl_module.compute_features = _original_compute_features
        se_module.generate_signals = _original_generate_signals
        _runtime["candidate_by_date"] = {}


def _run_backtest(universe: list[str], cfg: dict, mode: str, candidate_by_date=None) -> dict:
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
    if mode == "baseline_ab":
        return engine.run()
    with _runtime_patches(candidate_by_date or {}, mode):
        return engine.run()


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key in before:
        a = after.get(key)
        b = before.get(key)
        out[key] = (
            round(a - b, 6)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else None
        )
    return out


def _strategy_attr(result: dict, strategy: str) -> dict:
    return (result.get("by_strategy") or {}).get(strategy) or {}


def _trade_examples(result: dict, strategy: str) -> list[dict]:
    rows = [
        trade for trade in result.get("trades", [])
        if trade.get("strategy") == strategy
    ]
    return [
        {
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "exit_reason": trade.get("exit_reason"),
            "pnl": trade.get("pnl"),
            "pnl_pct": trade.get("pnl_pct"),
            "sector": trade.get("sector"),
        }
        for trade in rows[:20]
    ]


def _window_summary(label: str, cfg: dict, universe: list[str]) -> dict:
    snapshot = _load_snapshot(cfg["snapshot"])
    candidate_by_date = _build_candidate_map(snapshot, cfg, universe)
    shadow_candidates = sum(len(rows) for rows in candidate_by_date.values())

    baseline = _run_backtest(universe, cfg, "baseline_ab")
    ab_plus = _run_backtest(universe, cfg, "ab_plus_pullback", candidate_by_date)
    ab_plus_runtime = {
        "candidate_signals_seen": _runtime["candidate_count"],
        "signals_added_pre_sizing": _runtime["signals_added"],
        "signals_blocked_duplicate": _runtime["signals_blocked_duplicate"],
    }
    pullback_only = _run_backtest(universe, cfg, "pullback_only", candidate_by_date)
    pullback_only_runtime = {
        "candidate_signals_seen": _runtime["candidate_count"],
        "signals_added_pre_sizing": _runtime["signals_added"],
        "signals_blocked_duplicate": _runtime["signals_blocked_duplicate"],
    }

    baseline_metrics = _metrics(baseline)
    ab_plus_metrics = _metrics(ab_plus)
    pullback_only_metrics = _metrics(pullback_only)
    pullback_attr = _strategy_attr(ab_plus, "pullback_reclaim_long")
    candidate_tickers = Counter(
        ticker for rows in candidate_by_date.values() for ticker in rows
    )

    return {
        "window": label,
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "market_regime_summary": cfg["regime"],
        "snapshot": cfg["snapshot"],
        "shadow_candidate_count": shadow_candidates,
        "shadow_candidate_days": len(candidate_by_date),
        "top_candidate_tickers": candidate_tickers.most_common(12),
        "baseline_metrics": baseline_metrics,
        "ab_plus_pullback_metrics": ab_plus_metrics,
        "pullback_only_metrics": pullback_only_metrics,
        "delta_metrics": _delta(ab_plus_metrics, baseline_metrics),
        "ab_plus_runtime": ab_plus_runtime,
        "pullback_only_runtime": pullback_only_runtime,
        "pullback_trade_count": pullback_attr.get("trade_count", 0),
        "pullback_total_pnl": pullback_attr.get("total_pnl_usd"),
        "pullback_profit_factor": pullback_attr.get("profit_factor"),
        "pullback_win_rate": pullback_attr.get("win_rate"),
        "pullback_trade_examples": _trade_examples(ab_plus, "pullback_reclaim_long"),
    }


def _decision_support(windows: list[dict]) -> dict:
    improved = []
    drawdown_regressed = []
    ev_regressed_materially = []
    for row in windows:
        delta = row["delta_metrics"]
        if (delta.get("expected_value_score") or 0.0) > 0:
            improved.append(row["window"])
        if (delta.get("max_drawdown_pct") or 0.0) > 0.01:
            drawdown_regressed.append(row["window"])
        before_ev = row["baseline_metrics"].get("expected_value_score") or 0.0
        after_ev = row["ab_plus_pullback_metrics"].get("expected_value_score") or 0.0
        if before_ev > 0 and (before_ev - after_ev) / before_ev > 0.05:
            ev_regressed_materially.append(row["window"])

    accepted_candidate = (
        len(improved) >= 2
        and not drawdown_regressed
        and not ev_regressed_materially
    )
    return {
        "candidate_acceptance_rule": (
            "accepted_candidate iff AB+pullback EV improves in at least 2/3 "
            "windows with no >1pp drawdown regression and no >5% EV regression"
        ),
        "ev_improved_windows": improved,
        "drawdown_regressed_windows": drawdown_regressed,
        "ev_regressed_materially_windows": ev_regressed_materially,
        "accepted_candidate": accepted_candidate,
        "production_connection_justified": accepted_candidate,
        "production_connection_note": (
            "Production wiring is justified for a separate scoped ticket."
            if accepted_candidate
            else "Do not wire to production; replay failed the multi-window candidate gate."
        ),
    }


def _root_from_primary(windows: list[dict]) -> dict:
    primary = next(row for row in windows if row["window"] == "late_strong")
    metrics = primary["ab_plus_pullback_metrics"]
    return {
        "period": "2025-10-23 -> 2026-04-21",
        "total_trades": metrics.get("trade_count"),
        "win_rate": metrics.get("win_rate"),
        "total_pnl": metrics.get("total_pnl"),
        "sharpe": metrics.get("sharpe"),
        "sharpe_daily": metrics.get("sharpe_daily"),
        "max_drawdown_pct": metrics.get("max_drawdown_pct"),
        "survival_rate": metrics.get("survival_rate"),
        "expected_value_score": metrics.get("expected_value_score"),
        "benchmarks": {
            "strategy_total_return_pct": metrics.get("total_return_pct"),
        },
    }


def main() -> int:
    universe = get_universe()
    window_summaries = []
    for label, cfg in WINDOWS.items():
        row = _window_summary(label, cfg, universe)
        window_summaries.append(row)
        print(
            f"[{label}] EV {row['baseline_metrics']['expected_value_score']} -> "
            f"{row['ab_plus_pullback_metrics']['expected_value_score']} "
            f"delta={row['delta_metrics']['expected_value_score']} "
            f"pullback_trades={row['pullback_trade_count']} "
            f"pullback_pnl={row['pullback_total_pnl']}"
        )

    decision = _decision_support(window_summaries)
    root = _root_from_primary(window_summaries)
    root.update({
        "experiment_id": EXPERIMENT_ID,
        "status": "accepted_candidate" if decision["accepted_candidate"] else "rejected",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "The observed-positive multi-day pullback reclaim continuation "
            "shadow source can survive production-path replay with real sizing, "
            "slot competition, and existing exits."
        ),
        "single_causal_variable": "multi-day pullback reclaim continuation production-path shadow replay",
        "shadow_entry_definition": {
            "source_experiment": "exp-20260426-047",
            "fast_ma_days": FAST_MA_DAYS,
            "mid_ma_days": MID_MA_DAYS,
            "slow_ma_days": SLOW_MA_DAYS,
            "pullback_lookback_days": PULLBACK_LOOKBACK_DAYS,
            "recent_high_lookback_days": RECENT_HIGH_LOOKBACK_DAYS,
            "pullback_from_recent_high_range": [
                MIN_PULLBACK_FROM_HIGH,
                MAX_PULLBACK_FROM_HIGH,
            ],
            "candidate_day_rs_vs_spy_min": MIN_CANDIDATE_RS_VS_SPY,
            "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
        },
        "windows": window_summaries,
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
