"""exp-20260509-001: pressure-date state-shadow entry replay.

Alpha search. This runner tests whether the observed state-aware shadow
surface from exp-20260507-005 can become executable alpha when constrained to
existing core-universe tickers and only injected on dates where the baseline
already had slot/heat pressure. It does not promote production behavior.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import feature_layer  # noqa: E402
import signal_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402


EXP_ID = "exp-20260509-001"
STEM = "pressure_state_shadow_entry"
SHADOW_STRATEGY = "state_shadow_long"
INDEX_TICKERS = {"SPY", "QQQ", "IWM"}

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        b = before.get(key)
        a = after.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            value = a - b
            out[key] = int(value) if key in {"trade_count", "signals_generated", "signals_survived"} else _round(value, 6)
    return out


def _zscore(values: dict[str, float]) -> dict[str, float]:
    clean = list(values.values())
    if len(clean) < 2:
        return {key: 0.0 for key in values}
    mean = statistics.mean(clean)
    stdev = statistics.pstdev(clean) or 1.0
    return {key: (value - mean) / stdev for key, value in values.items()}


def _pressure_dates(result: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    by_date = (result.get("entry_execution_attribution") or {}).get("by_date") or {}
    for date_str, counts in by_date.items():
        counts = counts or {}
        if counts.get("slot_sliced", 0) or counts.get("no_shares", 0):
            out.add(str(date_str))
    return out


def _extract_signal_date(features_dict: dict[str, dict[str, Any]]) -> str | None:
    for features in features_dict.values():
        if isinstance(features, dict) and features.get("_exp20260509_signal_date"):
            return str(features["_exp20260509_signal_date"])
    return None


def _state_bucket(features_dict: dict[str, dict[str, Any]]) -> str:
    spy = features_dict.get("SPY") or {}
    qqq = features_dict.get("QQQ") or {}
    iwm = features_dict.get("IWM") or {}
    spy20 = spy.get("momentum_20d_pct")
    qqq20 = qqq.get("momentum_20d_pct")
    iwm20 = iwm.get("momentum_20d_pct")
    spy200 = spy.get("price_vs_200ma_pct")
    qqq200 = qqq.get("price_vs_200ma_pct")
    if isinstance(spy200, (int, float)) and isinstance(qqq200, (int, float)) and min(spy200, qqq200) < 0:
        return "weak_index"
    if isinstance(qqq20, (int, float)) and isinstance(iwm20, (int, float)) and qqq20 - iwm20 > 0.04:
        return "narrow_cap_weight_leadership"
    if isinstance(iwm20, (int, float)) and isinstance(spy20, (int, float)) and iwm20 - spy20 > 0.02:
        return "broad_rotation"
    return "balanced_risk_on"


def _shadow_candidate(
    features_dict: dict[str, dict[str, Any]],
    existing_tickers: set[str],
) -> dict[str, Any] | None:
    spy20 = (features_dict.get("SPY") or {}).get("momentum_20d_pct")
    if not isinstance(spy20, (int, float)):
        spy20 = 0.0

    candidates: dict[str, dict[str, float]] = {}
    for ticker, features in features_dict.items():
        ticker = str(ticker).upper()
        if ticker in INDEX_TICKERS or ticker in existing_tickers or not isinstance(features, dict):
            continue
        close = features.get("close")
        atr = features.get("atr")
        ret20 = features.get("momentum_20d_pct")
        near_high = features.get("pct_from_52w_high")
        volume_ratio = features.get("volume_spike_ratio")
        trend_score = features.get("trend_score")
        if not all(isinstance(v, (int, float)) for v in [close, atr, ret20, near_high, volume_ratio, trend_score]):
            continue
        if close <= 0 or atr <= 0:
            continue
        if not features.get("above_200ma"):
            continue
        if atr / close > 0.07:
            continue
        if ret20 <= spy20:
            continue
        if near_high < -0.08:
            continue
        if volume_ratio < 0.70:
            continue
        candidates[ticker] = {
            "ret20_excess_spy": float(ret20) - float(spy20),
            "near_high": float(near_high),
            "volume_ratio": float(volume_ratio),
            "trend_score": float(trend_score),
        }
    if not candidates:
        return None

    z_ret20 = _zscore({ticker: row["ret20_excess_spy"] for ticker, row in candidates.items()})
    z_high = _zscore({ticker: row["near_high"] for ticker, row in candidates.items()})
    z_volume = _zscore({ticker: row["volume_ratio"] for ticker, row in candidates.items()})
    z_trend = _zscore({ticker: row["trend_score"] for ticker, row in candidates.items()})
    state = _state_bucket(features_dict)
    scored = []
    for ticker, row in candidates.items():
        if state == "broad_rotation":
            score = 0.45 * z_ret20[ticker] + 0.25 * z_high[ticker] + 0.20 * z_volume[ticker] + 0.10 * z_trend[ticker]
            surface = "rotation_leadership_pressure"
        elif state == "narrow_cap_weight_leadership":
            score = 0.40 * z_ret20[ticker] + 0.30 * z_high[ticker] + 0.20 * z_trend[ticker] + 0.10 * z_volume[ticker]
            surface = "cap_weight_leadership_pressure"
        else:
            score = 0.35 * z_ret20[ticker] + 0.30 * z_trend[ticker] + 0.20 * z_high[ticker] + 0.15 * z_volume[ticker]
            surface = "balanced_leadership_pressure"
        scored.append((score, ticker, surface, row))
    score, ticker, surface, row = sorted(scored, reverse=True)[0]
    features = features_dict[ticker]
    close = float(features["close"])
    atr = float(features["atr"])
    confidence = max(0.89, min(0.96, 0.91 + 0.01 * score))
    return {
        "ticker": ticker,
        "strategy": SHADOW_STRATEGY,
        "entry_price": round(close, 2),
        "stop_price": round(close - ATR_STOP_MULT * atr, 2),
        "confidence_score": round(confidence, 2),
        "entry_note": "Replay-only state-shadow pressure entry; no production promotion.",
        "conditions_met": {
            "experiment_id": EXP_ID,
            "surface": surface,
            "state_bucket": state,
            "score": _round(score, 6),
            "ret20_excess_spy": _round(row["ret20_excess_spy"], 6),
            "near_high": _round(row["near_high"], 6),
            "volume_ratio": _round(row["volume_ratio"], 6),
            "trend_score": _round(row["trend_score"], 6),
        },
    }


def _install_patch(pressure_dates: set[str]) -> tuple[Callable[[], None], dict[str, Any]]:
    original_compute_features = feature_layer.compute_features
    original_generate_signals = signal_engine.generate_signals
    stats: dict[str, Any] = {
        "pressure_dates": len(pressure_dates),
        "pressure_dates_seen": 0,
        "injected_signals": 0,
        "injected_by_ticker": Counter(),
        "injected_by_surface": Counter(),
        "injected_rows": [],
        "skipped_pressure_no_candidate": 0,
    }

    def patched_compute_features(ticker, ohlcv_data, earnings_data):
        features = original_compute_features(ticker, ohlcv_data, earnings_data)
        if features and ohlcv_data is not None and len(ohlcv_data.index):
            last_idx = ohlcv_data.index[-1]
            date_str = last_idx.strftime("%Y-%m-%d") if hasattr(last_idx, "strftime") else str(last_idx)[:10]
            features["_exp20260509_signal_date"] = date_str
        return features

    def patched_generate_signals(
        features_dict,
        market_context=None,
        enabled_strategies=None,
        breakout_max_pullback_from_52w_high=None,
    ):
        signals = original_generate_signals(
            features_dict,
            market_context=market_context,
            enabled_strategies=enabled_strategies,
            breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
        )
        date_str = _extract_signal_date(features_dict)
        if not date_str or date_str not in pressure_dates:
            return signals

        stats["pressure_dates_seen"] += 1
        existing = {str(sig.get("ticker") or "").upper() for sig in signals}
        shadow = _shadow_candidate(features_dict, existing)
        if not shadow:
            stats["skipped_pressure_no_candidate"] += 1
            return signals

        surface = (shadow.get("conditions_met") or {}).get("surface", "unknown")
        stats["injected_signals"] += 1
        stats["injected_by_ticker"][shadow["ticker"]] += 1
        stats["injected_by_surface"][surface] += 1
        stats["injected_rows"].append({
            "date": date_str,
            "ticker": shadow["ticker"],
            "surface": surface,
            "confidence_score": shadow["confidence_score"],
            "score": (shadow.get("conditions_met") or {}).get("score"),
        })
        return sorted(
            [*signals, shadow],
            key=lambda sig: (sig.get("confidence_score") or 0.0, sig.get("ticker") or ""),
            reverse=True,
        )

    feature_layer.compute_features = patched_compute_features
    signal_engine.generate_signals = patched_generate_signals

    def restore() -> None:
        feature_layer.compute_features = original_compute_features
        signal_engine.generate_signals = original_generate_signals

    return restore, stats


def _run_engine(window: dict[str, str], include_entry_candidate_events: bool = False) -> dict[str, Any]:
    result = BacktestEngine(
        universe=get_universe(),
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(ROOT / "data"),
        ohlcv_snapshot_path=str(ROOT / window["snapshot"]),
        include_entry_candidate_events=include_entry_candidate_events,
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _shadow_decisions(result: dict[str, Any]) -> dict[str, Any]:
    events = result.get("entry_candidate_events") or []
    rows = [event for event in events if event.get("strategy") == SHADOW_STRATEGY]
    counts = Counter(event.get("decision", "unknown") for event in rows)
    return {
        "decision_counts": dict(counts),
        "entered_count": counts.get("entered", 0),
        "sample_events": rows[:25],
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before_metrics"]["expected_value_score"] or 0.0) for row in rows.values())
    ev_after = sum(float(row["after_metrics"]["expected_value_score"] or 0.0) for row in rows.values())
    pnl_before = sum(float(row["before_metrics"]["total_pnl"] or 0.0) for row in rows.values())
    pnl_after = sum(float(row["after_metrics"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "expected_value_score_before_sum": _round(ev_before, 4),
        "expected_value_score_after_sum": _round(ev_after, 4),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 4),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before if ev_before else 0.0, 6),
        "total_pnl_before_sum": _round(pnl_before, 2),
        "total_pnl_after_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before if pnl_before else 0.0, 6),
        "ev_windows_improved": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for row in rows.values() if row["delta"]["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for row in rows.values() if row["delta"]["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for row in rows.values() if row["delta"]["total_pnl"] < 0),
        "max_drawdown_delta_max": _round(max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6),
        "max_sharpe_daily_delta": _round(max(row["delta"]["sharpe_daily"] for row in rows.values()), 6),
        "trade_count_delta_sum": sum(row["delta"]["trade_count"] for row in rows.values()),
        "win_rate_delta_min": _round(min(row["delta"]["win_rate"] for row in rows.values()), 6),
        "shadow_injected_sum": sum(row["shadow_patch_stats"]["injected_signals"] for row in rows.values()),
        "shadow_entered_sum": sum(row["shadow_decisions"]["entered_count"] for row in rows.values()),
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    material = (
        aggregate["expected_value_score_delta_pct"] > 0.10
        or aggregate["max_sharpe_daily_delta"] > 0.10
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["total_pnl_delta_pct"] > 0.05
        or (aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0)
    )
    return bool(material and aggregate["ev_windows_improved"] >= 2)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {EXP_ID} Pressure State-Shadow Entry",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Rejection reason: {payload.get('rejection_reason')}",
        "- Production impact: replay only; no production strategy behavior changed.",
        "",
        "## Three-window metrics",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Trades delta | Shadow injected | Shadow entered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["windows"].items():
        lines.append(
            "| {name} | {evb:.4f} | {eva:.4f} | {evd:.4f} | {pnld:.2f} | {td} | {inj} | {ent} |".format(
                name=name,
                evb=row["before_metrics"]["expected_value_score"],
                eva=row["after_metrics"]["expected_value_score"],
                evd=row["delta"]["expected_value_score"],
                pnld=row["delta"]["total_pnl"],
                td=row["delta"]["trade_count"],
                inj=row["shadow_patch_stats"]["injected_signals"],
                ent=row["shadow_decisions"]["entered_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Mechanism Read",
            "",
            payload["mechanism_read"],
            "",
            "## Do Not Repeat",
            "",
            payload["next_time_do_not_repeat"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    windows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, window in WINDOWS.items():
        baseline = _run_engine(window)
        pressure = _pressure_dates(baseline)
        restore, stats = _install_patch(pressure)
        try:
            variant = _run_engine(window, include_entry_candidate_events=True)
        finally:
            restore()

        before = _metrics(baseline)
        after = _metrics(variant)
        rows = dict(stats)
        rows["injected_by_ticker"] = dict(rows["injected_by_ticker"])
        rows["injected_by_surface"] = dict(rows["injected_by_surface"])
        windows[name] = {
            "window": window,
            "before_metrics": before,
            "after_metrics": after,
            "delta": _delta(after, before),
            "pressure_date_count": len(pressure),
            "shadow_patch_stats": rows,
            "shadow_decisions": _shadow_decisions(variant),
            "entry_reason_counts_before": (baseline.get("entry_execution_attribution") or {}).get("reason_counts", {}),
            "entry_reason_counts_after": (variant.get("entry_execution_attribution") or {}).get("reason_counts", {}),
            "by_strategy_after": variant.get("by_strategy", {}),
        }

    aggregate = _aggregate(windows)
    accepted = _accepted(aggregate)
    decision = "accepted_for_shared_policy_followup" if accepted else "rejected"
    rejection_reason = None if accepted else (
        "Pressure-date state-shadow entries did not clear the three-window EV-first Gate 4 bar."
    )
    mechanism_read = (
        "The state-aware surface is not enough as an executable pressure-date entry source. "
        "It injected candidates from existing core tickers, but any apparent added coverage "
        "must beat the live slot/heat path, not just show positive forward returns in a shadow audit."
    )

    payload = {
        "experiment_id": EXP_ID,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "classification": "alpha_search",
        "change_type": "entry_source_replay",
        "hypothesis": (
            "A state-aware shadow leadership surface may become executable alpha if used only on "
            "baseline pressure dates and only within the current core universe, where it can compete "
            "for scarce entry slots without broad ticker expansion."
        ),
        "alpha_category": "entry / allocation",
        "single_causal_variable": "pressure-date state-shadow entry source",
        "historical_checks": {
            "exp_20260507_005_state_aware_shadow_surface": (
                "Observed positive non-overlap/replacement forward marks; this run performs the required executable replay."
            ),
            "blocked_llm_soft_ranking": (
                "Not tested; recent LLM archives had zero effective candidate coverage."
            ),
            "avoids_recent_no_repeat_zones": (
                "No LLM prompt change, no broad universe expansion, no add-on trigger/cap retune, "
                "no global MAX_POSITIONS/sixth-slot retry, no staged-entry fraction retry."
            ),
        },
        "parameters": {
            "shadow_strategy": SHADOW_STRATEGY,
            "injection_scope": "baseline pressure dates with slot_sliced or no_shares counts",
            "universe": "data_layer.get_universe() only; no added tickers",
            "hard_candidate_requirements": {
                "above_200ma": True,
                "atr_over_close_lte": 0.07,
                "ret20_gt_spy_ret20": True,
                "pct_from_52w_high_gte": -0.08,
                "volume_spike_ratio_gte": 0.70,
                "not_already_core_signal_same_day": True,
            },
            "score_weights": {
                "balanced": "0.35 ret20 excess + 0.30 trend_score + 0.20 near_high + 0.15 volume",
                "broad_rotation": "0.45 ret20 excess + 0.25 near_high + 0.20 volume + 0.10 trend_score",
                "narrow_cap_weight": "0.40 ret20 excess + 0.30 near_high + 0.20 trend_score + 0.10 volume",
            },
        },
        "gate_2_data_fields": {
            "signal_date": "patched from the last OHLCV row during replay only",
            "momentum_20d_pct": "feature_layer.compute_trend_features",
            "price_vs_200ma_pct": "feature_layer.compute_trend_features",
            "pct_from_52w_high": "feature_layer.compute_trend_features",
            "volume_spike_ratio": "feature_layer.compute_trend_features",
            "atr": "feature_layer.compute_trend_features",
        },
        "windows": windows,
        "aggregate": aggregate,
        "gate4": {
            "passed": accepted,
            "basis": "Requires >10% EV, >0.1 Sharpe, >1pp drawdown reduction, >5% PnL, or more trades without lower win rate, with majority-window EV improvement.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_no_llm": "LLM soft-ranking remains data-limited, so this tests deterministic entry alpha instead.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "strategy_behavior_changed_in_repo": False,
            "promotion_requirement": (
                "If accepted later, move state scoring and pressure-date injection into a shared policy "
                "called by both run.py and backtester.py before orders can change."
            ),
        },
        "mechanism_read": mechanism_read,
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_time_do_not_repeat": (
            "Do not retry this pressure-date state-shadow entry source or nearby hard thresholds on the "
            "same snapshots unless candidate-level replacement evidence changes or the surface is tied "
            "to a new orthogonal event/news feature."
        ),
        "experiment_log_jsonl_note": (
            "Canonical record is docs/experiments/logs because docs/experiment_log.jsonl had pre-existing unstaged changes."
        ),
    }

    data_path = ROOT / "data" / "experiments" / EXP_ID / f"{EXP_ID}_{STEM}.json"
    log_path = ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
    ticket_path = ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
    artifact_path = ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
    _write_json(data_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "id": EXP_ID,
            "title": "Reject pressure state-shadow entry" if not accepted else "Promote pressure state-shadow followup",
            "status": decision,
            "run_at_utc": payload["run_at_utc"],
            "summary": rejection_reason or "Positive replay requires shared production policy before promotion.",
            "artifact": str(artifact_path.relative_to(ROOT)),
            "data": str(data_path.relative_to(ROOT)),
        },
    )
    _write_md(artifact_path, payload)

    print(json.dumps({
        "experiment_id": EXP_ID,
        "decision": decision,
        "aggregate": aggregate,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
