"""exp-20260526-023/024/025: remaining Kova daily-OHLCV attributions.

This batch runner keeps the accepted VCP top-2 rank-notional paper sleeve
unchanged and runs three separate observed-only attribution experiments:

- exp-20260526-023: signal-day breakout volume plus high-close quality.
- exp-20260526-024: pre-signal three-week-tight behavior.
- exp-20260526-025: pre-signal moving-average structure.

Each experiment has one causal metadata bucket. No entry, ranking, sizing,
exit, universe, LLM/news, adapter, live-order, or paper-sleeve behavior is
changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    WINDOWS,
    _audit_open_positions,
    _date10,
    _flatten,
    _load_json,
    _load_snapshot,
    _load_source_rank_profile,
    _now,
    _num,
    _repo_rel,
    _round,
    _row_date,
    _row_value,
    _safe,
    _write_json,
    _write_text,
)


RUNNER = Path(__file__)
TEST_FILE = REPO_ROOT / "quant" / "test_kova_remaining_ohlcv_attributions.py"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

SOURCE_VARIANT = "rank2_125"

BREAKOUT_STRONG = "volume_expansion_high_close"
BREAKOUT_VOLUME_ONLY = "volume_expansion_not_high_close"
BREAKOUT_HIGH_CLOSE_ONLY = "high_close_without_volume_expansion"
BREAKOUT_NEITHER = "no_volume_expansion_or_high_close"
BREAKOUT_UNAVAILABLE = "unavailable"
BREAKOUT_BUCKETS = [
    BREAKOUT_STRONG,
    BREAKOUT_VOLUME_ONLY,
    BREAKOUT_HIGH_CLOSE_ONLY,
    BREAKOUT_NEITHER,
    BREAKOUT_UNAVAILABLE,
]

WEEKLY_TIGHT = "three_week_tight"
WEEKLY_NOT_TIGHT = "not_three_week_tight"
WEEKLY_UNAVAILABLE = "unavailable"
WEEKLY_BUCKETS = [WEEKLY_TIGHT, WEEKLY_NOT_TIGHT, WEEKLY_UNAVAILABLE]

MA_BULLISH = "bullish_ma_stack_close_above_10_21_50"
MA_ABOVE_50 = "close_above_50_without_full_stack"
MA_BROKEN = "below_50_or_broken_stack"
MA_UNAVAILABLE = "unavailable"
MA_BUCKETS = [MA_BULLISH, MA_ABOVE_50, MA_BROKEN, MA_UNAVAILABLE]


@dataclass(frozen=True)
class AttributionSpec:
    experiment_id: str
    title: str
    stem: str
    decision_prefix: str
    changed_variable: str
    bucket_field: str
    bucket_order: list[str]
    target_bucket: str
    rule_version: str
    trial_family: str
    trial_variant_id: str
    change_type: str
    new_evidence_type: str
    hypothesis: str
    field_definition: dict[str, Any]
    context_fn: Callable[[list[dict[str, Any]], dict[str, Any]], dict[str, Any]]
    why_not_other_changes: str


def _sma(values: list[float], lookback: int) -> float | None:
    if len(values) < lookback:
        return None
    return sum(values[-lookback:]) / lookback


def _signal_row_and_prior(
    rows: list[dict[str, Any]],
    signal_date: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    sorted_rows = sorted(rows, key=_row_date)
    signal_row = None
    prior: list[dict[str, Any]] = []
    for row in sorted_rows:
        row_date = _row_date(row)
        if row_date < signal_date:
            prior.append(row)
        elif row_date == signal_date:
            signal_row = row
            break
    return signal_row, prior


def compute_signal_day_breakout_quality_context(
    rows: list[dict[str, Any]],
    trade: dict[str, Any],
    *,
    volume_lookback: int = 20,
    min_prior_volume_rows: int = 10,
) -> dict[str, Any]:
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    shell = {
        "signal_day_breakout_quality_rule_version": "signal_day_breakout_quality_v1",
        "signal_day_breakout_quality_known_at": (
            "after_signal_date_close_before_next_open_paper_entry"
        ),
        "signal_day_breakout_quality_alters_orders": False,
        "signal_day_breakout_quality_trade_enabled": False,
        "signal_day_breakout_quality_volume_lookback": volume_lookback,
        "signal_day_breakout_quality_volume_ratio_threshold": 1.25,
        "signal_day_breakout_quality_close_location_threshold": 0.75,
    }
    if not signal_date:
        return {
            **shell,
            "signal_day_breakout_quality_bucket_v1": BREAKOUT_UNAVAILABLE,
            "signal_day_breakout_quality_available": False,
            "signal_day_breakout_quality_unavailable_reason": "missing_signal_date",
        }
    signal_row, prior_rows = _signal_row_and_prior(rows, signal_date)
    if signal_row is None:
        return {
            **shell,
            "signal_day_breakout_quality_bucket_v1": BREAKOUT_UNAVAILABLE,
            "signal_day_breakout_quality_available": False,
            "signal_day_breakout_quality_unavailable_reason": "missing_signal_day_ohlcv",
        }
    prior_window = prior_rows[-volume_lookback:]
    prior_volumes = [
        volume for row in prior_window for volume in [_row_value(row, "Volume")] if volume is not None
    ]
    signal_volume = _row_value(signal_row, "Volume")
    high = _row_value(signal_row, "High")
    low = _row_value(signal_row, "Low")
    close = _row_value(signal_row, "Close")
    if len(prior_volumes) < min_prior_volume_rows:
        return {
            **shell,
            "signal_day_breakout_quality_bucket_v1": BREAKOUT_UNAVAILABLE,
            "signal_day_breakout_quality_available": False,
            "signal_day_breakout_quality_unavailable_reason": "insufficient_prior_volume_rows",
            "prior_volume_row_count": len(prior_volumes),
        }
    if signal_volume is None or high is None or low is None or close is None or high <= low:
        return {
            **shell,
            "signal_day_breakout_quality_bucket_v1": BREAKOUT_UNAVAILABLE,
            "signal_day_breakout_quality_available": False,
            "signal_day_breakout_quality_unavailable_reason": "missing_signal_ohlcv_or_zero_range",
            "prior_volume_row_count": len(prior_volumes),
        }
    avg_prior_volume = sum(prior_volumes) / len(prior_volumes)
    if avg_prior_volume <= 0:
        return {
            **shell,
            "signal_day_breakout_quality_bucket_v1": BREAKOUT_UNAVAILABLE,
            "signal_day_breakout_quality_available": False,
            "signal_day_breakout_quality_unavailable_reason": "non_positive_prior_avg_volume",
            "prior_volume_row_count": len(prior_volumes),
        }
    volume_ratio = signal_volume / avg_prior_volume
    close_location = (close - low) / (high - low)
    volume_expansion = volume_ratio >= 1.25
    high_close = close_location >= 0.75
    if volume_expansion and high_close:
        bucket = BREAKOUT_STRONG
    elif volume_expansion:
        bucket = BREAKOUT_VOLUME_ONLY
    elif high_close:
        bucket = BREAKOUT_HIGH_CLOSE_ONLY
    else:
        bucket = BREAKOUT_NEITHER
    return {
        **shell,
        "signal_day_breakout_quality_bucket_v1": bucket,
        "signal_day_breakout_quality_available": True,
        "signal_day_breakout_quality_unavailable_reason": None,
        "prior_volume_row_count": len(prior_volumes),
        "signal_day_volume": _round(signal_volume, 2),
        "signal_day_avg_prior_20_volume": _round(avg_prior_volume, 2),
        "signal_day_volume_ratio_20": _round(volume_ratio, 6),
        "signal_day_close_location": _round(close_location, 6),
        "signal_day_volume_expansion": volume_expansion,
        "signal_day_high_close": high_close,
    }


def _completed_weekly_closes(
    rows: list[dict[str, Any]],
    signal_date: str,
) -> list[dict[str, Any]]:
    try:
        signal_dt = datetime.fromisoformat(signal_date).date()
    except ValueError:
        return []
    signal_week = signal_dt.isocalendar()[:2]
    groups: OrderedDict[tuple[int, int], dict[str, Any]] = OrderedDict()
    for row in sorted(rows, key=_row_date):
        row_date = _row_date(row)
        if not row_date or row_date >= signal_date:
            continue
        try:
            dt = datetime.fromisoformat(row_date).date()
        except ValueError:
            continue
        key = dt.isocalendar()[:2]
        if key == signal_week:
            continue
        close = _row_value(row, "Close")
        if close is None:
            continue
        groups[key] = {
            "iso_year": key[0],
            "iso_week": key[1],
            "week_end_date": row_date,
            "close": close,
        }
    return list(groups.values())


def compute_weekly_tightness_context(
    rows: list[dict[str, Any]],
    trade: dict[str, Any],
) -> dict[str, Any]:
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    shell = {
        "pre_signal_weekly_tightness_rule_version": "pre_signal_three_week_tight_v1",
        "pre_signal_weekly_tightness_known_at": (
            "after_signal_date_close_before_next_open_paper_entry; excludes signal week"
        ),
        "pre_signal_weekly_tightness_alters_orders": False,
        "pre_signal_weekly_tightness_trade_enabled": False,
        "pre_signal_weekly_tightness_max_close_spread_threshold": 0.03,
        "pre_signal_weekly_tightness_max_abs_weekly_return_threshold": 0.015,
    }
    if not signal_date:
        return {
            **shell,
            "pre_signal_weekly_tightness_bucket_v1": WEEKLY_UNAVAILABLE,
            "pre_signal_weekly_tightness_available": False,
            "pre_signal_weekly_tightness_unavailable_reason": "missing_signal_date",
        }
    weeks = _completed_weekly_closes(rows, signal_date)
    if len(weeks) < 4:
        return {
            **shell,
            "pre_signal_weekly_tightness_bucket_v1": WEEKLY_UNAVAILABLE,
            "pre_signal_weekly_tightness_available": False,
            "pre_signal_weekly_tightness_unavailable_reason": "fewer_than_4_completed_prior_weeks",
            "completed_prior_week_count": len(weeks),
        }
    last4 = weeks[-4:]
    last3 = weeks[-3:]
    closes = [float(row["close"]) for row in last3]
    prior_close = float(last4[0]["close"])
    weekly_returns = []
    prev = prior_close
    for close in closes:
        weekly_returns.append(close / prev - 1.0)
        prev = close
    close_spread = max(closes) / min(closes) - 1.0 if min(closes) > 0 else None
    max_abs_return = max(abs(value) for value in weekly_returns)
    tight = (
        close_spread is not None
        and close_spread <= 0.03
        and max_abs_return <= 0.015
    )
    return {
        **shell,
        "pre_signal_weekly_tightness_bucket_v1": WEEKLY_TIGHT if tight else WEEKLY_NOT_TIGHT,
        "pre_signal_weekly_tightness_available": True,
        "pre_signal_weekly_tightness_unavailable_reason": None,
        "completed_prior_week_count": len(weeks),
        "three_week_tight_weekly_closes": [
            {
                "week_end_date": row["week_end_date"],
                "close": _round(row["close"], 4),
            }
            for row in last3
        ],
        "three_week_tight_close_spread": _round(close_spread, 6),
        "three_week_tight_weekly_returns": [_round(value, 6) for value in weekly_returns],
        "three_week_tight_max_abs_weekly_return": _round(max_abs_return, 6),
    }


def compute_ma_structure_context(
    rows: list[dict[str, Any]],
    trade: dict[str, Any],
) -> dict[str, Any]:
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    shell = {
        "pre_signal_ma_structure_rule_version": "pre_signal_ma_structure_v1",
        "pre_signal_ma_structure_known_at": (
            "after_signal_date_close_before_next_open_paper_entry; uses last row before signal date"
        ),
        "pre_signal_ma_structure_alters_orders": False,
        "pre_signal_ma_structure_trade_enabled": False,
        "pre_signal_ma_structure_windows": [10, 21, 50],
    }
    if not signal_date:
        return {
            **shell,
            "pre_signal_ma_structure_bucket_v1": MA_UNAVAILABLE,
            "pre_signal_ma_structure_available": False,
            "pre_signal_ma_structure_unavailable_reason": "missing_signal_date",
        }
    prior_rows = [row for row in sorted(rows, key=_row_date) if _row_date(row) < signal_date]
    closes = [close for row in prior_rows for close in [_row_value(row, "Close")] if close is not None]
    if len(closes) < 50:
        return {
            **shell,
            "pre_signal_ma_structure_bucket_v1": MA_UNAVAILABLE,
            "pre_signal_ma_structure_available": False,
            "pre_signal_ma_structure_unavailable_reason": "fewer_than_50_prior_close_rows",
            "prior_close_row_count": len(closes),
        }
    last_close = closes[-1]
    ma10 = _sma(closes, 10)
    ma21 = _sma(closes, 21)
    ma50 = _sma(closes, 50)
    if ma10 is None or ma21 is None or ma50 is None:
        bucket = MA_UNAVAILABLE
        available = False
        reason = "missing_ma"
    elif last_close > ma10 > ma21 > ma50:
        bucket = MA_BULLISH
        available = True
        reason = None
    elif last_close > ma50:
        bucket = MA_ABOVE_50
        available = True
        reason = None
    else:
        bucket = MA_BROKEN
        available = True
        reason = None
    return {
        **shell,
        "pre_signal_ma_structure_bucket_v1": bucket,
        "pre_signal_ma_structure_available": available,
        "pre_signal_ma_structure_unavailable_reason": reason,
        "pre_signal_ma_asof_date": _row_date(prior_rows[-1]) if prior_rows else None,
        "prior_close_row_count": len(closes),
        "pre_signal_last_close": _round(last_close, 4),
        "pre_signal_sma10": _round(ma10, 4),
        "pre_signal_sma21": _round(ma21, 4),
        "pre_signal_sma50": _round(ma50, 4),
        "pre_signal_close_vs_sma50_pct": _round(last_close / ma50 - 1.0, 6)
        if ma50 and ma50 > 0
        else None,
        "pre_signal_sma10_vs_sma50_pct": _round(ma10 / ma50 - 1.0, 6)
        if ma10 and ma50 and ma50 > 0
        else None,
    }


SPECS = [
    AttributionSpec(
        experiment_id="exp-20260526-023",
        title="Kova Signal-Day Breakout Quality Attribution",
        stem="kova_signal_day_breakout_quality_attribution",
        decision_prefix="signal_day_breakout_quality",
        changed_variable="signal_day_breakout_quality_bucket_v1",
        bucket_field="signal_day_breakout_quality_bucket_v1",
        bucket_order=BREAKOUT_BUCKETS,
        target_bucket=BREAKOUT_STRONG,
        rule_version="signal_day_breakout_quality_v1",
        trial_family="vcp_kova_signal_day_breakout_quality_attribution",
        trial_variant_id="signal_day_volume_close_quality",
        change_type="kova_signal_day_breakout_quality_attribution",
        new_evidence_type="new_production_visible_daily_ohlcv_breakout_quality_field",
        hypothesis=(
            "Kova-style breakout-day volume expansion plus high-close quality may "
            "separate replacement value inside the accepted default-off VCP top-2 "
            "rank-notional paper sleeve."
        ),
        field_definition={
            "target_bucket": BREAKOUT_STRONG,
            "volume_expansion": "signal-day volume >= 1.25x average prior 20 trading-day volume",
            "high_close": "signal-day close location >= 0.75 within signal-day high-low range",
            "date_boundary": "prior volume average uses rows with Date < signal_date",
        },
        context_fn=compute_signal_day_breakout_quality_context,
        why_not_other_changes=(
            "Did not retune VCP, QQQ/SPY, top-N, rank-notional, exits, pocket "
            "pivot, weekly tightness, moving averages, or live/default orders."
        ),
    ),
    AttributionSpec(
        experiment_id="exp-20260526-024",
        title="Kova Pre-Signal Weekly Tightness Attribution",
        stem="kova_pre_signal_weekly_tightness_attribution",
        decision_prefix="weekly_tightness",
        changed_variable="pre_signal_weekly_tightness_bucket_v1",
        bucket_field="pre_signal_weekly_tightness_bucket_v1",
        bucket_order=WEEKLY_BUCKETS,
        target_bucket=WEEKLY_TIGHT,
        rule_version="pre_signal_three_week_tight_v1",
        trial_family="vcp_kova_weekly_tightness_attribution",
        trial_variant_id="three_week_tight_pre_signal",
        change_type="kova_pre_signal_weekly_tightness_attribution",
        new_evidence_type="new_production_visible_daily_ohlcv_weekly_tightness_field",
        hypothesis=(
            "Kova-style three-week-tight behavior before an accepted VCP breakout "
            "may identify lower-supply candidates with better replacement value "
            "inside the default-off VCP top-2 rank-notional paper sleeve."
        ),
        field_definition={
            "target_bucket": WEEKLY_TIGHT,
            "three_week_tight": (
                "last three completed pre-signal weekly closes have max/min close "
                "spread <= 3% and each consecutive weekly close return <= 1.5% in abs"
            ),
            "date_boundary": "signal week is excluded; only completed prior weeks count",
        },
        context_fn=compute_weekly_tightness_context,
        why_not_other_changes=(
            "Did not retune VCP, QQQ/SPY, top-N, rank-notional, exits, pocket "
            "pivot, signal-day breakout quality, moving averages, or live/default orders."
        ),
    ),
    AttributionSpec(
        experiment_id="exp-20260526-025",
        title="Kova Pre-Signal Moving-Average Structure Attribution",
        stem="kova_pre_signal_ma_structure_attribution",
        decision_prefix="ma_structure",
        changed_variable="pre_signal_ma_structure_bucket_v1",
        bucket_field="pre_signal_ma_structure_bucket_v1",
        bucket_order=MA_BUCKETS,
        target_bucket=MA_BULLISH,
        rule_version="pre_signal_ma_structure_v1",
        trial_family="vcp_kova_moving_average_structure_attribution",
        trial_variant_id="pre_signal_ma_stack",
        change_type="kova_pre_signal_ma_structure_attribution",
        new_evidence_type="new_production_visible_daily_ohlcv_ma_structure_field",
        hypothesis=(
            "Kova-style moving-average structure before an accepted VCP breakout "
            "may identify leaders with better replacement value inside the "
            "default-off VCP top-2 rank-notional paper sleeve."
        ),
        field_definition={
            "target_bucket": MA_BULLISH,
            "bullish_ma_stack": "last pre-signal close > SMA10 > SMA21 > SMA50",
            "date_boundary": "uses only rows with Date < signal_date",
        },
        context_fn=compute_ma_structure_context,
        why_not_other_changes=(
            "Did not retune VCP, QQQ/SPY, top-N, rank-notional, exits, pocket "
            "pivot, signal-day breakout quality, weekly tightness, or live/default orders."
        ),
    ),
]


def _trade_samples(rows: list[dict[str, Any]], spec: AttributionSpec) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        sample = {
            "window": row.get("window"),
            "ticker": row.get("ticker"),
            "signal_date": row.get("signal_date") or row.get("date"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "rank": row.get("vcp_candidate_rank_on_signal_date"),
            "bucket": row.get(spec.bucket_field),
            "pnl": _round(row.get("pnl"), 2),
            "pnl_pct_net": _round(row.get("pnl_pct_net"), 6),
        }
        for key in (
            "signal_day_volume_ratio_20",
            "signal_day_close_location",
            "three_week_tight_close_spread",
            "three_week_tight_max_abs_weekly_return",
            "pre_signal_close_vs_sma50_pct",
            "pre_signal_sma10_vs_sma50_pct",
        ):
            if key in row:
                sample[key] = row.get(key)
        out.append(sample)
    return out


def _trade_summary(rows: list[dict[str, Any]], spec: AttributionSpec) -> dict[str, Any]:
    pnl_values = [float(row.get("pnl") or 0.0) for row in rows]
    by_ticker_pnl: Counter[str] = Counter()
    by_window_count: Counter[str] = Counter()
    by_rank_count: Counter[str] = Counter()
    for row, pnl in zip(rows, pnl_values):
        by_ticker_pnl[str(row.get("ticker") or "").upper()] += pnl
        by_window_count[str(row.get("window") or "")] += 1
        by_rank_count[str(row.get("vcp_candidate_rank_on_signal_date") or "")] += 1
    positive_by_ticker = {
        ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0
    }
    positive_total = sum(positive_by_ticker.values())
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnl_values), 2),
        "avg_pnl": _round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
        "win_rate": _round(
            sum(1 for value in pnl_values if value > 0) / len(pnl_values),
            6,
        )
        if pnl_values
        else None,
        "by_window_count": dict(sorted(by_window_count.items())),
        "by_rank_count": dict(sorted(by_rank_count.items())),
        "by_ticker_pnl": {
            ticker: _round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "max_single_positive_pnl_share": _round(
            max(positive_by_ticker.values()) / positive_total,
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "positive_pnl_hhi": _round(
            sum((pnl / positive_total) ** 2 for pnl in positive_by_ticker.values()),
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "worst_trades": _trade_samples(sorted(rows, key=lambda row: row.get("pnl") or 0.0)[:5], spec),
        "best_trades": _trade_samples(
            sorted(rows, key=lambda row: row.get("pnl") or 0.0, reverse=True)[:5],
            spec,
        ),
    }


def _group_by_bucket(rows: list[dict[str, Any]], spec: AttributionSpec) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(spec.bucket_field) or "unavailable")].append(row)
    return OrderedDict((bucket, _trade_summary(grouped.get(bucket, []), spec)) for bucket in spec.bucket_order)


def _group_by_window_bucket(
    rows_by_window: dict[str, list[dict[str, Any]]],
    spec: AttributionSpec,
) -> dict[str, Any]:
    out: "OrderedDict[str, Any]" = OrderedDict()
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        out[label] = {
            "all_top2_rank_profile_trades": _trade_summary(rows, spec),
            "by_bucket": _group_by_bucket(rows, spec),
        }
    return out


def _enrich_trades(
    source: dict[str, Any],
    spec: AttributionSpec,
) -> dict[str, list[dict[str, Any]]]:
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        snapshot = _load_snapshot(cfg["snapshot"])
        source_rows = source["target_trades_by_window"].get(label, [])
        enriched: list[dict[str, Any]] = []
        for trade in source_rows:
            ticker = str(trade.get("ticker") or "").upper()
            context = spec.context_fn(snapshot.get(ticker, []), trade)
            enriched.append({**trade, "window": label, **context})
        out[label] = enriched
    return out


def _decision(
    all_rows: list[dict[str, Any]],
    by_bucket: dict[str, Any],
    by_window_bucket: dict[str, Any],
    spec: AttributionSpec,
) -> tuple[str, str, dict[str, Any]]:
    target = by_bucket[spec.target_bucket]
    other_rows = [row for row in all_rows if row.get(spec.bucket_field) != spec.target_bucket]
    other = _trade_summary(other_rows, spec)
    target_pnls_by_window = {
        label: by_window_bucket[label]["by_bucket"][spec.target_bucket]["total_pnl"]
        for label in WINDOWS
    }
    target_counts_by_window = {
        label: by_window_bucket[label]["by_bucket"][spec.target_bucket]["trade_count"]
        for label in WINDOWS
    }
    positive_target_windows = [
        label for label, pnl in target_pnls_by_window.items() if pnl is not None and pnl > 0
    ]
    concentration_passed = (
        target["max_single_positive_pnl_share"] is not None
        and target["positive_pnl_hhi"] is not None
        and target["max_single_positive_pnl_share"] < 0.40
        and target["positive_pnl_hhi"] < 0.30
    )
    target_avg = target["avg_pnl"]
    other_avg = other["avg_pnl"]
    promising = (
        target["trade_count"] >= 20
        and target["total_pnl"] is not None
        and target["total_pnl"] > 0
        and target_avg is not None
        and other_avg is not None
        and target_avg > other_avg
        and len(positive_target_windows) >= 2
        and concentration_passed
    )
    evidence = {
        "target_bucket": spec.target_bucket,
        "target_trade_count_min_20": target["trade_count"] >= 20,
        "target_positive_aggregate": target["total_pnl"] is not None and target["total_pnl"] > 0,
        "target_positive_windows": positive_target_windows,
        "target_trade_counts_by_window": target_counts_by_window,
        "target_avg_pnl": _round(target_avg, 2),
        "other_avg_pnl": _round(other_avg, 2),
        "target_beats_other_avg_pnl": (
            target_avg is not None and other_avg is not None and target_avg > other_avg
        ),
        "target_concentration_passed": concentration_passed,
        "target_max_single_positive_pnl_share": target["max_single_positive_pnl_share"],
        "target_positive_pnl_hhi": target["positive_pnl_hhi"],
    }
    if promising:
        return (
            f"observed_only_promising_{spec.decision_prefix}_attribution",
            (
                f"The `{spec.target_bucket}` bucket cleared the observed-only "
                "attribution bar. This can justify a later forward/replacement-value "
                "test, but no allocation change is made here."
            ),
            evidence,
        )
    return (
        f"observed_only_no_actionable_{spec.decision_prefix}_split",
        (
            f"The `{spec.target_bucket}` bucket did not clear the observed-only "
            "attribution bar. Keep the VCP top-2 rank-notional sleeve unchanged "
            "and do not turn this frozen-sample split into a gate."
        ),
        evidence,
    )


def _paths(spec: AttributionSpec) -> dict[str, Path]:
    return {
        "out_dir": REPO_ROOT / "data" / "experiments" / spec.experiment_id,
        "out_json": REPO_ROOT
        / "data"
        / "experiments"
        / spec.experiment_id
        / f"{spec.stem}.json",
        "log_json": REPO_ROOT / "experiments" / "logs" / f"{spec.experiment_id}.json",
        "ticket_json": REPO_ROOT / "experiments" / "tickets" / f"{spec.experiment_id}.json",
        "docs_ticket_json": REPO_ROOT
        / "docs"
        / "experiments"
        / "tickets"
        / f"{spec.experiment_id}.json",
        "artifact_md": REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{spec.experiment_id}_{spec.stem}.md",
    }


def _build_payload(source: dict[str, Any], spec: AttributionSpec) -> dict[str, Any]:
    paths = _paths(spec)
    rows_by_window = _enrich_trades(source, spec)
    all_rows = _flatten(rows_by_window)
    by_bucket = _group_by_bucket(all_rows, spec)
    by_window_bucket = _group_by_window_bucket(rows_by_window, spec)
    decision, interpretation, decision_evidence = _decision(
        all_rows,
        by_bucket,
        by_window_bucket,
        spec,
    )
    source_variant = source["variant"]
    source_trade_count = sum(len(rows) for rows in source["target_trades_by_window"].values())
    open_positions_audit = _audit_open_positions()
    bucket_counts = {
        bucket: by_bucket[bucket]["trade_count"]
        for bucket in spec.bucket_order
        if by_bucket[bucket]["trade_count"]
    }
    created_at = _now()
    return {
        "experiment_id": spec.experiment_id,
        "status": "observed_only",
        "decision": decision,
        "created_at": created_at,
        "lane": "alpha_search",
        "registry_lane": "alpha_discovery",
        "trial_family": spec.trial_family,
        "trial_variant_id": spec.trial_variant_id,
        "change_type": spec.change_type,
        "changed_variable": spec.changed_variable,
        "rule_version": spec.rule_version,
        "summary": interpretation,
        "alpha_hypothesis": spec.hypothesis,
        "history_check": {
            "exp-20260525-022": "Accepted QQQ-confirmed VCP top-1 paper sleeve.",
            "exp-20260525-027": "Kova pocket-pivot support gate rejected versus exp022.",
            "exp-20260525-032": "Volume dry-up support did not become a replacement rule.",
            "exp-20260525-037": "Accepted default-off top-2 VCP paper expansion.",
            "exp-20260526-007": "Accepted top-2 rank-notional profile [1.0, 1.25].",
            "exp-20260526-022": "Pre-signal higher-low/base-geometry rejected as an actionable gate.",
        },
        "single_causal_variable": {
            "name": spec.changed_variable,
            "buckets": spec.bucket_order,
            **spec.field_definition,
            "known_at": "after_signal_date_close_before_next_open_paper_entry",
        },
        "acceptance_standard": {
            "promotion_allowed_in_this_experiment": False,
            "reason": "Observed-only metadata attribution on a frozen source sleeve.",
            "promising_attribution_gate": (
                "target bucket has >=20 trades, positive aggregate PnL, positive PnL "
                "in at least two windows, better average PnL than the rest of the sleeve, "
                "max single positive contribution <40%, and positive PnL HHI <0.30"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
        },
        "gate1": {
            "passed": True,
            "baseline_core_stack": "exp-20260517-009 accepted core stack",
            "source_paper_baseline": "exp-20260526-007 rank2_125 VCP top-2 paper sleeve",
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get(
                    "expected_value_score_delta"
                ),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": source_trade_count,
                "target_trade_summary": source_variant.get("target_trade_summary"),
            },
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_ohlcv_fields": ["Date", "Open", "High", "Low", "Close", "Volume"],
            "required_market_confirmation_fields": ["SPY", "QQQ"],
            "field_completeness": {
                "source_trade_count": source_trade_count,
                "enriched_trade_count": len(all_rows),
                "unavailable_context_count": by_bucket.get("unavailable", {}).get(
                    "trade_count",
                    0,
                ),
            },
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "source_paper_survival_changed": False,
            "note": "Observed-only attribution on already selected exp007 paper trades.",
        },
        "gate4": {
            "passed": False,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": "Observed-only metadata attribution; no strategy behavior changed.",
            "decision_evidence": decision_evidence,
        },
        "source_trade_count": source_trade_count,
        "enriched_trade_count": len(all_rows),
        "bucket_counts": bucket_counts,
        "by_bucket": by_bucket,
        "by_window_bucket": by_window_bucket,
        "target_trades_by_window": rows_by_window,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "metadata_surface_changed": False,
            "read_only_attribution": True,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "multiple_testing_risk_bucket": "moderate",
        "prior_trial_count": 9,
        "nearby_prior_experiments": list(
            {
                "exp-20260525-022",
                "exp-20260525-027",
                "exp-20260525-032",
                "exp-20260525-037",
                "exp-20260526-007",
                "exp-20260526-022",
            }
        ),
        "new_evidence_type": spec.new_evidence_type,
        "why_not_other_changes": spec.why_not_other_changes,
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_023_kova_remaining_ohlcv_attributions.py"
        ),
        "artifacts": {
            "json": _repo_rel(paths["out_json"]),
            "markdown": _repo_rel(paths["artifact_md"]),
            "log": _repo_rel(paths["log_json"]),
            "ticket": _repo_rel(paths["ticket_json"]),
            "docs_ticket": _repo_rel(paths["docs_ticket_json"]),
        },
        "related_files": [
            _repo_rel(RUNNER),
            _repo_rel(TEST_FILE),
            _repo_rel(SOURCE_EXP007_JSON),
            _repo_rel(paths["out_json"]),
            _repo_rel(paths["artifact_md"]),
            _repo_rel(paths["log_json"]),
            _repo_rel(paths["ticket_json"]),
            _repo_rel(paths["docs_ticket_json"]),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def _bucket_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| bucket | trades | total pnl | avg pnl | win rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for bucket, summary in payload["by_bucket"].items():
        lines.append(
            "| {bucket} | {trades} | {pnl} | {avg} | {win} |".format(
                bucket=bucket,
                trades=summary["trade_count"],
                pnl=summary["total_pnl"],
                avg=summary["avg_pnl"],
                win=summary["win_rate"],
            )
        )
    return lines


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | bucket | trades | total pnl | avg pnl | win rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, row in payload["by_window_bucket"].items():
        for bucket, summary in row["by_bucket"].items():
            if summary["trade_count"] == 0:
                continue
            lines.append(
                "| {label} | {bucket} | {trades} | {pnl} | {avg} | {win} |".format(
                    label=label,
                    bucket=bucket,
                    trades=summary["trade_count"],
                    pnl=summary["total_pnl"],
                    avg=summary["avg_pnl"],
                    win=summary["win_rate"],
                )
            )
    return lines


def _build_report(payload: dict[str, Any], spec: AttributionSpec) -> str:
    target = payload["by_bucket"][spec.target_bucket]
    return "\n".join(
        [
            f"# {spec.experiment_id} {spec.title}",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            payload["summary"],
            "",
            "## Source",
            "",
            "- Source population: `exp-20260526-007` `rank2_125` selected paper trades.",
            "- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.",
            f"- Tested field: `{spec.changed_variable}`.",
            "",
            "## Aggregate Buckets",
            "",
            *_bucket_table(payload),
            "",
            "## Window Buckets",
            "",
            *_window_table(payload),
            "",
            "## Target Bucket Readout",
            "",
            f"- Target bucket: `{spec.target_bucket}`.",
            f"- Target trades: `{target['trade_count']}`.",
            f"- Target total PnL: `{target['total_pnl']}`.",
            f"- Target average PnL: `{target['avg_pnl']}`.",
            f"- Max single positive PnL share: `{target['max_single_positive_pnl_share']}`.",
            f"- Positive PnL HHI: `{target['positive_pnl_hhi']}`.",
            "",
            "## Gate 4",
            "",
            "No strategy promotion was possible in this experiment because this is read-only attribution.",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Repro",
            "",
            "```powershell",
            payload["repro_command"],
            "```",
            "",
        ]
    )


def _update_registry(payload: dict[str, Any], spec: AttributionSpec) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    paths = _paths(spec)
    for row in experiments:
        if not isinstance(row, dict) or row.get("experiment_id") != spec.experiment_id:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": row.get("lane") or payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(paths["ticket_json"]),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(paths["artifact_md"]),
                    "json": _repo_rel(paths["out_json"]),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": spec.experiment_id,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(paths["ticket_json"]),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(paths["artifact_md"]),
                    "json": _repo_rel(paths["out_json"]),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _jsonl_contains_experiment(path: Path, experiment_id: str) -> bool:
    if not path.exists():
        return False
    needle = f'"experiment_id": "{experiment_id}"'
    compact_needle = f'"experiment_id":"{experiment_id}"'
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            if needle in line or compact_needle in line:
                return True
    return False


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload["experiment_id"])
    if _jsonl_contains_experiment(path, experiment_id):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True) + "\n")


def _persist(payload: dict[str, Any], spec: AttributionSpec) -> None:
    paths = _paths(spec)
    _write_json(paths["out_json"], payload)
    _write_json(paths["log_json"], payload)
    ticket_payload = {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "registry_lane": payload["registry_lane"],
        "owner": "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "volatility_contraction_breakout",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": payload["related_files"]
        + [
            _repo_rel(EXPERIMENT_REGISTRY),
            _repo_rel(Path("docs/current_state.md")),
            _repo_rel(Path("docs/alpha-optimization-playbook.md")),
        ],
        "must_not_touch": [
            "quant/volatility_contraction_paper_sleeve.py",
            "quant/run.py",
            "quant/backtester.py",
        ],
        "locked_variables": [
            "core entries",
            "VCP compression and breakout",
            "QQQ/SPY gate",
            "top2 selection",
            "rank-notional profile",
            "sizing",
            "exits",
            "LLM/news",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "created_at": payload["created_at"],
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": payload["artifacts"]["markdown"],
            "json": payload["artifacts"]["json"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(paths["ticket_json"], ticket_payload)
    _write_json(paths["docs_ticket_json"], ticket_payload)
    _write_text(paths["artifact_md"], _build_report(payload, spec))
    _append_jsonl_once(EXPERIMENT_LOG, payload)
    _update_registry(payload, spec)


def main() -> None:
    source = _load_source_rank_profile()
    summaries = []
    for spec in SPECS:
        payload = _build_payload(source, spec)
        _persist(payload, spec)
        summaries.append(
            {
                "experiment_id": spec.experiment_id,
                "decision": payload["decision"],
                "bucket_counts": payload["bucket_counts"],
                "target_bucket": spec.target_bucket,
                "target_pnl": payload["by_bucket"][spec.target_bucket]["total_pnl"],
                "artifact": payload["artifacts"]["markdown"],
            }
        )
    print(json.dumps(summaries, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
