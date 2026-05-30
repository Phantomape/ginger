"""exp-20260530-016: catalyst-qualified pre-breakout momentum entry replay.

This alpha search tests one entry variable on top of the rejected
exp-20260530-013 early-entry scout: require a high-confidence non-OHLCV
catalyst inside the 10 calendar days before the near-breakout signal.

No shared production policy is changed by this runner.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260530-016"
STEM = "prebreakout_catalyst_qualified_entry"
TRIAL_FAMILY = "prebreakout_catalyst_qualified_entry"
TRIAL_VARIANT_ID = "high_confidence_catalyst_prebreakout_v1"
CHANGED_VARIABLE = "prebreakout_momentum_high_confidence_catalyst_required_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine, DEFAULT_CONFIG  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import feature_layer  # noqa: E402
import signal_engine  # noqa: E402
from exp_20260530_014_pre_entry_catalyst_attribution import (  # noqa: E402
    HIGH_CONFIDENCE_CATEGORIES,
    LOOKBACK_CALENDAR_DAYS,
    _event_index,
    _parse_date,
)


WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_016_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

MAX_DISTANCE_BELOW_20D_HIGH = 0.03
MIN_MOMENTUM_20D_PCT = 0.10
MIN_MOMENTUM_10D_PCT = 0.02
MIN_VOLUME_RATIO = 1.00
MIN_PRICE_VS_200MA_PCT = 0.03
MAX_ATR_OVER_CLOSE = 0.07
MIN_DAILY_CLOSE_LOCATION = 0.55
MIN_PCT_FROM_52W_HIGH = -0.08
MIN_RS_VS_SPY_10D = 0.00
MAX_DRAWDOWN_WORSE = 0.005


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(key): _safe(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_safe(value) for value in obj]
    if isinstance(obj, tuple):
        return [_safe(value) for value in obj]
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result_metrics(result: dict[str, Any]) -> dict[str, Any]:
    ret = result.get("strategy_total_return_pct")
    if ret is None:
        ret = (result.get("benchmarks") or {}).get("strategy_total_return_pct")
    if ret is None:
        ret = result.get("total_return_pct")
    trades = result.get("trade_count")
    if trades is None:
        trades = result.get("total_trades")
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(ret, 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": trades,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(after_value - before_value, 6)
    return out


def _prebreakout_signal(
    ticker: str,
    features: dict[str, Any],
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    close = _as_float(features.get("close"))
    atr = _as_float(features.get("atr"))
    high_20d = _as_float(features.get("high_20d"))
    if not close or not atr or not high_20d:
        return None

    if features.get("above_200ma") is not True:
        return None
    if features.get("breakout_20d") or features.get("breakdown_20d"):
        return None

    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 3:
        return None
    if atr / close > MAX_ATR_OVER_CLOSE:
        return None

    distance_to_20d_high = (close / high_20d) - 1.0
    m10 = _as_float(features.get("momentum_10d_pct"))
    m20 = _as_float(features.get("momentum_20d_pct"))
    vol = _as_float(features.get("volume_spike_ratio"))
    p200 = _as_float(features.get("price_vs_200ma_pct"))
    close_location = _as_float(features.get("daily_close_location"))
    pct52 = _as_float(features.get("pct_from_52w_high"))
    spy10 = _as_float((market_context or {}).get("spy_10d_return")) or 0.0

    required = (
        -MAX_DISTANCE_BELOW_20D_HIGH <= distance_to_20d_high < 0.0
        and m20 is not None
        and m20 >= MIN_MOMENTUM_20D_PCT
        and m10 is not None
        and m10 >= MIN_MOMENTUM_10D_PCT
        and m10 - spy10 >= MIN_RS_VS_SPY_10D
        and vol is not None
        and vol >= MIN_VOLUME_RATIO
        and p200 is not None
        and p200 >= MIN_PRICE_VS_200MA_PCT
        and close_location is not None
        and close_location >= MIN_DAILY_CLOSE_LOCATION
        and pct52 is not None
        and pct52 >= MIN_PCT_FROM_52W_HIGH
    )
    if not required:
        return None

    checks = [
        (True, 1.0),
        (m20 >= 0.15, 0.25),
        (m10 - spy10 >= 0.02, 0.25),
        (distance_to_20d_high >= -0.015, 0.25),
        (vol >= 1.20, 0.20),
        (close_location >= 0.70, 0.20),
        (pct52 >= -0.05, 0.20),
    ]
    total_weight = sum(weight for _, weight in checks)
    true_weight = sum(weight for passed, weight in checks if passed)
    confidence = round(true_weight / total_weight, 2)
    if (market_context or {}).get("market_regime", "").upper() == "NEUTRAL" and confidence <= 0.88:
        return None

    stop = round(close - ATR_STOP_MULT * atr, 2)
    return {
        "ticker": ticker,
        "strategy": "prebreakout_momentum_long",
        "entry_price": round(close, 2),
        "stop_price": stop,
        "confidence_score": confidence,
        "entry_note": (
            "Execute next-day open; cancel if open > entry_price x 1.015 "
            "or open < entry_price x 0.980"
        ),
        "conditions_met": {
            "above_200ma": True,
            "breakout_20d": False,
            "breakdown_20d": False,
            "distance_to_20d_high": _round(distance_to_20d_high, 6),
            "max_distance_below_20d_high": MAX_DISTANCE_BELOW_20D_HIGH,
            "momentum_10d_pct": m10,
            "momentum_20d_pct": m20,
            "rs_vs_spy_10d": _round(m10 - spy10, 6),
            "volume_spike_ratio": vol,
            "price_vs_200ma_pct": p200,
            "daily_close_location": close_location,
            "pct_from_52w_high": pct52,
            "prebreakout_rule": (
                "close within 0-3% below prior 20d high, not already breakout, "
                "m20>=10%, m10>=2%, vol>=20d average, above200>=3%, "
                "close location>=55%, pct52>=-8%, dte>3"
            ),
        },
    }


def _bear_deep_market(market_context: dict[str, Any] | None) -> bool:
    context = market_context or {}
    if str(context.get("market_regime") or "").upper() != "BEAR":
        return False
    spy_pct = _as_float(context.get("spy_pct_from_ma"))
    qqq_pct = _as_float(context.get("qqq_pct_from_ma"))
    if spy_pct is None or qqq_pct is None:
        return True
    return min(spy_pct, qqq_pct) <= -0.05


def _install_signal_date_features():
    original = feature_layer.compute_features

    def patched_compute_features(ticker, ohlcv_data, earnings_data):
        features = original(ticker, ohlcv_data, earnings_data)
        if features and ohlcv_data is not None and len(ohlcv_data):
            features["_signal_date"] = str(ohlcv_data.index[-1].date())
        return features

    feature_layer.compute_features = patched_compute_features
    return original


def _has_high_confidence_catalyst(
    event_index: dict[str, dict[Any, list[dict[str, Any]]]],
    ticker: str,
    signal_date_text: Any,
) -> tuple[bool, list[dict[str, Any]]]:
    signal_date = _parse_date(signal_date_text)
    if signal_date is None:
        return False, []
    start = signal_date - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    cursor = start
    events: list[dict[str, Any]] = []
    while cursor <= signal_date:
        events.extend(event_index.get(ticker.upper(), {}).get(cursor, []))
        cursor += timedelta(days=1)
    high_conf = [
        event
        for event in events
        if event.get("high_confidence")
        and event.get("category") in HIGH_CONFIDENCE_CATEGORIES
    ]
    return bool(high_conf), sorted(
        high_conf,
        key=lambda row: (row.get("date") or "", row.get("category") or ""),
    )


def _install_prebreakout_strategy(event_index: dict[str, dict[Any, list[dict[str, Any]]]]):
    original = signal_engine.generate_signals

    def patched_generate_signals(
        features_dict,
        market_context=None,
        enabled_strategies=None,
        breakout_max_pullback_from_52w_high=None,
    ):
        signals = original(
            features_dict,
            market_context=market_context,
            enabled_strategies=enabled_strategies,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )
        if _bear_deep_market(market_context):
            return signals

        for ticker, features in features_dict.items():
            if features:
                has_catalyst, catalyst_events = _has_high_confidence_catalyst(
                    event_index,
                    ticker,
                    features.get("_signal_date"),
                )
                if not has_catalyst:
                    continue
                signal = _prebreakout_signal(ticker, features, market_context)
                if signal:
                    signal["conditions_met"]["high_confidence_pre_entry_catalyst"] = True
                    signal["conditions_met"]["pre_entry_catalyst_lookback_days"] = (
                        LOOKBACK_CALENDAR_DAYS
                    )
                    signal["conditions_met"]["pre_entry_catalyst_categories"] = sorted(
                        {event.get("category") for event in catalyst_events}
                    )
                    signal["conditions_met"]["pre_entry_catalyst_count"] = len(
                        catalyst_events
                    )
                    signal["conditions_met"]["signal_date"] = features.get("_signal_date")
                    signal["pre_entry_catalyst_examples"] = catalyst_events[:5]
                    signals.append(signal)

        best: dict[str, dict[str, Any]] = {}
        for signal in signals:
            ticker = str(signal.get("ticker") or "")
            if (
                ticker not in best
                or float(signal.get("confidence_score") or 0)
                > float(best[ticker].get("confidence_score") or 0)
            ):
                best[ticker] = signal
        return sorted(
            best.values(),
            key=lambda signal: float(signal.get("confidence_score") or 0),
            reverse=True,
        )

    signal_engine.generate_signals = patched_generate_signals
    return original


def _run_window(
    universe: list[str],
    window: dict[str, str],
    *,
    with_prebreakout: bool,
    event_index: dict[str, dict[Any, list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    original_generate = None
    original_compute = None
    if with_prebreakout:
        original_compute = _install_signal_date_features()
        original_generate = _install_prebreakout_strategy(event_index or {})
    try:
        engine = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            config=dict(DEFAULT_CONFIG),
            ohlcv_snapshot_path=window["snapshot"],
        )
        result = engine.run()
    finally:
        if original_generate is not None:
            signal_engine.generate_signals = original_generate
        if original_compute is not None:
            feature_layer.compute_features = original_compute
    return result


def _aggregate(by_window: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(float(row[key]["expected_value_score"] or 0.0) for row in by_window.values()),
            4,
        ),
        "strategy_total_return_pct_sum": _round(
            sum(float(row[key]["strategy_total_return_pct"] or 0.0) for row in by_window.values()),
            4,
        ),
        "total_pnl_sum": _round(
            sum(float(row[key]["total_pnl"] or 0.0) for row in by_window.values()),
            2,
        ),
        "trade_count_sum": sum(int(row[key]["trade_count"] or 0) for row in by_window.values()),
        "signals_generated_sum": sum(
            int(row[key]["signals_generated"] or 0) for row in by_window.values()
        ),
        "signals_survived_sum": sum(
            int(row[key]["signals_survived"] or 0) for row in by_window.values()
        ),
        "min_survival_rate": _round(
            min(float(row[key]["survival_rate"] or 0.0) for row in by_window.values()),
            4,
        ),
        "max_drawdown_pct_max": _round(
            max(float(row[key]["max_drawdown_pct"] or 0.0) for row in by_window.values()),
            4,
        ),
    }


def _aggregate_delta(after_aggregate: dict[str, Any], before_aggregate: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before_aggregate.items():
        after_value = after_aggregate.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[f"{key}_delta"] = _round(after_value - before_value, 6)
    return out


def _aggregate_for_judge(aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": aggregate["expected_value_score_sum"],
        "benchmarks": {
            "strategy_total_return_pct": aggregate["strategy_total_return_pct_sum"],
        },
        "sharpe_daily": None,
        "max_drawdown_pct": aggregate["max_drawdown_pct_max"],
        "win_rate": None,
        "total_trades": aggregate["trade_count_sum"],
        "survival_rate": aggregate["min_survival_rate"],
        "total_pnl": aggregate["total_pnl_sum"],
    }


def _gate(by_window: dict[str, Any], aggregate_delta: dict[str, Any]) -> dict[str, Any]:
    checks = {label: row["delta"] for label, row in by_window.items()}
    ev_positive = sum(1 for row in checks.values() if row.get("expected_value_score", 0) > 0)
    ev_regressed = sum(1 for row in checks.values() if row.get("expected_value_score", 0) < 0)
    pnl_positive = sum(1 for row in checks.values() if row.get("total_pnl", 0) > 0)
    pnl_regressed = sum(1 for row in checks.values() if row.get("total_pnl", 0) < 0)
    survival_after_min = min(
        float(row["after"]["survival_rate"] or 0.0) for row in by_window.values()
    )
    drawdown_delta_max = max(
        float(row["delta"].get("max_drawdown_pct", 0.0) or 0.0)
        for row in by_window.values()
    )
    passed = (
        aggregate_delta.get("expected_value_score_sum_delta", 0) > 0
        and aggregate_delta.get("total_pnl_sum_delta", 0) > 0
        and ev_positive == len(by_window)
        and ev_regressed == 0
        and pnl_positive == len(by_window)
        and pnl_regressed == 0
        and survival_after_min >= 0.05
        and drawdown_delta_max <= MAX_DRAWDOWN_WORSE
    )
    failed_reasons: list[str] = []
    if aggregate_delta.get("expected_value_score_sum_delta", 0) <= 0:
        failed_reasons.append("aggregate_ev_not_positive")
    if aggregate_delta.get("total_pnl_sum_delta", 0) <= 0:
        failed_reasons.append("aggregate_pnl_not_positive")
    if ev_positive != len(by_window) or ev_regressed:
        failed_reasons.append("not_all_windows_ev_positive")
    if pnl_positive != len(by_window) or pnl_regressed:
        failed_reasons.append("not_all_windows_pnl_positive")
    if survival_after_min < 0.05:
        failed_reasons.append("survival_below_5pct")
    if drawdown_delta_max > MAX_DRAWDOWN_WORSE:
        failed_reasons.append("max_drawdown_worse_than_0_5pp")
    return {
        "passed": passed,
        "ev_positive_windows": ev_positive,
        "ev_regressed_windows": ev_regressed,
        "pnl_positive_windows": pnl_positive,
        "pnl_regressed_windows": pnl_regressed,
        "survival_after_min": _round(survival_after_min, 4),
        "max_drawdown_delta_max": _round(drawdown_delta_max, 6),
        "window_deltas": checks,
        "failed_reasons": failed_reasons,
        "rule": (
            "Pass only if aggregate EV/PnL improve, all three canonical windows "
            "improve on EV and PnL, survival stays >=5%, and max drawdown does "
            "not worsen by more than 0.5 percentage points."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Catalyst-Qualified Pre-Breakout Entry",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Aggregate EV delta: `{payload['delta_metrics']['aggregate']['expected_value_score_sum_delta']}`",
        f"- Aggregate PnL delta: `{payload['delta_metrics']['aggregate']['total_pnl_sum_delta']}`",
        f"- Gate 4 passed: `{payload['gate4']['passed']}`",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Max DD delta | Trades delta | Signals survived delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["windows"].items():
        delta = row["delta"]
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{delta.get('expected_value_score', 0):.4f} | "
            f"${delta.get('total_pnl', 0):,.2f} | "
            f"{delta.get('max_drawdown_pct', 0):.4f} | "
            f"{delta.get('trade_count', 0)} | "
            f"{delta.get('signals_survived', 0)} |"
        )
    lines.extend(
        [
            "",
            "This runner is replay-only. It temporarily injects the entry source "
            "inside signal generation and does not alter production code. A "
            "positive replay is not production-retained unless the same catalyst "
            "requirement is moved to a shared path in a separate change.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    timestamp = _utc_now()
    universe = get_universe()
    catalyst_index, catalyst_source_coverage = _event_index()
    windows: dict[str, Any] = {}
    for label, window in WINDOWS.items():
        before = _result_metrics(_run_window(universe, window, with_prebreakout=False))
        after = _result_metrics(
            _run_window(
                universe,
                window,
                with_prebreakout=True,
                event_index=catalyst_index,
            )
        )
        windows[label] = {
            "before": before,
            "after": after,
            "delta": _delta(after, before),
        }

    before_aggregate = _aggregate(windows, "before")
    after_aggregate = _aggregate(windows, "after")
    aggregate_delta = _aggregate_delta(after_aggregate, before_aggregate)
    gate4 = _gate(windows, aggregate_delta)
    decision = (
        "accepted_prebreakout_catalyst_qualified_entry_replay"
        if gate4["passed"]
        else "rejected_prebreakout_catalyst_qualified_entry"
    )
    status = "accepted" if gate4["passed"] else "rejected"
    actual_success = 1 if gate4["passed"] else 0

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "hypothesis": (
            "Catalyst-qualified near-breakout momentum candidates may recover "
            "SNOW-like entry latency while avoiding the false positives that "
            "killed the OHLCV-only prebreakout entry."
        ),
        "change_type": "entry_candidate_pool_alpha_search",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": (
            "Require high-confidence pre-entry catalyst context on the "
            "prebreakout momentum candidate source; no sizing, exit, ranking, "
            "universe, LLM/news, market-regime, or execution-cancel changes."
        ),
        "parameters": {
            "entry_shape": {
                "above_200ma": True,
                "exclude_breakout_20d": True,
                "exclude_breakdown_20d": True,
                "distance_to_prior_20d_high": "[-0.03, 0.0)",
                "momentum_20d_pct": ">= 0.10",
                "momentum_10d_pct": ">= 0.02",
                "rs_vs_spy_10d": ">= 0.00",
                "volume_spike_ratio": ">= 1.00",
                "price_vs_200ma_pct": ">= 0.03",
                "daily_close_location": ">= 0.55",
                "pct_from_52w_high": ">= -0.08",
                "atr_over_close_max": MAX_ATR_OVER_CLOSE,
                "days_to_earnings_block": "<= 3",
            },
            "target_stop_sizing": "existing shared risk_engine/portfolio_engine defaults",
            "catalyst_requirement": {
                "lookback_calendar_days": LOOKBACK_CALENDAR_DAYS,
                "high_confidence_categories": sorted(HIGH_CONFIDENCE_CATEGORIES),
                "signal_date_boundary": "event date <= signal date; entry is next open",
            },
            "windows": WINDOWS,
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows using the accepted "
            "core snapshots. The variant monkeypatches signal generation only "
            "inside this runner; no production code is changed."
        ),
        "date_range": {
            "primary": {
                "start": WINDOWS["late_strong"]["start"],
                "end": WINDOWS["late_strong"]["end"],
            },
            "secondary": [
                {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
                {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
            ],
        },
        "before_metrics": before_aggregate,
        "after_metrics": after_aggregate,
        "delta_metrics": {
            "aggregate": aggregate_delta,
            "by_window": gate4["window_deltas"],
        },
        "expected_value_score_delta": aggregate_delta.get(
            "expected_value_score_sum_delta"
        ),
        "total_pnl_delta": aggregate_delta.get("total_pnl_sum_delta"),
        "gate4": gate4,
        "decision": decision,
        "rejection_reason": (
            None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
        ),
        "next_evidence_needed": (
            "If rejected, do not retune this as a broad pullback/reclaim clone "
            "or a catalyst-keyword variant. A valid retry needs a materially "
            "better catalyst-quality field or forward replacement-value evidence "
            "on named latency cases."
        ),
        "catalyst_source_coverage": catalyst_source_coverage,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": True,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "promotion_note": (
                "Even if replay metrics pass, this is not retained as a "
                "production change unless a later shared default-off adapter or "
                "shared entry path exposes the same catalyst requirement."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: buy a strong near-breakout name before "
                "the formal breakout day only when a recent high-confidence "
                "catalyst is already production-visible."
            ),
            "2_history_check": {
                "exp-20260530-014": (
                    "Observed-only pre-entry catalyst context passed its usefulness "
                    "gate: 13 high-confidence tagged core trades, average PnL lift "
                    "$1,666.28, and positive lift in all three windows."
                ),
                "exp-20260512-024": (
                    "Rejected broad pullback/reclaim entry; aggregate EV delta "
                    "-2.3009 and PnL delta -$48,599.83, with EV regression in "
                    "all three windows. This experiment excludes 5-15% 52w "
                    "pullbacks and instead requires close within 3% of the prior "
                    "20-day high."
                ),
                "meta_research": (
                    "Recent OHLCV pullback families carry repeat risk. This run "
                    "uses the new catalyst field from exp-20260530-014 rather "
                    "than retuning OHLCV thresholds."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": gate4["rule"],
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "prediction": {
            "success_probability": 0.24,
            "expected_ev_delta": 0.2,
            "expected_pnl_delta": 4000.0,
            "main_failure_modes": [
                "thin_sample",
                "window_regression",
                "late_strong_false_positives",
                "catalyst_label_noise",
            ],
            "confidence_reason": (
                "exp-20260530-014 found useful high-confidence catalyst separation, "
                "but exp-20260530-013 and exp-20260512-024 show early-entry "
                "false-positive risk is high."
            ),
            "recorded_at": "2026-05-30T15:05:42+00:00",
            "brier_score": round((0.24 - actual_success) ** 2, 6),
        },
        "why_not_other_changes": (
            "Did not change breakout thresholds, volume-spike thresholds, scarce-slot "
            "routing, gap-cancel, stops, targets, add-ons, ranking, LLM/news gates, "
            "or production run.py. The only tested variable is requiring a "
            "high-confidence catalyst on the prebreakout source."
        ),
        "windows": windows,
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(BEFORE_AGG_JSON.relative_to(REPO_ROOT)),
            str(AFTER_AGG_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
            f"quant/experiments/{Path(__file__).name}",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, _aggregate_for_judge(before_aggregate))
    _write_json(AFTER_AGG_JSON, _aggregate_for_judge(after_aggregate))
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "codex-alpha-search",
            "status": status,
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "decision": decision,
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "updated_at": timestamp,
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(gate4), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
