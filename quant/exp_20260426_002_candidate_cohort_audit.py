"""exp-20260426-002 candidate-cohort composition audit.

Hypothesis:
    Candidate-day cohort composition may be a richer replayable sleeve-selection
    state than the rejected cheap day-state proxies. Instead of broad market-day
    states like OMDB or QQQ-vs-SPY momentum, inspect the accepted A+B stack's
    same-day candidate mix after each real pipeline stage.

This script is audit-only. It does not change production strategy code.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict, defaultdict
from statistics import mean


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine, Position  # noqa: E402
from data_layer import get_universe  # noqa: E402
import signal_engine as se_module  # noqa: E402
import risk_engine as re_module  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402


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

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_002_candidate_cohort_audit.json",
)

_state = {
    "window_label": None,
    "current_day": None,
    "days": {},
}


def _safe_mean(values):
    clean = [v for v in values if v is not None]
    return round(mean(clean), 6) if clean else None


def _round_or_none(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def _day_bucket(day: dict) -> str:
    pre_size = day.get("pre_size_count", 0)
    breakout = day.get("pre_size_by_strategy", {}).get("breakout_long", 0)
    trend = day.get("pre_size_by_strategy", {}).get("trend_long", 0)
    breakout_share = breakout / pre_size if pre_size else 0.0
    trend_share = trend / pre_size if pre_size else 0.0
    if pre_size == 0:
        return "no_candidates"
    if pre_size <= 2:
        return "sparse_candidates"
    if breakout_share >= 0.67:
        return "breakout_dominant"
    if trend_share >= 0.67:
        return "trend_dominant"
    return "mixed_candidates"


def _strategy_counts(signals):
    counts = defaultdict(int)
    for sig in signals or []:
        counts[sig.get("strategy", "unknown")] += 1
    return dict(sorted(counts.items()))


def _sector_counts(signals):
    counts = defaultdict(int)
    for sig in signals or []:
        counts[sig.get("sector", "Unknown")] += 1
    return dict(sorted(counts.items()))


def _top_sector_share(signals):
    if not signals:
        return None
    counts = _sector_counts(signals)
    top = max(counts.values()) if counts else 0
    return round(top / len(signals), 4) if top else None


def _strategy_metric(signals, strategy, extractor):
    values = [
        extractor(sig)
        for sig in signals or []
        if sig.get("strategy") == strategy
    ]
    return _safe_mean(values)


def _signal_snapshot(signals):
    return {
        "count": len(signals or []),
        "by_strategy": _strategy_counts(signals),
        "by_sector": _sector_counts(signals),
        "top_sector_share": _top_sector_share(signals),
        "avg_confidence": _safe_mean([
            sig.get("confidence_score") for sig in signals or []
        ]),
        "avg_trade_quality_score": _safe_mean([
            sig.get("trade_quality_score") for sig in signals or []
        ]),
        "avg_breakout_pct_from_52w_high": _strategy_metric(
            signals,
            "breakout_long",
            lambda sig: (sig.get("conditions_met") or {}).get("pct_from_52w_high"),
        ),
        "avg_trend_gap_vulnerability_pct": _strategy_metric(
            signals,
            "trend_long",
            lambda sig: sig.get("gap_vulnerability_pct"),
        ),
        "breakout_avg_tqs": _strategy_metric(
            signals, "breakout_long", lambda sig: sig.get("trade_quality_score")
        ),
        "trend_avg_tqs": _strategy_metric(
            signals, "trend_long", lambda sig: sig.get("trade_quality_score")
        ),
        "breakout_avg_confidence": _strategy_metric(
            signals, "breakout_long", lambda sig: sig.get("confidence_score")
        ),
        "trend_avg_confidence": _strategy_metric(
            signals, "trend_long", lambda sig: sig.get("confidence_score")
        ),
    }


def _get_day(day_str: str) -> dict:
    days = _state["days"]
    if day_str not in days:
        days[day_str] = {
            "signal_date": day_str,
            "window": _state["window_label"],
            "market_context": {},
            "raw_generated": [],
            "ranked_generated": [],
            "enriched": [],
            "pre_size": [],
            "sized": [],
            "entries": [],
        }
    return days[day_str]


def _patched_earnings_dict_for(self, today, *args, **kwargs):
    day_str = today.strftime("%Y-%m-%d")
    _state["current_day"] = day_str
    _get_day(day_str)
    return _original_earnings_dict_for(self, today, *args, **kwargs)


def _patched_generate_signals(
    features_dict,
    market_context=None,
    enabled_strategies=None,
    breakout_max_pullback_from_52w_high=None,
):
    out = _original_generate_signals(
        features_dict,
        market_context=market_context,
        enabled_strategies=enabled_strategies,
        breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
    )
    day = _get_day(_state["current_day"])
    day["market_context"] = {
        "market_regime": (market_context or {}).get("market_regime"),
        "spy_pct_from_ma": _round_or_none((market_context or {}).get("spy_pct_from_ma")),
        "qqq_pct_from_ma": _round_or_none((market_context or {}).get("qqq_pct_from_ma")),
        "spy_10d_return": _round_or_none((market_context or {}).get("spy_10d_return")),
        "qqq_10d_return": _round_or_none((market_context or {}).get("qqq_10d_return")),
    }
    day["raw_generated"] = [dict(sig) for sig in out]
    return out


def _patched_rank_signals_for_allocation(signals):
    out = _original_rank_signals_for_allocation(signals)
    day = _get_day(_state["current_day"])
    day["ranked_generated"] = [dict(sig) for sig in out]
    return out


def _patched_enrich_signals(signals, features_dict, atr_target_mult=None):
    out = _original_enrich_signals(
        signals,
        features_dict,
        atr_target_mult=atr_target_mult,
    )
    day = _get_day(_state["current_day"])
    day["enriched"] = [dict(sig) for sig in out]
    return out


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    day = _get_day(_state["current_day"])
    day["pre_size"] = [dict(sig) for sig in signals]
    out = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    day["sized"] = [dict(sig) for sig in out]
    return out


def _patched_position_init(
    self,
    ticker,
    entry_price,
    stop_price,
    target_price,
    shares,
    entry_date,
    strategy,
    sector="Unknown",
    entry_open_price=None,
    atr=None,
    target_mult_used=None,
    regime_exit_bucket=None,
    regime_exit_score=None,
    sizing_multipliers=None,
    base_risk_pct=None,
    actual_risk_pct=None,
):
    _original_position_init(
        self,
        ticker,
        entry_price,
        stop_price,
        target_price,
        shares,
        entry_date,
        strategy,
        sector=sector,
        entry_open_price=entry_open_price,
        atr=atr,
        target_mult_used=target_mult_used,
        regime_exit_bucket=regime_exit_bucket,
        regime_exit_score=regime_exit_score,
        sizing_multipliers=sizing_multipliers,
        base_risk_pct=base_risk_pct,
        actual_risk_pct=actual_risk_pct,
    )
    day = _get_day(_state["current_day"])
    day["entries"].append({
        "ticker": ticker,
        "strategy": strategy,
        "sector": sector,
        "entry_date": (
            entry_date.strftime("%Y-%m-%d")
            if hasattr(entry_date, "strftime")
            else str(entry_date)
        ),
        "shares": shares,
        "entry_price": _round_or_none(entry_price, 4),
        "entry_open_price": _round_or_none(entry_open_price, 4),
        "target_mult_used": _round_or_none(target_mult_used, 4),
        "regime_exit_bucket": regime_exit_bucket,
        "regime_exit_score": _round_or_none(regime_exit_score, 4),
        "base_risk_pct": _round_or_none(base_risk_pct, 6),
        "actual_risk_pct": _round_or_none(actual_risk_pct, 6),
        "sizing_multipliers": dict(sorted((sizing_multipliers or {}).items())),
    })


def _install_patches():
    global _original_earnings_dict_for
    global _original_generate_signals
    global _original_rank_signals_for_allocation
    global _original_enrich_signals
    global _original_size_signals
    global _original_position_init

    _original_earnings_dict_for = BacktestEngine._earnings_dict_for
    _original_generate_signals = se_module.generate_signals
    _original_rank_signals_for_allocation = se_module.rank_signals_for_allocation
    _original_enrich_signals = re_module.enrich_signals
    _original_size_signals = pe_module.size_signals
    _original_position_init = Position.__init__

    BacktestEngine._earnings_dict_for = _patched_earnings_dict_for
    se_module.generate_signals = _patched_generate_signals
    se_module.rank_signals_for_allocation = _patched_rank_signals_for_allocation
    re_module.enrich_signals = _patched_enrich_signals
    pe_module.size_signals = _patched_size_signals
    Position.__init__ = _patched_position_init


def _remove_patches():
    BacktestEngine._earnings_dict_for = _original_earnings_dict_for
    se_module.generate_signals = _original_generate_signals
    se_module.rank_signals_for_allocation = _original_rank_signals_for_allocation
    re_module.enrich_signals = _original_enrich_signals
    pe_module.size_signals = _original_size_signals
    Position.__init__ = _original_position_init


def _trade_key_from_trade(trade: dict):
    return (
        trade.get("ticker"),
        trade.get("entry_date"),
        trade.get("strategy"),
    )


def _trade_map_by_entry(trades):
    out = {}
    for trade in trades or []:
        out[_trade_key_from_trade(trade)] = trade
    return out


def _finalize_day(day: dict, trade_map: dict, max_positions: int) -> dict:
    raw_signals = day.get("raw_generated") or []
    ranked_signals = day.get("ranked_generated") or raw_signals
    enriched_signals = day.get("enriched") or []
    pre_size_signals = day.get("pre_size") or []
    sized_signals = day.get("sized") or []
    entries = day.get("entries") or []
    trades_for_day = []
    for entry in entries:
        key = (
            entry.get("ticker"),
            entry.get("entry_date"),
            entry.get("strategy"),
        )
        trade = trade_map.get(key)
        if trade:
            trades_for_day.append(trade)
    breakout_count = sum(
        1 for sig in pre_size_signals if sig.get("strategy") == "breakout_long"
    )
    trend_count = sum(
        1 for sig in pre_size_signals if sig.get("strategy") == "trend_long"
    )
    slot_collision = max(0, len(pre_size_signals) - max_positions)
    entered_trade_pnl = [trade.get("pnl") for trade in trades_for_day if trade.get("pnl") is not None]
    entered_trade_pnl_pct = [
        trade.get("pnl_pct_net")
        for trade in trades_for_day
        if trade.get("pnl_pct_net") is not None
    ]
    per_strategy_realized = defaultdict(float)
    for trade in trades_for_day:
        per_strategy_realized[trade.get("strategy", "unknown")] += trade.get("pnl") or 0.0

    out = {
        "signal_date": day["signal_date"],
        "market_context": day.get("market_context") or {},
        "raw_generated_count": len(raw_signals),
        "ranked_generated_count": len(ranked_signals),
        "enriched_count": len(enriched_signals),
        "pre_size_count": len(pre_size_signals),
        "sized_count": len(sized_signals),
        "entered_count": len(entries),
        "slot_collision_excess": slot_collision,
        "pre_size_breakout_share": (
            round(breakout_count / len(pre_size_signals), 4) if pre_size_signals else None
        ),
        "pre_size_trend_share": (
            round(trend_count / len(pre_size_signals), 4) if pre_size_signals else None
        ),
        "raw_snapshot": _signal_snapshot(raw_signals),
        "enriched_snapshot": _signal_snapshot(enriched_signals),
        "pre_size_snapshot": _signal_snapshot(pre_size_signals),
        "sized_snapshot": _signal_snapshot(sized_signals),
        "entries_by_strategy": _strategy_counts(entries),
        "entries_by_sector": _sector_counts(entries),
        "entry_tickers": sorted(entry.get("ticker") for entry in entries if entry.get("ticker")),
        "entry_target_mults": sorted({
            entry.get("target_mult_used")
            for entry in entries
            if entry.get("target_mult_used") is not None
        }),
        "realized_trade_count": len(trades_for_day),
        "realized_total_pnl": round(sum(entered_trade_pnl), 2) if entered_trade_pnl else 0.0,
        "realized_avg_pnl": round(sum(entered_trade_pnl) / len(entered_trade_pnl), 2)
        if entered_trade_pnl else None,
        "realized_avg_pnl_pct_net": _safe_mean(entered_trade_pnl_pct),
        "realized_pnl_by_strategy": {
            key: round(value, 2)
            for key, value in sorted(per_strategy_realized.items())
        },
    }
    out["cohort_bucket"] = _day_bucket({
        "pre_size_count": out["pre_size_count"],
        "pre_size_by_strategy": out["pre_size_snapshot"]["by_strategy"],
    })
    return out


def _bucket_summary(day_rows: list[dict]) -> dict:
    if not day_rows:
        return {}
    return {
        "day_count": len(day_rows),
        "avg_pre_size_count": _safe_mean([d.get("pre_size_count") for d in day_rows]),
        "avg_slot_collision_excess": _safe_mean([d.get("slot_collision_excess") for d in day_rows]),
        "avg_breakout_share": _safe_mean([d.get("pre_size_breakout_share") for d in day_rows]),
        "avg_trend_share": _safe_mean([d.get("pre_size_trend_share") for d in day_rows]),
        "avg_realized_total_pnl": _safe_mean([d.get("realized_total_pnl") for d in day_rows]),
        "avg_realized_pnl_pct_net": _safe_mean([d.get("realized_avg_pnl_pct_net") for d in day_rows]),
        "breakout_days": sum(
            1 for d in day_rows if d.get("pre_size_snapshot", {}).get("by_strategy", {}).get("breakout_long", 0) > 0
        ),
        "trend_days": sum(
            1 for d in day_rows if d.get("pre_size_snapshot", {}).get("by_strategy", {}).get("trend_long", 0) > 0
        ),
    }


def _window_summary(label: str, cfg: dict, result: dict, days: dict) -> dict:
    trade_map = _trade_map_by_entry(result.get("trades") or [])
    rows = [
        _finalize_day(day, trade_map, result.get("config_used", {}).get("MAX_POSITIONS", 5))
        for day_str, day in sorted(days.items())
    ]
    by_bucket = defaultdict(list)
    for row in rows:
        by_bucket[row["cohort_bucket"]].append(row)
    bucket_summary = {
        key: _bucket_summary(items)
        for key, items in sorted(by_bucket.items())
    }
    top_slot_collision_days = sorted(
        rows,
        key=lambda row: (row.get("slot_collision_excess") or 0, row.get("pre_size_count") or 0),
        reverse=True,
    )[:10]
    top_positive_days = sorted(
        rows,
        key=lambda row: row.get("realized_total_pnl") or 0.0,
        reverse=True,
    )[:10]
    top_negative_days = sorted(
        rows,
        key=lambda row: row.get("realized_total_pnl") or 0.0,
    )[:10]

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "signals_generated": result.get("signals_generated"),
            "signals_survived": result.get("signals_survived"),
            "survival_rate": result.get("survival_rate"),
        },
        "day_count": len(rows),
        "bucket_summary": bucket_summary,
        "top_slot_collision_days": [
            {
                "signal_date": row["signal_date"],
                "cohort_bucket": row["cohort_bucket"],
                "slot_collision_excess": row["slot_collision_excess"],
                "pre_size_count": row["pre_size_count"],
                "pre_size_breakout_share": row["pre_size_breakout_share"],
                "pre_size_trend_share": row["pre_size_trend_share"],
                "realized_total_pnl": row["realized_total_pnl"],
            }
            for row in top_slot_collision_days
        ],
        "top_positive_days": [
            {
                "signal_date": row["signal_date"],
                "cohort_bucket": row["cohort_bucket"],
                "pre_size_count": row["pre_size_count"],
                "pre_size_breakout_share": row["pre_size_breakout_share"],
                "pre_size_trend_share": row["pre_size_trend_share"],
                "realized_total_pnl": row["realized_total_pnl"],
                "entries_by_strategy": row["entries_by_strategy"],
            }
            for row in top_positive_days
        ],
        "top_negative_days": [
            {
                "signal_date": row["signal_date"],
                "cohort_bucket": row["cohort_bucket"],
                "pre_size_count": row["pre_size_count"],
                "pre_size_breakout_share": row["pre_size_breakout_share"],
                "pre_size_trend_share": row["pre_size_trend_share"],
                "realized_total_pnl": row["realized_total_pnl"],
                "entries_by_strategy": row["entries_by_strategy"],
            }
            for row in top_negative_days
        ],
        "days": rows,
    }


def _run_window(label: str, cfg: dict, universe: list[str]) -> dict:
    _state["window_label"] = label
    _state["current_day"] = None
    _state["days"] = {}
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
    result = engine.run()
    return _window_summary(label, cfg, result, dict(_state["days"]))


def main() -> int:
    universe = get_universe()
    _install_patches()
    try:
        windows = []
        for label, cfg in WINDOWS.items():
            summary = _run_window(label, cfg, universe)
            windows.append(summary)
            print(
                f"[{label}] EV={summary['baseline_metrics']['expected_value_score']} "
                f"days={summary['day_count']} "
                f"breakout_dom={summary['bucket_summary'].get('breakout_dominant', {}).get('day_count', 0)} "
                f"trend_dom={summary['bucket_summary'].get('trend_dominant', {}).get('day_count', 0)} "
                f"mixed={summary['bucket_summary'].get('mixed_candidates', {}).get('day_count', 0)} "
                f"sparse={summary['bucket_summary'].get('sparse_candidates', {}).get('day_count', 0)}"
            )
    finally:
        _remove_patches()

    payload = {
        "experiment_id": "exp-20260426-002",
        "status": "audit_only",
        "hypothesis": (
            "Candidate-day cohort composition may provide a richer replayable "
            "meta-allocation state than the rejected cheap day-state proxies."
        ),
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
