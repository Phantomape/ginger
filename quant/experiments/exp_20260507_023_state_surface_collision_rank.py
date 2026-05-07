"""exp-20260507-023 state-surface collision ranking replay.

Alpha-search replay only. The prior state-surface satellite replay found an
independent surface with positive three-window behavior, but the accepted live
adapter is observe-only until forward paper evidence exists. This run asks a
narrower production-relevant question that does not need new ticker data:

When the accepted A/B stack has more qualified entry candidates than available
slots, can a point-in-time state-surface score improve the scarce-slot ordering?

No production policy, LLM/news, event sleeve, universe membership, sizing, or
exit logic is changed by this script.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
import feature_layer  # noqa: E402
import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXP_ID = "exp-20260507-023"
STEM = "state_surface_collision_rank"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

INDEX_TICKERS = {"SPY", "QQQ", "IWM"}
RULE_VERSION = "state_surface_collision_rank_v1"

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

RANK_STATS: dict[str, int] = {
    "planner_calls": 0,
    "scarce_slot_calls": 0,
    "signals_reordered": 0,
    "signals_with_score": 0,
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"), 4
        ),
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "strategy_total_return_pct",
    ]
    return {
        key: _round((after.get(key) or 0) - (before.get(key) or 0), 4)
        for key in keys
        if isinstance(before.get(key), (int, float))
        and isinstance(after.get(key), (int, float))
    }


def _gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    ev_before = float(before.get("expected_value_score") or 0.0)
    pnl_before = float(before.get("total_pnl") or 0.0)
    win_before = float(before.get("win_rate") or 0.0)
    trades_before = int(before.get("trade_count") or 0)
    ev_after = float(after.get("expected_value_score") or 0.0)
    pnl_after = float(after.get("total_pnl") or 0.0)
    win_after = float(after.get("win_rate") or 0.0)
    trades_after = int(after.get("trade_count") or 0)
    checks = {
        "ev_up_gt_10pct": ev_before > 0 and (ev_after / ev_before - 1.0) > 0.10,
        "sharpe_up_gt_0_1": (
            float(after.get("sharpe_daily") or 0.0)
            - float(before.get("sharpe_daily") or 0.0)
        )
        > 0.1,
        "drawdown_down_gt_1pp": (
            float(before.get("max_drawdown_pct") or 0.0)
            - float(after.get("max_drawdown_pct") or 0.0)
        )
        > 1.0,
        "pnl_up_gt_5pct": pnl_before > 0 and (pnl_after / pnl_before - 1.0) > 0.05,
        "trades_up_without_winrate_drop": trades_after > trades_before
        and win_after >= win_before,
    }
    return {
        "passed": any(checks.values()),
        "checks": checks,
    }


def _scalar(series_value: Any) -> float | None:
    if hasattr(series_value, "item"):
        series_value = series_value.item()
    return _float_or_none(series_value)


def _add_surface_inputs(
    original_compute_features,
    ticker: str,
    ohlcv_data: Any,
    earnings_data: Any,
) -> dict[str, Any] | None:
    features = original_compute_features(ticker, ohlcv_data, earnings_data)
    if not features or ohlcv_data is None:
        return features
    try:
        close = _scalar(ohlcv_data["Close"].iloc[-1])
        volume = _scalar(ohlcv_data["Volume"].iloc[-1])
        if close and len(ohlcv_data) >= 6:
            close_5d = _scalar(ohlcv_data["Close"].iloc[-6])
            if close_5d:
                features["state_surface_momentum_5d_pct"] = round(
                    close / close_5d - 1.0, 6
                )
        if close and len(ohlcv_data) >= 61:
            close_60d = _scalar(ohlcv_data["Close"].iloc[-61])
            if close_60d:
                features["state_surface_momentum_60d_pct"] = round(
                    close / close_60d - 1.0, 6
                )
            high_60 = _scalar(ohlcv_data["High"].iloc[-60:].max())
            if high_60:
                features["state_surface_near_high_60"] = round(close / high_60, 6)
        if close and len(ohlcv_data) >= 50:
            sma50 = _scalar(ohlcv_data["Close"].iloc[-50:].mean())
            if sma50:
                features["state_surface_price_vs_50sma_pct"] = round(
                    close / sma50 - 1.0, 6
                )
        if volume and len(ohlcv_data) >= 21:
            avg_vol_20 = _scalar(ohlcv_data["Volume"].iloc[-21:-1].mean())
            if avg_vol_20:
                features["state_surface_volume_ratio_20"] = round(
                    volume / avg_vol_20, 6
                )
    except Exception:
        return features
    return features


def _zscore_map(values: dict[str, float]) -> dict[str, float]:
    clean = [float(value) for value in values.values() if value is not None]
    if len(clean) < 2:
        return {key: 0.0 for key in values}
    mean = statistics.mean(clean)
    stdev = statistics.pstdev(clean) or 1.0
    return {key: (float(value) - mean) / stdev for key, value in values.items()}


def _state_from_features(features_dict: dict[str, dict[str, Any]]) -> dict[str, Any]:
    spy = features_dict.get("SPY") or {}
    qqq = features_dict.get("QQQ") or {}
    iwm = features_dict.get("IWM") or {}
    spy_ret20 = _float_or_none(spy.get("momentum_20d_pct"))
    qqq_ret20 = _float_or_none(qqq.get("momentum_20d_pct"))
    iwm_ret20 = _float_or_none(iwm.get("momentum_20d_pct"))
    spy_pct200 = _float_or_none(spy.get("price_vs_200ma_pct"))
    qqq_pct200 = _float_or_none(qqq.get("price_vs_200ma_pct"))
    pct_values = [v for v in (spy_pct200, qqq_pct200) if v is not None]
    min_index_pct200 = min(pct_values) if pct_values else None
    qqq_minus_iwm = (
        qqq_ret20 - iwm_ret20
        if qqq_ret20 is not None and iwm_ret20 is not None
        else None
    )
    iwm_minus_spy = (
        iwm_ret20 - spy_ret20
        if iwm_ret20 is not None and spy_ret20 is not None
        else None
    )
    if min_index_pct200 is not None and min_index_pct200 < 0:
        state_bucket = "weak_index"
    elif qqq_minus_iwm is not None and qqq_minus_iwm > 0.04:
        state_bucket = "narrow_cap_weight_leadership"
    elif iwm_minus_spy is not None and iwm_minus_spy > 0.02:
        state_bucket = "broad_rotation"
    else:
        state_bucket = "balanced_risk_on"

    breadth_values = [
        _float_or_none(row.get("state_surface_price_vs_50sma_pct"))
        for ticker, row in features_dict.items()
        if ticker not in INDEX_TICKERS and row
    ]
    breadth_values = [value for value in breadth_values if value is not None]
    breadth50 = (
        sum(1 for value in breadth_values if value > 0) / len(breadth_values)
        if breadth_values
        else None
    )
    if breadth50 is None:
        breadth_bucket = "unknown"
    elif breadth50 >= 0.65:
        breadth_bucket = "broad_breadth"
    elif breadth50 <= 0.45:
        breadth_bucket = "thin_breadth"
    else:
        breadth_bucket = "mixed_breadth"

    return {
        "state_bucket": state_bucket,
        "breadth_bucket": breadth_bucket,
        "dispersion_bucket": "unknown",
        "spy_ret20": _round(spy_ret20, 6),
        "qqq_ret20": _round(qqq_ret20, 6),
        "iwm_ret20": _round(iwm_ret20, 6),
        "qqq_minus_iwm_ret20": _round(qqq_minus_iwm, 6),
        "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        "min_index_pct_from_200sma": _round(min_index_pct200, 6),
        "universe_breadth_above_50sma": _round(breadth50, 6),
    }


def _score_from_features(
    features_dict: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    state = _state_from_features(features_dict)
    spy_ret20 = float(state.get("spy_ret20") or 0.0)
    rows: dict[str, dict[str, float]] = {}
    for ticker, features in features_dict.items():
        ticker = str(ticker).upper()
        if ticker in INDEX_TICKERS or not features:
            continue
        ret20 = _float_or_none(features.get("momentum_20d_pct"))
        ret60 = _float_or_none(features.get("state_surface_momentum_60d_pct"))
        ret5 = _float_or_none(features.get("state_surface_momentum_5d_pct"))
        near_high = _float_or_none(features.get("state_surface_near_high_60"))
        volume_ratio = _float_or_none(features.get("state_surface_volume_ratio_20"))
        if None in (ret20, ret60, ret5, near_high, volume_ratio):
            continue
        rows[ticker] = {
            "ret20_excess_spy": float(ret20) - spy_ret20,
            "ret60": float(ret60),
            "ret5": float(ret5),
            "near_high_60": float(near_high),
            "volume_ratio_20": float(volume_ratio),
        }
    if not rows:
        return {}, state

    z_ret20 = _zscore_map(
        {ticker: row["ret20_excess_spy"] for ticker, row in rows.items()}
    )
    z_ret60 = _zscore_map({ticker: row["ret60"] for ticker, row in rows.items()})
    z_pause = _zscore_map({ticker: -abs(row["ret5"]) for ticker, row in rows.items()})
    z_high = _zscore_map({ticker: row["near_high_60"] for ticker, row in rows.items()})
    z_volume = _zscore_map(
        {ticker: row["volume_ratio_20"] for ticker, row in rows.items()}
    )

    state_bucket = str(state.get("state_bucket") or "")
    breadth_bucket = str(state.get("breadth_bucket") or "")
    scores = {}
    for ticker, values in rows.items():
        if state_bucket == "broad_rotation":
            surface = "rotation_breakout_leadership"
            score = (
                0.45 * z_ret20[ticker]
                + 0.25 * z_high[ticker]
                + 0.20 * z_volume[ticker]
                + 0.10 * z_ret60[ticker]
            )
        elif breadth_bucket == "broad_breadth":
            surface = "broad_breadth_trend_persistence"
            score = (
                0.40 * z_ret60[ticker]
                + 0.25 * z_ret20[ticker]
                + 0.20 * z_pause[ticker]
                + 0.15 * z_high[ticker]
            )
        else:
            surface = "balanced_state_leadership"
            score = (
                0.35 * z_ret60[ticker]
                + 0.35 * z_ret20[ticker]
                + 0.20 * z_high[ticker]
                + 0.10 * z_pause[ticker]
            )
        scores[ticker] = {
            "score": round(score, 6),
            "surface": surface,
            "features": {key: round(value, 6) for key, value in values.items()},
        }
    return scores, state


def _install_replay_patch() -> dict[str, Any]:
    original_compute_features = feature_layer.compute_features
    original_enrich_signals = risk_engine.enrich_signals
    original_plan_entry_candidates = backtester.plan_entry_candidates

    def compute_features_with_surface_inputs(ticker, ohlcv_data, earnings_data):
        return _add_surface_inputs(
            original_compute_features,
            ticker,
            ohlcv_data,
            earnings_data,
        )

    def enrich_signals_with_surface_score(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich_signals(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        scores, state = _score_from_features(features_dict or {})
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            row = scores.get(ticker)
            if not row:
                continue
            signal["state_surface_collision_score"] = row["score"]
            signal["state_surface_collision_surface"] = row["surface"]
            signal["state_surface_collision_state"] = {
                key: state.get(key)
                for key in (
                    "state_bucket",
                    "breadth_bucket",
                    "dispersion_bucket",
                    "universe_breadth_above_50sma",
                    "min_index_pct_from_200sma",
                )
            }
            signal["state_surface_collision_features"] = row["features"]
        return enriched

    def plan_entry_candidates_with_surface_rank(
        signals,
        open_positions,
        market_context=None,
        max_positions=None,
        **kwargs,
    ):
        input_signals = list(signals or [])
        active_positions_count = kwargs.get("active_positions_count")
        active_positions = (
            int(active_positions_count)
            if active_positions_count is not None
            else 0
        )
        max_pos = int(max_positions or 0)
        slots = max(0, max_pos - active_positions)
        RANK_STATS["planner_calls"] += 1
        if slots > 0 and len(input_signals) > slots:
            RANK_STATS["scarce_slot_calls"] += 1
            RANK_STATS["signals_with_score"] += sum(
                1 for signal in input_signals if signal.get("state_surface_collision_score") is not None
            )
            ranked = sorted(
                input_signals,
                key=lambda signal: (
                    -float(signal.get("state_surface_collision_score") or -999.0),
                    -float(signal.get("trade_quality_score") or 0.0),
                    -float(signal.get("confidence_score") or 0.0),
                    str(signal.get("ticker") or ""),
                ),
            )
            if [s.get("ticker") for s in ranked] != [s.get("ticker") for s in input_signals]:
                RANK_STATS["signals_reordered"] += 1
            planned, entry_plan = original_plan_entry_candidates(
                ranked,
                open_positions,
                market_context=market_context,
                max_positions=max_positions,
                **kwargs,
            )
            entry_plan["state_surface_collision_rank_applied"] = True
            entry_plan["state_surface_collision_rule_version"] = RULE_VERSION
            return planned, entry_plan
        planned, entry_plan = original_plan_entry_candidates(
            input_signals,
            open_positions,
            market_context=market_context,
            max_positions=max_positions,
            **kwargs,
        )
        entry_plan["state_surface_collision_rank_applied"] = False
        return planned, entry_plan

    feature_layer.compute_features = compute_features_with_surface_inputs
    risk_engine.enrich_signals = enrich_signals_with_surface_score
    backtester.plan_entry_candidates = plan_entry_candidates_with_surface_rank
    return {
        "feature_layer.compute_features": original_compute_features,
        "risk_engine.enrich_signals": original_enrich_signals,
        "backtester.plan_entry_candidates": original_plan_entry_candidates,
    }


def _restore_patch(originals: dict[str, Any]) -> None:
    feature_layer.compute_features = originals["feature_layer.compute_features"]
    risk_engine.enrich_signals = originals["risk_engine.enrich_signals"]
    backtester.plan_entry_candidates = originals["backtester.plan_entry_candidates"]


def _run_window(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _run_all_windows(patched: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, window in WINDOWS.items():
        result = _run_window(window)
        out[label] = {
            "window": dict(window),
            "metrics": _metrics(result),
            "trade_count_by_strategy": result.get("trade_count_by_strategy"),
            "convergence": result.get("convergence"),
        }
        if patched:
            out[label]["rank_stats"] = dict(RANK_STATS)
    return out


def _decision(comparisons: dict[str, Any]) -> tuple[str, str]:
    ev_wins = 0
    gate_passes = 0
    regressions = []
    for label, row in comparisons.items():
        before = row["baseline"]
        after = row["experiment"]
        if float(after.get("expected_value_score") or 0.0) > float(
            before.get("expected_value_score") or 0.0
        ):
            ev_wins += 1
        if row["gate4"]["passed"]:
            gate_passes += 1
        if float(after.get("expected_value_score") or 0.0) < float(
            before.get("expected_value_score") or 0.0
        ):
            regressions.append(label)
    if ev_wins >= 2 and gate_passes >= 2 and not regressions:
        return "accepted", "state-surface collision rank improved majority windows without EV regression"
    return (
        "rejected",
        "insufficient stable three-window improvement versus current accepted stack",
    )


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXP_ID} {STEM}",
        "",
        "## Hypothesis",
        "",
        (
            "When core A/B entry candidates exceed available slots, ranking the "
            "collision set by a point-in-time state-surface score improves "
            "allocation quality without adding ticker noise."
        ),
        "",
        "## Non-repeat check",
        "",
        (
            "This is not an event-bundle threshold/source/notional retune, not an "
            "LLM/earnings/options experiment, and not a raw watchlist expansion. "
            "It uses the already validated state-surface mechanism only as a "
            "scarce-slot ordering signal."
        ),
        "",
        "## Three-window results",
        "",
        "| Window | EV before | EV after | PnL before | PnL after | SharpeD before | SharpeD after | Gate4 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, row in payload["comparisons"].items():
        before = row["baseline"]
        after = row["experiment"]
        lines.append(
            "| {label} | {ev_b} | {ev_a} | {pnl_b} | {pnl_a} | {sh_b} | {sh_a} | {gate} |".format(
                label=label,
                ev_b=before.get("expected_value_score"),
                ev_a=after.get("expected_value_score"),
                pnl_b=before.get("total_pnl"),
                pnl_a=after.get("total_pnl"),
                sh_b=before.get("sharpe_daily"),
                sh_a=after.get("sharpe_daily"),
                gate="PASS" if row["gate4"]["passed"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"`{payload['decision']}` - {payload['decision_reason']}",
            "",
            "## Production impact",
            "",
            (
                "`replay_only`: no shared policy, run adapter, sizing, exits, "
                "LLM/news, event sleeve, or universe membership changed. If this "
                "had passed, the next step would have been a shared production "
                "parity policy rather than leaving ranking in the backtester."
            ),
            "",
            "## Files",
            "",
            f"- `{OUT_JSON.relative_to(REPO_ROOT).as_posix()}`",
            f"- `{LOG_JSON.relative_to(REPO_ROOT).as_posix()}`",
            f"- `{TICKET_JSON.relative_to(REPO_ROOT).as_posix()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baseline = _run_all_windows(patched=False)
    originals = _install_replay_patch()
    try:
        for key in RANK_STATS:
            RANK_STATS[key] = 0
        experiment = _run_all_windows(patched=True)
    finally:
        _restore_patch(originals)

    comparisons = {}
    for label in WINDOWS:
        before = baseline[label]["metrics"]
        after = experiment[label]["metrics"]
        comparisons[label] = {
            "baseline": before,
            "experiment": after,
            "delta": _delta(before, after),
            "gate4": _gate4(before, after),
        }
    decision, reason = _decision(comparisons)
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXP_ID,
        "hypothesis": (
            "state_surface score can improve scarce-slot core entry allocation "
            "when more A/B candidates exist than available slots"
        ),
        "change_type": "ranking_replay",
        "rule_version": RULE_VERSION,
        "date_range": {
            label: {k: v for k, v in window.items() if k in {"start", "end", "snapshot"}}
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "parameters": {
            "trigger": "only when len(signals) > available_slots",
            "ranking_key": [
                "state_surface_collision_score desc",
                "trade_quality_score desc",
                "confidence_score desc",
                "ticker asc",
            ],
            "state_surface_inputs": [
                "20d excess return vs SPY",
                "60d return",
                "5d pause score",
                "near 60d high",
                "20d volume ratio",
                "index state bucket",
                "50sma universe breadth bucket",
            ],
        },
        "baseline": baseline,
        "experiment": experiment,
        "comparisons": comparisons,
        "decision": decision,
        "decision_reason": reason,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "notes": (
                "Replay-only monkeypatch inside experiment script. Accepted live "
                "behavior would require shared production_parity policy wiring."
            ),
        },
        "llm_impact": "none",
        "modules_intentionally_unchanged": [
            "LLM/news gates",
            "event sleeve",
            "earnings_event_long",
            "universe membership",
            "sizing",
            "exit logic",
            "production run.py",
        ],
        "main_risk": (
            "Could mis-rank otherwise profitable lower-momentum pullback or "
            "breakout candidates during temporary leadership reversals."
        ),
        "started_at": started_at,
        "finished_at": finished_at,
    }

    ticket = {
        "title": "State-surface collision rank rejected",
        "summary": "Three-window replay did not justify production ranking change.",
        "status": decision,
        "experiment_id": EXP_ID,
        "decision_reason": reason,
        "next_action": (
            "Do not promote state-surface as core slot ranker; continue forward "
            "paper observation for the default-off satellite."
        ),
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _artifact(payload))

    print(json.dumps(_safe({
        "experiment_id": EXP_ID,
        "decision": decision,
        "decision_reason": reason,
        "comparisons": comparisons,
        "outputs": {
            "result": str(OUT_JSON.relative_to(REPO_ROOT)),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)),
            "ticket": str(TICKET_JSON.relative_to(REPO_ROOT)),
            "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        },
    }), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
