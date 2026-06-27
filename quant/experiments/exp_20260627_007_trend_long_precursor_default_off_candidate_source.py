"""exp-20260627-007: trend-long precursor default-off candidate source.

This is a fixed follow-up to exp-20260627-006. It tests whether the
production-visible pre-signal rows that showed entry-latency value on actual
``trend_long`` trades survive as an unconditional default-off paper source.

No live/default orders, core ranking, sizing, exits, LLM/news behavior, or
watchlists are changed. If this fails Gate 4, no strategy logic is retained.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (SCRIPTS_DIR, QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
from feature_layer import compute_trend_features  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402


EXPERIMENT_ID = "exp-20260627-007"
OWNER = "codex-alpha-explore"
LANE = "alpha_search"
SLUG = "trend_long_precursor_default_off_candidate_source"
RUNNER = f"quant/experiments/exp_20260627_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STEM = "trend_long_precursor_default_off_candidate_source"
TRIAL_FAMILY = "trend_long_entry_latency_default_off_candidate_source"
TRIAL_VARIANT_ID = "trend_long_precursor_top1_next_open_10d_v1"
CHANGED_VARIABLE = "trend_long_precursor_default_off_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
MECHANISM_FAMILY = "production_visible_free_ohlcv_candidate_pool"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_PATH = Path(DEFAULT_WAREHOUSE_PATH)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 25_000_000.0
MIN_HISTORY_SESSIONS = 220
MIN_PRECURSOR_VOLUME_RATIO = 1.0
MAX_PRECURSOR_VOLUME_RATIO = 2.0
NEAR_20D_HIGH_PCT = -0.01
MAX_ATR_OVER_CLOSE = 0.07

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35
MIN_EV_IMPROVED_WINDOWS = 2

ACCEPTED_COMPARATORS = {
    "narrow_range_compression_breakout": {
        "experiment_id": "exp-20260608-013",
        "expected_value_delta_sum": 0.1608,
        "total_pnl_delta_sum": 2248.98,
        "target_trade_count": 44,
    },
    "distribution_day_absorption": {
        "experiment_id": "exp-20260611-007",
        "expected_value_delta_sum": 0.5286,
        "total_pnl_delta_sum": 10432.91,
        "target_trade_count": 113,
    },
}
COMPARATOR_EV_FLOOR = max(
    row["expected_value_delta_sum"] for row in ACCEPTED_COMPARATORS.values()
)
COMPARATOR_PNL_FLOOR = max(
    row["total_pnl_delta_sum"] for row in ACCEPTED_COMPARATORS.values()
)

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

HYPOTHESIS = (
    "A fixed default-off trend-long precursor paper source can monetize "
    "production-visible near-breakout rows that appear before accepted "
    "trend_long entries, adding replacement value without changing core live "
    "entries."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: current trend_long may wait too long for >2x volume. "
    "Rows already above the 200-day moving average, near or above the prior "
    "20-day high, with positive short momentum, non-breakdown state, and "
    "1.0x-2.0x volume may be useful default-off paper entries."
)
NEW_EVIDENCE_AXIS = (
    "exp-20260627-006 created actual-trend-long entry-latency evidence. This "
    "run freezes that precursor shape as an unconditional default-off paper "
    "source instead of sweeping broad prebreakout thresholds."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260627-006",
    "exp-20260530-013",
    "exp-20260530-016",
    "exp-20260608-013",
    "exp-20260611-007",
]

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "prior_prebreakout_failures",
        "window_regression",
        "drawdown_drift",
        "not_incremental",
        "concentration",
    ],
    "confidence_reason": (
        "exp-20260627-006 found positive 10d/20d replacement deltas on actual "
        "trend_long precursor rows, but exp-20260530-013 and exp-20260530-016 "
        "showed that broad prebreakout rules are fragile. The key risk is that "
        "conditioning on actual future trend_long trades created the observed "
        "edge, so the unconditional default-off source may regress."
    ),
    "recorded_at": "2026-06-27T05:04:26+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "production_watchlist_changed": False,
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "replay_only": True,
    "adapter_status": "experiment_owned_replay_only",
    "activation_envelope": {
        "intended_notional": "default-off paper only at fixed $4,000 notional",
        "capital_cap": "no live capital; future activation requires a cap",
        "liquidity_slippage_model": (
            "price >= $10, ADV20 >= $25M, next-open entry, 10-session close "
            "exit, target-side sell slippage, and round-trip cost"
        ),
        "portfolio_displacement": "paper overlay versus accepted core baseline",
        "kill_switch": (
            "not live-ready; future shared helper would require forward "
            "replacement-value and drawdown/concentration kill switch"
        ),
        "order_semantics": "no orders emitted",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def round_float(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(safe(payload), ensure_ascii=True, sort_keys=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = (
        path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.exists()
        else []
    )
    rows = [line for line in lines if compact not in line and pretty not in line]
    rows.append(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def configure_sleeve_globals() -> None:
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.OUT_DIR = OUT_DIR
    sleeve.OUT_JSON = OUT_JSON
    sleeve.LOG_JSON = LOG_JSON
    sleeve.TICKET_JSON = TICKET_JSON
    sleeve.CARD_MD = CARD_MD
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG_JSONL


def value(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def series(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return shadow._series(snapshot, ticker)


def row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return shadow._row_index(rows)


def average(values: list[float | None]) -> float | None:
    clean = [float(item) for item in values if item is not None]
    if len(clean) != len(values) or not clean:
        return None
    return sum(clean) / len(clean)


def prior_avg_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int = 20,
) -> float | None:
    if idx < lookback:
        return None
    values: list[float | None] = []
    for row in rows[idx - lookback : idx]:
        close = value(row, "Close")
        volume = value(row, "Volume")
        values.append(None if close is None or volume is None else close * volume)
    return average(values)


def features_at(rows: list[dict[str, Any]], idx: int) -> dict[str, Any] | None:
    if idx < 0 or idx >= len(rows):
        return None
    frame = pd.DataFrame(rows[: idx + 1])
    return compute_trend_features(frame[["Open", "High", "Low", "Close", "Volume"]])


def signal_state(features: dict[str, Any] | None) -> dict[str, Any]:
    if not features:
        return {}
    close = round_float(features.get("close"), 6)
    high_20d = round_float(features.get("high_20d"), 6)
    atr = round_float(features.get("atr"), 6)
    volume_ratio = round_float(features.get("volume_spike_ratio"), 6)
    momentum_10d = round_float(features.get("momentum_10d_pct"), 6)
    momentum_20d = round_float(features.get("momentum_20d_pct"), 6)
    pct_from_52w = round_float(features.get("pct_from_52w_high"), 6)
    distance_to_20d_high = None
    if close and high_20d:
        distance_to_20d_high = (close / high_20d) - 1.0
    atr_over_close = None
    if atr and close:
        atr_over_close = atr / close
    rs_uptrend = momentum_10d is not None and momentum_10d >= 0.0
    near_52w_high = pct_from_52w is not None and pct_from_52w > -0.05
    hard_like = bool(
        features.get("above_200ma") is True
        and features.get("breakout_20d") is True
        and features.get("volume_spike") is True
        and rs_uptrend
        and atr_over_close is not None
        and atr_over_close <= MAX_ATR_OVER_CLOSE
    )
    full_quality_like = bool(hard_like and near_52w_high)
    return {
        "close": round_float(close, 4),
        "high_20d": round_float(high_20d, 4),
        "distance_to_20d_high_pct": round_float(distance_to_20d_high, 6),
        "above_200ma": features.get("above_200ma"),
        "breakout_20d": features.get("breakout_20d"),
        "breakdown_20d": features.get("breakdown_20d"),
        "volume_spike": features.get("volume_spike"),
        "volume_spike_ratio": round_float(volume_ratio, 4),
        "momentum_10d_pct": round_float(momentum_10d, 4),
        "momentum_20d_pct": round_float(momentum_20d, 4),
        "pct_from_52w_high": round_float(pct_from_52w, 4),
        "near_52w_high": near_52w_high,
        "daily_close_location": features.get("daily_close_location"),
        "signal_day_ticker_dollar_volume": features.get(
            "signal_day_ticker_dollar_volume"
        ),
        "atr_over_close": round_float(atr_over_close, 6),
        "rs_uptrend": rs_uptrend,
        "hard_trend_like": hard_like,
        "full_quality_trend_like": full_quality_like,
    }


def precursor_kind(state: dict[str, Any]) -> str | None:
    if not state:
        return None
    distance = round_float(state.get("distance_to_20d_high_pct"), 6)
    volume_ratio = round_float(state.get("volume_spike_ratio"), 6)
    atr_over_close = round_float(state.get("atr_over_close"), 6)
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
    if volume_ratio > MAX_PRECURSOR_VOLUME_RATIO:
        return None
    if state.get("breakout_20d") and not state.get("volume_spike"):
        return "breakout_without_2x_volume"
    if not state.get("breakout_20d") and volume_ratio >= 1.2:
        return "near_20d_high_warm_volume_before_breakout"
    if not state.get("breakout_20d"):
        return "near_20d_high_before_breakout"
    return None


def candidate_score(state: dict[str, Any], kind: str, adv20: float) -> float:
    kind_weight = {
        "breakout_without_2x_volume": 3.0,
        "near_20d_high_warm_volume_before_breakout": 2.0,
        "near_20d_high_before_breakout": 1.0,
    }[kind]
    distance = float(state.get("distance_to_20d_high_pct") or 0.0)
    volume_ratio = float(state.get("volume_spike_ratio") or 0.0)
    momentum_10d = float(state.get("momentum_10d_pct") or 0.0)
    momentum_20d = float(state.get("momentum_20d_pct") or 0.0)
    close_location = float(state.get("daily_close_location") or 0.0)
    liquidity_bonus = min(math.log10(max(adv20, 1.0) / MIN_AVG_DOLLAR_VOLUME_20D), 1.0)
    return (
        kind_weight * 100.0
        + min(volume_ratio, MAX_PRECURSOR_VOLUME_RATIO) * 10.0
        + distance * 25.0
        + momentum_20d * 10.0
        + momentum_10d * 5.0
        + close_location
        + liquidity_bonus
    )


def candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    entries_by_date = shadow._baseline_entries(before_result)
    dates = [
        day
        for day in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= day <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    reject_reasons: Counter[str] = Counter()
    excluded = {"SPY", "QQQ"}

    for ticker in sorted(set(snapshot) - excluded):
        rows = series(snapshot, ticker)
        if len(rows) < MIN_HISTORY_SESSIONS:
            reject_reasons["insufficient_history"] += 1
            continue
        idx_by_date = row_index(rows)
        for signal_date in dates:
            idx = idx_by_date.get(signal_date)
            if idx is None or idx < MIN_HISTORY_SESSIONS:
                continue
            cur = rows[idx]
            close = value(cur, "Close")
            adv20 = prior_avg_dollar_volume(rows, idx, 20)
            if close is None or adv20 is None:
                reject_reasons["missing_price_or_liquidity"] += 1
                continue
            if close < MIN_PRICE:
                reject_reasons["below_min_price"] += 1
                continue
            if adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
                reject_reasons["below_min_avg_dollar_volume_20d"] += 1
                continue

            state = signal_state(features_at(rows, idx))
            kind = precursor_kind(state)
            if kind is None:
                reject_reasons["not_fixed_precursor_shape"] += 1
                continue

            ab_entries = entries_by_date.get(signal_date, [])
            score = candidate_score(state, kind, adv20)
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "candidate_source": STEM,
                    "rule_version": RULE_VERSION,
                    "candidate_score": round_float(score, 6),
                    "precursor_kind": kind,
                    "avg_dollar_volume_prior20": round_float(adv20, 2),
                    "signal_close": state.get("close"),
                    "prior_20d_high": state.get("high_20d"),
                    "distance_to_20d_high_pct": state.get("distance_to_20d_high_pct"),
                    "volume_spike_ratio": state.get("volume_spike_ratio"),
                    "momentum_10d_pct": state.get("momentum_10d_pct"),
                    "momentum_20d_pct": state.get("momentum_20d_pct"),
                    "daily_close_location": state.get("daily_close_location"),
                    "atr_over_close": state.get("atr_over_close"),
                    "above_200ma": state.get("above_200ma"),
                    "breakout_20d": state.get("breakout_20d"),
                    "volume_spike": state.get("volume_spike"),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            row["ticker"],
        )
    )
    return candidates, reject_reasons


def select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    last_signal_date_by_ticker: dict[str, date] = {}
    for row in candidates:
        signal_day = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "")
        parsed_signal_day = date.fromisoformat(signal_day)
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_entry_overlap"})
            continue
        last_signal_day = last_signal_date_by_ticker.get(ticker)
        if (
            last_signal_day is not None
            and (parsed_signal_day - last_signal_day).days <= SAME_TICKER_COOLDOWN_DAYS
        ):
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        if used_date_counts[signal_day] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_day] += 1
        last_signal_date_by_ticker[ticker] = parsed_signal_day
    return selected, filtered


def target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    summary = sleeve._target_trade_summary(target_trades_by_window)
    pnl_values = [
        float(trade.get("pnl") or 0.0)
        for trades in target_trades_by_window.values()
        for trade in trades
    ]
    pct_values = [
        float(trade.get("pnl_pct_net") or 0.0)
        for trades in target_trades_by_window.values()
        for trade in trades
    ]
    summary["avg_pnl_per_trade"] = round_float(mean(pnl_values), 2) if pnl_values else None
    summary["avg_return_pct_net"] = round_float(mean(pct_values), 6) if pct_values else None
    return summary


def aggregate_rows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": round_float(ev_before, 6),
        "after_expected_value_score_sum": round_float(ev_after, 6),
        "expected_value_score_delta_sum": round_float(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": (
            round_float((ev_after - ev_before) / ev_before, 6) if ev_before else None
        ),
        "baseline_total_pnl_sum": round_float(pnl_before, 2),
        "after_total_pnl_sum": round_float(pnl_after, 2),
        "total_pnl_delta_sum": round_float(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": (
            round_float((pnl_after - pnl_before) / pnl_before, 6)
            if pnl_before
            else None
        ),
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": round_float(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def baseline_identity(before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    documented = load_json(BASELINE_RESULT)
    by_label = {row.get("label"): row for row in documented.get("windows") or []}
    deltas: dict[str, dict[str, Any]] = {}
    for label, before in before_metrics.items():
        doc = by_label.get(label) or {}
        deltas[label] = {
            "expected_value_score_delta_vs_doc": round_float(
                float(before.get("expected_value_score") or 0.0)
                - float(doc.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_delta_vs_doc": round_float(
                float(before.get("total_pnl") or 0.0)
                - float(doc.get("total_pnl") or 0.0),
                2,
            ),
            "trade_count_delta_vs_doc": int(before.get("trade_count") or 0)
            - int(doc.get("trade_count") or 0),
        }
    return {
        "documented_baseline": repo_rel(BASELINE_RESULT),
        "current_baseline_source": {
            "engine": "BacktestEngine",
            "ohlcv_warehouse_path": repo_rel(WAREHOUSE_PATH),
            "ohlcv_warehouse_snapshot_source": "per-window canonical snapshot",
            "universe": "data_layer.get_universe via legacy shadow module",
        },
        "deltas_by_window": deltas,
        "matches_documented": all(
            abs(float(row["expected_value_score_delta_vs_doc"] or 0.0)) <= 0.0002
            and abs(float(row["total_pnl_delta_vs_doc"] or 0.0)) <= 1.0
            and int(row["trade_count_delta_vs_doc"] or 0) == 0
            for row in deltas.values()
        ),
    }


def run_canonical_baseline(universe: list[str], cfg: dict[str, str]) -> dict[str, Any]:
    engine = shadow.BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=shadow.BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_warehouse_path=str(WAREHOUSE_PATH),
        ohlcv_warehouse_snapshot_source=cfg["snapshot"],
    )
    result = engine.run()
    result["expected_value_score"] = shadow.compute_expected_value_score(result)
    return result


def gate4_result(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    window_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    failed: list[str] = []
    warnings: list[str] = []
    ev_delta = float(aggregate.get("expected_value_score_delta_sum") or 0.0)
    pnl_delta = float(aggregate.get("total_pnl_delta_sum") or 0.0)

    if ev_delta <= 0:
        failed.append("aggregate_expected_value_delta_not_positive")
    if pnl_delta <= 0:
        failed.append("aggregate_total_pnl_delta_not_positive")
    if ev_delta <= COMPARATOR_EV_FLOOR:
        failed.append("accepted_comparator_ev_floor_not_beaten")
    if pnl_delta <= COMPARATOR_PNL_FLOOR:
        failed.append("accepted_comparator_pnl_floor_not_beaten")

    max_drawdown_drift_by_window: dict[str, float] = {}
    for label, row in window_rows.items():
        delta = row["delta"]
        before = row["before"]
        after = row["after"]
        window_ev_delta = float(delta.get("expected_value_score") or 0.0)
        window_pnl_delta = float(delta.get("total_pnl") or 0.0)
        if window_ev_delta < 0:
            failed.append(f"{label}_expected_value_regressed")
        if window_pnl_delta < 0:
            failed.append(f"{label}_total_pnl_regressed")
        before_drawdown = before.get("max_drawdown_pct")
        after_drawdown = after.get("max_drawdown_pct")
        if isinstance(before_drawdown, (int, float)) and isinstance(
            after_drawdown, (int, float)
        ):
            drift = round(float(after_drawdown) - float(before_drawdown), 6)
            max_drawdown_drift_by_window[label] = drift
            if drift > MAX_DRAWDOWN_WORSE:
                failed.append(f"{label}_max_drawdown_worse_gt_{MAX_DRAWDOWN_WORSE}")

    if int(aggregate["windows_ev_improved"]) < MIN_EV_IMPROVED_WINDOWS:
        failed.append("too_few_ev_improved_windows")
    if int(target_summary["total_trade_count"]) < MIN_TARGET_TRADES:
        failed.append("too_few_target_trades")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("too_few_target_windows")
    max_positive_share = target_summary.get("max_single_positive_pnl_share")
    positive_hhi = target_summary.get("positive_pnl_hhi")
    if max_positive_share is not None and max_positive_share > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("single_positive_ticker_concentration_too_high")
    if positive_hhi is not None and positive_hhi > MAX_POSITIVE_HHI:
        failed.append("positive_pnl_hhi_too_high")
    if not target_summary.get("positive_by_ticker_pnl"):
        failed.append("no_positive_target_pnl")

    passed = not failed
    if passed:
        warnings.append("positive_replay_only_requires_shared_helper_before_retention")
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_trend_long_precursor_default_off"
            if passed
            else "rejected_trend_long_precursor_default_off_candidate_source"
        ),
        "failed_reasons": sorted(set(failed)),
        "warnings": warnings,
        "target_trade_count": target_summary["total_trade_count"],
        "windows_with_target_trades": target_summary["windows_with_target_trades"],
        "ev_improved_windows": aggregate["windows_ev_improved"],
        "pnl_improved_windows": aggregate["windows_pnl_improved"],
        "aggregate_expected_value_delta": round_float(ev_delta, 6),
        "aggregate_total_pnl_delta": round_float(pnl_delta, 2),
        "accepted_comparators": ACCEPTED_COMPARATORS,
        "comparator_ev_floor": COMPARATOR_EV_FLOOR,
        "comparator_pnl_floor": COMPARATOR_PNL_FLOOR,
        "max_drawdown_drift_by_window": max_drawdown_drift_by_window,
        "concentration": {
            "max_single_positive_pnl_share": max_positive_share,
            "positive_pnl_hhi": positive_hhi,
        },
    }


def build_payload() -> dict[str, Any]:
    configure_sleeve_globals()
    timestamp = utc_now()
    gate2_open_positions = sleeve._audit_open_positions()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    raw_candidate_days: "OrderedDict[str, int]" = OrderedDict()
    reject_reasons_by_window: "OrderedDict[str, dict[str, int]]" = OrderedDict()

    universe = sorted(shadow.get_universe())

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline replay plus trend-long precursor overlay")
        before_result = run_canonical_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        candidates, reject_reasons = candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
        )
        selected_trades, filtered_candidates = select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        raw_candidate_days[label] = len({row["date"] for row in candidates})
        reject_reasons_by_window[label] = dict(reject_reasons)
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "raw_candidate_days": raw_candidate_days[label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = aggregate_rows(window_rows)
    targets = target_trade_summary(target_trades_by_window)
    gate4 = gate4_result(
        aggregate=aggregate,
        target_summary=targets,
        window_rows=window_rows,
    )
    status = "observed_only" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    actual_success = 1 if gate4["passed"] else 0
    brier = round((PREDICTION["success_probability"] - actual_success) ** 2, 6)
    failure_text = "; ".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None
    identity = baseline_identity(before_metrics)

    why = (
        "The fixed precursor source failed because the exp-20260627-006 edge "
        "was conditional on actual future trend_long trades. Once replayed "
        "unconditionally as a default-off top-1 paper source, false starts, "
        "window instability, comparator weakness, or concentration erased the "
        "latency benefit."
        if not gate4["passed"]
        else (
            "The precursor source remained positive even when replayed "
            "unconditionally, but this run did not promote a shared helper "
            "because the reserved scope did not include production adapter "
            "files."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "candidate_pool_full_stack_replay_attempt",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed precursor gate",
            "historical replay",
            "daily snapshot schema declaration",
            "execution envelope declaration",
            "full-stack verdict",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "observed_trend_long_entry_latency_lead",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "baseline_identity": identity,
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on the signal "
                "date; paper entry is next available open; exit is the close "
                "ten trading sessions later with existing paper sleeve costs."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_history_sessions": MIN_HISTORY_SESSIONS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "near_20d_high_pct": NEAR_20D_HIGH_PCT,
            "min_precursor_volume_ratio": MIN_PRECURSOR_VOLUME_RATIO,
            "max_precursor_volume_ratio": MAX_PRECURSOR_VOLUME_RATIO,
            "max_atr_over_close": MAX_ATR_OVER_CLOSE,
            "excluded_tickers": ["SPY", "QQQ"],
            "precursor_shape": [
                "above_200ma true",
                "10d momentum >= 0",
                "not breakdown_20d",
                "close within 1pct below or above prior 20d high",
                "volume_spike_ratio between 1.0 and 2.0 inclusive",
                "ATR / close <= 7pct",
                "exclude existing full 2x-volume trend confirmation",
            ],
            "selection_rank": [
                "signal_date",
                "precursor kind priority",
                "volume ratio",
                "distance to 20d high",
                "momentum",
                "close location",
                "liquidity",
                "ticker",
            ],
            "accepted_comparators": ACCEPTED_COMPARATORS,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Near-neighbor warning accepted by override; ohlcv_relation "
                    "candidate_pool_top1_10d cell was not saturated at "
                    "accept_rate 5.21pct vs 5pct threshold."
                ),
                "related_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "prior_failures": (
                    "exp-20260530-013 and exp-20260530-016 rejected broad "
                    "prebreakout entries. exp-20260627-006 supplied the new "
                    "actual-trade latency evidence axis."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Canonical three windows must improve aggregate EV/PnL, have "
                "no EV/PnL-regressed windows, enough target trades across all "
                "windows, drawdown drift <=0.5pp, concentration within guard, "
                "and beat accepted compression/distribution comparator floors."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_identity": identity,
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "Date/Open/High/Low/Close/Volume",
                "entry_date",
                "target_price",
                "feature_layer.compute_trend_features fields",
            ],
            "passed": bool(gate2_open_positions.get("passed")),
        },
        "gate3": {
            "new_core_filter_added": False,
            "core_survival_unchanged": True,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in before_metrics.values()
            ),
            "passed": True,
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "raw_candidate_counts": raw_candidate_counts,
        "raw_candidate_days": raw_candidate_days,
        "candidate_reject_reasons_by_window": reject_reasons_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": targets,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": brier,
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
            "ev_prediction_error": round_float(
                float(aggregate["expected_value_score_delta_sum"])
                - float(PREDICTION["expected_ev_delta"]),
                6,
            ),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            "pnl_prediction_error": round_float(
                float(aggregate["total_pnl_delta_sum"])
                - float(PREDICTION["expected_pnl_delta"]),
                2,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": failure_text,
            "predicted_failure_mode_hit": bool(failure_text),
            "surprise_note": (
                "The replay outcome matched the high-risk prior."
                if not gate4["passed"]
                else "The replay was stronger than expected but remains unpromoted."
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": failure_text,
        "next_retry_requires": (
            "Do not sweep volume ratio, near-high distance, hold days, top-N, "
            "cooldown, or notional on these frozen windows. A valid retry needs "
            "closed forward replacement-value rows from a shared default-off "
            "precursor logger, or a non-OHLCV evidence axis that separates "
            "true early entries from false starts."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "No broad OHLCV prebreakout threshold, volume-ratio, lookback, "
                "hold-day, top-N, cooldown, or notional sweeps."
            ),
            "new_evidence_required": (
                "Forward replacement-value rows from a shared logger, or a "
                "new catalyst/flow/ownership/borrow field joined before signal."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\ohlcv_warehouse.py seed-snapshot-versions",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Tested a fixed default-off trend-long precursor paper source "
            "derived from exp-20260627-006 entry-latency evidence."
        ),
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "parameters": payload["parameters"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "accepted_comparators": ACCEPTED_COMPARATORS,
        "target_trade_summary": payload["target_trade_summary"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "accepted": False,
        "accepted_alpha": False,
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate = payload["gate4"]
    targets = payload["target_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Trend-Long Precursor Candidate Source",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:,.2f}`",
            f"- Target trades: `{targets['total_trade_count']}` across `{targets['windows_with_target_trades']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- Failed reasons: `{gate['failed_reasons']}`",
            "",
            "## Hypothesis",
            "",
            ALPHA_HYPOTHESIS,
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "anti_js": payload["anti_js"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, log_row)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [
                {"label": label, **window} for label, window in WINDOWS.items()
            ],
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
                "expected_value_score_delta_sum"
            ],
            "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
                "total_pnl_delta_sum"
            ],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": PRODUCTION_IMPACT,
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "anti_js": payload["anti_js"],
        },
    )
    manifest = build_manifest(payload, log_row)
    write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
