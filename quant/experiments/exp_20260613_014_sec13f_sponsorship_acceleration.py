"""exp-20260613-014: PIT SEC 13F sponsorship acceleration candidate pool.

Replay-only alpha search. This tests one candidate-source policy: when the
latest fully-ended SEC 13F filing window shows rising institutional holder and
value sponsorship versus the prior fully-ended filing window, admit the most
liquid leadership-confirmed stock as a default-off next-open paper candidate.

implementation_mode: private_replay_scout. Escape reason: historical 13F
window parsing and PIT window joins are unproven for this alpha surface. A
positive result is only a lead until the same window availability, sponsorship
feature builder, same-day OHLCV gates, core-overlap exclusion, next-open entry,
10-day exit, cooldown, and ledger fields are implemented in shared historical
replay and daily default-off snapshot code.

This is not promoted to production. No shared policy, live order path, live
ranking, sizing, exits, LLM/news behavior, or watchlist behavior changes. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
import urllib.request
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from kova_data_sidecar import DEFAULT_USER_AGENT, parse_sec13f_zip  # noqa: E402
from sec13f_ingest import (  # noqa: E402
    RULE_VERSION as SEC13F_RULE_VERSION,
    _window_bounds,
    aggregate_universe_holdings,
    load_company_name_index,
    window_label,
    window_url,
)


EXPERIMENT_ID = "exp-20260613-014"
STEM = "sec13f_sponsorship_acceleration"
TRIAL_FAMILY = "sec13f_sponsorship_acceleration_candidate_pool"
TRIAL_VARIANT_ID = "sec13f_sponsorship_acceleration_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_sponsorship_acceleration_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_014_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 20

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_HISTORY_SESSIONS = 60
MIN_HOLDER_COUNT = 50
MIN_HOLDER_DELTA = 3
MIN_HOLDER_GROWTH_PCT = 0.03
MIN_VALUE_GROWTH_PCT = 0.02
MIN_SIGNAL_RETURN = -0.002
MIN_RET20_EXCESS_SPY = 0.02
MIN_RET60_EXCESS_SPY = -0.02
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.60
MAX_VOLUME_RATIO_20D = 2.40
MAX_RET5 = 0.12
MAX_REALIZED_VOL_20D = 0.08

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

# Fully ended filing windows needed for the canonical three backtest windows.
# Signals only see a filing-window aggregate after that window has ended.
SEC13F_WINDOW_STARTS = (
    (2024, 6),
    (2024, 9),
    (2024, 12),
    (2025, 3),
    (2025, 6),
    (2025, 9),
    (2025, 12),
)

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "decision": "accepted_source_consensus_allocator_extension",
    "expected_value_score_delta_sum": 2.1849,
    "total_pnl_delta_sum": 40397.21,
    "note": (
        "Promotion comparator only. This private 13F scout is still lead-only "
        "without a shared daily helper even if numeric Gate 4 passes."
    ),
}

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "historical_13f_download_blocked",
        "stale_quarterly_data",
        "no_incremental_edge",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "13F was previously blocked by missing PIT ticker-mapped holdings and "
        "exp-20260613-007 repaired current ingestion, but older filing-window "
        "downloads and PIT joins are unproven. The mechanism is quarterly "
        "institutional sponsorship acceleration confirmed by liquid price "
        "leadership, while 13D/13G event scouts failed on staleness/sparsity."
    ),
    "recorded_at": "2026-06-13T10:07:22+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_live_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "Historical 13F filing-window downloads and PIT window joins are "
        "unproven for this surface. A positive result is lead-only until the "
        "same 13F window availability, ticker mapping, sponsorship feature "
        "builder, same-day OHLCV gates, core-overlap exclusion, next-open "
        "entry, costs, hold, and cooldown run in shared historical replay and "
        "daily default-off snapshots."
    ),
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_13f": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": False,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes in this scout",
        "failure_handling": "missing 13F pair, OHLCV, next open, or exit bar rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result remains "
        "a replay lead until a shared default-off helper computes the exact "
        "PIT 13F sponsorship pair, leadership gates, overlap exclusion, entry, "
        "exit, costs, cooldown, and ledger fields identically in historical "
        "replay and daily production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: stocks with rising SEC 13F holder count and total "
        "reported value between fully ended filing windows, confirmed by "
        "same-day liquid leadership, may add durable next-open paper alpha."
    ),
    "2_history_check": {
        "exp-20260613-007": (
            "Measurement repair ingested the latest SEC 13F structured dataset "
            "and achieved ticker-mapped coverage, but did not test an alpha "
            "policy or historical PIT window join."
        ),
        "exp-20260527-906": (
            "Earlier 13F/watchlist work was blocked by stub data and forbidden "
            "from alpha claims until real filings were ingested."
        ),
        "exp-20260612-015": (
            "SEC 13D activist initiation was rejected: aggregate EV/PnL fell "
            "and all three windows regressed."
        ),
        "exp-20260612-016": (
            "SEC 13G passive-stake initiation was rejected, likely because "
            "annual/batch events were stale and lost holder-level information."
        ),
        "difference": (
            "This tests quarterly aggregate institutional sponsorship "
            "acceleration with conservative PIT availability, not a 13D/13G "
            "filing-date event trigger or an LLM/news ranking surface."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no window EV/PnL regression occurs, at "
        "least 20 paper trades span all 3 windows, survival >=5%, drawdown "
        "drift <=0.5pp, and concentration passes. A positive result is still "
        "lead-only until shared daily parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_014_sec13f_sponsorship_acceleration.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _safe_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def _download_to_temp(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(request, timeout=240) as response:
        dest.write_bytes(response.read())


def _load_13f_history(universe: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    name_index = load_company_name_index()
    by_label: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=f"{EXPERIMENT_ID}_13f_") as tmp_name:
        tmp_root = Path(tmp_name)
        for year, month in SEC13F_WINDOW_STARTS:
            label = window_label(year, month)
            start, end = _window_bounds(year, month)
            url = window_url(year, month)
            zip_path = tmp_root / f"{label}_form13f.zip"
            try:
                _download_to_temp(url, zip_path)
                rows = list(
                    parse_sec13f_zip(
                        zip_path,
                        asof_date=end.isoformat(),
                        cusip_ticker_map=None,
                    )
                )
                holdings, cusip_map = aggregate_universe_holdings(
                    rows,
                    name_index=name_index,
                    universe=universe,
                )
            except Exception as exc:  # pragma: no cover - network/data boundary
                errors.append(
                    {
                        "window_label": label,
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                        "url": url,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            payload = {
                "window_label": label,
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "known_after": end.isoformat(),
                "window_url": url,
                "raw_position_row_count": len(rows),
                "universe_covered_count": len(holdings),
                "universe_coverage_pct": round(100.0 * len(holdings) / max(len(universe), 1), 2),
                "cusip_map_size": len(cusip_map),
                "holdings_by_ticker": holdings,
            }
            by_label[label] = payload
            source_summaries.append(
                {
                    key: value
                    for key, value in payload.items()
                    if key != "holdings_by_ticker"
                }
            )
            print(
                f"[{EXPERIMENT_ID}] loaded 13F {label}: "
                f"{len(holdings)} tickers from {len(rows)} rows"
            )
    history_summary = {
        "rule_version": SEC13F_RULE_VERSION,
        "universe_size": len(universe),
        "window_count_requested": len(SEC13F_WINDOW_STARTS),
        "window_count_loaded": len(by_label),
        "windows_loaded": source_summaries,
        "download_errors": errors,
        "source_storage": "SEC zip files downloaded to a temp directory only; not committed",
    }
    return by_label, history_summary


def _ordered_13f_windows(holdings_by_label: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(holdings_by_label.values())
    rows.sort(key=lambda row: row["window_end"])
    return rows


def _latest_prior_13f_pair(
    signal_date: str,
    ordered_windows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    signal = _safe_date(signal_date)
    available = [
        row
        for row in ordered_windows
        if _safe_date(row["window_end"]) <= signal
    ]
    if len(available) < 2:
        return None
    return available[-1], available[-2]


def _configure_framework_globals() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    framework.sleeve.STEM = STEM
    framework.sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.sleeve.HOLD_DAYS = HOLD_DAYS
    framework.sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    latest_13f: dict[str, Any],
    prior_13f: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    latest_holdings = latest_13f["holdings_by_ticker"].get(ticker)
    prior_holdings = prior_13f["holdings_by_ticker"].get(ticker)
    if not latest_holdings or not prior_holdings:
        return None

    holder_count = int(latest_holdings.get("holder_count") or 0)
    prior_holder_count = int(prior_holdings.get("holder_count") or 0)
    holder_delta = holder_count - prior_holder_count
    holder_growth_pct = holder_delta / max(prior_holder_count, 1)
    value_usd = _float(latest_holdings.get("total_value_usd")) or 0.0
    prior_value_usd = _float(prior_holdings.get("total_value_usd")) or 0.0
    value_delta = value_usd - prior_value_usd
    value_growth_pct = value_delta / max(prior_value_usd, 1.0)
    if holder_count < MIN_HOLDER_COUNT:
        return None
    if holder_delta < MIN_HOLDER_DELTA:
        return None
    if holder_growth_pct < MIN_HOLDER_GROWTH_PCT:
        return None
    if value_growth_pct < MIN_VALUE_GROWTH_PCT:
        return None

    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < MIN_HISTORY_SESSIONS or spy_idx < MIN_HISTORY_SESSIONS:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx)
    required = [
        signal_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol,
    ]
    if any(value is None for value in required):
        return None
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if float(signal_return) < MIN_SIGNAL_RETURN:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if float(close_location) < MIN_CLOSE_LOCATION:
        return None
    if float(volume_ratio) < MIN_VOLUME_RATIO_20D:
        return None
    if float(volume_ratio) > MAX_VOLUME_RATIO_20D:
        return None
    if float(ret5) > MAX_RET5:
        return None
    if float(realized_vol) > MAX_REALIZED_VOL_20D:
        return None

    score = (
        1.55 * holder_growth_pct
        + 0.85 * min(value_growth_pct, 0.75)
        + 1.25 * ret20_excess_spy
        + 0.55 * ret60_excess_spy
        + 0.40 * float(close_location)
        + 0.12 * min(float(volume_ratio), 1.8)
        + 0.05 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        - 0.55 * max(float(ret5), 0.0)
        - 0.40 * float(realized_vol)
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SEC13F_SPONSORSHIP_ACCELERATION_LIQUID_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": _round(signal_return),
        "candidate_ret5": _round(ret5),
        "candidate_ret20": _round(ret20),
        "candidate_ret60": _round(ret60),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": _round(close_location),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_volume_ratio_20d": _round(volume_ratio),
        "candidate_realized_vol_20d": _round(realized_vol),
        "sec13f_latest_window": latest_13f["window_label"],
        "sec13f_latest_window_end": latest_13f["window_end"],
        "sec13f_prior_window": prior_13f["window_label"],
        "sec13f_prior_window_end": prior_13f["window_end"],
        "sec13f_holder_count": holder_count,
        "sec13f_prior_holder_count": prior_holder_count,
        "sec13f_holder_delta": holder_delta,
        "sec13f_holder_growth_pct": round(holder_growth_pct, 6),
        "sec13f_total_value_usd": round(value_usd, 2),
        "sec13f_prior_total_value_usd": round(prior_value_usd, 2),
        "sec13f_value_delta_usd": round(value_delta, 2),
        "sec13f_value_growth_pct": round(value_growth_pct, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("sec13f_holder_delta") or 0.0),
        -float(row.get("sec13f_holder_growth_pct") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
    ordered_13f_windows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        value
        for value in framework.shadow._trading_dates(snapshot)
        if cfg["start"] <= value <= cfg["end"]
    ]
    indices = {ticker: framework.shadow._row_index(rows) for ticker, rows in snapshot.items()}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "trading_day_count": len(dates),
        "days_with_13f_pair": 0,
        "days_with_raw_13f_candidates": 0,
        "raw_13f_candidates": 0,
        "days_without_13f_pair": 0,
        "rule_version": RULE_VERSION,
    }
    for signal_date in dates:
        pair = _latest_prior_13f_pair(signal_date, ordered_13f_windows)
        if pair is None:
            scan["days_without_13f_pair"] += 1
            continue
        latest_13f, prior_13f = pair
        scan["days_with_13f_pair"] += 1
        ab_entries = entries_by_date.get(signal_date, [])
        same_day_core = {
            str(entry.get("ticker") or "").upper()
            for entry in ab_entries
        }
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            if ticker not in snapshot:
                continue
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                latest_13f=latest_13f,
                prior_13f=prior_13f,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = ticker in same_day_core
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_13f_candidates"] += 1
        scan["raw_13f_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "latest_13f_window": latest_13f["window_label"],
                "prior_13f_window": prior_13f["window_label"],
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_holder_delta": top["sec13f_holder_delta"],
                "top_candidate_holder_growth_pct": top["sec13f_holder_growth_pct"],
                "top_candidate_value_growth_pct": top["sec13f_value_growth_pct"],
            }
        )
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    return candidates, contexts, scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = framework.shadow._trading_dates(snapshot)
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
        trade = framework.sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    passed = not failed
    gate.update(
        {
            "passed": passed,
            "decision": (
                "positive_replay_lead_not_promoted_sec13f_sponsorship_acceleration"
                if passed
                else "rejected_sec13f_sponsorship_acceleration_candidate_pool"
            ),
            "failed_reasons": failed,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "accepted_allocator_comparator_beaten": {
                "ev": float(aggregate["expected_value_score_delta_sum"] or 0.0)
                > ACCEPTED_ALLOCATOR_COMPARATOR["expected_value_score_delta_sum"],
                "pnl": float(aggregate["total_pnl_delta_sum"] or 0.0)
                > ACCEPTED_ALLOCATOR_COMPARATOR["total_pnl_delta_sum"],
            },
        }
    )
    return gate


def _blocked_payload(
    *,
    timestamp: str,
    gate2_open_positions: dict[str, Any],
    history_summary: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_sec13f_sponsorship_acceleration_historical_data_unavailable",
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "experiment_local_replay_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "production_visible_free_sec_13f_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260613-007",
            "exp-20260527-906",
            "exp-20260612-015",
            "exp-20260612-016",
        ],
        "prior_trial_count": 4,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "pit_sec_13f_quarterly_sponsorship_acceleration",
        "prediction": {**PREDICTION, "actual_success": 0},
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": False,
            "failure_modes_observed": [reason],
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window core replay was not run",
            "windows": framework.WINDOWS,
            "blocked_reason": reason,
        },
        "gate_questions": PRE_RUN_QUESTIONS,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {"passed": False, "blocked_reason": reason},
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "SEC 13F structured data filing-window zip downloads",
                "SEC 13F name-mapped ticker holdings",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": bool(gate2_open_positions.get("passed")),
        },
        "gate3": {"passed": False, "blocked_reason": reason},
        "gate4": {
            "passed": False,
            "decision": "blocked_sec13f_sponsorship_acceleration_historical_data_unavailable",
            "failed_reasons": [reason],
        },
        "sec13f_history_summary": history_summary,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The alpha hypothesis could not be evaluated because the required "
            "historical SEC 13F filing-window data did not load."
        ),
        "rejection_reason": reason,
        "next_evidence_needed": (
            "Fetch the missing historical 13F filing-window zip files or add a "
            "checked-in small fixture for parser/schema validation before "
            "retrying the same PIT sponsorship policy."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The experiment was blocked by unavailable historical 13F "
                "window data, so no alpha conclusion was drawn."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep 13F thresholds without first making the PIT "
                "historical filing windows available and auditable."
            ),
            "new_evidence_required": "Historical 13F filing windows for 2024-2025.",
        },
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


def _build_payload() -> dict[str, Any]:
    _configure_framework_globals()
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()
    holdings_by_label, history_summary = _load_13f_history(set(sector_entries_all))
    ordered_13f_windows = _ordered_13f_windows(holdings_by_label)
    if len(ordered_13f_windows) < 4:
        return _blocked_payload(
            timestamp=timestamp,
            gate2_open_positions=gate2_open_positions,
            history_summary=history_summary,
            reason="historical_13f_window_count_too_low",
        )

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and PIT SEC 13F sponsorship replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        sector_entries = {
            ticker: meta
            for ticker, meta in sector_entries_all.items()
            if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "sec13f_windows_loaded": history_summary["window_count_loaded"],
        }
        candidates, contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
            ordered_13f_windows=ordered_13f_windows,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        for trade in selected_trades:
            trade["window"] = label
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        contexts_by_window[label] = contexts[:200]
        context_scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_day_count": scan.get("days_with_raw_13f_candidates", 0),
            "days_with_13f_pair": scan.get("days_with_13f_pair", 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework.sleeve._aggregate(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    passed = bool(gate4["passed"])
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": passed,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
    }
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "experiment_local_replay_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_13f_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260613-007",
            "exp-20260527-906",
            "exp-20260612-015",
            "exp-20260612-016",
        ],
        "prior_trial_count": 4,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "pit_sec_13f_quarterly_sponsorship_acceleration",
        "prediction": {
            **PREDICTION,
            "actual_success": 1 if passed else 0,
            "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
            "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            "brier_score": calibration["brier_score"],
        },
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "experiment-local PIT SEC 13F sponsorship acceleration paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec13f_provenance": (
                "SEC structured Form 13F filing-window zip files. A signal day "
                "uses only the latest window whose end date is <= signal date "
                "and compares it with the prior fully ended window."
            ),
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Signal uses only 13F windows fully ended by the signal date "
                "and signal-date OHLCV available after the close. Paper entry "
                "is next available open with existing entry slippage; exit is "
                "the close 10 trading days after signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_history_sessions": MIN_HISTORY_SESSIONS,
            "min_holder_count": MIN_HOLDER_COUNT,
            "min_holder_delta": MIN_HOLDER_DELTA,
            "min_holder_growth_pct": MIN_HOLDER_GROWTH_PCT,
            "min_value_growth_pct": MIN_VALUE_GROWTH_PCT,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "same_ticker_core_overlap_excluded": True,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "sec13f_history_summary": history_summary,
        "gate_questions": PRE_RUN_QUESTIONS,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SEC 13F window_label/window_end/ticker/holder_count/total_value_usd",
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
                "No core entry filter is added. The 13F source is additive "
                "default-off paper; core signals and survival are unchanged "
                "from baseline."
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
        "contexts_by_window": contexts_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "interpretation": (
            "The SEC 13F sponsorship acceleration source cleared numeric Gate "
            "4, but remains only a replay lead because no shared daily helper "
            "or production default-off snapshot was promoted."
            if passed
            else (
                "The SEC 13F sponsorship acceleration source was rejected "
                "under the standard three-window protocol."
            )
        ),
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "A retry needs materially different 13F information, such as "
            "manager-quality segmentation, new-position concentration, "
            "sector-normalized sponsorship surprise, or closed forward rows "
            "from a shared default-off helper. Do not sweep the same frozen "
            "thresholds on holder/value growth."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed 13F sponsorship bundle passed numerically, but it "
                "is not accepted alpha because the daily/shared helper parity "
                "surface is absent."
                if passed
                else (
                    "The fixed 13F sponsorship bundle failed Gate 4. The most "
                    "likely reasons are that quarterly aggregate 13F data is "
                    "stale after a full filing-window delay, holder/value "
                    "growth is partly market-cap and price-level exposure, and "
                    "large liquid leaders with institutional accumulation are "
                    "already represented in the core/risk-on signals."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping holder-count, value-growth, ADV, "
                "close-location, top-N, hold-day, cooldown, or notional "
                "thresholds on the same frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs manager identity/quality, true new-position "
                "signals, sector-relative sponsorship surprise, or shared "
                "daily default-off forward rows."
            ),
        },
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


def _window_metric_row(payload: dict[str, Any], label: str) -> str:
    before = payload.get("before_metrics", {}).get(label, {})
    after = payload.get("after_metrics", {}).get(label, {})
    delta = payload.get("delta_metrics", {}).get("by_window", {}).get(label, {})
    scan = payload.get("context_scan_by_window", {}).get(label, {})
    trades = len(payload.get("target_trades_by_window", {}).get(label, []))
    return (
        "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
        "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
        "{pair_days} | {cand_days} | {trades} |"
    ).format(
        label=label,
        bev=float(before.get("expected_value_score") or 0.0),
        aev=float(after.get("expected_value_score") or 0.0),
        dev=float(delta.get("expected_value_score") or 0.0),
        bpnl=float(before.get("total_pnl") or 0.0),
        apnl=float(after.get("total_pnl") or 0.0),
        dpnl=float(delta.get("total_pnl") or 0.0),
        dd=float(delta.get("max_drawdown_pct") or 0.0),
        pair_days=scan.get("days_with_13f_pair", 0),
        cand_days=scan.get("days_with_raw_13f_candidates", 0),
        trades=trades,
    )


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | 13F-pair days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if payload["status"] != "blocked":
        for label in framework.WINDOWS:
            rows.append(_window_metric_row(payload, label))
        aggregate = payload["delta_metrics"]["aggregate"]
        aggregate_lines = [
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
        ]
    else:
        aggregate_lines = [
            "- Blocked reason: `{}`".format(payload["rejection_reason"]),
        ]
    history = payload["sec13f_history_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 13F Sponsorship Acceleration",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## 13F History",
            "",
            "- Requested windows: `{}`".format(history["window_count_requested"]),
            "- Loaded windows: `{}`".format(history["window_count_loaded"]),
            "- Download errors: `{}`".format(len(history.get("download_errors") or [])),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            *aggregate_lines,
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload.get("delta_metrics", {}).get("aggregate", {})
    windows: list[dict[str, Any]] = []
    if payload["status"] != "blocked":
        for label in framework.WINDOWS:
            windows.append(
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
                    "days_with_13f_pair": payload["context_scan_by_window"][label].get(
                        "days_with_13f_pair"
                    ),
                    "candidate_day_count": payload["context_scan_by_window"][label].get(
                        "days_with_raw_13f_candidates"
                    ),
                    "target_trade_count": len(payload["target_trades_by_window"][label]),
                }
            )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": bool(payload.get("gate4", {}).get("passed")),
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": f"{_repo_rel(OUT_JSON)}#before_metrics",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum", 0.0),
        "aggregate_expected_value_delta_pct": aggregate.get("expected_value_score_delta_pct"),
        "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum", 0.0),
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": windows,
        "sec13f_history_summary": payload["sec13f_history_summary"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": None
        if payload.get("gate4", {}).get("passed")
        else payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload.get("delta_metrics", {}).get("aggregate", {})
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": bool(payload.get("gate4", {}).get("passed")),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate.get("expected_value_score_delta_sum", 0.0),
        "aggregate_strategy_total_pnl_delta": aggregate.get("total_pnl_delta_sum", 0.0),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload.get("prior_trial_count", 4),
        "nearby_prior_experiments": payload.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": payload.get("multiple_testing_risk_bucket", "moderate"),
        "new_evidence_type": payload.get(
            "new_evidence_type",
            "pit_sec_13f_quarterly_sponsorship_acceleration",
        ),
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
