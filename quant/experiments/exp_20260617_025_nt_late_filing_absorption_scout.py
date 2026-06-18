"""exp-20260617-025: SEC NT late-filing notice absorption scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
NT 10-K / NT 10-Q late-filing notices are usually negative disclosure-delay
events, but can become positive candidate-pool events when signal-day price
action absorbs the notice versus SPY before the next-open paper entry.

This is distinct from rejected early-filing timeliness runs: it tests a late
notice form family from EDGAR submissions, not filed-lag promptness thresholds
from Companyfacts. No production code, shared adapter, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed. A
positive result is only a replay lead until a shared historical/daily helper
reproduces it. No JavaScript is used.
"""

from __future__ import annotations

import bisect
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260617-025"
STEM = "nt_late_filing_absorption_scout"
TRIAL_FAMILY = "free_sec_submissions_nt_late_filing_absorption_candidate_pool"
TRIAL_VARIANT_ID = "nt_late_filing_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_nt_late_filing_notice_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
SUBMISSIONS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_025_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

NT_FORMS = {"NT 10-K", "NT 10-Q", "NT 10-K/A", "NT 10-Q/A"}
FORM_WEIGHTS = {
    "NT 10-Q": 1.00,
    "NT 10-K": 0.92,
    "NT 10-Q/A": 0.70,
    "NT 10-K/A": 0.62,
}

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.0
MIN_SIGNAL_EXCESS_SPY = 0.005
MIN_CLOSE_LOCATION = 0.56
MIN_VOLUME_RATIO_20D = 0.75
MAX_REALIZED_VOL_20D = 0.120
MIN_RET20_EXCESS_SPY = -0.050
MAX_EVENT_AGE_TRADING_DAYS = 3

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "late_filing_notices_are_true_accounting_delay_risk",
        "thin_sample",
        "old_thin_window_regression",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "This is the materially different disclosure-timing field explicitly "
        "allowed after the rejected 10-K/10-Q early-filing tests: SEC NT "
        "late-filing notices from EDGAR submissions are free, PIT, and "
        "production-visible. The edge is contrarian absorption, but late "
        "filings can be genuine accounting/control risk, so expected success "
        "is low."
    ),
    "recorded_at": "2026-06-17T20:04:31+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing SEC submissions cache, missing CIK mapping, missing NT "
            "late-filing notice rows, missing OHLCV, missing next open, or "
            "missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "SEC NT 10-K/NT 10-Q notice events, acceptance-time signal date, "
        "price-absorption gate, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC NT 10-K/NT 10-Q late-filing notices are "
        "normally negative, but when same-day price action absorbs the filing-"
        "delay shock versus SPY, the delayed-disclosure overhang may be priced "
        "in and create a 10-trading-day continuation/rebound candidate."
    ),
    "2_history_check": {
        "exp-20260617-020": (
            "Rejected broad annual 10-K early-filing timeliness. This run tests "
            "late notice forms, not early filed-lag promptness."
        ),
        "exp-20260617-022": (
            "Rejected broad quarterly 10-Q early-filing timeliness. Its closeout "
            "explicitly named NT 10-K/10-Q late-filing notices as materially "
            "different disclosure-timing evidence."
        ),
        "exp-20260617-023": (
            "Rejected SEC offering price absorption. This run uses filing-delay "
            "notice forms, not financing/prospectus forms."
        ),
        "exp-20260617-024": (
            "Rejected S-8 employee-equity absorption. This run is not an "
            "employee-equity or dilution-capacity event."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_025_nt_late_filing_absorption_scout.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _d10(value: Any) -> str:
    text = str(value or "")[:10]
    return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else ""


def _acceptance_after_close(value: Any) -> bool:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(text) < 14:
        return False
    try:
        hour = int(text[8:10])
        minute = int(text[10:12])
        second = int(text[12:14])
    except ValueError:
        return False
    return (hour, minute, second) >= (16, 0, 0)


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is not None:
        return _EVENT_INDEX_CACHE

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
            """
        ).fetchall()
    for ticker, cik in rows:
        try:
            ticker_ciks[str(ticker).upper()] = int(cik)
        except (TypeError, ValueError):
            stats["invalid_cik_rows"] += 1

    index: dict[str, list[dict[str, Any]]] = {}
    for ticker, cik in ticker_ciks.items():
        path = SUBMISSIONS_CACHE / f"CIK{cik:010d}.json"
        stats["warehouse_tickers_with_cik"] += 1
        if not path.exists():
            stats["missing_submissions_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_submissions_cache_file"] += 1
            continue
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form") or []
        filing_dates = recent.get("filingDate") or []
        acceptance_times = recent.get("acceptanceDateTime") or []
        accessions = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []
        events: list[dict[str, Any]] = []
        for i in range(min(len(forms), len(filing_dates))):
            form = str(forms[i] or "").upper()
            if form not in NT_FORMS:
                continue
            filing_date = _d10(filing_dates[i])
            if not filing_date:
                continue
            accession = str(accessions[i]) if i < len(accessions) else ""
            primary_doc = str(primary_docs[i]) if i < len(primary_docs) else ""
            acceptance = str(acceptance_times[i]) if i < len(acceptance_times) else ""
            events.append(
                {
                    "ticker": ticker,
                    "cik": f"{cik:010d}",
                    "form": form,
                    "filing_date": filing_date,
                    "accepted_after_close": _acceptance_after_close(acceptance),
                    "acceptance_datetime": acceptance,
                    "accession_number": accession,
                    "primary_document": primary_doc,
                    "form_weight": FORM_WEIGHTS.get(form, 0.40),
                }
            )
            stats[f"form_{form}"] += 1
        if events:
            events.sort(key=lambda row: (row["filing_date"], row["form"], row["accession_number"]))
            index[ticker] = events
            stats["tickers_with_nt_events"] += 1
            stats["nt_event_count"] += len(events)

    summary = {
        "submissions_cache": _repo_rel(SUBMISSIONS_CACHE),
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "nt_forms": sorted(NT_FORMS),
        **dict(stats),
    }
    _EVENT_INDEX_CACHE = (index, summary)
    return _EVENT_INDEX_CACHE


def _load_broad_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    index, _summary = _load_event_index()
    start = base.framework._parse_date(cfg["start"]) - timedelta(days=120)
    end = base.framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(index) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                f"from ohlcv where ticker in ({placeholders}) "
                "and date >= ? and date <= ? order by ticker, date"
            )
            params = [*chunk, base.framework._date_str(start), base.framework._date_str(end)]
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


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "sec_submissions_nt_10k_10q_forms_not_companyfacts",
    }


def _signal_date_for_event(event: dict[str, Any], dates: list[str]) -> str | None:
    filing_date = event["filing_date"]
    pos = (
        bisect.bisect_right(dates, filing_date)
        if event.get("accepted_after_close")
        else bisect.bisect_left(dates, filing_date)
    )
    if pos >= len(dates):
        return None
    signal_date = dates[pos]
    age = sum(1 for day in dates if filing_date <= day <= signal_date) - 1
    if age > MAX_EVENT_AGE_TRADING_DAYS:
        return None
    return signal_date


def _absorption_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = base.framework.shadow._series(snapshot, ticker)
    spy_rows = base.framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    if spy_idx is None or spy_idx < 60:
        return None
    close = base.framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = base.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = base.framework._daily_return(rows, idx)
    spy_signal_return = base.framework._daily_return(spy_rows, spy_idx)
    if signal_return is None or spy_signal_return is None:
        return None
    signal_excess_spy = float(signal_return) - float(spy_signal_return)
    if float(signal_return) < MIN_SIGNAL_RETURN:
        return None
    if signal_excess_spy < MIN_SIGNAL_EXCESS_SPY:
        return None
    close_location = base.framework._close_location(rows[idx])
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    volume_ratio = base.framework._volume_ratio(rows, idx)
    if volume_ratio is None or volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    realized_vol = base.framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20 = base.framework._ret(rows, idx, 20)
    spy_ret20 = base.framework._ret(spy_rows, spy_idx, 20)
    ret60 = base.framework._ret(rows, idx, 60)
    ret20_excess_spy = None if ret20 is None or spy_ret20 is None else float(ret20) - float(spy_ret20)
    if ret20_excess_spy is None or ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    return {
        "candidate_close": _round(close, 4),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_signal_excess_spy": _round(signal_excess_spy, 6),
        "candidate_ret20": _round(ret20, 6) if ret20 is not None else None,
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60": _round(ret60, 6) if ret60 is not None else None,
        "candidate_close_location": _round(close_location, 6),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = _signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan[f"form_{event['form']}"] += 1
            confirm = _absorption_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_absorption_or_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.75 * float(confirm["candidate_signal_excess_spy"])
                + 0.40 * float(confirm["candidate_close_location"])
                + 0.25 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                + 0.08 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
                + 0.18 * float(event["form_weight"])
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_NT_LATE_FILING_ABSORPTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_nt_form_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_submissions": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "nt_form": event["form"],
                    "nt_filing_date": event["filing_date"],
                    "nt_accepted_after_close": event["accepted_after_close"],
                    "nt_acceptance_datetime": event["acceptance_datetime"],
                    "nt_accession_number": event["accession_number"],
                    "nt_primary_document": event["primary_document"],
                    "nt_form_weight": event["form_weight"],
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["candidate_signal_excess_spy"] or 0.0),
            -float(row["candidate_close_location"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = scan["eligible_event_tickers"]
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "nt_forms": sorted(NT_FORMS),
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_nt_late_filing_absorption"
        if gate["passed"]
        else "rejected_sec_nt_late_filing_absorption_candidate_pool"
    )
    return gate


def _load_companyfacts_rows_stub(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    return []


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._load_window_snapshot = _load_broad_window_snapshot
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The SEC NT late-filing notice absorption source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    return (
        "The SEC NT late-filing notice absorption source did not clear Gate 4 "
        f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The fixed "
        "bundle tested NT 10-K/NT 10-Q late-filing notice forms plus signal-day "
        "SPY-relative price absorption. The result is not retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = _interpretation(payload)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_submissions_filing_delay_candidate_pool",
            "new_evidence_type": "sec_submissions_nt_10k_10q_forms_with_price_absorption",
            "nearby_prior_experiments": [
                "exp-20260617-020",
                "exp-20260617-022",
                "exp-20260617-023",
                "exp-20260617-024",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
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
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "nt_forms": sorted(NT_FORMS),
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "SEC NT late-filing events are read from EDGAR submissions cache recent "
        "filings for forms NT 10-K, NT 10-Q, NT 10-K/A, and NT 10-Q/A. The "
        "signal date is the filing date unless the SEC acceptance timestamp is "
        "after 16:00, in which case it is the next trading day. Candidates must "
        "show signal-day price absorption before next-open paper entry: "
        "non-negative daily return, return minus SPY >= 0.5%, close location >= "
        "0.56, volume ratio >= 0.75, realized vol <= 12%, ret20 excess vs SPY "
        ">= -5%, price >= $10, and ADV20 >= $50M. Paper entry is the next "
        "available open with entry slippage; exit is the close 10 trading days "
        "after the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["submissions_source"] = _repo_rel(SUBMISSIONS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "SEC submissions recent.form (NT 10-K/NT 10-Q)",
        "SEC submissions recent.filingDate",
        "SEC submissions recent.acceptanceDateTime",
        "SEC submissions recent.accessionNumber",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed NT late-filing absorption bundle fails, do not retry by "
        "sweeping NT form lists, signal excess, close-location, volume, "
        "volatility, ret20, price/ADV, event-age, top-N, hold days, cooldown, "
        "or notional on these frozen windows. A valid retry needs materially "
        "richer PIT delay economics such as explicit issuer reason, auditor/"
        "control language, late-period financial restatement linkage, or closed "
        "forward replacement-value observations."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping NT form lists, signal excess, close-"
            "location, volume, volatility, ret20, price/ADV, event-age, top-N, "
            "hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=sum(v for k, v in scan.items() if k.startswith("form_")),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC NT Late-Filing Absorption",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
