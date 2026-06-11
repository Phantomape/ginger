"""exp-20260611-013: delayed SEC filing confirmation leadership scout.

Replay-only alpha search. This tests one candidate-source policy:
after a PIT-safe SEC filing is usable, wait 1-3 trading sessions and only
admit the stock if price/volume action confirms relative leadership before a
default-off next-open paper entry with a fixed 10-trading-day hold.

This is not promoted to production. No shared policy, live order path, live
ranking, sizing, exits, LLM/news behavior, or watchlist behavior changes.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260611-013"
STEM = "delayed_sec_filing_confirmation_leadership"
TRIAL_FAMILY = "delayed_sec_filing_confirmation_candidate_pool"
TRIAL_VARIANT_ID = "delayed_sec_filing_confirmation_top1_next_open_10d_v1"
CHANGED_VARIABLE = "delayed_sec_filing_confirmation_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_EVENTS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

ACCEPTED_FORMS = {"8-K", "10-Q", "10-K"}
MIN_EVENT_LAG_SESSIONS = 1
MAX_EVENT_LAG_SESSIONS = 3
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.006
MIN_RELATIVE_VS_SPY = 0.008
MIN_RELATIVE_VS_QQQ = 0.002
MIN_CLOSE_LOCATION = 0.65
MIN_VOLUME_RATIO_20D = 1.05
MAX_VOLUME_RATIO_20D = 5.00
MIN_RET5 = -0.060
MAX_RET5 = 0.140
MAX_RET20 = 0.360
MIN_RET20_EXCESS_SPY = -0.010
MIN_RET60_EXCESS_SPY = -0.040
MAX_REALIZED_VOL_20D = 0.095

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
    "target_trade_count": 113,
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "generic_sec_filing_noise",
        "delayed_confirmation_relabels_momentum",
        "old_thin_regression",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Prior SEC same-day text, cadence, complexity, and periodic-report "
        "absorption variants failed. This fixed scout changes the causal "
        "timing: it waits for delayed market confirmation after a PIT-safe "
        "filing instead of retuning phrases or forms."
    ),
    "recorded_at": "2026-06-11T10:07:20Z",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "uses_llm": False,
    "uses_free_sec_filing_events": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "PIT-safe filing lag, confirmation fields, overlap exclusion, next-open "
        "paper entry, hold, costs, cooldown, comparator, and concentration "
        "controls in historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT-safe SEC filings may be underreacted to only "
        "after a 1-3 session confirmation window. Require delayed "
        "SPY/QQQ-relative leadership, high close quality, abnormal volume, "
        "liquidity, and non-parabolic trend guards before next-open paper "
        "entry."
    ),
    "2_history_check": {
        "exp-20260610-023": (
            "SEC contract/customer/order text leadership was rejected because "
            "explicit phrase hits were too sparse."
        ),
        "exp-20260610-024": (
            "SEC earnings cadence surprise absorption was rejected with only "
            "five trades."
        ),
        "exp-20260611-001": (
            "SEC filing complexity/change density was rejected; generic "
            "filing metadata was not enough."
        ),
        "exp-20260611-012": (
            "Same-day 10-Q/10-K periodic-report absorption was rejected with "
            "nine trades and weak replacement value."
        ),
        "difference": (
            "This is not a phrase, form, or same-day threshold retune. It "
            "tests whether delayed post-filing confirmation changes the "
            "source utility. It is scout-only because the new evidence is "
            "timing rather than richer filing semantics."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no EV/PnL window regression, at least 20 "
        "target trades across all 3 windows, survival >=5%, drawdown drift "
        "<=0.5pp, concentration passes, and the accepted distribution-day "
        "comparator is beaten. Even if positive, replay-only status is not "
        "accepted production alpha."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_013_delayed_sec_filing_confirmation_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_sec_events() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not SEC_EVENTS_PATH.exists():
        return rows
    with SEC_EVENTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            form = str(row.get("form_type") or row.get("form_base") or "").upper()
            ticker = str(row.get("ticker") or "").upper()
            usable_date = str(row.get("usable_trade_date") or "")[:10]
            if form not in ACCEPTED_FORMS:
                continue
            if not ticker or not usable_date:
                continue
            if row.get("is_amendment") is True:
                continue
            if row.get("pit_safe_flag") is False:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "usable_trade_date": usable_date,
                    "filing_date": str(row.get("filing_date") or "")[:10],
                    "accepted_at": row.get("accepted_at"),
                    "accession_number": row.get("accession_number"),
                    "form_type": form,
                    "form_base": row.get("form_base"),
                    "eight_k_item_codes": row.get("eight_k_item_codes") or [],
                    "items_raw": row.get("items_raw"),
                    "size": _float_or_none(row.get("size")),
                    "archive_url": row.get("archive_url"),
                    "pit_safe_flag": row.get("pit_safe_flag"),
                }
            )
    return rows


def _events_by_usable_date_ticker(
    events: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    form_counts: Counter[str] = Counter()
    ticker_count: Counter[str] = Counter()
    for event in events:
        usable_date = str(event["usable_trade_date"])[:10]
        ticker = str(event["ticker"]).upper()
        form = str(event.get("form_type") or "").upper()
        out.setdefault(usable_date, {}).setdefault(ticker, []).append(event)
        form_counts[form] += 1
        ticker_count[ticker] += 1
    return out, {
        "eligible_event_count": len(events),
        "eligible_event_day_count": len(out),
        "eligible_event_ticker_count": len(ticker_count),
        "eligible_form_distribution": dict(sorted(form_counts.items())),
    }


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    delayed_events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60:
        return None

    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    close_location = framework._close_location(row)
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx)
    required = [
        signal_return,
        spy_return,
        qqq_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None

    relative_vs_spy = float(signal_return) - float(spy_return)
    relative_vs_qqq = float(signal_return) - float(qqq_return)
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)

    if float(signal_return) < MIN_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_RELATIVE_VS_SPY:
        return None
    if relative_vs_qqq < MIN_RELATIVE_VS_QQQ:
        return None
    if float(close_location) < MIN_CLOSE_LOCATION:
        return None
    if float(volume_ratio) < MIN_VOLUME_RATIO_20D:
        return None
    if float(volume_ratio) > MAX_VOLUME_RATIO_20D:
        return None
    if float(ret5) < MIN_RET5 or float(ret5) > MAX_RET5:
        return None
    if float(ret20) > MAX_RET20:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if float(realized_vol20) > MAX_REALIZED_VOL_20D:
        return None

    form_counts = Counter(str(event.get("form_type") or "") for event in delayed_events)
    lag_values = [
        int(event["event_lag_sessions"])
        for event in delayed_events
        if event.get("event_lag_sessions") is not None
    ]
    event_score = sum(_event_score(event) for event in delayed_events)
    lag_score = max(0.0, 0.12 - 0.03 * (min(lag_values) - 1)) if lag_values else 0.0
    score = (
        event_score
        + lag_score
        + 4.0 * relative_vs_spy
        + 2.0 * relative_vs_qqq
        + 1.00 * ret20_excess_spy
        + 0.35 * float(close_location)
        + 0.12 * min(float(volume_ratio), 3.0)
        + 0.04 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        - 0.55 * float(realized_vol20)
    )
    sector_meta = sector_entries[ticker]
    accessions = [
        str(event.get("accession_number") or "")
        for event in delayed_events
        if event.get("accession_number")
    ][:5]
    return {
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source": "DELAYED_SEC_FILING_CONFIRMATION_PAPER",
        "strategy": "delayed_sec_filing_confirmation_candidate_pool",
        "candidate_score": round(score, 6),
        "candidate_event_score": round(event_score, 6),
        "candidate_event_lag_min": min(lag_values) if lag_values else None,
        "candidate_event_lag_max": max(lag_values) if lag_values else None,
        "candidate_event_count": len(delayed_events),
        "candidate_form_distribution": dict(sorted(form_counts.items())),
        "candidate_accessions": accessions,
        "candidate_signal_return": round(float(signal_return), 6),
        "candidate_spy_return": round(float(spy_return), 6),
        "candidate_qqq_return": round(float(qqq_return), 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_ret5": round(float(ret5), 6),
        "candidate_ret20": round(float(ret20), 6),
        "candidate_ret60": round(float(ret60), 6),
        "candidate_spy_ret20": round(float(spy_ret20), 6),
        "candidate_spy_ret60": round(float(spy_ret60), 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(float(close_location), 6),
        "candidate_volume_ratio_20d": round(float(volume_ratio), 6),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_realized_vol_20d": round(float(realized_vol20), 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "uses_free_sec_filing_events": True,
        "uses_free_ohlcv": True,
        "uses_llm": False,
        "trade_enabled": False,
        "alters_orders": False,
        "delayed_events": delayed_events[:5],
        "decision_id": f"DELAYED_SEC_CONFIRM:{RULE_VERSION}:{signal_date}:{ticker}",
    }


def _event_score(event: dict[str, Any]) -> float:
    form = str(event.get("form_type") or "").upper()
    size = _float_or_none(event.get("size")) or 0.0
    score = 1.10 if form == "8-K" else 1.20 if form == "10-Q" else 1.00
    if size >= 20_000_000:
        score += 0.20
    elif size >= 5_000_000:
        score += 0.08
    item_codes = event.get("eight_k_item_codes") or []
    if isinstance(item_codes, list):
        score += min(len(item_codes), 4) * 0.02
    return score


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_event_score") or 0.0),
        -float(row.get("candidate_relative_vs_spy") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("sector") or ""),
        str(row.get("ticker") or ""),
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
    events_by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]],
    event_scan: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    trading_dates = framework.shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    dates = [
        date_value
        for date_value in trading_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    lag_distribution: Counter[int] = Counter()
    form_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "delayed_signal_days": 0,
        "days_with_raw_delayed_sec_candidates": 0,
        "raw_delayed_sec_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "event_lag_sessions_min": MIN_EVENT_LAG_SESSIONS,
        "event_lag_sessions_max": MAX_EVENT_LAG_SESSIONS,
        **event_scan,
    }
    for signal_date in dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < MAX_EVENT_LAG_SESSIONS:
            continue
        delayed_by_ticker: dict[str, list[dict[str, Any]]] = {}
        for lag in range(MIN_EVENT_LAG_SESSIONS, MAX_EVENT_LAG_SESSIONS + 1):
            event_date = trading_dates[pos - lag]
            for ticker, events in (events_by_date_ticker.get(event_date) or {}).items():
                if ticker not in sector_entries:
                    continue
                for event in events:
                    delayed_by_ticker.setdefault(ticker, []).append(
                        {**event, "event_lag_sessions": lag}
                    )
                    lag_distribution[lag] += 1
                    form_distribution[str(event.get("form_type") or "")] += 1
        if not delayed_by_ticker:
            continue
        scan["delayed_signal_days"] += 1
        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {str(entry.get("ticker") or "").upper() for entry in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, delayed_events in sorted(delayed_by_ticker.items()):
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                delayed_events=delayed_events,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_delayed_sec_candidates"] += 1
        scan["raw_delayed_sec_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_forms": top["candidate_form_distribution"],
                "top_candidate_event_lag_min": top["candidate_event_lag_min"],
                "top_candidate_relative_vs_spy": top["candidate_relative_vs_spy"],
                "top_candidate_volume_ratio_20d": top["candidate_volume_ratio_20d"],
            }
        )
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "lag_distribution": dict(sorted(lag_distribution.items())),
            "form_distribution_seen_in_delay_windows": dict(sorted(form_distribution.items())),
        }
    )
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


def _aggregate_window_rows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return framework.sleeve._aggregate(rows)


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
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_distribution_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_distribution_pnl_not_beaten")
    passed = not failed
    gate.update(
        {
            "passed": passed,
            "decision": (
                "positive_replay_lead_not_promoted_delayed_sec_filing_confirmation"
                if passed
                else "rejected_delayed_sec_filing_confirmation_candidate_pool"
            ),
            "failed_reasons": failed,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        }
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_framework_globals()
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    sec_events = _load_sec_events()
    events_by_date_ticker, event_scan = _events_by_usable_date_ticker(sec_events)
    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()
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
        print(f"[{label}] core baseline and delayed SEC confirmation replay")
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
            "sec_event_source": _repo_rel(SEC_EVENTS_PATH),
        }
        candidates, contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
            events_by_date_ticker=events_by_date_ticker,
            event_scan=event_scan,
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
        contexts_by_window[label] = contexts
        context_scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "delayed_signal_day_count": scan.get("delayed_signal_days", 0),
            "candidate_day_count": scan.get("days_with_raw_delayed_sec_candidates", 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = _aggregate_window_rows(window_rows)
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
        "mechanism_family": "production_visible_free_sec_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260610-023",
            "exp-20260610-024",
            "exp-20260611-001",
            "exp-20260611-012",
            "exp-20260611-007",
        ],
        "prior_trial_count": 5,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "delayed_pit_sec_filing_confirmation_timing",
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
                "experiment-local delayed SEC filing confirmation paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec_event_source": _repo_rel(SEC_EVENTS_PATH),
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Signal uses only PIT SEC filing usable date and signal-date "
                "OHLCV available after the close. Paper entry is next available "
                "open with existing entry slippage; exit is the close 10 "
                "trading days after signal with target-side sell slippage and "
                "ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_forms": sorted(ACCEPTED_FORMS),
            "min_event_lag_sessions": MIN_EVENT_LAG_SESSIONS,
            "max_event_lag_sessions": MAX_EVENT_LAG_SESSIONS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
            "min_relative_vs_qqq": MIN_RELATIVE_VS_QQQ,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_ret20": MAX_RET20,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "same_ticker_core_overlap_excluded": True,
            "single_causal_variable": CHANGED_VARIABLE,
        },
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
                "SEC filing event ticker/form_type/usable_trade_date/pit_safe_flag",
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
                "No core entry filter is added. The delayed SEC source is "
                "additive default-off paper; core signals and survival are "
                "unchanged from baseline."
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
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "interpretation": (
            "The delayed SEC confirmation source cleared the numeric replay "
            "gates, but remains only a replay lead because no shared daily "
            "helper was promoted."
            if passed
            else (
                "The delayed SEC confirmation source was rejected under the "
                "standard three-window protocol and current accepted "
                "distribution-day comparator."
            )
        ),
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "A retry needs materially richer PIT filing semantics or forward "
            "replacement rows. Do not sweep forms, lag days, return, volume, "
            "top-N, hold-day, cooldown, or notional thresholds on the same "
            "frozen windows."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed delayed SEC confirmation bundle passed numerically, "
                "but it is still not accepted alpha because a shared daily "
                "helper and forward paper rows are required before any "
                "production-visible promotion."
                if passed
                else (
                    "The fixed delayed SEC confirmation bundle failed Gate 4. "
                    "The likely reason is that a filing followed by delayed "
                    "relative strength is still mostly generic momentum or "
                    "already-priced event information after next-open "
                    "execution, costs, cooldown, and overlap controls."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping SEC forms, lag sessions, same-day "
                "return, relative-strength, close-location, volume, ret5/ret20, "
                "top-N, hold-day, cooldown, or notional thresholds."
            ),
            "new_evidence_required": (
                "A retry needs richer PIT semantics such as named customer, "
                "supplier, contract value/duration, parsed filing surprise, or "
                "closed forward replacement-value data."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Signal days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {sig_days} | {cand_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                sig_days=scan.get("delayed_signal_days", 0),
                cand_days=scan.get("days_with_raw_delayed_sec_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Delayed SEC Filing Confirmation Leadership",
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
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
        "baseline_result_file": f"{_repo_rel(OUT_JSON)}#before_metrics",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
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
                "delayed_signal_day_count": payload["context_scan_by_window"][label].get(
                    "delayed_signal_days"
                ),
                "candidate_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_delayed_sec_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": None
        if payload["gate4"]["passed"]
        else payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
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
