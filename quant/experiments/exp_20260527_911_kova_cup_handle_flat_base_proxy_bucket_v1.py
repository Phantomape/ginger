"""exp-20260527-911: Kova cup-with-handle / flat-base proxy attribution.

This read-only attribution asks whether the accepted exp-20260526-007 VCP
top-2 paper sleeve contains a useful Kova-style pre-breakout base shape:

- cup-with-handle proxy;
- flat-base proxy;
- deep or loose base proxy;
- no clear cup/flat proxy.

No entry, ranking, sizing, exit, universe, LLM/news, backtester, run.py, live
order, or default paper-order behavior is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    WINDOWS,
    _audit_open_positions,
    _date10,
    _load_json,
    _load_snapshot,
    _now,
    _num,
    _repo_rel,
    _safe,
    _write_json,
    _write_text,
)


EXPERIMENT_ID = "exp-20260527-911"
STEM = "kova_cup_handle_flat_base_proxy_bucket_v1"
OUT_JSON_NAME = "exp_20260527_911_kova_cup_handle_flat_base_proxy_bucket_v1.json"
TRIAL_FAMILY = "kova_cup_handle_flat_base_proxy_attribution"
CHANGED_VARIABLE = "kova_cup_handle_flat_base_proxy_bucket_v1"
RULE_VERSION = "kova_cup_flat_base_proxy_v1"
SOURCE_VARIANT = "rank2_125"

LOOKBACK_TRADING_DAYS = 80
MIN_PRIOR_ROWS = 45
HANDLE_LOOKBACK_DAYS = 12
FLAT_LOOKBACK_DAYS = 20
MIN_MATERIAL_BUCKET_TRADES = 20
MAX_SINGLE_POSITIVE_PNL_SHARE = 0.40
MIN_POSITIVE_WINDOWS = 2

BUCKET_CUP_HANDLE = "cup_with_handle_proxy"
BUCKET_FLAT_BASE = "flat_base_proxy"
BUCKET_DEEP_LOOSE = "deep_or_loose_base_proxy"
BUCKET_NO_CLEAR = "no_clear_cup_or_flat_base_proxy"
BUCKET_INSUFFICIENT = "insufficient_pre_signal_history"
BUCKET_UNAVAILABLE = "unavailable"
BUCKET_ORDER = [
    BUCKET_CUP_HANDLE,
    BUCKET_FLAT_BASE,
    BUCKET_DEEP_LOOSE,
    BUCKET_NO_CLEAR,
    BUCKET_INSUFFICIENT,
    BUCKET_UNAVAILABLE,
]

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / OUT_JSON_NAME
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    found = False
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for existing in handle:
                if experiment_id not in existing:
                    continue
                try:
                    row = json.loads(existing)
                except json.JSONDecodeError:
                    continue
                if row.get("experiment_id") == experiment_id:
                    found = True
                    break
    if not found:
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(line + "\n")
        return
    temp_path = path.with_name(path.name + f".{EXPERIMENT_ID}.tmp")
    with path.open("r", encoding="utf-8", errors="replace") as src, temp_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        replaced = False
        for existing in src:
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                dst.write(existing.rstrip("\n") + "\n")
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    dst.write(line + "\n")
                    replaced = True
                continue
            dst.write(existing.rstrip("\n") + "\n")
    try:
        temp_path.replace(path)
    except PermissionError:
        with temp_path.open("r", encoding="utf-8", errors="replace") as src, path.open(
            "w", encoding="utf-8", newline=""
        ) as dst:
            for chunk in src:
                dst.write(chunk)
        try:
            temp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


def _round(value: Any, digits: int = 4) -> Any:
    number = _num(value)
    if number is None:
        return None
    return round(number, digits)


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _source_trade_rows(source: dict[str, Any]) -> "OrderedDict[str, list[dict[str, Any]]]":
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        out[label] = [
            {**row, "window": label}
            for row in source["target_trades_by_window"].get(label, [])
        ]
    return out


def _row_date(row: dict[str, Any]) -> str:
    return _date10(row.get("Date") if "Date" in row else row.get("date"))


def _field(row: dict[str, Any], name: str) -> float | None:
    value = row.get(name)
    if value is None:
        value = row.get(name.lower())
    return _num(value)


def _load_ohlcv_by_window() -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {label: _load_snapshot(cfg["snapshot"]) for label, cfg in WINDOWS.items()}


def _safe_max(values: list[float]) -> float | None:
    return max(values) if values else None


def _safe_min(values: list[float]) -> float | None:
    return min(values) if values else None


def _range_drawdown(rows: list[dict[str, Any]]) -> float | None:
    highs = [_field(row, "High") for row in rows]
    lows = [_field(row, "Low") for row in rows]
    highs = [value for value in highs if value is not None and value > 0]
    lows = [value for value in lows if value is not None and value > 0]
    high = _safe_max(highs)
    low = _safe_min(lows)
    if high is None or low is None or high <= 0:
        return None
    return (high - low) / high


def _close_range(rows: list[dict[str, Any]]) -> float | None:
    closes = [_field(row, "Close") for row in rows]
    closes = [value for value in closes if value is not None and value > 0]
    high = _safe_max(closes)
    low = _safe_min(closes)
    if high is None or low is None or high <= 0:
        return None
    return (high - low) / high


def _index_of_min(values: list[float]) -> int:
    return min(range(len(values)), key=lambda idx: values[idx])


def _shape_context(
    trade: dict[str, Any],
    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    window = str(trade.get("window") or "")
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    signal_close = _num(trade.get("close") if "close" in trade else trade.get("Close"))
    base_pnl = _num(trade.get("pnl")) or 0.0
    notional = _num(trade.get("paper_notional_usd")) or 0.0
    bars = ohlcv_by_window.get(window, {}).get(ticker, [])
    prior_rows = [row for row in bars if _row_date(row) < signal_date]
    prior_rows = prior_rows[-LOOKBACK_TRADING_DAYS:]
    base = {
        "window": window,
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": _date10(trade.get("entry_date")),
        "exit_date": _date10(trade.get("exit_date")),
        "pnl": round(base_pnl, 4),
        "paper_notional_usd": round(notional, 4),
        "pnl_pct_net": round(base_pnl / notional, 6) if notional else None,
        "bucket": BUCKET_UNAVAILABLE,
        CHANGED_VARIABLE: BUCKET_UNAVAILABLE,
        "available": False,
        "reason": None,
        "alters_orders": False,
        "trade_enabled": False,
        "rule_version": RULE_VERSION,
        "known_at": (
            "after_signal_date_close_before_next_open_paper_entry; "
            "uses only ticker OHLCV rows with Date < signal_date"
        ),
        "lookback_trading_days": LOOKBACK_TRADING_DAYS,
        "prior_row_count": len(prior_rows),
        "signal_close": _round(signal_close, 4),
    }
    if not bars:
        base["reason"] = "missing_ohlcv_rows"
        return base
    if signal_close is None or signal_close <= 0:
        base["reason"] = "missing_signal_close"
        return base
    if len(prior_rows) < MIN_PRIOR_ROWS:
        base.update(
            {
                "bucket": BUCKET_INSUFFICIENT,
                CHANGED_VARIABLE: BUCKET_INSUFFICIENT,
                "reason": "insufficient_pre_signal_history",
            }
        )
        return base

    highs = [_field(row, "High") for row in prior_rows]
    lows = [_field(row, "Low") for row in prior_rows]
    valid_pairs = [
        (idx, high, low)
        for idx, (high, low) in enumerate(zip(highs, lows))
        if high is not None and low is not None and high > 0 and low > 0
    ]
    if len(valid_pairs) < MIN_PRIOR_ROWS:
        base["reason"] = "missing_high_low_fields"
        return base

    numeric_highs = [float(high) for _, high, _ in valid_pairs]
    numeric_lows = [float(low) for _, _, low in valid_pairs]
    base_high = max(numeric_highs)
    base_low = min(numeric_lows)
    base_depth = (base_high - base_low) / base_high if base_high > 0 else None
    low_pair_idx = _index_of_min(numeric_lows)
    low_idx = valid_pairs[low_pair_idx][0]
    highs_before_low = [
        float(high)
        for idx, high, _ in valid_pairs
        if idx < low_idx and high is not None and high > 0
    ]
    highs_after_low = [
        float(high)
        for idx, high, _ in valid_pairs
        if idx >= low_idx and high is not None and high > 0
    ]
    left_high = _safe_max(highs_before_low)
    post_low_high = _safe_max(highs_after_low)
    handle_rows = prior_rows[-HANDLE_LOOKBACK_DAYS:]
    flat_rows = prior_rows[-FLAT_LOOKBACK_DAYS:]
    last_60_rows = prior_rows[-60:]
    handle_drawdown = _range_drawdown(handle_rows)
    flat_drawdown = _range_drawdown(flat_rows)
    flat_close_tightness = _close_range(flat_rows)
    last_60_high = _safe_max(
        [value for value in (_field(row, "High") for row in last_60_rows) if value is not None]
    )
    handle_high = _safe_max(
        [value for value in (_field(row, "High") for row in handle_rows) if value is not None]
    )
    handle_low = _safe_min(
        [value for value in (_field(row, "Low") for row in handle_rows) if value is not None]
    )
    handle_close_position = None
    if handle_high is not None and handle_low is not None and handle_high > handle_low:
        handle_close_position = (signal_close - handle_low) / (handle_high - handle_low)

    cup_sequence_ok = (
        left_high is not None
        and post_low_high is not None
        and low_idx >= 10
        and low_idx <= len(prior_rows) - 8
        and post_low_high >= left_high * 0.85
    )
    cup_depth_ok = base_depth is not None and 0.12 <= base_depth <= 0.42
    cup_recovery_ok = left_high is not None and signal_close >= left_high * 0.88
    handle_ok = (
        handle_drawdown is not None
        and 0.03 <= handle_drawdown <= 0.18
        and handle_close_position is not None
        and handle_close_position >= 0.50
    )
    cup_with_handle = cup_sequence_ok and cup_depth_ok and cup_recovery_ok and handle_ok

    flat_base = (
        base_depth is not None
        and base_depth <= 0.25
        and flat_drawdown is not None
        and flat_drawdown <= 0.12
        and flat_close_tightness is not None
        and flat_close_tightness <= 0.15
        and last_60_high is not None
        and signal_close >= last_60_high * 0.93
    )
    deep_or_loose = (
        (base_depth is not None and base_depth > 0.45)
        or (handle_drawdown is not None and handle_drawdown > 0.22)
        or (flat_drawdown is not None and flat_drawdown > 0.20)
    )

    if cup_with_handle:
        bucket = BUCKET_CUP_HANDLE
        reason = "cup_depth_recovery_and_handle_proxy_passed"
    elif flat_base:
        bucket = BUCKET_FLAT_BASE
        reason = "flat_base_tightness_proxy_passed"
    elif deep_or_loose:
        bucket = BUCKET_DEEP_LOOSE
        reason = "base_too_deep_or_loose_for_cup_flat_proxy"
    else:
        bucket = BUCKET_NO_CLEAR
        reason = "no_clear_cup_or_flat_proxy"

    base.update(
        {
            "bucket": bucket,
            CHANGED_VARIABLE: bucket,
            "available": True,
            "reason": reason,
            "base_high": _round(base_high, 4),
            "base_low": _round(base_low, 4),
            "base_depth": _round(base_depth, 6),
            "low_idx_from_lookback_start": low_idx,
            "left_high_before_low": _round(left_high, 4),
            "post_low_high": _round(post_low_high, 4),
            "signal_vs_left_high_pct": _round(
                signal_close / left_high - 1.0 if left_high else None,
                6,
            ),
            "handle_drawdown": _round(handle_drawdown, 6),
            "handle_close_position": _round(handle_close_position, 6),
            "flat_drawdown": _round(flat_drawdown, 6),
            "flat_close_tightness": _round(flat_close_tightness, 6),
            "last_60_high": _round(last_60_high, 4),
            "cup_sequence_ok": cup_sequence_ok,
            "cup_depth_ok": cup_depth_ok,
            "cup_recovery_ok": cup_recovery_ok,
            "handle_ok": handle_ok,
            "flat_base_ok": flat_base,
            "deep_or_loose_ok": deep_or_loose,
        }
    )
    return base


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    notionals = [float(row.get("paper_notional_usd") or 0.0) for row in rows]
    pct_returns = [
        pnl / notional
        for pnl, notional in zip(pnls, notionals)
        if notional and math.isfinite(pnl / notional)
    ]
    total_pnl = sum(pnls)
    total_notional = sum(notionals)
    ret_pct = total_pnl / total_notional if total_notional else 0.0
    if len(pct_returns) >= 2 and pstdev(pct_returns) > 0:
        trade_sharpe_proxy = mean(pct_returns) / pstdev(pct_returns) * math.sqrt(len(pct_returns))
    else:
        trade_sharpe_proxy = 0.0
    positive_pnls = [pnl for pnl in pnls if pnl > 0]
    positive_sum = sum(positive_pnls)
    max_single_positive_share = (
        max(positive_pnls) / positive_sum
        if positive_sum > 0 and positive_pnls
        else None
    )
    by_window_pnl = OrderedDict()
    for label in WINDOWS:
        by_window_pnl[label] = round(
            sum(float(row.get("pnl") or 0.0) for row in rows if row.get("window") == label),
            4,
        )
    return {
        "trade_count": len(rows),
        "total_pnl": round(total_pnl, 4),
        "total_notional": round(total_notional, 4),
        "return_on_notional": round(ret_pct, 6),
        "avg_pnl": round(total_pnl / len(rows), 4) if rows else 0.0,
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6) if pnls else 0.0,
        "trade_sharpe_proxy": round(trade_sharpe_proxy, 6),
        "expected_value_proxy": round(ret_pct * trade_sharpe_proxy, 6),
        "positive_windows": sum(1 for value in by_window_pnl.values() if value > 0),
        "by_window_pnl": by_window_pnl,
        "max_single_positive_pnl_share": round(max_single_positive_share, 6)
        if max_single_positive_share is not None
        else None,
    }


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = _metric_summary(rows)
    by_bucket: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    bucket_windows: "OrderedDict[str, OrderedDict[str, dict[str, Any]]]" = OrderedDict()
    for bucket in BUCKET_ORDER:
        bucket_rows = [row for row in rows if row.get("bucket") == bucket]
        summary = _metric_summary(bucket_rows)
        summary["pnl_share"] = round(
            summary["total_pnl"] / aggregate["total_pnl"], 6
        ) if aggregate["total_pnl"] else None
        by_bucket[bucket] = summary
        bucket_windows[bucket] = OrderedDict()
        for window in WINDOWS:
            bucket_windows[bucket][window] = _metric_summary(
                [row for row in bucket_rows if row.get("window") == window]
            )

    promising_buckets = []
    for bucket, summary in by_bucket.items():
        if bucket in {BUCKET_INSUFFICIENT, BUCKET_UNAVAILABLE}:
            continue
        concentration = summary["max_single_positive_pnl_share"]
        concentration_ok = concentration is not None and concentration < MAX_SINGLE_POSITIVE_PNL_SHARE
        if (
            summary["trade_count"] >= MIN_MATERIAL_BUCKET_TRADES
            and summary["total_pnl"] > 0
            and summary["positive_windows"] >= MIN_POSITIVE_WINDOWS
            and summary["expected_value_proxy"] > aggregate["expected_value_proxy"]
            and concentration_ok
        ):
            promising_buckets.append(bucket)

    return {
        "aggregate": aggregate,
        "by_bucket": by_bucket,
        "bucket_windows": bucket_windows,
        "classification_counts": dict(
            sorted(Counter(row.get("bucket") for row in rows).items())
        ),
        "promising_buckets": promising_buckets,
        "material_bucket_count": sum(
            1
            for bucket, summary in by_bucket.items()
            if bucket not in {BUCKET_INSUFFICIENT, BUCKET_UNAVAILABLE}
            and summary["trade_count"] >= MIN_MATERIAL_BUCKET_TRADES
        ),
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str]:
    aggregate = summary["aggregate"]
    promising = summary["promising_buckets"]
    textbook_buckets = {BUCKET_CUP_HANDLE, BUCKET_FLAT_BASE}
    promising_textbook = [bucket for bucket in promising if bucket in textbook_buckets]
    promising_inverse = [bucket for bucket in promising if bucket not in textbook_buckets]
    evidence = {
        "source_trade_count": aggregate["trade_count"],
        "source_total_pnl": aggregate["total_pnl"],
        "source_expected_value_proxy": aggregate["expected_value_proxy"],
        "material_bucket_count": summary["material_bucket_count"],
        "promising_buckets": promising,
        "promising_textbook_cup_flat_buckets": promising_textbook,
        "promising_inverse_or_non_textbook_buckets": promising_inverse,
        "min_material_bucket_trades": MIN_MATERIAL_BUCKET_TRADES,
        "min_positive_windows": MIN_POSITIVE_WINDOWS,
        "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE,
        "classification_counts": summary["classification_counts"],
        "promotion_grade": False,
        "playbook_frozen_sample_guard": True,
    }
    if promising_textbook:
        return (
            "observed_only_promising_kova_cup_flat_base_proxy_requires_forward_evidence",
            "observed_only",
            evidence,
            (
                "The Kova cup/flat-base proxy found at least one material "
                "bucket with better closed-trade EV proxy than the source "
                "aggregate, but this remains observed-only because the "
                "playbook freezes frozen-sample base-geometry promotion "
                "without new forward evidence."
            ),
        )
    if promising_inverse:
        return (
            "observed_only_inverse_kova_base_shape_signal_requires_forward_evidence",
            "observed_only",
            evidence,
            (
                "The textbook Kova cup/flat-base proxy was not the useful "
                "bucket; the only material outperforming bucket was the "
                "non-textbook deep/loose base proxy. Treat this as an inverse "
                "diagnostic clue, not as a production ranking or entry rule."
            ),
        )
    return (
        "observed_only_kova_cup_flat_base_proxy_not_actionable",
        "observed_only",
        evidence,
        (
            "The Kova cup/flat-base proxy did not produce a material, stable, "
            "low-concentration bucket that beats the source aggregate EV proxy. "
            "No base-shape rule should be promoted from this attribution."
        ),
    )


def _build_payload() -> dict[str, Any]:
    created_at = _now()
    source = _load_source_rank_profile()
    trades_by_window = _source_trade_rows(source)
    trades = [row for rows in trades_by_window.values() for row in rows]
    ohlcv_by_window = _load_ohlcv_by_window()
    attribution_rows = [_shape_context(trade, ohlcv_by_window) for trade in trades]
    summary = _summaries(attribution_rows)
    decision, status, evidence, summary_text = _decision(summary)
    open_positions_audit = _audit_open_positions()
    source_variant = source["variant"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": created_at,
        "status": status,
        "registry_lane": "alpha_discovery",
        "lane": "alpha_discovery",
        "decision": decision,
        "summary": summary_text,
        "alpha_hypothesis": (
            "Kova cup-with-handle and flat-base pre-breakout shape may explain "
            "which accepted VCP top-2 paper trades have better forward payoff, "
            "but should be measured as read-only attribution before any "
            "frozen-sample retune."
        ),
        "change_type": "read_only_kova_base_shape_attribution",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "parameters": {
            "lookback_trading_days": LOOKBACK_TRADING_DAYS,
            "min_prior_rows": MIN_PRIOR_ROWS,
            "handle_lookback_days": HANDLE_LOOKBACK_DAYS,
            "flat_lookback_days": FLAT_LOOKBACK_DAYS,
            "cup_depth_range": [0.12, 0.42],
            "cup_recovery_min_left_high_fraction": 0.88,
            "handle_drawdown_range": [0.03, 0.18],
            "flat_base_max_depth": 0.25,
            "flat_drawdown_max": 0.12,
            "flat_close_tightness_max": 0.15,
        },
        "acceptance_standard": (
            "Observed-only: require a bucket with >=20 trades, positive PnL "
            "in at least two canonical windows, expected_value_proxy above "
            "the source aggregate, and max single positive PnL share below "
            "40% before considering future forward evidence. No production "
            "promotion from this run."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Kova cup-with-handle or flat-base shape may identify better "
                "VCP breakout payoffs."
            ),
            "1_category": "ranking_attribution",
            "1_playbook_alignment": (
                "Aligned only as remaining Kova direction discovery; the "
                "playbook blocks frozen-sample base-geometry promotion without "
                "new evidence."
            ),
            "2_history_check": {
                "exp-20260526-022": "Higher-low base geometry attribution already exists.",
                "exp-20260526-023": "Adjacent base-shape/history work exists.",
                "exp-20260526-024": "Adjacent VCP base/risk context work exists.",
                "exp-20260526-025": "Adjacent VCP base/risk context work exists.",
                "exp-20260527-909": "Kova confirmation pyramid was rejected on risk-adjusted proxy.",
                "exp-20260527-910": "Kova fixed max-loss stop was rejected on PnL/EV regression.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Read-only attribution bucket: >=20 trades, positive PnL in "
                ">=2 windows, EV proxy above source aggregate, concentration <40%."
            ),
            "5_reproducibility": "Script writes JSON, markdown, ticket, log, and JSONL row.",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp007 source sleeve",
            "paper_exit": "10 trading days after signal from exp007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
            "attribution_only": True,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get("expected_value_score_delta"),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": len(trades),
                "target_trade_summary": source_variant.get("target_trade_summary"),
            },
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_open_position_fields": ["entry_date", "target_price"],
            "required_trade_fields": [
                "ticker",
                "signal_date",
                "entry_date",
                "exit_date",
                "paper_notional_usd",
                "pnl",
            ],
            "required_ohlcv_fields": ["Date", "Open", "High", "Low", "Close"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(trades),
            "source_survival_changed": False,
            "note": "No filter is added; this only assigns read-only pre-signal shape buckets.",
        },
        "gate4": {
            "passed": False,
            "attribution_gate_passed": bool(summary["promising_buckets"]),
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": (
                "Read-only frozen-sample base-shape attribution; no production "
                "strategy rule changed or promoted."
            ),
            "decision_evidence": evidence,
        },
        "source_metrics": summary["aggregate"],
        "bucket_metrics": summary["by_bucket"],
        "bucket_window_metrics": summary["bucket_windows"],
        "classification_counts": summary["classification_counts"],
        "promising_buckets": summary["promising_buckets"],
        "attribution_rows": attribution_rows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "attribution_only": True,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260527_911_kova_cup_handle_flat_base_proxy_bucket_v1.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "why_not_other_changes": (
            "Did not alter VCP entries, exits, rank-notional profile, ranking, "
            "universe, LLM/news, backtester, run.py, or live/default orders."
        ),
    }


def _bucket_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| bucket | trades | total pnl | ev proxy | win rate | positive windows | max single positive share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_metrics"].items():
        lines.append(
            "| {bucket} | {trades} | {pnl} | {ev} | {win} | {windows} | {share} |".format(
                bucket=bucket,
                trades=row["trade_count"],
                pnl=row["total_pnl"],
                ev=row["expected_value_proxy"],
                win=row["win_rate"],
                windows=row["positive_windows"],
                share=row["max_single_positive_pnl_share"],
            )
        )
    return lines


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| bucket | late_strong pnl | mid_weak pnl | old_thin pnl |",
        "|---|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_metrics"].items():
        by_window = row["by_window_pnl"]
        lines.append(
            "| {bucket} | {late} | {mid} | {old} |".format(
                bucket=bucket,
                late=by_window.get("late_strong"),
                mid=by_window.get("mid_weak"),
                old=by_window.get("old_thin"),
            )
        )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Kova Cup/Flat Base Proxy Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Source Aggregate",
        "",
        f"- Trades: `{payload['source_metrics']['trade_count']}`.",
        f"- Total PnL: `{payload['source_metrics']['total_pnl']}`.",
        f"- EV proxy: `{payload['source_metrics']['expected_value_proxy']}`.",
        f"- Return on notional: `{payload['source_metrics']['return_on_notional']}`.",
        "",
        "## Buckets",
        "",
        *_bucket_table(payload),
        "",
        "## Window PnL",
        "",
        *_window_table(payload),
        "",
        "## Gate 4",
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
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    for row in experiments:
        if not isinstance(row, dict):
            continue
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    existing = _existing_ticket()
    ticket_payload = {
        "experiment_id": payload["experiment_id"],
        "experiment_uid": existing.get("experiment_uid"),
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["registry_lane"],
        "owner": existing.get("owner") or "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "kova_base_shape_attribution",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 5),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_vcp_trade_base_shape_attribution",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_911_kova_cup_handle_flat_base_proxy_bucket_v1.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
        ],
        "must_not_touch": [
            "quant/backtester.py",
            "quant/run.py",
            "operator_inputs/open_positions.json",
            "data/experiments/exp-20260527-017/broad_market_sector_open_crowding_haircut.json",
        ],
        "locked_variables": [
            "Kova cup/flat-base proxy bucket only",
            "entries",
            "exits",
            "ranking",
            "sizing",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "created_at": existing.get("created_at", payload["created_at"]),
        "claimed_at": existing.get("claimed_at"),
        "completed_at": payload["created_at"],
        "prediction": existing.get("prediction"),
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
    _write_json(TICKET_JSON, ticket_payload)
    _write_json(DOCS_TICKET_JSON, ticket_payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "source_metrics": payload["source_metrics"],
                "classification_counts": payload["classification_counts"],
                "bucket_metrics": payload["bucket_metrics"],
                "promising_buckets": payload["promising_buckets"],
                "gate4": payload["gate4"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
