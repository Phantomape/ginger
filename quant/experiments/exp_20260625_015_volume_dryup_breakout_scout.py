"""exp-20260625-015: volume dry-up breakout candidate-pool scout.

Private replay scout for a fixed OHLCV candidate-pool hypothesis. It tests
whether liquid stocks that show point-in-time 20-vs-60 day volume dry-up before
a close above the prior 20-day high add next-open, 10-trading-day paper alpha.

No production code, shared policy, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive replay would only
be a lead requiring a shared default-off helper and daily snapshot.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


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
from data_layer import get_universe  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402


EXPERIMENT_ID = "exp-20260625-015"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "volume_dryup_breakout_scout"
RUNNER = f"quant/experiments/exp_20260625_015_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STEM = "volume_dryup_breakout_scout"
TRIAL_FAMILY = "volume_dryup_breakout_candidate_pool"
TRIAL_VARIANT_ID = "volume_dryup_20v60_breakout_top1_10d_v1"
CHANGED_VARIABLE = "volume_dryup_breakout_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
MECHANISM_FAMILY = "production_visible_free_ohlcv_candidate_pool"

WAREHOUSE = DEFAULT_WAREHOUSE_PATH
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_015_{SLUG}.json"
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

MIN_HISTORY_SESSIONS = 80
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MAX_VOLUME_DRYUP_20V60 = 0.72
MIN_SIGNAL_VOLUME_RATIO_TO_PRIOR20 = 0.80
MIN_BREAKOUT_MARGIN = 0.0
MIN_CLOSE_LOCATION = 0.70
MIN_SIGNAL_RETURN = -0.005
MAX_SIGNAL_RETURN = 0.10
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.03
MAX_REALIZED_VOL_20D = 0.08

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
COMPARATOR_PNL_FLOOR = max(row["total_pnl_delta_sum"] for row in ACCEPTED_COMPARATORS.values())

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
    "Liquid stocks with a point-in-time 20-vs-60 day volume dry-up before a "
    "close above the prior 20-day high may identify supply-exhaustion "
    "breakouts distinct from prior narrow-range compression families."
)
ALPHA_HYPOTHESIS = (
    "candidate-pool alpha: pre-signal average volume contraction "
    "(avg_volume_20d_prior / avg_volume_60d_prior <= 0.72), followed by a "
    "high-location close above the prior 20-day high and SPY-relative trend, "
    "may add next-open 10-day paper alpha on liquid common stocks."
)
NEW_EVIDENCE_AXIS = (
    "Machine-checkable new gate shape: pre-breakout volume_dryup_ratio_20v60 "
    "computed from point-in-time OHLCV before signal; no prior accepted or "
    "rejected family used this field as the independent evidence axis, and "
    "this does not retune narrow-range compression thresholds."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260608-013",
    "exp-20260610-017",
    "exp-20260613-018",
    "exp-20260615-005",
    "exp-20260623-008",
]

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "ohlcv_relation_source_saturation",
        "near_neighbor_compression_family",
        "window_regression",
        "accepted_comparator_not_beaten",
        "thin_trade_count_after_breakout_gate",
    ],
    "confidence_reason": (
        "OHLCV candidate-pool families are near source saturation and prior "
        "breakout/compression tests are hard comparators. The only reason to "
        "run this scout is that pre-breakout 20-vs-60 volume dry-up is a "
        "machine-checkable field not previously used as the independent axis."
    ),
    "recorded_at": "2026-06-25T13:20:00+00:00",
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
    "adapter_status": "private_replay_only_no_live_adapter",
    "parity_note": (
        "This is an experiment-owned private replay scout. A positive result "
        "would require a shared default-off helper that computes the same "
        "pre-breakout volume dry-up, breakout, liquidity, relative-strength, "
        "next-open paper entry, 10-trading-day exit, cost model, cooldown, and "
        "concentration checks before any daily report, candidate priority, "
        "sizing, watchlist, paper ledger, or order surface could change."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe(payload: Any) -> Any:
    if isinstance(payload, OrderedDict):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, Counter):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, dict):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(safe(value) for value in payload)
    if isinstance(payload, Path):
        return repo_rel(payload)
    if isinstance(payload, date):
        return payload.isoformat()
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
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


def load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = date.fromisoformat(cfg["start"]) - timedelta(days=130)
    end = date.fromisoformat(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(WAREHOUSE) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, start.isoformat(), end.isoformat()]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def value(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def average(values: list[float | None]) -> float | None:
    if not values or any(item is None for item in values):
        return None
    valid = [float(item) for item in values if item is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = value(rows[idx - 1], "Close")
    close = value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = value(rows[idx - lookback], "Close")
    close = value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def prior_avg_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    return average([value(row, "Volume") for row in rows[idx - lookback : idx]])


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


def close_location(row: dict[str, Any]) -> float | None:
    high = value(row, "High")
    low = value(row, "Low")
    close = value(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def realized_vol_prior(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int = 20,
) -> float | None:
    if idx < lookback + 1:
        return None
    values = [daily_return(rows, pos) for pos in range(idx - lookback, idx)]
    if any(item is None for item in values):
        return None
    valid = [float(item) for item in values if item is not None]
    mean_value = sum(valid) / len(valid)
    variance = sum((item - mean_value) ** 2 for item in valid) / len(valid)
    return math.sqrt(variance)


def prior_high(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    highs = [value(row, "High") for row in rows[idx - lookback : idx]]
    if any(item is None for item in highs):
        return None
    return max(float(item) for item in highs if item is not None)


def candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    entries_by_date = shadow._baseline_entries(before_result)
    dates = [
        day
        for day in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= day <= str(cfg["end"])
    ]
    spy_rows = shadow._series(snapshot, "SPY")
    spy_idx_by_date = shadow._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    reject_reasons: Counter[str] = Counter()

    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in shadow.EXCLUDED_TICKERS:
            continue
        rows = shadow._series(snapshot, ticker)
        idx_by_date = shadow._row_index(rows)
        for signal_date in dates:
            idx = idx_by_date.get(signal_date)
            spy_idx = spy_idx_by_date.get(signal_date)
            if idx is None or spy_idx is None:
                continue
            if idx < MIN_HISTORY_SESSIONS or spy_idx < 60:
                continue

            cur = rows[idx]
            close = value(cur, "Close")
            open_ = value(cur, "Open")
            cur_volume = value(cur, "Volume")
            high20 = prior_high(rows, idx, 20)
            avg_vol20 = prior_avg_volume(rows, idx, 20)
            avg_vol60 = prior_avg_volume(rows, idx, 60)
            adv20 = prior_avg_dollar_volume(rows, idx, 20)
            signal_ret = daily_return(rows, idx)
            ticker_ret20 = ret(rows, idx, 20)
            ticker_ret60 = ret(rows, idx, 60)
            spy_ret20 = ret(spy_rows, spy_idx, 20)
            spy_ret60 = ret(spy_rows, spy_idx, 60)
            loc = close_location(cur)
            vol20 = realized_vol_prior(rows, idx, 20)
            if None in (
                close,
                open_,
                cur_volume,
                high20,
                avg_vol20,
                avg_vol60,
                adv20,
                signal_ret,
                ticker_ret20,
                ticker_ret60,
                spy_ret20,
                spy_ret60,
                loc,
                vol20,
            ):
                reject_reasons["missing_required_ohlcv_or_benchmark_field"] += 1
                continue

            assert close is not None
            assert high20 is not None
            assert avg_vol20 is not None
            assert avg_vol60 is not None
            assert adv20 is not None
            assert cur_volume is not None
            assert signal_ret is not None
            assert ticker_ret20 is not None
            assert ticker_ret60 is not None
            assert spy_ret20 is not None
            assert spy_ret60 is not None
            assert loc is not None
            assert vol20 is not None

            if close < MIN_PRICE:
                reject_reasons["below_min_price"] += 1
                continue
            if adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
                reject_reasons["below_min_avg_dollar_volume_20d"] += 1
                continue
            if avg_vol60 <= 0 or avg_vol20 <= 0:
                reject_reasons["invalid_prior_volume_average"] += 1
                continue

            volume_dryup_ratio = avg_vol20 / avg_vol60
            if volume_dryup_ratio > MAX_VOLUME_DRYUP_20V60:
                reject_reasons["not_volume_dryup_20v60"] += 1
                continue

            breakout_margin = (close / high20) - 1.0 if high20 > 0 else None
            if breakout_margin is None or breakout_margin <= MIN_BREAKOUT_MARGIN:
                reject_reasons["not_close_above_prior_20d_high"] += 1
                continue

            signal_volume_ratio = cur_volume / avg_vol20
            if signal_volume_ratio < MIN_SIGNAL_VOLUME_RATIO_TO_PRIOR20:
                reject_reasons["signal_volume_not_confirming"] += 1
                continue
            if signal_ret < MIN_SIGNAL_RETURN:
                reject_reasons["signal_return_too_weak"] += 1
                continue
            if signal_ret > MAX_SIGNAL_RETURN:
                reject_reasons["signal_return_too_extended"] += 1
                continue
            if loc < MIN_CLOSE_LOCATION:
                reject_reasons["close_location_too_low"] += 1
                continue

            ret20_excess_spy = ticker_ret20 - spy_ret20
            ret60_excess_spy = ticker_ret60 - spy_ret60
            if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
                reject_reasons["ret20_not_spy_leading"] += 1
                continue
            if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
                reject_reasons["ret60_spy_lag_too_large"] += 1
                continue
            if vol20 > MAX_REALIZED_VOL_20D:
                reject_reasons["realized_vol_20d_too_high"] += 1
                continue

            ab_entries = entries_by_date.get(signal_date, [])
            score = (
                (MAX_VOLUME_DRYUP_20V60 - volume_dryup_ratio) * 2.0
                + breakout_margin * 10.0
                + ret20_excess_spy * 2.0
                + loc * 0.25
                + min(math.log10(max(adv20, 1.0) / MIN_AVG_DOLLAR_VOLUME_20D), 1.0)
                * 0.05
                + min(signal_volume_ratio, 3.0) * 0.10
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "candidate_source": STEM,
                    "rule_version": RULE_VERSION,
                    "candidate_score": round_float(score, 6),
                    "volume_dryup_ratio_20v60": round_float(volume_dryup_ratio, 6),
                    "avg_volume_prior20": round_float(avg_vol20, 2),
                    "avg_volume_prior60": round_float(avg_vol60, 2),
                    "avg_dollar_volume_prior20": round_float(adv20, 2),
                    "prior_20d_high": round_float(high20, 4),
                    "signal_close": round_float(close, 4),
                    "breakout_margin": round_float(breakout_margin, 6),
                    "signal_return": round_float(signal_ret, 6),
                    "signal_volume_ratio_to_prior20": round_float(signal_volume_ratio, 6),
                    "ret20": round_float(ticker_ret20, 6),
                    "ret60": round_float(ticker_ret60, 6),
                    "spy_ret20": round_float(spy_ret20, 6),
                    "spy_ret60": round_float(spy_ret60, 6),
                    "ret20_excess_spy": round_float(ret20_excess_spy, 6),
                    "ret60_excess_spy": round_float(ret60_excess_spy, 6),
                    "close_location": round_float(loc, 6),
                    "realized_vol_prior20": round_float(vol20, 6),
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
            float(row["volume_dryup_ratio_20v60"] or 999.0),
            -float(row["breakout_margin"] or 0.0),
            -float(row["ret20_excess_spy"] or 0.0),
            -float(row["avg_dollar_volume_prior20"] or 0.0),
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
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
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


def gate4_result(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    window_rows: "OrderedDict[str, dict[str, Any]]",
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

    ev_improved_windows = 0
    pnl_improved_windows = 0
    max_drawdown_drift_by_window: dict[str, float] = {}
    for label, row in window_rows.items():
        delta = row["delta"]
        before = row["before"]
        after = row["after"]
        window_ev_delta = float(delta.get("expected_value_score") or 0.0)
        window_pnl_delta = float(delta.get("total_pnl") or 0.0)
        if window_ev_delta > 0:
            ev_improved_windows += 1
        if window_pnl_delta > 0:
            pnl_improved_windows += 1
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

    if ev_improved_windows < MIN_EV_IMPROVED_WINDOWS:
        failed.append("too_few_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
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
        warnings.append("private_replay_positive_only_requires_shared_default_off_helper")
    return {
        "passed": passed,
        "decision": (
            "positive_private_replay_lead_not_promoted_volume_dryup_breakout"
            if passed
            else "rejected_volume_dryup_breakout_candidate_pool"
        ),
        "failed_reasons": sorted(set(failed)),
        "warnings": warnings,
        "target_trade_count": target_summary["total_trade_count"],
        "windows_with_target_trades": target_summary["windows_with_target_trades"],
        "ev_improved_windows": ev_improved_windows,
        "pnl_improved_windows": pnl_improved_windows,
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
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    eligible_tickers = {ticker for ticker in universe if ticker not in shadow.EXCLUDED_TICKERS}

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    candidate_reject_reasons_by_window: "OrderedDict[str, dict[str, int]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and volume dry-up breakout replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = load_window_snapshot(cfg=cfg, eligible_tickers=eligible_tickers)
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "eligible_universe_ticker_count": len(eligible_tickers),
            "eligible_ticker_coverage_count": len(set(snapshot).intersection(eligible_tickers)),
            "source": repo_rel(WAREHOUSE),
        }
        candidates, reject_reasons = candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            universe=universe,
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
        candidate_reject_reasons_by_window[label] = dict(reject_reasons)
        raw_candidate_counts[label] = len(candidates)
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = gate4_result(
        aggregate=aggregate,
        target_summary=target_summary,
        window_rows=window_rows,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "observed_only" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    rejection_reason = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    post_run_reflection = {
        "why_result_happened": (
            "The volume dry-up breakout surface produced a replayable candidate "
            "pool, but the fixed rule must beat both the canonical core baseline "
            "and accepted OHLCV candidate-pool comparators. Any failure on "
            "aggregate EV/PnL, window regression, sample size, or comparator "
            "floor rejects this near-saturation OHLCV family."
        ),
        "realized_failure_mode": (
            "private_replay_positive_only"
            if gate4["passed"]
            else "ohlcv_relation_saturation_or_accepted_comparator_not_beaten"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry adjacent 20/60 volume dry-up thresholds, prior-high "
            "lookbacks, close-location cutoffs, signal-volume guards, relative "
            "strength cutoffs, top-N, hold days, cooldown, or notional on these "
            "frozen windows unless there is a new machine-checkable evidence "
            "axis outside this OHLCV relation surface."
        ),
        "new_evidence_required": (
            "A valid reopen needs a new non-OHLCV confirmation field, a true "
            "forward replacement row showing allocation value, or a distinct "
            "data source. Another adjacent volume-dry-up breakout retune is not "
            "new evidence."
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout_no_shared_helper",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "causal_components": [
            "pre-signal avg_volume_20d_prior / avg_volume_60d_prior dry-up gate",
            "close above prior 20-day high breakout gate",
            "liquidity and high-close-location confirmation",
            "SPY-relative 20/60-day trend guard",
            "daily top-1 next-open 10-day paper replay",
            "accepted core baseline overlay comparison",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high_ohlcv_relation_near_saturation_but_new_gate_shape_declared",
        "new_evidence_type": "point_in_time_pre_breakout_volume_dryup_20v60_ohlcv_field",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "experiment-owned private replay overlay"
            ),
            "windows": WINDOWS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "candidate_ohlcv_source": repo_rel(WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "The candidate is known after signal-day close. Paper entry is "
                "the next open; exit is close 10 trading days after the signal "
                "with the existing sleeve cost/slippage model."
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
            "max_volume_dryup_20v60": MAX_VOLUME_DRYUP_20V60,
            "min_signal_volume_ratio_to_prior20": MIN_SIGNAL_VOLUME_RATIO_TO_PRIOR20,
            "min_breakout_margin": MIN_BREAKOUT_MARGIN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate_result": (
                    "Allowed only with novelty override. The near-neighbor "
                    "check surfaced accepted compression/breakout OHLCV "
                    "families, but this run declares a machine-checkable new "
                    "pre-breakout volume_dryup_ratio_20v60 field as the "
                    "independent evidence axis."
                ),
                "exp-20260608-013": (
                    "Accepted narrow-range compression breakout comparator; "
                    "current run must beat it and does not retune compression."
                ),
                "exp-20260610-017": (
                    "Compression tail-state breakout near neighbor; current "
                    "run uses volume dry-up, not range compression."
                ),
                "exp-20260623-008": (
                    "Daily short-volume broad-universe OHLCV-adjacent candidate "
                    "pool did not justify adjacent retunes without new evidence."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Gate 4 on canonical windows: aggregate EV and PnL positive, no "
                "window EV/PnL regression, at least two EV-improved windows, at "
                "least 20 trades across all 3 windows, survival >=5%, drawdown "
                "drift <=0.5pp, concentration pass, and accepted compression/"
                "distribution comparator EV/PnL floors beaten. Positive private "
                "replay is only a lead, not accepted alpha."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{repo_rel(OUT_JSON)}#before_metrics",
            "canonical_baseline_result_file": repo_rel(BASELINE_RESULT),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "QQQ daily OHLCV",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "candidate_surface": {
                "eligible_universe_ticker_count": len(eligible_tickers),
                "raw_candidate_counts": raw_candidate_counts,
                "warehouse_coverage_by_window": warehouse_coverage_by_window,
            },
            "pit_notes": (
                "Volume dry-up uses rows before the signal day. Breakout, close "
                "location, relative trend, and signal-volume confirmation use "
                "signal-day close/volume; entry is next open."
            ),
            "passed": bool(sum(raw_candidate_counts.values())) and gate2_open_positions["passed"],
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round_float(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The volume dry-up "
                "breakout source is an additive private replay paper overlay."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_reject_reasons_by_window": candidate_reject_reasons_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The private volume dry-up breakout replay cleared Gate 4 as an "
            "observed-only lead. It is not accepted alpha because no shared "
            "helper or daily default-off parity surface was promoted."
            if gate4["passed"]
            else (
                "The private volume dry-up breakout candidate pool did not "
                "clear Gate 4. Do not promote it or retry adjacent OHLCV "
                "dry-up/breakout thresholds on the same frozen windows without "
                "a materially new evidence axis."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, avoid adjacent volume-dry-up breakout retunes. A "
            "valid retry needs a new non-OHLCV confirmation field, a new data "
            "source, or mature forward replacement-value rows. If positive, "
            "next step is a shared default-off helper plus daily snapshot "
            "before acceptance."
        ),
        "post_run_reflection": post_run_reflection,
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Volume Dry-Up Breakout Scout",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "- Lane: `alpha_search`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            "Private replay only. No shared helper, run adapter, backtester adapter, daily snapshot, production watchlist, ranking, sizing, exit, paper order, or live order behavior changed.",
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "raw_candidate_counts": payload["raw_candidate_counts"],
            "open_positions": payload["gate2"]["open_positions"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "anti_js": "No JavaScript was used.",
    }


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
        "gate2": log_row["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["interpretation"],
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
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [
                {"label": label, **window} for label, window in WINDOWS.items()
            ],
            "acceptance_rule": payload["pre_run_questions"]["4_success_failure_standard"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": log_row["aggregate_expected_value_delta"],
            "aggregate_strategy_total_pnl_delta": log_row[
                "aggregate_strategy_total_pnl_delta"
            ],
            "gate1": payload["gate1"],
            "gate2": log_row["gate2"],
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
