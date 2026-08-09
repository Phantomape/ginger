"""Shared default-off TSA weekly checkpoint-throughput paper policy.

The module is deliberately pure and source-injected.  Historical replay and
the daily snapshot both use the same source normaliser, event evaluator, and
fixed-basket candidate builder.  No function fetches data or creates orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse


SLEEVE_NAME = "TSA_CHECKPOINT_THROUGHPUT_PAPER"
RULE_VERSION = "tsa_weekly_positive_yoy_acceleration_travel_basket_5d_v1"
SOURCE_SCHEMA_VERSION = "tsa_checkpoint_weekly_record_v1"
DAILY_SNAPSHOT_SCHEMA_VERSION = "tsa_checkpoint_throughput_daily_snapshot_v1"

TRAVEL_BASKET_V1 = (
    "AAL",
    "ABNB",
    "ALK",
    "BKNG",
    "CPA",
    "DAL",
    "EXPE",
    "HLT",
    "LUV",
    "MAR",
    "SKYW",
    "TNL",
    "UAL",
    "VAC",
)
TRADE_ENABLED = False
LEG_NOTIONAL_USD = 1_000.0
EVENT_NOTIONAL_USD = 14_000.0
HOLD_SESSIONS = 5
COOLDOWN_SESSIONS = 0
ROUND_TRIP_COST_PCT = 0.0035
ATR_PERIOD = 14
ATR_TARGET_MULTIPLE = 3.5

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_SHA_FIELDS = ("source_sha256", "raw_sha256", "report_sha256")
_TOTAL_FIELDS = (
    "weekly_total",
    "national_weekly_total",
    "current_week_total",
    "throughput_total",
)
_COMPARISON_TOTAL_FIELDS = (
    "prior_year_weekly_total",
    "comparison_weekly_total",
    "year_ago_weekly_total",
)
_COMPARISON_DATE_FIELDS = (
    "comparison_week_ending",
    "prior_year_week_ending",
    "year_ago_week_ending",
)


class TSAContractError(ValueError):
    """Raised when source or price inputs violate the locked contract."""


def _iso_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _finite_positive(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _first_present(source: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field in fields:
        if field in source and source.get(field) is not None:
            return source.get(field)
    return None


def _payload_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _official_tsa_url(value: Any) -> str | None:
    text = str(value or "").strip()
    parsed = urlparse(text)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "tsa.gov" or hostname.endswith(".tsa.gov")
    ):
        return None
    return text


def _raw_availability_date(record: Mapping[str, Any]) -> str | None:
    report_date = _iso_date(
        record.get("report_date")
        or record.get("publication_date")
        or record.get("knowledge_date")
    )
    knowledge_date = _iso_date(record.get("knowledge_date"))
    known = [day for day in (report_date, knowledge_date) if day is not None]
    return max(known) if known else None


def _normalise_source_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise TSAContractError("source_record_not_mapping")
    row = dict(raw)
    is_report = bool(row.get("is_report", True))
    week_ending = _iso_date(
        row.get("week_ending") or row.get("week_end") or row.get("period_end")
    )
    if week_ending is None:
        raise TSAContractError("week_ending_missing_or_invalid")

    report_date = _iso_date(
        row.get("report_date")
        or row.get("publication_date")
        or row.get("knowledge_date")
    )
    knowledge_date = _iso_date(row.get("knowledge_date"))
    if is_report and report_date is None:
        raise TSAContractError(f"report_date_missing:{week_ending}")
    if report_date is None:
        report_date = week_ending
    if knowledge_date is None:
        knowledge_date = report_date
    availability_date = max(report_date, knowledge_date)
    if week_ending > availability_date:
        raise TSAContractError(f"week_ending_after_availability:{week_ending}")

    weekly_total = _finite_positive(_first_present(row, _TOTAL_FIELDS))
    if weekly_total is None:
        raise TSAContractError(f"weekly_total_missing_or_invalid:{week_ending}")

    source_url = _official_tsa_url(row.get("source_url"))
    if source_url is None:
        raise TSAContractError(f"official_source_url_missing_or_invalid:{week_ending}")
    source_sha256 = str(_first_present(row, _SOURCE_SHA_FIELDS) or "").lower()
    if _SHA256_RE.fullmatch(source_sha256) is None:
        raise TSAContractError(f"source_sha256_missing_or_invalid:{week_ending}")

    comparison_date_raw = _first_present(row, _COMPARISON_DATE_FIELDS)
    comparison_total_raw = _first_present(row, _COMPARISON_TOTAL_FIELDS)
    comparison_week_ending = _iso_date(comparison_date_raw)
    comparison_weekly_total = _finite_positive(comparison_total_raw)
    if (comparison_date_raw is None) != (comparison_total_raw is None):
        raise TSAContractError(f"partial_embedded_comparison:{week_ending}")
    if comparison_date_raw is not None:
        expected = (date.fromisoformat(week_ending) - timedelta(days=364)).isoformat()
        if comparison_week_ending != expected:
            raise TSAContractError(f"comparison_not_exact_364_days:{week_ending}")
        if comparison_weekly_total is None:
            raise TSAContractError(f"comparison_total_invalid:{week_ending}")

    canonical = {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "week_ending": week_ending,
        "report_date": report_date,
        "knowledge_date": knowledge_date,
        "availability_date": availability_date,
        "weekly_total": weekly_total,
        "comparison_week_ending": comparison_week_ending,
        "comparison_weekly_total": comparison_weekly_total,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "is_report": is_report,
    }
    canonical["source_record_sha256"] = _payload_sha256(canonical)
    return canonical


def normalise_tsa_checkpoint_weekly_records(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and canonicalise immutable TSA weekly source records."""

    normalised = [_normalise_source_record(record) for record in records]
    normalised.sort(key=lambda row: (row["week_ending"], row["availability_date"]))
    seen_weeks: set[str] = set()
    for row in normalised:
        week = str(row["week_ending"])
        if week in seen_weeks:
            raise TSAContractError(f"duplicate_week_ending:{week}")
        seen_weeks.add(week)
    return normalised


def _comparison_for_record(
    record: Mapping[str, Any],
    *,
    by_week: Mapping[str, Mapping[str, Any]],
) -> tuple[float | None, str | None, str | None]:
    target_week = (
        date.fromisoformat(str(record["week_ending"])) - timedelta(days=364)
    ).isoformat()
    anchor = by_week.get(target_week)
    if anchor is not None:
        return (
            float(anchor["weekly_total"]),
            target_week,
            str(anchor["source_record_sha256"]),
        )
    if record.get("comparison_week_ending") == target_week:
        total = _finite_positive(record.get("comparison_weekly_total"))
        if total is not None:
            return total, target_week, str(record["source_record_sha256"])
    return None, target_week, None


def evaluate_tsa_checkpoint_throughput_events(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Evaluate the strict positive-YoY and positive-acceleration rule."""

    raw_records = list(records)
    try:
        canonical = normalise_tsa_checkpoint_weekly_records(raw_records)
    except TSAContractError as error:
        return [], {
            "measurement_valid": False,
            "source_contract_error_count": 1,
            "source_contract_errors": [str(error)],
            "source_record_count": len(raw_records),
            "report_record_count": 0,
            "trigger_count": 0,
        }

    by_week = {str(row["week_ending"]): row for row in canonical}
    reports = [row for row in canonical if row["is_report"]]
    reports_by_week = {str(row["week_ending"]): row for row in reports}

    yoy_by_week: dict[str, dict[str, Any]] = {}
    for row in reports:
        comparison_total, comparison_week, comparison_source_sha = (
            _comparison_for_record(row, by_week=by_week)
        )
        yoy = (
            float(row["weekly_total"]) / comparison_total - 1.0
            if comparison_total is not None
            else None
        )
        yoy_by_week[str(row["week_ending"])] = {
            "comparison_week_ending": comparison_week,
            "comparison_weekly_total": comparison_total,
            "comparison_source_record_sha256": comparison_source_sha,
            "yoy_growth": yoy,
        }

    evaluations: list[dict[str, Any]] = []
    filter_totals: Counter[str] = Counter()
    for row in reports:
        week = str(row["week_ending"])
        current = yoy_by_week[week]
        prior_week = (date.fromisoformat(week) - timedelta(days=7)).isoformat()
        prior_report = reports_by_week.get(prior_week)
        prior = yoy_by_week.get(prior_week)
        current_yoy = current["yoy_growth"]
        prior_yoy = prior.get("yoy_growth") if prior is not None else None
        consecutive = bool(
            prior_report is not None
            and str(prior_report["availability_date"]) < str(row["availability_date"])
        )
        acceleration = (
            float(current_yoy) - float(prior_yoy)
            if current_yoy is not None and prior_yoy is not None and consecutive
            else None
        )
        event_ready = current_yoy is not None and acceleration is not None
        yoy_positive = bool(event_ready and float(current_yoy) > 0.0)
        acceleration_positive = bool(event_ready and float(acceleration) > 0.0)
        triggered = bool(event_ready and yoy_positive and acceleration_positive)
        if current_yoy is None:
            filter_reason = "missing_exact_364_day_comparator"
        elif prior_report is None or not consecutive:
            filter_reason = "missing_preceding_report_week"
        elif prior_yoy is None:
            filter_reason = "preceding_report_missing_364_day_comparator"
        elif not yoy_positive:
            filter_reason = "weekly_yoy_not_strictly_positive"
        elif not acceleration_positive:
            filter_reason = "weekly_yoy_acceleration_not_strictly_positive"
        else:
            filter_reason = None
        if filter_reason:
            filter_totals[filter_reason] += 1
        evaluations.append(
            {
                **row,
                **current,
                "prior_report_week_ending": prior_week,
                "prior_report_yoy_growth": prior_yoy,
                "yoy_acceleration": acceleration,
                "event_ready": event_ready,
                "yoy_positive": yoy_positive,
                "acceleration_positive": acceleration_positive,
                "triggered": triggered,
                "filter_reason": filter_reason,
                "decision_id": (
                    f"tsa_checkpoint:{RULE_VERSION}:{row['week_ending']}:"
                    f"{row['availability_date']}"
                ),
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
            }
        )

    return evaluations, {
        "measurement_valid": True,
        "source_contract_error_count": 0,
        "source_contract_errors": [],
        "source_record_count": len(canonical),
        "report_record_count": len(reports),
        "trigger_count": sum(bool(row["triggered"]) for row in evaluations),
        "filter_totals": dict(sorted(filter_totals.items())),
        "canonical_records_sha256": _payload_sha256(canonical),
    }


def _normalise_bar_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for raw in rows or []:
        if not isinstance(raw, Mapping):
            continue
        day = _iso_date(raw.get("date") or raw.get("Date"))
        if day is None:
            continue
        if day in by_date:
            raise TSAContractError(f"duplicate_ohlcv_date:{day}")
        values = {}
        for field in ("open", "high", "low", "close"):
            value = _finite_positive(
                raw.get(field) if field in raw else raw.get(field.title())
            )
            values[field] = value
        by_date[day] = {"date": day, **values}
    return [by_date[day] for day in sorted(by_date)]


def _normalise_trading_dates(values: Iterable[Any]) -> list[str]:
    dates: set[str] = set()
    for raw in values or []:
        value = raw
        if isinstance(raw, Mapping):
            if raw.get("is_regular_session") is False:
                continue
            session_type = str(raw.get("session_type") or "").strip().lower()
            if session_type and session_type not in {"regular", "regular_session"}:
                continue
            value = raw.get("date") or raw.get("session_date")
        day = _iso_date(value)
        if day is None:
            raise TSAContractError("invalid_trading_session_date")
        if date.fromisoformat(day).weekday() >= 5:
            raise TSAContractError(f"weekend_regular_session:{day}")
        dates.add(day)
    return sorted(dates)


def _prepare_market_inputs(
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    trading_dates: Iterable[Any] | None,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    bars = {
        str(ticker).upper(): _normalise_bar_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if trading_dates is not None:
        calendar = _normalise_trading_dates(trading_dates)
    else:
        calendar = [row["date"] for row in bars.get("SPY", [])]
        calendar = _normalise_trading_dates(calendar)
    return bars, calendar


def _strict_next_session(day: str, calendar: Sequence[str]) -> str | None:
    return next((candidate for candidate in calendar if candidate > day), None)


def _atr14_before_entry(
    ticker_rows: Sequence[Mapping[str, Any]],
    *,
    calendar: Sequence[str],
    entry_position: int,
) -> tuple[float | None, str | None]:
    if entry_position < ATR_PERIOD:
        return None, "insufficient_prior_14_sessions"
    by_date = {str(row["date"]): row for row in ticker_rows}
    atr_dates = list(calendar[entry_position - ATR_PERIOD : entry_position])
    true_ranges: list[float] = []
    previous_close: float | None = None
    if entry_position > ATR_PERIOD:
        previous_day = calendar[entry_position - ATR_PERIOD - 1]
        previous = by_date.get(previous_day)
        previous_close = (
            _finite_positive(previous.get("close")) if previous is not None else None
        )
    for index, day in enumerate(atr_dates):
        row = by_date.get(day)
        if row is None:
            return None, f"missing_atr_bar:{day}"
        high = _finite_positive(row.get("high"))
        low = _finite_positive(row.get("low"))
        close = _finite_positive(row.get("close"))
        if high is None or low is None or close is None or high < low:
            return None, f"invalid_atr_bar:{day}"
        if index == 0 and previous_close is None:
            previous_close = close
        assert previous_close is not None
        true_ranges.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
        previous_close = close
    if len(true_ranges) != ATR_PERIOD:
        return None, "insufficient_prior_14_sessions"
    atr = sum(true_ranges) / ATR_PERIOD
    return (atr, None) if math.isfinite(atr) and atr > 0 else (None, "invalid_atr14")


def _build_event_legs(
    *,
    entry_date: str,
    bars: Mapping[str, Sequence[Mapping[str, Any]]],
    calendar: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    entry_position = calendar.index(entry_date)
    legs: list[dict[str, Any]] = []
    misses: list[dict[str, str]] = []
    for ticker in TRAVEL_BASKET_V1:
        rows = bars.get(ticker) or []
        by_date = {str(row["date"]): row for row in rows}
        entry_row = by_date.get(entry_date)
        entry_open = (
            _finite_positive(entry_row.get("open")) if entry_row is not None else None
        )
        if entry_open is None:
            misses.append({"ticker": ticker, "reason": "missing_exact_entry_open"})
            continue
        atr14, atr_error = _atr14_before_entry(
            rows, calendar=calendar, entry_position=entry_position
        )
        if atr14 is None:
            misses.append({"ticker": ticker, "reason": str(atr_error)})
            continue
        legs.append(
            {
                "ticker": ticker,
                "entry_date": entry_date,
                "entry_price": round(entry_open, 4),
                "entry_open_price": round(entry_open, 4),
                "atr14": round(atr14, 8),
                "target_price": round(
                    entry_open + ATR_TARGET_MULTIPLE * atr14, 4
                ),
                "target_price_role": (
                    "signal_contract_ATR_metadata_only; "
                    "fixed_5_session_exit_controls_realized_close"
                ),
                "paper_notional_usd": LEG_NOTIONAL_USD,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    if misses or len(legs) != len(TRAVEL_BASKET_V1):
        return [], misses or [{"ticker": "*", "reason": "fixed_basket_incomplete"}]
    return legs, []


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }


def build_tsa_checkpoint_throughput_candidates(
    *,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str | None = None,
    end: str | None = None,
    trading_dates: Iterable[Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build strict all-or-none 14-leg event candidates."""

    start_iso = _iso_date(start) if start is not None else None
    end_iso = _iso_date(end) if end is not None else None
    if start is not None and start_iso is None:
        raise ValueError(f"invalid start: {start!r}")
    if end is not None and end_iso is None:
        raise ValueError(f"invalid end: {end!r}")
    evaluations, source_audit = evaluate_tsa_checkpoint_throughput_events(records)
    if not source_audit["measurement_valid"]:
        return [], {
            **source_audit,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "selected_event_count": 0,
            "selected_leg_count": 0,
            "reject_totals": {"source_contract_invalid": 1},
            "pending_events": [],
            "missed_events": [],
            "production_impact": _production_impact(),
        }

    try:
        bars, calendar = _prepare_market_inputs(ohlcv_by_ticker, trading_dates)
    except TSAContractError as error:
        return [], {
            **source_audit,
            "measurement_valid": False,
            "market_contract_errors": [str(error)],
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "selected_event_count": 0,
            "selected_leg_count": 0,
            "reject_totals": {"market_contract_invalid": 1},
            "pending_events": [],
            "missed_events": [],
            "production_impact": _production_impact(),
        }
    rejects: Counter[str] = Counter()
    generated = 0
    selected: list[dict[str, Any]] = []
    pending_events: list[dict[str, Any]] = []
    missed_events: list[dict[str, Any]] = []

    for event in evaluations:
        intended_entry_date = _strict_next_session(
            str(event["report_date"]), calendar
        )
        first_available_entry_date = _strict_next_session(
            str(event["availability_date"]), calendar
        )
        opportunity_date = intended_entry_date or str(event["report_date"])
        in_window = (start_iso is None or opportunity_date >= start_iso) and (
            end_iso is None or opportunity_date <= end_iso
        )
        if not in_window:
            continue
        generated += 1
        if not event["triggered"]:
            rejects[str(event.get("filter_reason") or "not_triggered")] += 1
            continue
        if intended_entry_date is None:
            pending = {
                **event,
                "intended_entry_date": None,
                "first_available_entry_date": first_available_entry_date,
                "status": "pending_intended_next_regular_session",
                "paper_status": "pending",
                "trade_enabled": False,
            }
            pending_events.append(pending)
            rejects["pending_intended_next_regular_session"] += 1
            continue
        availability_is_late = (
            first_available_entry_date is not None
            and first_available_entry_date > intended_entry_date
        ) or (
            first_available_entry_date is None
            and str(event["availability_date"]) >= intended_entry_date
        )
        if availability_is_late:
            missed = {
                **event,
                "entry_date": None,
                "intended_entry_date": intended_entry_date,
                "first_available_entry_date": first_available_entry_date,
                "late_discovery": True,
                "status": "missed_fail_closed_late_discovery",
                "paper_status": "missed",
                "missed_reason": (
                    "source_knowledge_not_available_by_intended_entry_open"
                ),
                "trade_enabled": False,
            }
            missed_events.append(missed)
            rejects["missed_fail_closed_late_discovery"] += 1
            continue
        if first_available_entry_date != intended_entry_date:
            pending = {
                **event,
                "intended_entry_date": intended_entry_date,
                "first_available_entry_date": first_available_entry_date,
                "status": "pending_source_availability_session",
                "paper_status": "pending",
                "trade_enabled": False,
            }
            pending_events.append(pending)
            rejects["pending_source_availability_session"] += 1
            continue
        entry_date = intended_entry_date
        legs, misses = _build_event_legs(
            entry_date=entry_date, bars=bars, calendar=calendar
        )
        if misses:
            missed = {
                **event,
                "entry_date": entry_date,
                "status": "missed_fail_closed_fixed_basket",
                "paper_status": "missed",
                "missing_legs": misses,
                "trade_enabled": False,
            }
            missed_events.append(missed)
            rejects["fixed_basket_entry_or_atr_incomplete"] += 1
            continue
        selected.append(
            {
                **event,
                "signal_date": event["availability_date"],
                "entry_date": entry_date,
                "intended_entry_date": intended_entry_date,
                "first_available_entry_date": first_available_entry_date,
                "late_discovery": False,
                "entry_semantics": (
                    "first_regular_session_open_strictly_after_report_date; "
                    "knowledge_must_be_available_by_that_session"
                ),
                "legs": legs,
                "eligible_tickers": list(TRAVEL_BASKET_V1),
                "eligible_leg_count": len(legs),
                "event_notional_usd": EVENT_NOTIONAL_USD,
                "paper_notional_usd": EVENT_NOTIONAL_USD,
                "hold_sessions": HOLD_SESSIONS,
                "cooldown_sessions": COOLDOWN_SESSIONS,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "exit_semantics": "fifth_regular_session_close_no_early_target",
                "paper_status": "candidate",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    survived = len(selected)
    return selected, {
        **source_audit,
        "measurement_valid": True,
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else 0.0,
        "selected_event_count": survived,
        "selected_leg_count": survived * len(TRAVEL_BASKET_V1),
        "reject_totals": dict(sorted(rejects.items())),
        "pending_events": pending_events,
        "missed_events": missed_events,
        "production_impact": _production_impact(),
    }


def _settle_candidate(
    candidate: Mapping[str, Any],
    *,
    bars: Mapping[str, Sequence[Mapping[str, Any]]],
    calendar: Sequence[str],
    end: str,
) -> tuple[str, dict[str, Any]]:
    entry_date = str(candidate["entry_date"])
    entry_position = calendar.index(entry_date)
    exit_position = entry_position + HOLD_SESSIONS - 1
    if exit_position >= len(calendar) or calendar[exit_position] > end:
        return "open", {
            **candidate,
            "status": "open_incomplete_5_session_horizon",
            "paper_status": "open",
            "scheduled_exit_date": (
                calendar[exit_position] if exit_position < len(calendar) else None
            ),
            "trade_enabled": False,
        }
    holding_dates = list(calendar[entry_position : exit_position + 1])
    exit_date = holding_dates[-1]
    missing: list[dict[str, Any]] = []
    by_ticker_date: dict[str, dict[str, Mapping[str, Any]]] = {}
    for ticker in TRAVEL_BASKET_V1:
        index = {str(row["date"]): row for row in bars.get(ticker, [])}
        by_ticker_date[ticker] = index
        for session_date in holding_dates:
            row = index.get(session_date)
            absent = [
                field
                for field in ("open", "high", "low", "close")
                if row is None or _finite_positive(row.get(field)) is None
            ]
            if absent:
                missing.append(
                    {
                        "ticker": ticker,
                        "date": session_date,
                        "missing_fields": absent,
                    }
                )
    if missing:
        return "missed", {
            **candidate,
            "status": "missed_fail_closed_holding_bars",
            "paper_status": "missed",
            "scheduled_exit_date": exit_date,
            "missing_bars": missing,
            "trade_enabled": False,
        }

    trades: list[dict[str, Any]] = []
    leg_by_ticker = {str(leg["ticker"]): leg for leg in candidate["legs"]}
    for ticker in TRAVEL_BASKET_V1:
        leg = dict(leg_by_ticker[ticker])
        exit_price = float(by_ticker_date[ticker][exit_date]["close"])
        entry_price = float(leg["entry_price"])
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **leg,
                "decision_id": candidate["decision_id"],
                "week_ending": candidate["week_ending"],
                "report_date": candidate["report_date"],
                "knowledge_date": candidate["knowledge_date"],
                "exit_date": exit_date,
                "scheduled_exit_date": exit_date,
                "exit_price": round(exit_price, 4),
                "exit_reason": "scheduled_fifth_session_close",
                "hold_sessions_realized": HOLD_SESSIONS,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(LEG_NOTIONAL_USD * net_return, 2),
                "pnl_usd": round(LEG_NOTIONAL_USD * net_return, 2),
                "outcome_status": "settled",
                "paper_status": "closed",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    event = {
        **candidate,
        "status": "closed",
        "paper_status": "closed",
        "exit_date": exit_date,
        "scheduled_exit_date": exit_date,
        "exit_reason": "scheduled_fifth_session_close",
        "hold_sessions_realized": HOLD_SESSIONS,
        "closed_leg_count": len(trades),
        "trades": trades,
        "pnl": round(sum(float(row["pnl"]) for row in trades), 2),
        "pnl_usd": round(sum(float(row["pnl_usd"]) for row in trades), 2),
        "trade_enabled": False,
    }
    return "closed", event


def replay_tsa_checkpoint_throughput_paper_trades(
    *,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str,
    end: str,
    trading_dates: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Replay the locked five-session, costed, fixed-basket paper policy."""

    start_iso, end_iso = _iso_date(start), _iso_date(end)
    if start_iso is None or end_iso is None:
        raise ValueError("start and end must be ISO dates")
    candidates, audit = build_tsa_checkpoint_throughput_candidates(
        records=records,
        ohlcv_by_ticker=ohlcv_by_ticker,
        start=start_iso,
        end=end_iso,
        trading_dates=trading_dates,
    )
    try:
        bars, calendar = _prepare_market_inputs(ohlcv_by_ticker, trading_dates)
    except TSAContractError:
        bars, calendar = {}, []

    trades: list[dict[str, Any]] = []
    event_trades: list[dict[str, Any]] = []
    open_events: list[dict[str, Any]] = []
    missed_events: list[dict[str, Any]] = list(audit.get("missed_events") or [])
    if audit.get("measurement_valid"):
        for candidate in candidates:
            category, event = _settle_candidate(
                candidate, bars=bars, calendar=calendar, end=end_iso
            )
            if category == "closed":
                event_trades.append(event)
                trades.extend(event["trades"])
            elif category == "open":
                open_events.append(event)
            else:
                missed_events.append(event)

    return {
        "selected_candidates": candidates,
        "trades": trades,
        "event_trades": event_trades,
        "pending_events": list(audit.get("pending_events") or []),
        "open_events": open_events,
        "missed_events": missed_events,
        "signals_generated": int(audit.get("signals_generated") or 0),
        "signals_survived": int(audit.get("signals_survived") or 0),
        "survival_rate": float(audit.get("survival_rate") or 0.0),
        "settled_event_count": len(event_trades),
        "settled_leg_count": len(trades),
        "candidate_audit": audit,
        "reject_totals": dict(audit.get("reject_totals") or {}),
        "orders": [],
        "trade_enabled": False,
        "production_impact": _production_impact(),
    }


def empty_tsa_checkpoint_throughput_paper_state() -> dict[str, Any]:
    return {
        "pending_decision_ids": [],
        "open_decision_ids": [],
        "closed_decision_ids": [],
        "missed_decision_ids": [],
        "seen_entry_decision_ids": [],
    }


def empty_tsa_checkpoint_throughput_paper_sleeve_snapshot(
    as_of_date: str,
    reason: str = "not_available",
) -> dict[str, Any]:
    as_of = _iso_date(as_of_date) or str(as_of_date)
    return {
        "schema": DAILY_SNAPSHOT_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "status": "unavailable",
        "reason": reason,
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_count_today": 0,
        "missed_count": 0,
        "candidates": [],
        "pending_events": [],
        "pending_entries": [],
        "open_events": [],
        "open_positions": [],
        "closed_events": [],
        "closed_today": [],
        "missed_events": [],
        "orders": [],
        "state": empty_tsa_checkpoint_throughput_paper_state(),
        "production_impact": _production_impact(),
    }


def build_tsa_checkpoint_throughput_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    trading_dates: Iterable[Any] | None = None,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an as-of-safe, idempotent, default-off daily lifecycle view."""

    as_of = _iso_date(as_of_date)
    if as_of is None:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    records_as_of: list[Mapping[str, Any]] = []
    for raw in records:
        if not isinstance(raw, Mapping):
            records_as_of.append(raw)
            continue
        available = _raw_availability_date(raw)
        if available is None or available <= as_of:
            records_as_of.append(raw)

    bars_as_of: dict[str, list[Mapping[str, Any]]] = {}
    for ticker, rows in (ohlcv_by_ticker or {}).items():
        bars_as_of[str(ticker)] = [
            row
            for row in rows
            if not isinstance(row, Mapping)
            or (day := _iso_date(row.get("date") or row.get("Date"))) is None
            or day <= as_of
        ]
    calendar_as_of = None
    if trading_dates is not None:
        calendar_as_of = [
            raw
            for raw in trading_dates
            if (
                _iso_date(
                    raw.get("date") or raw.get("session_date")
                    if isinstance(raw, Mapping)
                    else raw
                )
                or "9999-12-31"
            )
            <= as_of
        ]

    replay = replay_tsa_checkpoint_throughput_paper_trades(
        records=records_as_of,
        ohlcv_by_ticker=bars_as_of,
        start="1900-01-01",
        end=as_of,
        trading_dates=calendar_as_of,
    )
    prior_state = dict(state or empty_tsa_checkpoint_throughput_paper_state())
    prior_seen = set(prior_state.get("seen_entry_decision_ids") or [])
    prior_closed = set(prior_state.get("closed_decision_ids") or [])
    prior_missed = set(prior_state.get("missed_decision_ids") or [])

    todays_candidates = [
        row
        for row in replay["selected_candidates"]
        if row["entry_date"] == as_of and row["decision_id"] not in prior_seen
    ]
    pending_events = list(replay["pending_events"])
    open_events = list(replay["open_events"])
    closed_events = list(replay["event_trades"])
    missed_events = list(replay["missed_events"])
    closed_today = [
        row
        for row in closed_events
        if row.get("exit_date") == as_of and row["decision_id"] not in prior_closed
    ]
    newly_missed = [
        row for row in missed_events if row["decision_id"] not in prior_missed
    ]

    seen = set(prior_seen)
    seen.update(
        row["decision_id"]
        for row in replay["selected_candidates"]
        if row.get("entry_date") and row["entry_date"] <= as_of
    )
    closed_ids = set(prior_closed)
    closed_ids.update(row["decision_id"] for row in closed_events)
    missed_ids = set(prior_missed)
    missed_ids.update(row["decision_id"] for row in missed_events)
    next_state = {
        "pending_decision_ids": sorted(
            {row["decision_id"] for row in pending_events}
        ),
        "open_decision_ids": sorted({row["decision_id"] for row in open_events}),
        "closed_decision_ids": sorted(closed_ids),
        "missed_decision_ids": sorted(missed_ids),
        "seen_entry_decision_ids": sorted(seen),
    }

    return {
        "schema": DAILY_SNAPSHOT_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "status": "ok" if replay["candidate_audit"].get("measurement_valid") else "invalid",
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": len(todays_candidates),
        "pending_count": len(pending_events),
        "open_position_count": len(open_events),
        "closed_count_today": len(closed_today),
        "closed_event_count": len(closed_events),
        "missed_count": len(missed_events),
        "new_missed_count": len(newly_missed),
        "candidates": todays_candidates,
        "pending_events": pending_events,
        "pending_entries": pending_events,
        "open_events": open_events,
        "open_positions": open_events,
        "closed_events": closed_events,
        "closed_today": closed_today,
        "missed_events": missed_events,
        "signals_generated": replay["signals_generated"],
        "signals_survived": replay["signals_survived"],
        "survival_rate": replay["survival_rate"],
        "orders": [],
        "state": next_state,
        "audit": replay["candidate_audit"],
        "strategy_behavior_changed": False,
        "alters_orders": False,
        "production_impact": _production_impact(),
    }


__all__ = [
    "ATR_PERIOD",
    "ATR_TARGET_MULTIPLE",
    "COOLDOWN_SESSIONS",
    "DAILY_SNAPSHOT_SCHEMA_VERSION",
    "EVENT_NOTIONAL_USD",
    "HOLD_SESSIONS",
    "LEG_NOTIONAL_USD",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "SOURCE_SCHEMA_VERSION",
    "TRADE_ENABLED",
    "TRAVEL_BASKET_V1",
    "TSAContractError",
    "build_tsa_checkpoint_throughput_candidates",
    "build_tsa_checkpoint_throughput_paper_sleeve_snapshot",
    "empty_tsa_checkpoint_throughput_paper_sleeve_snapshot",
    "empty_tsa_checkpoint_throughput_paper_state",
    "evaluate_tsa_checkpoint_throughput_events",
    "normalise_tsa_checkpoint_weekly_records",
    "replay_tsa_checkpoint_throughput_paper_trades",
]
