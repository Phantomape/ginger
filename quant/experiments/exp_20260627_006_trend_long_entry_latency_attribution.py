"""exp-20260627-006: observed-only trend_long entry latency attribution.

This runner does not change production, backtest, ranking, sizing, or order
behavior. It measures whether actual accepted-stack ``trend_long`` trades had
production-visible precursor rows in the 1-5 sessions before the official
trend signal day, and whether those earlier next-open entries had better
forward replacement value.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd


EXPERIMENT_ID = "exp-20260627-006"
STEM = "trend_long_entry_latency_attribution"
CHANGED_VARIABLE = "trend_long_pre_signal_latency_replacement_value_v1"
TRIAL_FAMILY = "trend_long_entry_latency_attribution"
TRIAL_VARIANT_ID = "trend_long_actual_trade_precursor_lookback_1_5d_v1"

LOOKBACK_SESSIONS = 5
NEAR_20D_HIGH_PCT = -0.01
MIN_PRECURSOR_VOLUME_RATIO = 1.0
MIN_WARM_VOLUME_RATIO = 1.2
MAX_ATR_OVER_CLOSE = 0.07
MIN_OBSERVED_COVERAGE = 0.55
MIN_POSITIVE_WINDOWS = 2
MIN_POSITIVE_20D_SHARE = 0.55
MAX_MEDIAN_PRE_ENTRY_MAE = -0.04

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from feature_layer import compute_trend_features  # noqa: E402


WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "backtest": (
            "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
            "backtest_results_warehouse_snapshot_late_strong_20260604.json"
        ),
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "backtest": (
            "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
            "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
        ),
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "backtest": (
            "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
            "backtest_results_warehouse_snapshot_old_thin_20260604.json"
        ),
    },
}

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_006_{STEM}.json"
TRADE_ROWS_JSON = OUT_DIR / f"{STEM}_trade_rows.json"
CANDIDATE_ROWS_JSON = OUT_DIR / f"{STEM}_candidate_rows.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
BASELINE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_safe(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_safe(v) for v in obj)
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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


def _date_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(pd.Timestamp(value).date())


def _load_snapshot(path: Path) -> dict[str, pd.DataFrame]:
    payload = _load_json(path)
    raw = payload.get("ohlcv")
    if not isinstance(raw, dict):
        raise ValueError(f"Snapshot missing ohlcv dict: {path}")
    out: dict[str, pd.DataFrame] = {}
    for ticker, rows in raw.items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        out[str(ticker).upper()] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return out


def _baseline_aggregate() -> dict[str, Any]:
    payload = _load_json(BASELINE_SUMMARY)
    windows = payload.get("windows") or []
    return {
        "expected_value_score_sum": _round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl_sum": _round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count_sum": int(sum(int(w.get("trade_count") or 0) for w in windows)),
        "signals_generated_sum": int(
            sum(int(w.get("signals_generated") or 0) for w in windows)
        ),
        "signals_survived_sum": int(
            sum(int(w.get("signals_survived") or 0) for w in windows)
        ),
        "min_survival_rate": _round(
            min(float(w.get("survival_rate") or 0.0) for w in windows), 4
        ),
        "max_drawdown_pct_max": _round(
            max(float(w.get("max_drawdown_pct") or 0.0) for w in windows), 4
        ),
        "windows": [
            {
                "label": w.get("label"),
                "start": w.get("start"),
                "end": w.get("end"),
                "expected_value_score": w.get("expected_value_score"),
                "total_pnl": w.get("total_pnl"),
                "trade_count": w.get("trade_count"),
                "survival_rate": w.get("survival_rate"),
                "max_drawdown_pct": w.get("max_drawdown_pct"),
            }
            for w in windows
        ],
    }


def _features_at(frame: pd.DataFrame, idx: int) -> dict[str, Any] | None:
    if idx < 0 or idx >= len(frame):
        return None
    return compute_trend_features(frame.iloc[: idx + 1])


def _return_from_open(frame: pd.DataFrame, entry_idx: int, horizon: int) -> float | None:
    target_idx = entry_idx + horizon
    if entry_idx < 0 or target_idx >= len(frame):
        return None
    entry_open = _as_float(frame["Open"].iloc[entry_idx])
    target_close = _as_float(frame["Close"].iloc[target_idx])
    if not entry_open or target_close is None:
        return None
    return (target_close / entry_open) - 1.0


def _mfe_from_open(frame: pd.DataFrame, entry_idx: int, horizon: int) -> float | None:
    end_idx = min(len(frame) - 1, entry_idx + horizon)
    if entry_idx < 0 or entry_idx > end_idx:
        return None
    entry_open = _as_float(frame["Open"].iloc[entry_idx])
    if not entry_open:
        return None
    max_high = _as_float(frame["High"].iloc[entry_idx : end_idx + 1].max())
    return (max_high / entry_open) - 1.0 if max_high is not None else None


def _mae_from_open(frame: pd.DataFrame, entry_idx: int, end_idx: int) -> float | None:
    if entry_idx < 0 or entry_idx > end_idx or entry_idx >= len(frame):
        return None
    end_idx = min(end_idx, len(frame) - 1)
    entry_open = _as_float(frame["Open"].iloc[entry_idx])
    if not entry_open:
        return None
    min_low = _as_float(frame["Low"].iloc[entry_idx : end_idx + 1].min())
    return (min_low / entry_open) - 1.0 if min_low is not None else None


def _return_to_price(entry_open: float | None, exit_price: float | None) -> float | None:
    if not entry_open or exit_price is None:
        return None
    return (exit_price / entry_open) - 1.0


def _signal_state(features: dict[str, Any] | None) -> dict[str, Any]:
    if not features:
        return {}
    close = _as_float(features.get("close"))
    high_20d = _as_float(features.get("high_20d"))
    atr = _as_float(features.get("atr"))
    volume_ratio = _as_float(features.get("volume_spike_ratio"))
    momentum_10d = _as_float(features.get("momentum_10d_pct"))
    pct_from_52w = _as_float(features.get("pct_from_52w_high"))
    distance_to_20d_high = None
    if close and high_20d:
        distance_to_20d_high = (close / high_20d) - 1.0
    atr_over_close = None
    if atr and close:
        atr_over_close = atr / close
    rs_uptrend = momentum_10d is not None and momentum_10d >= 0.0
    near_52w_high = pct_from_52w is not None and pct_from_52w > -0.05
    rs_strong_without_spy = momentum_10d is not None and momentum_10d > 0.0
    hard_like = bool(
        features.get("above_200ma") is True
        and features.get("breakout_20d") is True
        and features.get("volume_spike") is True
        and rs_uptrend
        and atr_over_close is not None
        and atr_over_close <= MAX_ATR_OVER_CLOSE
    )
    full_quality_like = bool(hard_like and (near_52w_high or rs_strong_without_spy))
    return {
        "close": _round(close, 4),
        "high_20d": _round(high_20d, 4),
        "distance_to_20d_high_pct": _round(distance_to_20d_high, 6),
        "above_200ma": features.get("above_200ma"),
        "breakout_20d": features.get("breakout_20d"),
        "breakdown_20d": features.get("breakdown_20d"),
        "volume_spike": features.get("volume_spike"),
        "volume_spike_ratio": _round(volume_ratio, 4),
        "momentum_10d_pct": _round(momentum_10d, 4),
        "momentum_20d_pct": _round(features.get("momentum_20d_pct"), 4),
        "pct_from_52w_high": _round(pct_from_52w, 4),
        "near_52w_high": near_52w_high,
        "atr_over_close": _round(atr_over_close, 6),
        "rs_uptrend": rs_uptrend,
        "hard_trend_like": hard_like,
        "full_quality_trend_like": full_quality_like,
    }


def _precursor_kind(state: dict[str, Any]) -> str | None:
    if not state:
        return None
    distance = _as_float(state.get("distance_to_20d_high_pct"))
    volume_ratio = _as_float(state.get("volume_spike_ratio"))
    atr_over_close = _as_float(state.get("atr_over_close"))
    if state.get("above_200ma") is not True:
        return None
    if state.get("rs_uptrend") is not True:
        return None
    if state.get("breakdown_20d") is True:
        return None
    if atr_over_close is None or atr_over_close > MAX_ATR_OVER_CLOSE:
        return None
    if distance is None or distance < NEAR_20D_HIGH_PCT:
        return None
    if volume_ratio is None or volume_ratio < MIN_PRECURSOR_VOLUME_RATIO:
        return None
    if state.get("full_quality_trend_like"):
        return "full_quality_trend_like_before_recorded_entry"
    if state.get("breakout_20d") and not state.get("volume_spike"):
        return "breakout_without_2x_volume"
    if not state.get("breakout_20d") and volume_ratio >= MIN_WARM_VOLUME_RATIO:
        return "near_20d_high_warm_volume_before_breakout"
    if not state.get("breakout_20d"):
        return "near_20d_high_before_breakout"
    return "near_or_breakout_precursor"


def _find_index(frame: pd.DataFrame, date_text: Any) -> int | None:
    target = pd.Timestamp(date_text).normalize()
    matches = frame.index.get_indexer([target])
    if len(matches) == 0 or matches[0] < 0:
        return None
    return int(matches[0])


def _candidate_payload(
    *,
    window: str,
    ticker: str,
    frame: pd.DataFrame,
    actual_entry_idx: int,
    actual_exit_price: float | None,
    actual_return_10d: float | None,
    actual_return_20d: float | None,
    actual_return_to_exit: float | None,
    signal_idx: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start_idx = max(0, signal_idx - LOOKBACK_SESSIONS)
    for candidate_signal_idx in range(start_idx, signal_idx):
        entry_idx = candidate_signal_idx + 1
        features = _features_at(frame, candidate_signal_idx)
        state = _signal_state(features)
        kind = _precursor_kind(state)
        if kind is None:
            continue
        entry_open = _as_float(frame["Open"].iloc[entry_idx])
        actual_open = _as_float(frame["Open"].iloc[actual_entry_idx])
        forward_10d = _return_from_open(frame, entry_idx, 10)
        forward_20d = _return_from_open(frame, entry_idx, 20)
        return_to_exit = _return_to_price(entry_open, actual_exit_price)
        pre_entry_mae = _mae_from_open(frame, entry_idx, actual_entry_idx)
        pre_entry_mfe = _mfe_from_open(frame, entry_idx, actual_entry_idx - entry_idx)
        rows.append(
            {
                "window": window,
                "ticker": ticker,
                "precursor_kind": kind,
                "candidate_signal_date": _date_str(frame.index[candidate_signal_idx]),
                "candidate_entry_date": _date_str(frame.index[entry_idx]),
                "actual_signal_date": _date_str(frame.index[signal_idx]),
                "actual_entry_date": _date_str(frame.index[actual_entry_idx]),
                "lead_sessions_vs_actual_entry": actual_entry_idx - entry_idx,
                "lead_sessions_vs_actual_signal": signal_idx - candidate_signal_idx,
                "candidate_entry_open": _round(entry_open, 4),
                "actual_entry_open": _round(actual_open, 4),
                "entry_price_advantage_pct": _round(
                    ((actual_open / entry_open) - 1.0)
                    if actual_open and entry_open
                    else None,
                    6,
                ),
                "candidate_forward_10d_return_pct": _round(forward_10d, 6),
                "actual_forward_10d_return_pct": _round(actual_return_10d, 6),
                "forward_10d_delta_pct": _round(
                    (forward_10d - actual_return_10d)
                    if forward_10d is not None and actual_return_10d is not None
                    else None,
                    6,
                ),
                "candidate_forward_20d_return_pct": _round(forward_20d, 6),
                "actual_forward_20d_return_pct": _round(actual_return_20d, 6),
                "forward_20d_delta_pct": _round(
                    (forward_20d - actual_return_20d)
                    if forward_20d is not None and actual_return_20d is not None
                    else None,
                    6,
                ),
                "candidate_return_to_actual_exit_price_pct": _round(return_to_exit, 6),
                "actual_return_to_actual_exit_price_pct": _round(
                    actual_return_to_exit, 6
                ),
                "return_to_actual_exit_delta_pct": _round(
                    (return_to_exit - actual_return_to_exit)
                    if return_to_exit is not None
                    and actual_return_to_exit is not None
                    else None,
                    6,
                ),
                "pre_entry_mae_until_actual_entry_pct": _round(pre_entry_mae, 6),
                "pre_entry_mfe_until_actual_entry_pct": _round(pre_entry_mfe, 6),
                "signal_state": state,
            }
        )
    return rows


def _best_by(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    usable = [row for row in rows if row.get(key) is not None]
    if not usable:
        return None
    return max(usable, key=lambda row: float(row.get(key) or -999.0))


def _median(values: list[Any]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return float(median(clean))


def _mean(values: list[Any]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return float(mean(clean))


def _positive_share(rows: list[dict[str, Any]], key: str) -> float | None:
    clean = [float(row[key]) for row in rows if row.get(key) is not None]
    if not clean:
        return None
    return sum(1 for v in clean if v > 0.0) / len(clean)


def _summarize_selected(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row["latest_precursor"] for row in rows if row.get("latest_precursor")]
    total = len(rows)
    by_kind = Counter(row.get("precursor_kind") for row in selected)
    return {
        "total_trend_long_trades": total,
        "trades_with_latest_precursor": len(selected),
        "latest_precursor_coverage": _round(len(selected) / total if total else None, 4),
        "median_lead_sessions_vs_actual_entry": _round(
            _median([row.get("lead_sessions_vs_actual_entry") for row in selected]), 4
        ),
        "median_entry_price_advantage_pct": _round(
            _median([row.get("entry_price_advantage_pct") for row in selected]), 6
        ),
        "mean_entry_price_advantage_pct": _round(
            _mean([row.get("entry_price_advantage_pct") for row in selected]), 6
        ),
        "median_forward_10d_delta_pct": _round(
            _median([row.get("forward_10d_delta_pct") for row in selected]), 6
        ),
        "median_forward_20d_delta_pct": _round(
            _median([row.get("forward_20d_delta_pct") for row in selected]), 6
        ),
        "median_return_to_actual_exit_delta_pct": _round(
            _median([row.get("return_to_actual_exit_delta_pct") for row in selected]),
            6,
        ),
        "median_pre_entry_mae_until_actual_entry_pct": _round(
            _median([row.get("pre_entry_mae_until_actual_entry_pct") for row in selected]),
            6,
        ),
        "positive_forward_10d_delta_share": _round(
            _positive_share(selected, "forward_10d_delta_pct"), 4
        ),
        "positive_forward_20d_delta_share": _round(
            _positive_share(selected, "forward_20d_delta_pct"), 4
        ),
        "positive_return_to_exit_delta_share": _round(
            _positive_share(selected, "return_to_actual_exit_delta_pct"), 4
        ),
        "precursor_kind_counts": dict(sorted(by_kind.items())),
    }


def _summarize_oracle_best(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    selected = [
        row.get("oracle_best_20d_precursor")
        for row in rows
        if row.get("oracle_best_20d_precursor")
    ]
    if field == "forward_10d_delta_pct":
        selected = [
            row.get("oracle_best_10d_precursor")
            for row in rows
            if row.get("oracle_best_10d_precursor")
        ]
    return {
        "trade_count": len(selected),
        "median_delta_pct": _round(_median([row.get(field) for row in selected]), 6),
        "positive_delta_share": _round(_positive_share(selected, field), 4),
        "median_lead_sessions_vs_actual_entry": _round(
            _median([row.get("lead_sessions_vs_actual_entry") for row in selected]), 4
        ),
    }


def _window_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for window in WINDOWS:
        subset = [row for row in rows if row.get("window") == window]
        out[window] = _summarize_selected(subset)
    return out


def _positive_window_count(rows: list[dict[str, Any]], key: str) -> int:
    count = 0
    for window in WINDOWS:
        selected = [
            row["latest_precursor"]
            for row in rows
            if row.get("window") == window and row.get("latest_precursor")
        ]
        med = _median([row.get(key) for row in selected])
        if med is not None and med > 0.0:
            count += 1
    return count


def _top_cases(rows: list[dict[str, Any]], key: str, reverse: bool) -> list[dict[str, Any]]:
    selected = [
        {
            "window": row.get("window"),
            "ticker": row.get("ticker"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "pnl_pct_net": row.get("pnl_pct_net"),
            "latest_precursor": row.get("latest_precursor"),
        }
        for row in rows
        if row.get("latest_precursor") and row["latest_precursor"].get(key) is not None
    ]
    selected.sort(
        key=lambda row: float(row["latest_precursor"].get(key) or 0.0),
        reverse=reverse,
    )
    return selected[:8]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    summary = payload["attribution_summary"]
    gate = payload["observed_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Trend Long Entry Latency Attribution",
        "",
        "## Decision",
        "",
        f"- Status: {payload['status']}",
        f"- Decision: {payload['decision']}",
        f"- Observed gate passed: {gate['passed']}",
        f"- Failed reasons: {', '.join(gate['failed_reasons']) or 'none'}",
        "",
        "## Main Read",
        "",
        (
            f"- Actual trend_long trades analyzed: "
            f"{summary['latest_precursor']['total_trend_long_trades']}"
        ),
        (
            f"- Trades with a latest 1-5 session precursor: "
            f"{summary['latest_precursor']['trades_with_latest_precursor']} "
            f"({summary['latest_precursor']['latest_precursor_coverage']})"
        ),
        (
            f"- Median lead vs actual entry: "
            f"{summary['latest_precursor']['median_lead_sessions_vs_actual_entry']} "
            "sessions"
        ),
        (
            f"- Median entry price advantage: "
            f"{summary['latest_precursor']['median_entry_price_advantage_pct']}"
        ),
        (
            f"- Median 10d delta: "
            f"{summary['latest_precursor']['median_forward_10d_delta_pct']}"
        ),
        (
            f"- Median 20d delta: "
            f"{summary['latest_precursor']['median_forward_20d_delta_pct']}"
        ),
        (
            f"- Median return-to-actual-exit delta: "
            f"{summary['latest_precursor']['median_return_to_actual_exit_delta_pct']}"
        ),
        (
            f"- Median pre-entry MAE before actual entry: "
            f"{summary['latest_precursor']['median_pre_entry_mae_until_actual_entry_pct']}"
        ),
        "",
        "## Interpretation",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Reproduce",
        "",
        "```powershell",
        f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}",
        "```",
    ]
    return "\n".join(lines) + "\n"


def _analyze_trade(
    *,
    window: str,
    trade: dict[str, Any],
    frame: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_idx = _find_index(frame, trade.get("entry_date"))
    if entry_idx is None or entry_idx <= 0:
        return (
            {
                "window": window,
                "ticker": ticker,
                "entry_date": trade.get("entry_date"),
                "analysis_error": "entry_date_not_found_or_no_prior_signal_day",
            },
            [],
        )
    signal_idx = entry_idx - 1
    actual_open = _as_float(frame["Open"].iloc[entry_idx])
    exit_price = _as_float(trade.get("exit_raw_price") or trade.get("exit_price"))
    actual_return_10d = _return_from_open(frame, entry_idx, 10)
    actual_return_20d = _return_from_open(frame, entry_idx, 20)
    actual_return_to_exit = _return_to_price(actual_open, exit_price)
    actual_state = _signal_state(_features_at(frame, signal_idx))

    candidate_rows = _candidate_payload(
        window=window,
        ticker=ticker,
        frame=frame,
        actual_entry_idx=entry_idx,
        actual_exit_price=exit_price,
        actual_return_10d=actual_return_10d,
        actual_return_20d=actual_return_20d,
        actual_return_to_exit=actual_return_to_exit,
        signal_idx=signal_idx,
    )
    latest = candidate_rows[-1] if candidate_rows else None
    earliest = candidate_rows[0] if candidate_rows else None
    best_10d = _best_by(candidate_rows, "forward_10d_delta_pct")
    best_20d = _best_by(candidate_rows, "forward_20d_delta_pct")

    row = {
        "window": window,
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": _round(trade.get("pnl"), 2),
        "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
        "actual_signal_date": _date_str(frame.index[signal_idx]),
        "actual_entry_open": _round(actual_open, 4),
        "actual_exit_price_used": _round(exit_price, 4),
        "actual_forward_10d_return_pct": _round(actual_return_10d, 6),
        "actual_forward_20d_return_pct": _round(actual_return_20d, 6),
        "actual_return_to_actual_exit_price_pct": _round(actual_return_to_exit, 6),
        "actual_signal_state": actual_state,
        "candidate_count": len(candidate_rows),
        "latest_precursor": latest,
        "earliest_precursor": earliest,
        "oracle_best_10d_precursor": best_10d,
        "oracle_best_20d_precursor": best_20d,
    }
    return row, candidate_rows


def main() -> int:
    timestamp = _utc_now()
    before_after = _baseline_aggregate()
    trade_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    source_counts: dict[str, Any] = {}

    for window, spec in WINDOWS.items():
        backtest = _load_json(REPO_ROOT / spec["backtest"])
        frames = _load_snapshot(REPO_ROOT / spec["snapshot"])
        trades = [
            trade
            for trade in backtest.get("trades", [])
            if trade.get("strategy") == "trend_long"
        ]
        source_counts[window] = {
            "trend_long_trades": len(trades),
            "snapshot_tickers": len(frames),
            "backtest_artifact": spec["backtest"],
            "snapshot": spec["snapshot"],
        }
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            frame = frames.get(ticker)
            if frame is None or frame.empty:
                trade_rows.append(
                    {
                        "window": window,
                        "ticker": ticker,
                        "entry_date": trade.get("entry_date"),
                        "analysis_error": "ticker_missing_from_snapshot",
                    }
                )
                continue
            row, rows = _analyze_trade(window=window, trade=trade, frame=frame)
            trade_rows.append(row)
            candidate_rows.extend(rows)

    latest_summary = _summarize_selected(trade_rows)
    positive_10d_windows = _positive_window_count(trade_rows, "forward_10d_delta_pct")
    positive_20d_windows = _positive_window_count(trade_rows, "forward_20d_delta_pct")
    coverage = latest_summary.get("latest_precursor_coverage") or 0.0
    median_10d = latest_summary.get("median_forward_10d_delta_pct") or 0.0
    median_20d = latest_summary.get("median_forward_20d_delta_pct") or 0.0
    positive_20d_share = latest_summary.get("positive_forward_20d_delta_share") or 0.0
    median_mae = latest_summary.get("median_pre_entry_mae_until_actual_entry_pct")
    mae_ok = median_mae is not None and median_mae >= MAX_MEDIAN_PRE_ENTRY_MAE
    observed_passed = bool(
        coverage >= MIN_OBSERVED_COVERAGE
        and median_10d > 0.0
        and median_20d > 0.0
        and positive_20d_windows >= MIN_POSITIVE_WINDOWS
        and positive_20d_share >= MIN_POSITIVE_20D_SHARE
        and mae_ok
    )
    failed_reasons = [
        reason
        for reason, failed in [
            ("latest_precursor_coverage_below_55pct", coverage < MIN_OBSERVED_COVERAGE),
            ("median_10d_delta_not_positive", median_10d <= 0.0),
            ("median_20d_delta_not_positive", median_20d <= 0.0),
            ("fewer_than_two_positive_20d_windows", positive_20d_windows < MIN_POSITIVE_WINDOWS),
            (
                "positive_20d_delta_share_below_55pct",
                positive_20d_share < MIN_POSITIVE_20D_SHARE,
            ),
            ("median_pre_entry_mae_worse_than_4pct", not mae_ok),
        ]
        if failed
    ]
    decision = (
        "observed_entry_latency_lead"
        if observed_passed
        else "observed_only_no_actionable_trend_long_latency_edge"
    )
    actual_success = 1 if observed_passed else 0
    post_run_reflection = {
        "why_result_happened": (
            "The edge appeared because the diagnostic conditioned on actual "
            "trend_long trades instead of replaying a broad prebreakout "
            "candidate pool. Most useful rows were already above the prior "
            "20-day high but had volume between 1.0x and 2.0x, so the official "
            "2x volume confirmation often delayed entry by one session without "
            "much added pre-entry drawdown. The late_strong window stayed mixed, "
            "which is why this is a lead rather than an entry rule."
            if observed_passed
            else (
                "The diagnostic failed because actual trend_long trades did not "
                "show enough stable precursor coverage or forward replacement "
                "value after the same PIT next-open entry envelope was applied."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retune a generic OHLCV prebreakout threshold, volume ratio, "
            "lookback length, hold horizon, or near-high distance on the frozen "
            "windows. Prior broad prebreakout entries were rejected, and this "
            "run only supports named latency attribution on already-accepted "
            "trend_long trades."
        ),
        "new_evidence_required": (
            "A promotable next step needs a shared default-off paper helper that "
            "prospectively logs breakout-without-2x-volume precursor rows, "
            "records displacement versus the accepted comparator, and then runs "
            "Gate 1-4 with a fixed rule. A non-OHLCV catalyst or forward-row "
            "maturation axis would be needed before any live/default entry "
            "timing change."
        ),
    }
    prediction = {
        "success_probability": 0.35,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "prior_prebreakout_failures",
            "precursors_absent",
            "earlier_entries_worse",
            "window_concentration",
            "needs_non_ohlcv_evidence",
        ],
        "confidence_reason": (
            "Prior OHLCV-only and catalyst-qualified prebreakout entries both "
            "failed Gate 4, so broad early-entry success was unlikely. This run "
            "had a better but still risky prior because it measured only named "
            "actual trend_long trades, where false positives are lower; the main "
            "risk was that the apparent benefit would concentrate in one window "
            "or disappear once next-open execution and pre-entry MAE were counted."
        ),
        "recorded_at": "2026-06-27T04:22:22+00:00",
    }
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": round(
            (prediction["success_probability"] - actual_success) ** 2, 6
        ),
        "calibration_direction": (
            "underconfident" if observed_passed else "directionally_calibrated"
        ),
        "surprise_level": "medium" if observed_passed else "low",
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": 0.0,
        "ev_prediction_error": 0.0,
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": 0.0,
        "pnl_prediction_error": 0.0,
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": None if observed_passed else "; ".join(failed_reasons),
        "predicted_failure_mode_hit": False if observed_passed else bool(failed_reasons),
        "surprise_note": (
            "The prior was too cautious: broad prebreakout entries failed, but "
            "actual-trade-only breakout-without-2x-volume precursor rows showed "
            "enough replacement value to pass the read-only gate."
            if observed_passed
            else "The negative outcome matched the prior failures in broad early-entry tests."
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "lane": "alpha_search",
        "hypothesis": (
            "Current trend_long may enter too late because it waits for a "
            "prior-20d-high close breakout plus >2x volume confirmation; actual "
            "trend_long trades may already have production-visible near-breakout "
            "precursor rows 1-5 sessions earlier with better replacement value."
        ),
        "change_type": "observed_only_entry_timing_attribution",
        "implementation_mode": "read_only_attribution",
        "mechanism_family": "entry",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "production_visible_ohlcv_precursor_rows_on_actual_trend_long_trades",
        "new_evidence_axis": (
            "Direct forward replacement-value attribution on the actual accepted "
            "trend_long trades' own 1-5 session pre-signal rows; not a broad "
            "prebreakout candidate-pool replay, threshold retune, or production "
            "entry change."
        ),
        "parameters": {
            "lookback_sessions_before_actual_signal": LOOKBACK_SESSIONS,
            "near_20d_high_pct": NEAR_20D_HIGH_PCT,
            "min_precursor_volume_ratio": MIN_PRECURSOR_VOLUME_RATIO,
            "min_warm_volume_ratio": MIN_WARM_VOLUME_RATIO,
            "max_atr_over_close": MAX_ATR_OVER_CLOSE,
            "precursor_core_checks": [
                "above_200ma true",
                "10d momentum >= 0",
                "not breakdown_20d",
                "close within 1pct below or above prior 20d high",
                "volume_spike_ratio >= 1.0",
                "ATR / close <= 7pct",
            ],
            "windows": WINDOWS,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "entry: the accepted trend_long confirmation stack may be late; "
                "measure actual-trade precursor replacement value before any "
                "entry rule proposal."
            ),
            "2_history_check": {
                "exp-20260530-013": (
                    "Rejected OHLCV-only prebreakout entry: aggregate EV -1.9239 "
                    "and PnL -$48,109.45."
                ),
                "exp-20260530-016": (
                    "Rejected catalyst-qualified prebreakout entry: aggregate "
                    "EV +0.0211 but not all windows positive."
                ),
                "novelty_gate": (
                    "exp-20260627-006 passed novelty because it is direct "
                    "actual-trade latency attribution, not a new prebreakout "
                    "candidate-pool replay."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only lead if latest precursor coverage >=55pct, "
                "median 10d and 20d deltas are positive, at least two windows "
                "have positive 20d median deltas, positive 20d share >=55pct, "
                "and median pre-entry MAE is no worse than -4pct."
            ),
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "backtest_protocol": (
            "Reads docs/backtesting.md canonical 20260604 accepted-stack "
            "per-window backtest artifacts and matching OHLCV snapshots. No "
            "after strategy variant is run because no behavior changes."
        ),
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
        },
        "source_counts": source_counts,
        "attribution_summary": {
            "latest_precursor": latest_summary,
            "oracle_best_10d_precursor": _summarize_oracle_best(
                trade_rows, "forward_10d_delta_pct"
            ),
            "oracle_best_20d_precursor": _summarize_oracle_best(
                trade_rows, "forward_20d_delta_pct"
            ),
            "window_summaries": _window_summaries(trade_rows),
            "top_positive_20d_latest_cases": _top_cases(
                trade_rows, "forward_20d_delta_pct", reverse=True
            ),
            "top_negative_20d_latest_cases": _top_cases(
                trade_rows, "forward_20d_delta_pct", reverse=False
            ),
        },
        "observed_gate": {
            "passed": observed_passed,
            "rule": (
                "Coverage >=55pct, median 10d/20d latest-precursor deltas >0, "
                "at least two windows with positive median 20d delta, positive "
                "20d delta share >=55pct, and median pre-entry MAE >= -4pct."
            ),
            "latest_precursor_coverage": coverage,
            "median_forward_10d_delta_pct": median_10d,
            "median_forward_20d_delta_pct": median_20d,
            "positive_10d_windows": positive_10d_windows,
            "positive_20d_windows": positive_20d_windows,
            "positive_20d_delta_share": positive_20d_share,
            "median_pre_entry_mae_until_actual_entry_pct": median_mae,
            "failed_reasons": failed_reasons,
        },
        "decision": decision,
        "rejection_reason": None if observed_passed else "; ".join(failed_reasons),
        "post_run_reflection": post_run_reflection,
        "next_retry_requires": (
            "Do not retune a broad OHLCV prebreakout entry. A valid next step "
            "needs either named latency cases with materially better forward "
            "replacement rows, a shared default-off paper helper that logs "
            "precursor rows prospectively, or a non-OHLCV evidence axis that "
            "separates early entries from false starts."
        ),
        "prediction": prediction,
        "calibration": calibration,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "read_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_realistic_execution_envelope": "Not evaluated; observed-only attribution.",
            "live_ready": False,
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(TRADE_ROWS_JSON),
            _repo_rel(CANDIDATE_ROWS_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(TRADE_ROWS_JSON, trade_rows)
    _write_json(CANDIDATE_ROWS_JSON, candidate_rows)
    _write_json(BEFORE_AGG_JSON, before_after)
    _write_json(AFTER_AGG_JSON, before_after)
    _write_json(DOC_LOG, payload)
    ticket = _load_json(DOC_TICKET) if DOC_TICKET.exists() else {}
    ticket.update(
        {
            "status": "observed_only",
            "completed_at": timestamp,
            "prediction": prediction,
            "result": {
                "decision": decision,
                "observed_gate": payload["observed_gate"],
                "artifact": _repo_rel(OUT_JSON),
                "calibration": calibration,
                "summary": post_run_reflection["why_result_happened"],
            },
        }
    )
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps(_safe(payload["observed_gate"]), indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
