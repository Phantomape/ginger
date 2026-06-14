"""exp-20260614-007: earnings-catalyst peer underreaction scout.

Replay-only alpha search. The single decision hypothesis is that an
earnings-related SEC filing with a strong first post-event close can transfer
delayed demand to same-industry, high-correlation peers that have not yet
reacted. The candidate is observed after the catalyst reaction close and enters
paper at the next open with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260614-007"
STEM = "earnings_peer_underreaction"
TRIAL_FAMILY = "earnings_catalyst_peer_underreaction_candidate_pool"
TRIAL_VARIANT_ID = "sec_earnings_catalyst_peer_underreaction_top1_next_open_10d_v1"
CHANGED_VARIABLE = "earnings_peer_underreaction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_007_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_EVENTS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

CORR_LOOKBACK_DAYS = 60
MIN_CORR_OBSERVATIONS = 45
MIN_PRIOR_CORR = 0.55
MIN_INDUSTRY_PEER_COUNT = 3

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_CATALYST_T1_RETURN = 0.025
MIN_CATALYST_T1_EXCESS_SPY = 0.020
MAX_CATALYST_T1_RETURN = 0.220
MIN_CANDIDATE_SIGNAL_RETURN = -0.025
MAX_CANDIDATE_SIGNAL_RETURN = 0.018
MIN_CANDIDATE_SIGNAL_VS_SPY = -0.015
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.020
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.050
MIN_CANDIDATE_CLOSE_LOCATION = 0.35
MAX_CANDIDATE_REALIZED_VOL_20D = 0.100
MIN_EVENT_CANDIDATE_REACTION_GAP = 0.030

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ROLLING_CORR_PEER_SHOCK_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
    "aggregate_expected_value_delta": 0.3845,
    "aggregate_pnl_delta": 6107.66,
}

PREDICTION = {
    "success_probability": 0.23,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "same_sector_peer_transfer_still_noisy",
        "sec_event_overlap_with_accepted_financial_report",
        "window_regression",
        "drawdown_drift",
        "thin_sample",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation relation alpha shows peer relations can "
        "work, while generic same-sector and correlation-breakdown variants "
        "failed. This test adds a free PIT SEC earnings catalyst and requires "
        "the candidate peer to underreact before next-open paper entry; main "
        "risk is that the catalyst effect is already priced or duplicated by "
        "accepted SEC financial-report and peer-shock helpers."
    ),
    "recorded_at": "2026-06-14T05:05:38+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
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
    "uses_free_sec_event_metadata": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing SEC event date, OHLCV, correlation, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same SEC "
        "earnings catalyst set, first post-event reaction, same-industry "
        "rolling-correlation peer relation, underreaction gate, same-ticker "
        "core-overlap exclusion, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: earnings-related SEC filing winners with a strong "
        "first post-event close can transfer delayed demand to same-industry "
        "high-correlation peers that have not yet reacted."
    ),
    "2_history_check": {
        "exp-20260606-025": (
            "Accepted rolling-correlation peer-shock shared adapter is the "
            "binding relation comparator: EV +0.3845, PnL +$6,107.66."
        ),
        "exp-20260613-028": (
            "Rejected multi-peer same-sector purity; this run adds an explicit "
            "SEC earnings catalyst rather than requiring pure peer-price support."
        ),
        "exp-20260614-006": (
            "Rejected correlation-breakdown idiosyncratic leader; this run "
            "looks for underreacting peers after an external catalyst, not the "
            "leader itself."
        ),
        "exp-20260614-004": (
            "Accepted SEC financial-report RS20 notional support on the direct "
            "event sleeve; this run tests peer transfer and must not alter that "
            "shared helper."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least 20 paper "
        "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted rolling-corr peer-shock comparator "
        "must be beaten. Replay-only positives are leads until shared daily/"
        "backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_007_earnings_peer_underreaction.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_framework() -> None:
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
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._configure_sleeve_globals()


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _load_sec_events_by_date() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    if not SEC_EVENTS_PATH.exists():
        return {}, {"error": "missing_sec_events_path", "path": _repo_rel(SEC_EVENTS_PATH)}
    for line in SEC_EVENTS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        stats["raw_rows"] += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            stats["json_decode_failed"] += 1
            continue
        if not isinstance(row, dict):
            stats["non_object_rows"] += 1
            continue
        if row.get("pit_safe_flag") is False or row.get("is_amendment"):
            stats["pit_or_amendment_dropped"] += 1
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not ticker or not usable:
            stats["missing_ticker_or_usable_trade_date"] += 1
            continue
        kind = _event_kind(row)
        if not kind:
            stats["non_earnings_event_dropped"] += 1
            continue
        by_date[usable].append(
            {
                "ticker": ticker,
                "usable_trade_date": usable,
                "event_kind": kind,
                "form_base": str(row.get("form_base") or "").upper(),
                "form_type": row.get("form_type"),
                "item_codes": _item_codes(row),
                "accession_number": row.get("accession_number"),
                "accepted_at": row.get("accepted_at"),
                "filing_date": row.get("filing_date"),
                "archive_url": row.get("archive_url"),
            }
        )
        stats[f"{kind}_rows"] += 1
    return dict(by_date), {
        "path": _repo_rel(SEC_EVENTS_PATH),
        "rows_by_usable_trade_date": len(by_date),
        "candidate_event_rows": sum(len(rows) for rows in by_date.values()),
        **dict(stats),
    }


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=100)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
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


def _event_kind(row: dict[str, Any]) -> str | None:
    form_base = str(row.get("form_base") or "").upper()
    item_codes = _item_codes(row)
    if form_base == "8-K" and "2.02" in item_codes:
        return "earnings_8k_item_2_02"
    if form_base in {"10-Q", "10-K"}:
        return "periodic_report"
    return None


def _item_codes(row: dict[str, Any]) -> list[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return [str(value).strip() for value in raw if str(value).strip()]
    raw_text = str(row.get("items_raw") or "")
    return [part.strip() for part in raw_text.split(",") if part.strip()]


def _industry_key(meta: dict[str, Any]) -> str:
    industry = str(meta.get("industry") or "").strip()
    if industry:
        return industry
    sector = str(meta.get("sector") or "").strip()
    return f"sector::{sector}" if sector else ""


def _industry_groups(
    sector_entries: dict[str, dict[str, Any]],
    available_tickers: set[str],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for ticker, meta in sector_entries.items():
        ticker_u = str(ticker).upper()
        if ticker_u not in available_tickers:
            continue
        key = _industry_key(meta)
        if key:
            groups[key].append(ticker_u)
    return {key: sorted(values) for key, values in groups.items()}


def _prior_return_vector(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    prior_dates: list[str],
) -> list[float] | None:
    rows = framework.shadow._series(snapshot, ticker)
    values: list[float] = []
    for day in prior_dates:
        idx = indices.get(ticker, {}).get(day)
        if idx is None or idx < 1:
            return None
        value = framework._daily_return(rows, idx)
        if value is None:
            return None
        values.append(float(value))
    if len(values) < MIN_CORR_OBSERVATIONS:
        return None
    return values


def _pearson_corr(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < MIN_CORR_OBSERVATIONS:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_var = sum((value - left_mean) ** 2 for value in left)
    right_var = sum((value - right_mean) ** 2 for value in right)
    if left_var <= 0.0 or right_var <= 0.0:
        return None
    cov = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    return cov / math.sqrt(left_var * right_var)


def _event_reaction_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    dates: list[str],
    date_pos: dict[str, int],
    sector_entries: dict[str, dict[str, Any]],
    event: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(event.get("ticker") or "").upper()
    event_date = str(event.get("usable_trade_date") or "")[:10]
    if ticker not in sector_entries or ticker not in snapshot:
        return None
    event_pos = date_pos.get(event_date)
    if event_pos is None or event_pos + 1 >= len(dates):
        return None
    signal_date = dates[event_pos + 1]
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, "SPY")
    event_idx = indices.get(ticker, {}).get(event_date)
    signal_idx = indices.get(ticker, {}).get(signal_date)
    spy_event_idx = indices.get("SPY", {}).get(event_date)
    spy_signal_idx = indices.get("SPY", {}).get(signal_date)
    if None in (event_idx, signal_idx, spy_event_idx, spy_signal_idx):
        return None
    if event_idx is None or signal_idx is None or spy_event_idx is None or spy_signal_idx is None:
        return None
    event_close = framework._value(rows[event_idx], "Close")
    signal_close = framework._value(rows[signal_idx], "Close")
    spy_event_close = framework._value(spy_rows[spy_event_idx], "Close")
    spy_signal_close = framework._value(spy_rows[spy_signal_idx], "Close")
    if not event_close or not signal_close or not spy_event_close or not spy_signal_close:
        return None
    event_return = (signal_close / event_close) - 1.0
    spy_return = (spy_signal_close / spy_event_close) - 1.0
    event_excess = event_return - spy_return
    if event_return < MIN_CATALYST_T1_RETURN:
        return None
    if event_return > MAX_CATALYST_T1_RETURN:
        return None
    if event_excess < MIN_CATALYST_T1_EXCESS_SPY:
        return None
    adv20 = framework._avg_dollar_volume(rows, signal_idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    industry = _industry_key(sector_entries[ticker])
    if not industry:
        return None
    return {
        **event,
        "event_ticker": ticker,
        "event_date": event_date,
        "signal_date": signal_date,
        "event_t1_return": _round(event_return, 6),
        "spy_t1_return": _round(spy_return, 6),
        "event_t1_excess_spy": _round(event_excess, 6),
        "event_avg_dollar_volume_20d": _round(adv20, 2),
        "event_sector": sector_entries[ticker].get("sector"),
        "event_industry": sector_entries[ticker].get("industry"),
        "industry_key": industry,
    }


def _candidate_for_peer(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    event_context: dict[str, Any],
    ticker: str,
    prior_dates: list[str],
) -> dict[str, Any] | None:
    event_ticker = str(event_context["event_ticker"]).upper()
    if ticker == event_ticker:
        return None
    signal_date = str(event_context["signal_date"])
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    close_location = framework._close_location(rows[idx])
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx, 20)
    if any(
        value is None
        for value in (
            signal_return,
            spy_signal_return,
            close_location,
            ret20,
            ret60,
            spy_ret20,
            spy_ret60,
            realized_vol,
        )
    ):
        return None
    assert signal_return is not None
    assert spy_signal_return is not None
    assert close_location is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol is not None
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if signal_return > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    candidate_signal_vs_spy = signal_return - spy_signal_return
    if candidate_signal_vs_spy < MIN_CANDIDATE_SIGNAL_VS_SPY:
        return None
    reaction_gap = float(event_context["event_t1_return"]) - signal_return
    if reaction_gap < MIN_EVENT_CANDIDATE_REACTION_GAP:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None
    event_vec = _prior_return_vector(snapshot, indices, event_ticker, prior_dates)
    peer_vec = _prior_return_vector(snapshot, indices, ticker, prior_dates)
    if event_vec is None or peer_vec is None:
        return None
    corr = _pearson_corr(event_vec, peer_vec)
    if corr is None or corr < MIN_PRIOR_CORR:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    score = (
        1.75 * corr
        + 3.00 * float(event_context["event_t1_excess_spy"])
        + 1.25 * float(event_context["event_t1_return"])
        + 0.55 * ret20_excess_spy
        + 0.20 * ret60_excess_spy
        + 0.15 * close_location
        - 0.85 * max(signal_return, 0.0)
        - 0.45 * realized_vol
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "EARNINGS_PEER_UNDERREACTION_PAPER",
        "candidate_score": _round(score, 6),
        "rule_version": RULE_VERSION,
        "source_rule_version": RULE_VERSION,
        "event_ticker": event_ticker,
        "event_date": event_context["event_date"],
        "event_signal_date": event_context["signal_date"],
        "event_kind": event_context["event_kind"],
        "event_form_base": event_context["form_base"],
        "event_item_codes": event_context["item_codes"],
        "event_accession_number": event_context.get("accession_number"),
        "event_t1_return": event_context["event_t1_return"],
        "event_t1_excess_spy": event_context["event_t1_excess_spy"],
        "spy_t1_return": event_context["spy_t1_return"],
        "event_candidate_reaction_gap": _round(reaction_gap, 6),
        "rolling_corr_prior60": _round(corr, 6),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_signal_vs_spy": _round(candidate_signal_vs_spy, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_spy_ret20": _round(spy_ret20, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60": _round(ret60, 6),
        "candidate_spy_ret60": _round(spy_ret60, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "event_sector": event_context.get("event_sector"),
        "event_industry": event_context.get("event_industry"),
        "known_at": "after_catalyst_t1_close_before_next_open_paper_entry",
        "uses_free_sec_event_metadata": True,
        "uses_free_ohlcv": True,
        "uses_llm": False,
        "trade_enabled": False,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
    sec_events_by_date: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = framework.shadow._trading_dates(snapshot)
    date_pos = {day: pos for pos, day in enumerate(dates)}
    window_dates = [
        day
        for day in dates
        if str(cfg["start"]) <= day <= str(cfg["end"])
    ]
    groups = _industry_groups(sector_entries, set(snapshot))
    candidates_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    event_contexts: list[dict[str, Any]] = []
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["industry_group_count"] = len(groups)

    for event_date, events in sorted(sec_events_by_date.items()):
        event_pos = date_pos.get(event_date)
        if event_pos is None or event_pos + 1 >= len(dates):
            continue
        signal_date = dates[event_pos + 1]
        if signal_date < str(cfg["start"]) or signal_date > str(cfg["end"]):
            continue
        if event_pos < CORR_LOOKBACK_DAYS:
            scan["events_without_prior_lookback"] += len(events)
            continue
        prior_dates = dates[event_pos - CORR_LOOKBACK_DAYS : event_pos]
        for event in events:
            scan["sec_events_in_window"] += 1
            context = _event_reaction_context(
                snapshot=snapshot,
                indices=indices,
                dates=dates,
                date_pos=date_pos,
                sector_entries=sector_entries,
                event=event,
            )
            if context is None:
                scan["events_failed_catalyst_reaction"] += 1
                continue
            peer_tickers = groups.get(str(context["industry_key"]) or "", [])
            if len(peer_tickers) < MIN_INDUSTRY_PEER_COUNT:
                scan["events_failed_min_industry_peer_count"] += 1
                continue
            scan["catalyst_events_passed"] += 1
            context_sample = {
                "event_ticker": context["event_ticker"],
                "signal_date": context["signal_date"],
                "event_kind": context["event_kind"],
                "event_t1_return": context["event_t1_return"],
                "event_t1_excess_spy": context["event_t1_excess_spy"],
                "industry_key": context["industry_key"],
                "peer_pool_count": len(peer_tickers),
            }
            event_contexts.append(context_sample)
            for ticker in peer_tickers:
                candidate = _candidate_for_peer(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    event_context=context,
                    ticker=ticker,
                    prior_dates=prior_dates,
                )
                if candidate is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                candidate["same_day_ab_entry_count"] = len(ab_entries)
                candidate["same_day_ab_overlap"] = bool(ab_entries)
                candidate["same_ticker_ab_overlap"] = any(
                    str(trade.get("ticker") or "").upper() == ticker
                    for trade in ab_entries
                )
                key = (signal_date, ticker)
                existing = candidates_by_key.get(key)
                if existing is None or float(candidate["candidate_score"]) > float(existing["candidate_score"]):
                    candidates_by_key[key] = candidate
                scan["raw_peer_candidate_rows"] += 1

    candidates = list(candidates_by_key.values())
    scan["deduped_candidate_rows"] = len(candidates)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["event_t1_excess_spy"] or 0.0),
            -float(row["rolling_corr_prior60"] or 0.0),
            -float(row["event_candidate_reaction_gap"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    return candidates, event_contexts, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "sec_events_path": _repo_rel(SEC_EVENTS_PATH),
        "correlation_lookback_days": CORR_LOOKBACK_DAYS,
        "min_prior_corr": MIN_PRIOR_CORR,
        "min_catalyst_t1_return": MIN_CATALYST_T1_RETURN,
        "min_catalyst_t1_excess_spy": MIN_CATALYST_T1_EXCESS_SPY,
        "min_event_candidate_reaction_gap": MIN_EVENT_CANDIDATE_REACTION_GAP,
    }


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
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= ROLLING_CORR_PEER_SHOCK_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_rolling_corr_peer_shock_ev_not_beaten")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= ROLLING_CORR_PEER_SHOCK_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_rolling_corr_peer_shock_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["rolling_corr_peer_shock_comparator"] = ROLLING_CORR_PEER_SHOCK_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_earnings_peer_underreaction"
        if gate["passed"]
        else "rejected_earnings_peer_underreaction_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()
    sec_events_by_date, sec_event_archive_summary = _load_sec_events_by_date()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    event_contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and earnings peer-underreaction replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = _load_window_snapshot(
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
        }
        candidates, event_contexts, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
            sec_events_by_date=sec_events_by_date,
        )
        selected_trades, filtered_candidates = framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        event_contexts_by_window[label] = event_contexts[:200]
        context_scan_by_window[label] = context_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "event_context_count": len(event_contexts),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    rejection_reason = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "Earnings-related SEC filing winners may transfer delayed demand "
            "to high-correlation same-industry peers that have not yet reacted "
            "by the first post-event close."
        ),
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_event_relation_candidate_pool",
        "new_evidence_type": "free_sec_event_catalyst_plus_ohlcv_relation_edge",
        "nearby_prior_experiments": [
            "exp-20260606-025",
            "exp-20260613-028",
            "exp-20260614-006",
            "exp-20260614-004",
        ],
        "prior_trial_count": 4,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec_event_archive": _repo_rel(SEC_EVENTS_PATH),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "SEC filing metadata is known by usable_trade_date. Catalyst "
                "reaction is measured at the first post-event close; peer "
                "paper entry is the next available open with existing entry "
                "slippage; exit is the close 10 trading days after the signal "
                "with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "correlation_lookback_days": CORR_LOOKBACK_DAYS,
            "min_prior_corr": MIN_PRIOR_CORR,
            "min_industry_peer_count": MIN_INDUSTRY_PEER_COUNT,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_catalyst_t1_return": MIN_CATALYST_T1_RETURN,
            "min_catalyst_t1_excess_spy": MIN_CATALYST_T1_EXCESS_SPY,
            "max_catalyst_t1_return": MAX_CATALYST_T1_RETURN,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_signal_vs_spy": MIN_CANDIDATE_SIGNAL_VS_SPY,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "min_event_candidate_reaction_gap": MIN_EVENT_CANDIDATE_REACTION_GAP,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "SEC event ticker",
                "SEC event usable_trade_date",
                "SEC event form_base/items_raw/eight_k_item_codes",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV for T+1 excess reaction",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "signals_generated_by_window": {
                label: before_metrics[label].get("signals_generated")
                for label in before_metrics
            },
            "signals_survived_by_window": {
                label: before_metrics[label].get("signals_survived")
                for label in before_metrics
            },
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate")
                for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate "
                "source is additive default-off paper, so core signals generated/"
                "survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "rolling_corr_peer_shock_comparator": ROLLING_CORR_PEER_SHOCK_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "sec_event_archive_summary": sec_event_archive_summary,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "event_context_samples_by_window": event_contexts_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The SEC earnings-catalyst peer-underreaction source cleared Gate 4 "
            "as a replay-only/default-off lead, but no production surface was "
            "promoted."
            if gate4["passed"]
            else (
                "The SEC earnings-catalyst peer-underreaction source did not "
                "clear Gate 4 or did not beat the accepted rolling-correlation "
                "peer-shock comparator. Do not promote or tune this fixed peer "
                "transfer definition on the same frozen windows."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "A retry needs materially stronger PIT relation provenance, such as "
            "named customer/supplier links, source text that binds a peer "
            "relation, or forward replacement-value rows. Do not sweep catalyst "
            "reaction, correlation, industry, signal-return, top-N, hold, "
            "cooldown, or notional thresholds on frozen windows."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "If rejected, the SEC catalyst did not make same-industry peer "
                "transfer durable enough after next-open execution, costs, and "
                "competition with the accepted rolling-correlation relation "
                "helper. The likely edge either remains with the direct SEC "
                "financial-report sleeve or needs a stronger economic relation "
                "than industry plus prior correlation."
            ),
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping catalyst reaction thresholds, "
                "correlation lookback/minimum, industry-vs-sector grouping, "
                "candidate underreaction gap, volume/close/ret guards, top-N, "
                "hold days, cooldown, or notional on these frozen windows."
            ),
            "new_evidence_required": (
                "Need named economic relation provenance or closed forward "
                "replacement-value rows before revisiting SEC catalyst peer "
                "underreaction."
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Catalyst events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("catalyst_events_passed", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Earnings Peer Underreaction",
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
            "- Accepted rolling-corr comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                ROLLING_CORR_PEER_SHOCK_COMPARATOR["aggregate_expected_value_delta"],
                ROLLING_CORR_PEER_SHOCK_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
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
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "rolling_corr_peer_shock_comparator": ROLLING_CORR_PEER_SHOCK_COMPARATOR,
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
                "catalyst_event_count": payload["context_scan_by_window"][label].get(
                    "catalyst_events_passed"
                ),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
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
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
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
    _write_manifest(payload)


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


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
