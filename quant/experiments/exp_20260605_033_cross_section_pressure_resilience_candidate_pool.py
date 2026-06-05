"""exp-20260605-033: cross-section pressure resilience candidate pool.

Replay-only alpha search.  It tests one broad, free-OHLCV candidate source:
after a broad cross-sectional pressure day, admit the one liquid sector-known
stock that stayed resilient versus SPY/QQQ and closed strong, then replay a
default-off next-open paper entry with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
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
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260605-033"
STEM = "cross_section_pressure_resilience_candidate_pool"
TRIAL_FAMILY = "cross_section_pressure_resilience_candidate_pool"
TRIAL_VARIANT_ID = "cross_section_pressure_resilience_candidate_source_v1"
CHANGED_VARIABLE = "cross_section_pressure_resilience_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

WAREHOUSE = REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
SECTOR_MAP = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_033_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_CONTEXT_LIQUID_COUNT = 250
MIN_PRESSURE_DOWN_FRACTION = 0.58
MIN_PRESSURE_TAIL_DOWN_FRACTION = 0.18
MAX_PRESSURE_MEDIAN_RETURN = -0.004
MIN_PRESSURE_DISPERSION = 0.018
MAX_SPY_PRESSURE_RETURN = -0.0075
MAX_QQQ_PRESSURE_RETURN = -0.010

MIN_CANDIDATE_SIGNAL_RETURN = 0.0
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.018
MIN_CANDIDATE_RELATIVE_VS_QQQ = 0.022
MIN_CANDIDATE_CLOSE_LOCATION = 0.65
MIN_CANDIDATE_RET20_EXCESS_SPY = 0.0
MAX_CANDIDATE_RET5 = 0.10
MAX_CANDIDATE_REALIZED_VOL_20 = 0.075

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

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

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "ohlcv_momentum_relabeling",
        "drawdown_drift",
        "concentration_failed",
        "thin_pressure_sample",
    ],
    "confidence_reason": (
        "Recent broad OHLCV candidate pools mostly failed, but cross-sectional "
        "pressure plus resilience is a materially different production-visible "
        "state variable and can be tested replay-only with strict gates."
    ),
    "recorded_at": "2026-06-05T21:05:44Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same broad "
        "warehouse cross-sectional pressure fields, sector-known liquidity "
        "universe, same-day core overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, and concentration controls in "
        "both replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "DIA",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UUP",
    "USO",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_sleeve_globals() -> None:
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
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _date_str(value: date) -> str:
    return value.isoformat()


def _load_sector_entries() -> dict[str, dict[str, Any]]:
    payload = json.loads(SECTOR_MAP.read_text(encoding="utf-8"))
    entries = payload.get("entries", payload)
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in entries.items():
        if not isinstance(meta, dict):
            continue
        ticker_u = str(ticker).upper()
        sector = meta.get("sector")
        if meta.get("status") != "ok" or not sector:
            continue
        if ticker_u in EXCLUDED_TICKERS or "." in ticker_u or "-" in ticker_u:
            continue
        out[ticker_u] = {
            "sector": sector,
            "industry": meta.get("industry"),
            "sector_coverage_status": meta.get("status"),
        }
    return out


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = _parse_date(cfg["start"]) - timedelta(days=100)
    end = _parse_date(cfg["end"]) + timedelta(days=40)
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
            params = [*chunk, _date_str(start), _date_str(end)]
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


def _value(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _value(rows[idx - 1], "Close")
    close = _value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = _value(rows[idx - lookback], "Close")
    close = _value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _value(row, "Close")
        volume = _value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = _value(rows[idx], "Volume")
    if current is None:
        return None
    prior = [_value(row, "Volume") for row in rows[idx - lookback : idx]]
    if any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    if avg <= 0:
        return None
    return current / avg


def _close_location(row: dict[str, Any]) -> float | None:
    high = _value(row, "High")
    low = _value(row, "Low")
    close = _value(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    values = [_daily_return(rows, day_idx) for day_idx in range(idx - lookback + 1, idx + 1)]
    if any(value is None for value in values):
        return None
    valid = [float(value) for value in values if value is not None]
    mean_value = sum(valid) / len(valid)
    variance = sum((value - mean_value) ** 2 for value in valid) / len(valid)
    return math.sqrt(variance)


def _context_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None:
        return None
    spy_ret = _daily_return(spy_rows, spy_idx)
    qqq_ret = _daily_return(qqq_rows, qqq_idx)
    if spy_ret is None or qqq_ret is None:
        return None

    returns: list[float] = []
    for ticker in sector_entries:
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        close = _value(rows[idx], "Close")
        if close is None or close < MIN_PRICE:
            continue
        adv20 = _avg_dollar_volume(rows, idx)
        if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        daily = _daily_return(rows, idx)
        if daily is not None:
            returns.append(daily)

    if len(returns) < MIN_CONTEXT_LIQUID_COUNT:
        return None
    mean_value = sum(returns) / len(returns)
    variance = sum((value - mean_value) ** 2 for value in returns) / len(returns)
    dispersion = math.sqrt(variance)
    down_fraction = sum(1 for value in returns if value < 0.0) / len(returns)
    tail_down_fraction = sum(1 for value in returns if value <= -0.03) / len(returns)
    median_return = median(returns)
    passed = (
        spy_ret <= MAX_SPY_PRESSURE_RETURN
        and qqq_ret <= MAX_QQQ_PRESSURE_RETURN
        and down_fraction >= MIN_PRESSURE_DOWN_FRACTION
        and tail_down_fraction >= MIN_PRESSURE_TAIL_DOWN_FRACTION
        and median_return <= MAX_PRESSURE_MEDIAN_RETURN
        and dispersion >= MIN_PRESSURE_DISPERSION
    )
    return {
        "date": signal_date,
        "passed": passed,
        "liquid_universe_count": len(returns),
        "spy_signal_day_return": round(spy_ret, 6),
        "qqq_signal_day_return": round(qqq_ret, 6),
        "cross_section_down_fraction": round(down_fraction, 6),
        "cross_section_tail_down_fraction": round(tail_down_fraction, 6),
        "cross_section_median_return": round(median_return, 6),
        "cross_section_dispersion": round(dispersion, 6),
        "rule_version": RULE_VERSION,
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 20 or spy_idx < 20 or qqq_idx < 20:
        return None
    row = rows[idx]
    close = _value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = _daily_return(rows, idx)
    spy_return = _daily_return(spy_rows, spy_idx)
    qqq_return = _daily_return(qqq_rows, qqq_idx)
    if signal_return is None or spy_return is None or qqq_return is None:
        return None
    relative_vs_spy = signal_return - spy_return
    relative_vs_qqq = signal_return - qqq_return
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if relative_vs_qqq < MIN_CANDIDATE_RELATIVE_VS_QQQ:
        return None
    close_location = _close_location(row)
    if close_location is None or close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    ret5 = _ret(rows, idx, 5)
    ret20 = _ret(rows, idx, 20)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    if ret5 is None or ret20 is None or spy_ret20 is None:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    realized_vol = _realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None
    volume_ratio = _volume_ratio(rows, idx) or 0.0
    sector_meta = sector_entries[ticker]
    score = (
        2.5 * relative_vs_spy
        + 2.0 * relative_vs_qqq
        + 0.35 * close_location
        + 0.75 * ret20_excess_spy
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.60 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "CROSS_SECTION_PRESSURE_RESILIENCE_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "pressure_context": context,
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    pressure_contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "pressure_days": 0,
        "non_pressure_days": 0,
        "missing_context_days": 0,
    }
    for signal_date in dates:
        context = _context_for_day(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=signal_date,
        )
        if context is None:
            context_scan["missing_context_days"] += 1
            continue
        if not context["passed"]:
            context_scan["non_pressure_days"] += 1
            continue
        context_scan["pressure_days"] += 1
        pressure_contexts.append(context)
        for ticker in sector_entries:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    return candidates, pressure_contexts, context_scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _aggregate_window_rows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return sleeve._aggregate(rows)


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_cross_section_pressure_resilience"
            if passed
            else "rejected_cross_section_pressure_resilience_candidate_pool"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    _configure_sleeve_globals()
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = _load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    pressure_contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and cross-section pressure replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = _load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(
                set(snapshot).intersection(sector_entries)
            ),
            "source": _repo_rel(WAREHOUSE),
        }
        candidates, pressure_contexts, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries={
                ticker: meta
                for ticker, meta in sector_entries.items()
                if ticker in snapshot
            },
        )
        selected_trades, filtered_candidates = _select_paper_trades(
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
        pressure_contexts_by_window[label] = pressure_contexts
        context_scan_by_window[label] = context_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "pressure_day_count": len(pressure_contexts),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = _aggregate_window_rows(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "accepted" if gate4["passed"] else "rejected"
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
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Cross-sectional pressure days may reveal higher-quality broad "
            "candidates: stocks that stay liquid, close strong, and outperform "
            "SPY/QQQ during broad synchronous stress can produce default-off "
            "next-open paper alpha without adding noisy tickers."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260605-013",
            "exp-20260528-035",
            "exp-20260528-036",
            "exp-20260605-023",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_cross_section_pressure_resilience",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": WINDOWS,
            "candidate_ohlcv_source": _repo_rel(WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on signal date. "
                "Paper entry is next available open with existing entry "
                "slippage; exit is the close 10 trading days after the signal "
                "with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_context_liquid_count": MIN_CONTEXT_LIQUID_COUNT,
            "min_pressure_down_fraction": MIN_PRESSURE_DOWN_FRACTION,
            "min_pressure_tail_down_fraction": MIN_PRESSURE_TAIL_DOWN_FRACTION,
            "max_pressure_median_return": MAX_PRESSURE_MEDIAN_RETURN,
            "min_pressure_dispersion": MIN_PRESSURE_DISPERSION,
            "max_spy_pressure_return": MAX_SPY_PRESSURE_RETURN,
            "max_qqq_pressure_return": MAX_QQQ_PRESSURE_RETURN,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
            "min_candidate_relative_vs_qqq": MIN_CANDIDATE_RELATIVE_VS_QQQ,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool alpha: after broad cross-sectional pressure, "
                "liquid sector-known stocks that stay resilient versus SPY/QQQ "
                "may be cleaner next-open paper candidates than raw momentum."
            ),
            "2_history_check": {
                "exp-20260605-013": (
                    "Broad low-beta residual momentum candidate pool was "
                    "rejected due PnL loss, two window regressions, and "
                    "drawdown deterioration."
                ),
                "exp-20260528-035/036": (
                    "Sector/industry breadth breakout variants were rejected; "
                    "this test uses market-wide pressure plus single-day "
                    "resilience instead of broad sector breadth agreement."
                ),
                "exp-20260605-023": (
                    "Observed-only breadth alignment did not show a stable "
                    "monotonic ladder."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three canonical windows. Aggregate EV/PnL must be "
                "positive; no EV/PnL regression window; at least 20 paper "
                "trades across all 3 windows; survival >=5%; drawdown drift "
                "<=0.5pp; concentration pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260605_033_cross_section_pressure_resilience_candidate_pool.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "QQQ daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The pressure "
                "resilience candidate source is additive default-off paper, so "
                "core signals generated/survived are unchanged from baseline."
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
        "context_scan_by_window": context_scan_by_window,
        "pressure_contexts_by_window": pressure_contexts_by_window,
        "pressure_context_samples_by_window": OrderedDict(
            (label, rows[:20]) for label, rows in pressure_contexts_by_window.items()
        ),
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The pressure-resilience candidate source cleared Gate 4 as a "
            "replay-only/default-off lead, but no production surface was "
            "promoted."
            if gate4["passed"]
            else (
                "The pressure-resilience candidate source did not clear Gate 4. "
                "Do not promote or retry this fixed OHLCV pressure/resilience "
                "definition on the same frozen windows without a materially new "
                "PIT state field or forward replacement-value data."
            )
        ),
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "A retry needs a materially new PIT state field, such as real-time "
            "breadth/changepoint persistence or cost-adjusted replacement rows; "
            "do not simply retune pressure thresholds, hold days, cooldown, "
            "or paper notional on this frozen sample."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Pressure days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {pressure} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                pressure=len(payload["pressure_contexts_by_window"][label]),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Cross-Section Pressure Resilience Candidate Pool",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "pressure_day_count": len(payload["pressure_contexts_by_window"][label]),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {
            **payload["calibration"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(_safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
