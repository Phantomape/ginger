"""exp-20260612-023: Form 144 sale-notice absorption scout.

Replay-only alpha search. This tests one candidate-pool policy bundle:
public-issuer Form 144 planned-sale notices from the local EDGAR form index are
admitted only when the issuer's signal-day price action absorbs the supply
notice. Qualified rows get a default-off next-open paper entry, fixed 10-day
hold, one trade per day, core-overlap exclusion, and same-ticker cooldown.

The data surface is new and has no shared daily helper, so a positive replay is
lead-only. No production path, shared policy, order, ranking, sizing, exit,
watchlist, LLM, or news behavior changes. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import sys
from bisect import bisect_left
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260612-023"
STEM = "form144_sale_notice_absorption"
TRIAL_FAMILY = "form144_sale_notice_absorption_candidate_pool"
TRIAL_VARIANT_ID = "form144_absorbed_top1_next_open_10d_v1"
CHANGED_VARIABLE = "form144_sale_notice_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_EVENTS_PATH = OUT_DIR / "form144_sale_notice_events.jsonl"
SEC_COMPANY_TICKERS = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
SEC_FORM_INDEX_DIR = REPO_ROOT / "data" / "cache" / "sec" / "form_index"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 20

MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 20_000_000.0
MIN_HISTORY_SESSIONS = 60
MIN_SIGNAL_RETURN = -0.004
MIN_RELATIVE_VS_SPY = 0.0
MIN_CLOSE_LOCATION = 0.52
MIN_VOLUME_RATIO_20D = 0.70
MAX_VOLUME_RATIO_20D = 4.00
MAX_RET5 = 0.12
MAX_REALIZED_VOL_20D = 0.12

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

FORM_LINE_RE = re.compile(
    r"^(?P<form>144)\s+"
    r"(?P<company>.+?)\s+"
    r"(?P<cik>\d{1,10})\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<file>edgar/data/\d+/\S+\.txt)\s*$"
)

ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
    "target_trade_count": 113,
}

FORM4_SALE_NEIGHBOR = {
    "experiment_id": "exp-20260611-026",
    "decision": "rejected_form4_sale_absorption_leadership_candidate_pool",
    "expected_value_score_delta_sum": -0.1340,
    "total_pnl_delta_sum": -1537.49,
}

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.16,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "form144_is_stale_or_negative_supply",
        "form4_sale_absorption_neighbor_failed",
        "thin_declared_universe_sample",
        "window_regression",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Mechanism: Form 144 is a free SEC planned-sale notice that can expose "
        "supply overhang before or during distribution. If same-day price, "
        "relative strength, close location, and liquidity absorb the notice, "
        "the stock may have real demand under known supply. Nearby history: "
        "Form 4 sale absorption failed, so this is only a scout because Form "
        "144 is an earlier planned-sale notice with broader coverage, not a "
        "completed-sale disclosure. Main disconfirmer: Form 144 may be stale, "
        "routine, or simply negative supply."
    ),
    "recorded_at": "2026-06-12T22:06:17+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "The Form 144 event archive is built from local EDGAR form-index files "
        "inside this experiment. No shared daily helper or production daily "
        "index fetcher exists yet, so a positive result is lead-only until the "
        "same event build, absorption gates, overlap exclusion, next-open "
        "paper entry, costs, hold, and cooldown are implemented in shared "
        "historical replay and daily default-off snapshots."
    ),
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
        "No production code changes. Positive replay would require a shared "
        "default-off helper plus daily EDGAR Form 144 snapshot parity before "
        "any accepted-alpha claim."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: Form 144 planned-sale notices that are absorbed by "
        "same-day price/liquidity may identify supply-overhang absorption. "
        "The fixed policy tests whether those candidates add next-open 10-day "
        "paper EV after liquidity, price, absorption, core-overlap, top-1/day, "
        "and cooldown guards."
    ),
    "2_history_check": {
        "exp-20260611-026": (
            "Form 4 sale absorption was rejected at -0.1340 EV and -$1,537.49. "
            "This is a nearby negative prior."
        ),
        "difference": (
            "Form 144 is a planned-sale notice and can arrive before completed "
            "Form 4 sale reporting. This experiment tests earlier supply "
            "overhang plus same-day absorption, not completed insider sales."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption is the closest positive "
            "supply/absorption comparator at +0.5286 EV and +$10,432.91."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no EV/PnL window regression, target trades "
        "cover all three windows, survival/drawdown/concentration pass, and "
        "the accepted distribution-day absorption comparator is beaten. Even "
        "if positive, replay-only status is not accepted production alpha."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260612_023_form144_sale_notice_absorption.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_cik_ticker_map() -> dict[int, set[str]]:
    raw = json.loads(SEC_COMPANY_TICKERS.read_text(encoding="utf-8"))
    by_cik: dict[int, set[str]] = defaultdict(set)
    values = raw.values() if isinstance(raw, dict) else raw
    for row in values:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        try:
            cik = int(row.get("cik_str"))
        except (TypeError, ValueError):
            continue
        by_cik[cik].add(ticker)
    return by_cik


def _parse_form_index_line(line: str, source_index_file: str) -> dict[str, Any] | None:
    if not line.startswith("144"):
        return None
    match = FORM_LINE_RE.match(line.rstrip())
    if not match:
        return None
    file_name = match.group("file")
    return {
        "form_type": match.group("form"),
        "company_name": " ".join(match.group("company").split()),
        "cik": int(match.group("cik")),
        "filing_date": match.group("date"),
        "file_name": file_name,
        "accession": Path(file_name).stem,
        "source_index_file": source_index_file,
    }


def _build_sec_event_archive() -> dict[str, Any]:
    by_cik = _load_cik_ticker_map()
    rows_by_accession: dict[str, list[dict[str, Any]]] = defaultdict(list)
    index_files = sorted(SEC_FORM_INDEX_DIR.glob("form_*.idx"))
    raw_144_rows = 0
    malformed_144_rows = 0
    for path in index_files:
        source = _repo_rel(path)
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.startswith("144"):
                    continue
                raw_144_rows += 1
                parsed = _parse_form_index_line(line, source)
                if parsed is None:
                    malformed_144_rows += 1
                    continue
                ticker_set = by_cik.get(int(parsed["cik"])) or set()
                if not ticker_set:
                    continue
                for ticker in sorted(ticker_set):
                    rows_by_accession[parsed["accession"]].append(
                        {**parsed, "ticker": ticker}
                    )

    events: list[dict[str, Any]] = []
    ambiguous_accessions = 0
    for accession, rows in rows_by_accession.items():
        tickers = sorted({str(row["ticker"]).upper() for row in rows})
        if len(tickers) != 1:
            ambiguous_accessions += 1
            continue
        row = sorted(rows, key=lambda item: (item["filing_date"], item["cik"]))[0]
        events.append(
            {
                "filing_date": row["filing_date"],
                "cik": row["cik"],
                "ticker": tickers[0],
                "accession": accession,
                "form_type": row["form_type"],
                "company_name": row["company_name"],
                "source_index_file": row["source_index_file"],
                "event_rule": "form144_public_issuer_sale_notice",
                "ticker_mapping_source": _repo_rel(SEC_COMPANY_TICKERS),
            }
        )

    events.sort(
        key=lambda row: (
            str(row["filing_date"]),
            str(row["ticker"]),
            str(row["accession"]),
        )
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    framework._write_text(
        SEC_EVENTS_PATH,
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in events
        ),
    )
    return {
        "source_form_index_dir": _repo_rel(SEC_FORM_INDEX_DIR),
        "source_company_ticker_map": _repo_rel(SEC_COMPANY_TICKERS),
        "source_index_file_count": len(index_files),
        "raw_form144_rows": raw_144_rows,
        "malformed_form144_rows": malformed_144_rows,
        "public_single_ticker_accession_count": len(events),
        "ambiguous_public_ticker_accessions_dropped": ambiguous_accessions,
        "event_ticker_count": len({row["ticker"] for row in events}),
        "event_archive": _repo_rel(SEC_EVENTS_PATH),
    }


def _load_sec_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not SEC_EVENTS_PATH.exists():
        return events
    with SEC_EVENTS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper()
            filing_date = str(row.get("filing_date") or "")[:10]
            if not ticker or not filing_date:
                continue
            events.append(
                {
                    "ticker": ticker,
                    "filing_date": filing_date,
                    "cik": row.get("cik"),
                    "accession_number": row.get("accession"),
                    "form_type": row.get("form_type"),
                    "company_name": row.get("company_name"),
                    "source_index_file": row.get("source_index_file"),
                }
            )
    events.sort(key=lambda row: (row["filing_date"], row["ticker"], row["accession_number"]))
    return events


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < MIN_HISTORY_SESSIONS:
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
    close_location = framework._close_location(row)
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    realized_vol20 = framework._realized_vol(rows, idx)
    required = [signal_return, spy_return, close_location, volume_ratio, ret5, ret20, realized_vol20]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert spy_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert realized_vol20 is not None
    relative_vs_spy = signal_return - spy_return
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_RELATIVE_VS_SPY:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    if ret5 > MAX_RET5:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None
    sector_meta = sector_entries[ticker]
    score = (
        1.8 * relative_vs_spy
        + 1.1 * signal_return
        + 0.60 * close_location
        + 0.20 * min(volume_ratio, 3.0)
        + 0.05 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.25 * realized_vol20
    )
    return {
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source": "FORM144_SALE_NOTICE_ABSORPTION_PAPER",
        "strategy": TRIAL_FAMILY,
        "candidate_score": round(score, 6),
        "candidate_filing_date": event.get("filing_date"),
        "candidate_accession": event.get("accession_number"),
        "candidate_form_type": event.get("form_type"),
        "candidate_company_name": event.get("company_name"),
        "candidate_event_lag_sessions": event.get("event_lag_sessions"),
        "candidate_signal_return": framework._round(signal_return, 6),
        "candidate_relative_vs_spy": framework._round(relative_vs_spy, 6),
        "candidate_ret5": framework._round(ret5, 6),
        "candidate_ret20": framework._round(ret20, 6),
        "candidate_close_location": framework._round(close_location, 6),
        "candidate_volume_ratio_20d": framework._round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_realized_vol_20d": framework._round(realized_vol20, 6),
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
        "decision_id": f"FORM144_ABSORBED:{RULE_VERSION}:{signal_date}:{ticker}",
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row.get("candidate_score") or 0.0),
        -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
    )


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    trading_dates = framework.shadow._trading_dates(snapshot)
    dates_in_window = [
        date_value
        for date_value in trading_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    events_by_signal_date: dict[str, list[dict[str, Any]]] = {}
    scan = {
        "scanned_trading_days": len(dates_in_window),
        "event_signal_days": 0,
        "days_with_raw_form144_candidates": 0,
        "raw_form144_candidates": 0,
        "events_mapped_to_window_signal_days": 0,
        "events_without_signal_ohlcv_row": 0,
        "events_outside_declared_universe": 0,
        "same_ticker_core_overlap_rejections": 0,
    }
    for event in events:
        ticker = str(event["ticker"]).upper()
        filing_date = str(event["filing_date"])[:10]
        pos = bisect_left(trading_dates, filing_date)
        if pos >= len(trading_dates):
            continue
        signal_date = trading_dates[pos]
        if not (str(cfg["start"]) <= signal_date <= str(cfg["end"])):
            continue
        if ticker not in sector_entries:
            scan["events_outside_declared_universe"] += 1
            continue
        if indices.get(ticker, {}).get(signal_date) is None:
            scan["events_without_signal_ohlcv_row"] += 1
            continue
        events_by_signal_date.setdefault(signal_date, []).append(
            {**event, "event_lag_sessions": 0 if filing_date == signal_date else 1}
        )
        scan["events_mapped_to_window_signal_days"] += 1

    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    for signal_date in dates_in_window:
        day_events = events_by_signal_date.get(signal_date) or []
        if not day_events:
            continue
        scan["event_signal_days"] += 1
        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {str(entry.get("ticker") or "").upper() for entry in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for event in sorted(day_events, key=lambda row: (str(row["ticker"]), str(row["accession_number"]))):
            ticker = str(event["ticker"]).upper()
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                event=event,
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
        scan["days_with_raw_form144_candidates"] += 1
        scan["raw_form144_candidates"] += len(day_rows)
        top = day_rows[0]
        contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_filing_date": top["candidate_filing_date"],
                "top_candidate_signal_return": top["candidate_signal_return"],
                "top_candidate_relative_vs_spy": top["candidate_relative_vs_spy"],
            }
        )
    candidates.sort(key=lambda row: (row["date"], *_candidate_sort_key(row)))
    scan["rule_version"] = RULE_VERSION
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


def _aggregate_window_rows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return framework.sleeve._aggregate(rows)


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
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("survival_floor_breached")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        < ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_distribution_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        < ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_distribution_pnl_not_beaten")
    return {
        "passed": not failed,
        "decision": "positive_replay_lead_not_promoted" if not failed else "rejected_form144_sale_notice_absorption_candidate_pool",
        "failed_reasons": failed,
        "aggregate_ev_delta": framework._round(aggregate["expected_value_score_delta_sum"], 6),
        "aggregate_pnl_delta": framework._round(aggregate["total_pnl_delta_sum"], 2),
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "max_drawdown_worse": framework._round(aggregate["max_drawdown_delta_max"], 6),
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "minimum_core_survival_rate": framework._round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "nearby_form4_sale_neighbor": FORM4_SALE_NEIGHBOR,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    event_archive_summary = _build_sec_event_archive()
    events = _load_sec_events()
    sector_entries = framework._load_sector_entries()
    eligible = set(sector_entries) | {str(row["ticker"]).upper() for row in events}

    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    raw_candidate_counts: OrderedDict[str, int] = OrderedDict()
    contexts_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    context_scan_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()

    universe = sorted(framework.get_universe())
    for label, cfg in framework.WINDOWS.items():
        snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=eligible)
        before_result = framework.shadow._run_baseline(universe, cfg)
        candidates, contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
            events=events,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        before = framework.overlay_helper._metrics(before_result)
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
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "window_start": cfg["start"],
            "window_end": cfg["end"],
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "event_signal_day_count": scan.get("event_signal_days", 0),
            "candidate_day_count": scan.get("days_with_raw_form144_candidates", 0),
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
        "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
    }
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    interpretation = (
        "The Form 144 absorbed-sale-notice source cleared numeric replay gates, "
        "but remains lead-only because no shared daily helper or production "
        "EDGAR daily-index fetcher was promoted."
        if passed
        else (
            "The Form 144 absorbed-sale-notice source was rejected under the "
            "standard three-window protocol and accepted distribution-day "
            "absorption comparator."
        )
    )
    why = (
        "The fixed Form 144 bundle passed numerically, but is not accepted alpha "
        "because shared replay/daily parity and forward replacement-value rows "
        "are required before production-visible promotion."
        if passed
        else (
            "The fixed Form 144 bundle failed Gate 4. The likely reason is that "
            "planned-sale notices are routine or stale supply signals; same-day "
            "absorption did not add enough fresh demand evidence beyond generic "
            "leadership and the accepted distribution absorption comparator."
        )
    )
    gate2_open_positions = framework.sleeve._audit_open_positions()
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
        "mechanism_family": "production_visible_free_sec_sale_notice_candidate_pool",
        "nearby_prior_experiments": ["exp-20260611-026", "exp-20260611-007"],
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "pit_sec_form144_sale_notice_archive",
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
                "experiment-local SEC Form 144 sale-notice absorption paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sec_event_source": _repo_rel(SEC_EVENTS_PATH),
            "sec_event_provenance": (
                "EDGAR quarterly form indexes 2024Q4-2026Q2; Form 144 rows "
                "mapped to exactly one public issuer ticker through "
                "data/reference/sec_company_tickers.json; ambiguous accessions "
                "dropped."
            ),
            "replay_llm": False,
            "replay_news": False,
            "execution_model": (
                "Signal uses only the PIT filing date from the EDGAR form index "
                "and signal-date OHLCV after the close. Signal day is the first "
                "trading day on or after filing date. Entry is next open; exit "
                "is close 10 trading days after signal with existing paper costs."
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
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "same_day_rank_rule": "absorption_score_then_liquidity",
            "same_ticker_core_overlap_excluded": True,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "event_archive_summary": event_archive_summary,
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
                "SEC Form 144 event ticker/filing_date/accession/form_type",
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
                "No core entry filter is added. The Form 144 source is additive "
                "default-off paper; core signals and survival are unchanged."
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
        "nearby_form4_sale_neighbor": FORM4_SALE_NEIGHBOR,
        "interpretation": interpretation,
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "A retry needs materially richer Form 144 semantics, such as parsed "
            "planned-sale size, insider role, sale percentage, or closed forward "
            "replacement-value rows from a shared daily helper. Do not sweep "
            "liquidity, price, absorption, top-N, hold-day, cooldown, or "
            "notional thresholds on the same frozen windows."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping liquidity, price, signal-return, "
                "relative-strength, close-location, volume-ratio, top-N, "
                "hold-day, cooldown, or notional thresholds, and do not simply "
                "merge this with the rejected Form 4 sale absorption lane."
            ),
            "new_evidence_required": (
                "Parsed Form 144 document fields, holder role, planned-sale "
                "size as percent of float, a broader PIT universe, or forward "
                "replacement-value rows from a shared helper."
            ),
        },
        "registry_persistence_note": (
            "persist_self_registered_result is the intended registry/ticket "
            "path. On this Windows checkout, atomic ticket replacement can be "
            "denied by ACL state; the runner falls back to a non-atomic update "
            "of this experiment's ticket while preserving the artifact, log, "
            "card, manifest, and JSONL record."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(SEC_EVENTS_PATH),
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
                sig_days=scan.get("event_signal_days", 0),
                cand_days=scan.get("days_with_raw_form144_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    archive = payload["event_archive_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form 144 Sale-Notice Absorption",
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
            "## Event Archive",
            "",
            "- Public single-ticker Form 144 accessions: `{}`".format(
                archive["public_single_ticker_accession_count"]
            ),
            "- Tickers: `{}`".format(archive["event_ticker_count"]),
            "- Ambiguous accessions dropped: `{}`".format(
                archive["ambiguous_public_ticker_accessions_dropped"]
            ),
            "",
            "## Gate 1-4",
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
            "- Accepted distribution comparator EV/PnL: `{}` / `${:,.2f}`".format(
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
        "change_type": payload["change_type"],
        "implementation_mode": "private_replay_scout",
        "causal_components": [
            "SEC form-index Form 144 event archive",
            "issuer ticker mapping",
            "same-day absorption gates",
            "same-ticker core overlap exclusion",
            "next-open paper entry",
            "10d exit",
            "costs",
            "three-window Gate 1-4",
        ],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": f"{_repo_rel(OUT_JSON)}#before_metrics",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "nearby_form4_sale_neighbor": FORM4_SALE_NEIGHBOR,
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
                "event_signal_day_count": payload["context_scan_by_window"][label].get(
                    "event_signal_days"
                ),
                "candidate_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_form144_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "event_archive_summary": payload["event_archive_summary"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": None
        if payload["gate4"]["passed"]
        else payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "registry_persistence_note": payload["registry_persistence_note"],
        "related_files": payload["related_files"],
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
    try:
        persist_self_registered_result(
            REGISTRY_JSON,
            experiment_id=EXPERIMENT_ID,
            lane="alpha_search",
            prediction=PREDICTION,
            result=result,
            status=payload["status"],
            fields=fields,
        )
    except PermissionError as exc:
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
        ticket.update(
            {
                **fields,
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "result": result,
                "registry_persistence_error": repr(exc),
                "registry_persistence_note": payload["registry_persistence_note"],
            }
        )
        framework._write_json(TICKET_JSON, ticket)


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
            _repo_rel(SEC_EVENTS_PATH),
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
            _repo_rel(SEC_EVENTS_PATH): framework._sha256(SEC_EVENTS_PATH),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
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
