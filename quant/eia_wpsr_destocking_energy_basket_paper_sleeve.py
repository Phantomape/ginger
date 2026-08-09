"""Shared, default-off EIA WPSR de-stocking energy basket sleeve.

The causal decision is deliberately narrow: one first-published WPSR Table 4
record is one event, and the three frozen national inventory series form one
indivisible composite.  Historical replay and the daily paper snapshot both
call :func:`build_eia_wpsr_destocking_energy_basket_candidates`; neither path
may add price leadership, volatility relief, or a product-specific override.

This module never emits an executable order.  ``trade_enabled`` is hard-coded
to ``False`` on every public result.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

try:  # pragma: no cover - supports both ``quant.foo`` and direct imports.
    from constants import ROUND_TRIP_COST_PCT
    from fill_model import (
        SLIPPAGE_BPS_TARGET,
        apply_entry_fill,
        apply_slippage,
        apply_target_fill,
    )
except ImportError:  # pragma: no cover
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.fill_model import (
        SLIPPAGE_BPS_TARGET,
        apply_entry_fill,
        apply_slippage,
        apply_target_fill,
    )


SLEEVE_NAME = "EIA_WPSR_DESTOCKING_ENERGY_BASKET_PAPER"
RULE_VERSION = "eia_wpsr_table4_broad_destocking_energy_basket_10d_v1"
SOURCE_RULE_VERSION = "eia_wpsr_archived_table4_first_release_v1"

INVENTORY_SERIES = (
    "commercial_crude_oil_excluding_spr",
    "total_motor_gasoline",
    "distillate_fuel_oil",
)
ENERGY_BASKET_V1 = (
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "OXY",
    "SLB",
    "BKR",
    "MPC",
    "VLO",
    "PSX",
)

SEASONAL_YEARS = 5
SEASONAL_WEEK_RADIUS = 2
MIN_SEASONAL_OBSERVATIONS = 15
TRAILING_SCORE_OBSERVATIONS = 104
SCORE_PERCENTILE = 0.80
MIN_NEGATIVE_EXCESS_SERIES = 2
COOLDOWN_SESSIONS = 10
HOLD_SESSIONS = 10
ATR_PERIOD = 14
ATR_TARGET_MULTIPLE = 3.5
LEG_NOTIONAL_USD = 1_000.0
MIN_ELIGIBLE_LEGS = 8
MIN_ENTRY_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
ADV_PERIOD = 20


_SERIES_ALIASES = {
    "commercialcrudeoilexcludingspr": "commercial_crude_oil_excluding_spr",
    "commercialcrudeexcludingspr": "commercial_crude_oil_excluding_spr",
    "commercialcrudeoilstocksexcludingspr": "commercial_crude_oil_excluding_spr",
    "totalmotorgasoline": "total_motor_gasoline",
    "totalmotorgasolinestocks": "total_motor_gasoline",
    "distillatefueloil": "distillate_fuel_oil",
    "distillatefueloilstocks": "distillate_fuel_oil",
}

_ARCHIVE_TABLE4_URL_RE = re.compile(
    r"^https://(?:www\.)?eia\.gov/petroleum/supply/weekly/archive/"
    r"(?P<year>\d{4})/(?P<stamp>\d{4}_\d{2}_\d{2})/csv/table4\.csv$",
    re.IGNORECASE,
)
_EIA_OFFICIAL_URL_RE = re.compile(r"^https://(?:www\.)?eia\.gov/", re.IGNORECASE)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_ERRATA_RELEASE_DATE = "2023-12-28"


def _production_impact() -> dict[str, Any]:
    return {
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "max_displacement": 0,
    }


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _normalised_label(value: Any) -> str:
    return "".join(character for character in str(value or "").lower() if character.isalnum())


def _canonical_series_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if text in INVENTORY_SERIES:
        return text
    return _SERIES_ALIASES.get(_normalised_label(text))


def _inventory_rows(value: Any) -> dict[str, Mapping[str, Any]] | None:
    output: dict[str, Mapping[str, Any]] = {}
    if isinstance(value, Mapping):
        iterator = value.items()
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        iterator = (
            (
                row.get("series") or row.get("name") or row.get("inventory"),
                row,
            )
            for row in value
            if isinstance(row, Mapping)
        )
    else:
        return None
    for raw_name, row in iterator:
        canonical = _canonical_series_name(raw_name)
        if canonical is None or not isinstance(row, Mapping) or canonical in output:
            return None
        output[canonical] = row
    if set(output) != set(INVENTORY_SERIES):
        return None
    return output


def _normalise_record(record: Mapping[str, Any]) -> dict[str, Any] | None:
    release_date = _iso_date(record.get("release_date"))
    week_ending = _iso_date(record.get("week_ending"))
    inventories = _inventory_rows(record.get("inventories"))
    if release_date is None or week_ending is None or inventories is None:
        return None
    release_day = date.fromisoformat(release_date)
    week_ending_day = date.fromisoformat(week_ending)
    release_lag_days = (release_day - week_ending_day).days
    if not 2 <= release_lag_days <= 13:
        return None
    source_url = str(record.get("source_url") or "").strip()
    source_match = _ARCHIVE_TABLE4_URL_RE.fullmatch(source_url)
    raw_sha256 = str(record.get("raw_sha256") or record.get("archive_sha256") or "").strip()
    if source_match is None or _SHA256_RE.fullmatch(raw_sha256) is None:
        return None
    source_release = source_match.group("stamp").replace("_", "-")
    if source_match.group("year") != release_date[:4] or source_release != release_date:
        return None
    difference_semantics = str(record.get("difference_semantics") or "").strip()
    if difference_semantics not in {
        "published_difference",
        "official_errata_revision",
    }:
        return None
    official_notice_url = None
    official_notice_sha256 = None
    if difference_semantics == "official_errata_revision":
        official_notice_url = str(record.get("official_notice_url") or "").strip()
        official_notice_sha256 = str(
            record.get("official_notice_sha256") or ""
        ).strip()
        if (
            release_date != _ERRATA_RELEASE_DATE
            or _EIA_OFFICIAL_URL_RE.match(official_notice_url) is None
            or _SHA256_RE.fullmatch(official_notice_sha256) is None
        ):
            return None
    canonical: dict[str, dict[str, float]] = {}
    for series in INVENTORY_SERIES:
        row = inventories[series]
        current = _finite_float(row.get("current"))
        prior = _finite_float(row.get("prior"))
        difference = _finite_float(row.get("difference"))
        reported_implied_prior = _finite_float(row.get("implied_corrected_prior"))
        reported_residual = _finite_float(row.get("arithmetic_residual"))
        if (
            current is None
            or prior is None
            or difference is None
            or reported_implied_prior is None
            or reported_residual is None
            or prior <= 0
        ):
            return None
        implied_corrected_prior = current - difference
        if implied_corrected_prior <= 0:
            return None
        arithmetic_residual = prior - implied_corrected_prior
        if (
            not math.isclose(
                reported_implied_prior,
                implied_corrected_prior,
                abs_tol=0.0021,
            )
            or not math.isclose(
                reported_residual,
                arithmetic_residual,
                abs_tol=0.0021,
            )
        ):
            return None
        if (
            difference_semantics != "official_errata_revision"
            and not math.isclose(arithmetic_residual, 0.0, abs_tol=0.0021)
        ):
            return None
        canonical[series] = {
            "current": current,
            "prior": prior,
            "difference": difference,
            "implied_corrected_prior": implied_corrected_prior,
            "arithmetic_residual": arithmetic_residual,
            "weekly_change_rate": difference / implied_corrected_prior,
        }
    return {
        "release_date": release_date,
        "week_ending": week_ending,
        "inventories": canonical,
        "source_url": source_url,
        "raw_sha256": raw_sha256.lower(),
        "release_lag_days": release_lag_days,
        "difference_semantics": difference_semantics,
        "official_notice_url": official_notice_url,
        "official_notice_sha256": (
            official_notice_sha256.lower() if official_notice_sha256 else None
        ),
        "source_rule_version": SOURCE_RULE_VERSION,
    }


def normalise_eia_wpsr_table4_records(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return unique canonical Table 4 rows, dropping malformed source rows.

    The higher-level builder exposes the dropped count as a Gate-2 hard-fail
    audit field and admits no candidates when any source row is malformed.
    """

    by_release: dict[str, dict[str, Any]] = {}
    seen_week_endings: set[str] = set()
    invalid = False
    for record in records:
        row = _normalise_record(record) if isinstance(record, Mapping) else None
        if (
            row is None
            or row["release_date"] in by_release
            or row["week_ending"] in seen_week_endings
        ):
            invalid = True
            continue
        by_release[row["release_date"]] = row
        seen_week_endings.add(row["week_ending"])
    if invalid:
        return []
    return [by_release[key] for key in sorted(by_release)]


def _iso_week_distance(target_week: int, candidate_week: int, candidate_year: int) -> int:
    """Circular ISO-week distance on the candidate year's 52/53-week cycle."""

    weeks_in_candidate_year = date(candidate_year, 12, 28).isocalendar().week
    target_on_candidate_cycle = min(target_week, weeks_in_candidate_year)
    difference = abs(target_on_candidate_cycle - candidate_week)
    return min(difference, weeks_in_candidate_year - difference)


def _seasonal_median(
    history: Sequence[Mapping[str, Any]],
    current_week_ending: str,
    series: str,
) -> tuple[float | None, int]:
    current = date.fromisoformat(current_week_ending).isocalendar()
    values: list[float] = []
    for row in history:
        prior = date.fromisoformat(str(row["week_ending"])).isocalendar()
        if not (current.year - SEASONAL_YEARS <= prior.year < current.year):
            continue
        if _iso_week_distance(current.week, prior.week, prior.year) > SEASONAL_WEEK_RADIUS:
            continue
        value = _finite_float(row["inventories"][series].get("weekly_change_rate"))
        if value is not None:
            values.append(value)
    if len(values) < MIN_SEASONAL_OBSERVATIONS:
        return None, len(values)
    return statistics.median(values), len(values)


def _nearest_rank(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("nearest-rank percentile needs at least one value")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def evaluate_eia_wpsr_destocking_events(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply the PIT seasonal composite and trailing-score threshold.

    Only scores from earlier releases enter either baseline.  The p80 is the
    nearest-rank percentile of exactly the preceding 104 valid scores.
    """

    raw = [record for record in records]
    normalised = normalise_eia_wpsr_table4_records(raw)
    if len(normalised) != len(raw):
        return [], {
            "measurement_valid": False,
            "input_record_count": len(raw),
            "normalised_record_count": len(normalised),
            "source_contract_error_count": len(raw) - len(normalised),
            "source_contract_error": "malformed_or_duplicate_archived_table4_record",
        }

    evaluations: list[dict[str, Any]] = []
    valid_scores: list[float] = []
    rejects: Counter[str] = Counter()
    for idx, row in enumerate(normalised):
        excess: dict[str, float] = {}
        seasonal_counts: dict[str, int] = {}
        for series in INVENTORY_SERIES:
            baseline, count = _seasonal_median(normalised[:idx], row["week_ending"], series)
            seasonal_counts[series] = count
            if baseline is not None:
                excess[series] = row["inventories"][series]["weekly_change_rate"] - baseline
        if len(excess) != len(INVENTORY_SERIES):
            rejects["insufficient_seasonal_history"] += 1
            evaluations.append(
                {
                    **row,
                    "seasonal_observation_counts": seasonal_counts,
                    "event_ready": False,
                    "triggered": False,
                    "filter_reason": "insufficient_seasonal_history",
                    "trade_enabled": False,
                }
            )
            continue

        score = -sum(excess.values()) / len(INVENTORY_SERIES)
        negative_count = sum(value < 0 for value in excess.values())
        threshold = None
        if len(valid_scores) >= TRAILING_SCORE_OBSERVATIONS:
            threshold = _nearest_rank(valid_scores[-TRAILING_SCORE_OBSERVATIONS:], SCORE_PERCENTILE)
        breadth_passed = negative_count >= MIN_NEGATIVE_EXCESS_SERIES
        threshold_passed = threshold is not None and score > threshold
        triggered = breadth_passed and threshold_passed
        if threshold is None:
            reason = "insufficient_trailing_score_history"
        elif not breadth_passed:
            reason = "fewer_than_two_negative_excess_series"
        elif not threshold_passed:
            reason = "score_not_strictly_above_trailing_p80"
        else:
            reason = None
        if reason:
            rejects[reason] += 1
        evaluations.append(
            {
                **row,
                "seasonal_excess_change_rates": excess,
                "seasonal_observation_counts": seasonal_counts,
                "negative_excess_series_count": negative_count,
                "destocking_score": score,
                "trailing_score_count": min(len(valid_scores), TRAILING_SCORE_OBSERVATIONS),
                "trailing_score_p80": threshold,
                "breadth_passed": breadth_passed,
                "threshold_passed": threshold_passed,
                "event_ready": threshold is not None,
                "triggered": triggered,
                "filter_reason": reason,
                "trade_enabled": False,
            }
        )
        valid_scores.append(score)

    return evaluations, {
        "measurement_valid": True,
        "input_record_count": len(raw),
        "normalised_record_count": len(normalised),
        "source_contract_error_count": 0,
        "valid_score_count": len(valid_scores),
        "trigger_count_before_cooldown_and_liquidity": sum(row["triggered"] for row in evaluations),
        "reject_totals": dict(sorted(rejects.items())),
    }


def _normalise_bars(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        day = _iso_date(row.get("date") or row.get("Date"))
        open_price = _finite_float(row.get("open") if "open" in row else row.get("Open"))
        high = _finite_float(row.get("high") if "high" in row else row.get("High"))
        low = _finite_float(row.get("low") if "low" in row else row.get("Low"))
        close = _finite_float(row.get("close") if "close" in row else row.get("Close"))
        volume = _finite_float(row.get("volume") if "volume" in row else row.get("Volume"))
        if day and open_price and close and open_price > 0 and close > 0:
            output[day] = {
                "date": day,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
    return [output[key] for key in sorted(output)]


def _trading_dates(
    bars: Mapping[str, Sequence[Mapping[str, Any]]],
    supplied: Iterable[Any] | None,
) -> list[str]:
    if supplied is not None:
        return sorted({day for value in supplied if (day := _iso_date(value))})
    if bars.get("SPY"):
        return [str(row["date"]) for row in bars["SPY"]]
    return sorted({str(row["date"]) for ticker in ENERGY_BASKET_V1 for row in bars.get(ticker, [])})


def _strict_next_session(release_date: str, trading_dates: Sequence[str]) -> str | None:
    return next((day for day in trading_dates if day > release_date), None)


def _event_decision_id(event: Mapping[str, Any]) -> str:
    return (
        f"{SLEEVE_NAME}:{RULE_VERSION}:"
        f"{event['release_date']}:{event['week_ending']}"
    )


def _adv20(rows: Sequence[Mapping[str, Any]], entry_idx: int) -> float | None:
    prior = rows[max(0, entry_idx - ADV_PERIOD) : entry_idx]
    if len(prior) != ADV_PERIOD:
        return None
    values: list[float] = []
    for row in prior:
        close = _finite_float(row.get("close"))
        volume = _finite_float(row.get("volume"))
        if close is None or volume is None or close <= 0 or volume <= 0:
            return None
        values.append(close * volume)
    return sum(values) / ADV_PERIOD


def _atr14(rows: Sequence[Mapping[str, Any]], entry_idx: int) -> float | None:
    prior = rows[max(0, entry_idx - ATR_PERIOD) : entry_idx]
    if len(prior) != ATR_PERIOD:
        return None
    true_ranges: list[float] = []
    start_idx = entry_idx - ATR_PERIOD
    for idx in range(start_idx, entry_idx):
        high = _finite_float(rows[idx].get("high"))
        low = _finite_float(rows[idx].get("low"))
        previous_close = _finite_float(rows[idx - 1].get("close")) if idx > 0 else None
        if high is None or low is None or previous_close is None:
            return None
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return sum(true_ranges) / ATR_PERIOD


def build_eia_wpsr_destocking_energy_basket_candidates(
    *,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str | None = None,
    end: str | None = None,
    trading_dates: Iterable[Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build fixed-basket event decisions with PIT liquidity and cooldown."""

    start_iso = _iso_date(start) if start is not None else None
    end_iso = _iso_date(end) if end is not None else None
    if start is not None and start_iso is None:
        raise ValueError(f"invalid start: {start!r}")
    if end is not None and end_iso is None:
        raise ValueError(f"invalid end: {end!r}")
    raw_records = [record for record in records]
    evaluations, source_audit = evaluate_eia_wpsr_destocking_events(raw_records)
    supplied_calendar = list(trading_dates) if trading_dates is not None else None
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    calendar = _trading_dates(bars, supplied_calendar)
    calendar_pos = {day: idx for idx, day in enumerate(calendar)}
    global_rejects: Counter[str] = Counter(source_audit.get("reject_totals") or {})
    window_rejects: Counter[str] = Counter()
    if not source_audit["measurement_valid"] or not calendar:
        if not calendar:
            window_rejects["missing_trading_calendar"] += 1
        return [], {
            **source_audit,
            "measurement_valid": False,
            "event_evaluations": evaluations,
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "reject_totals": dict(sorted(window_rejects.items())),
            "global_reject_totals": dict(sorted(global_rejects.items())),
            "production_impact": _production_impact(),
        }

    generated = 0
    triggered_in_window = 0
    selected: list[dict[str, Any]] = []
    next_allowed_position = -1
    for event in evaluations:
        entry_date = _strict_next_session(event["release_date"], calendar)
        if entry_date is None:
            release_in_window = (
                (start_iso is None or event["release_date"] >= start_iso)
                and (end_iso is None or event["release_date"] <= end_iso)
            )
            if release_in_window:
                window_rejects["missing_strict_next_session"] += 1
            continue
        in_window = (start_iso is None or entry_date >= start_iso) and (end_iso is None or entry_date <= end_iso)
        if in_window:
            generated += 1
        if not event["triggered"]:
            if in_window and event.get("filter_reason"):
                window_rejects[str(event["filter_reason"])] += 1
            continue
        if in_window:
            triggered_in_window += 1

        legs: list[dict[str, Any]] = []
        leg_rejects: Counter[str] = Counter()
        for ticker in ENERGY_BASKET_V1:
            ticker_rows = bars.get(ticker) or []
            entry_idx = next((idx for idx, row in enumerate(ticker_rows) if row["date"] == entry_date), None)
            if entry_idx is None:
                leg_rejects["missing_entry_bar"] += 1
                continue
            raw_open = _finite_float(ticker_rows[entry_idx].get("open"))
            adv = _adv20(ticker_rows, entry_idx)
            atr = _atr14(ticker_rows, entry_idx)
            if raw_open is None or raw_open < MIN_ENTRY_PRICE:
                leg_rejects["entry_price_below_10"] += 1
                continue
            if adv is None or adv < MIN_AVG_DOLLAR_VOLUME_20D:
                leg_rejects["adv20_below_50m_or_missing"] += 1
                continue
            if atr is None or atr <= 0:
                leg_rejects["atr14_missing"] += 1
                continue
            entry_fill = apply_entry_fill(raw_open, adv_dollar=adv, notional=LEG_NOTIONAL_USD)
            legs.append(
                {
                    "ticker": ticker,
                    "entry_date": entry_date,
                    "entry_open_price": round(raw_open, 4),
                    "entry_price": round(float(entry_fill), 4),
                    "avg_dollar_volume_20d": round(adv, 2),
                    "atr14": round(atr, 6),
                    "target_price": round(float(entry_fill) + ATR_TARGET_MULTIPLE * atr, 4),
                    "paper_notional_usd": LEG_NOTIONAL_USD,
                    "trade_enabled": False,
                }
            )
        if len(legs) < MIN_ELIGIBLE_LEGS:
            if in_window:
                window_rejects["fewer_than_8_eligible_legs"] += 1
                window_rejects.update({f"leg_{key}": value for key, value in leg_rejects.items()})
            continue
        position = calendar_pos[entry_date]
        if position < next_allowed_position:
            if in_window:
                window_rejects["ten_session_cooldown"] += 1
            continue
        candidate = {
            **event,
            "signal_date": event["release_date"],
            "entry_date": entry_date,
            "decision_id": _event_decision_id(event),
            "eligible_leg_count": len(legs),
            "eligible_tickers": [leg["ticker"] for leg in legs],
            "legs": legs,
            "event_notional_usd": LEG_NOTIONAL_USD * len(legs),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "hold_sessions": HOLD_SESSIONS,
            "rule_version": RULE_VERSION,
            "trade_enabled": False,
            "alters_orders": False,
        }
        next_allowed_position = position + COOLDOWN_SESSIONS
        if in_window:
            selected.append(candidate)

    return selected, {
        **source_audit,
        "measurement_valid": True,
        "event_evaluations": evaluations,
        "signals_generated": generated,
        "signals_survived": len(selected),
        "survival_rate": round(len(selected) / generated, 6) if generated else 0.0,
        "window_trigger_count_before_cooldown_and_liquidity": triggered_in_window,
        "selected_event_count": len(selected),
        "selected_leg_count": sum(len(row["legs"]) for row in selected),
        "reject_totals": dict(sorted(window_rejects.items())),
        "global_reject_totals": dict(sorted(global_rejects.items())),
        "production_impact": _production_impact(),
    }


def replay_eia_wpsr_destocking_energy_basket_paper_trades(
    *,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str,
    end: str,
    trading_dates: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Replay eligible legs, exiting at the 3.5x ATR target or session 10."""

    supplied_calendar = list(trading_dates) if trading_dates is not None else None
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    selected, audit = build_eia_wpsr_destocking_energy_basket_candidates(
        records=records,
        ohlcv_by_ticker=bars,
        start=start,
        end=end,
        trading_dates=supplied_calendar,
    )
    end_iso = _iso_date(end)
    if end_iso is None:
        raise ValueError(f"invalid end: {end!r}")
    calendar = _trading_dates(bars, supplied_calendar)
    calendar_pos = {day: idx for idx, day in enumerate(calendar)}
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    event_trades: list[dict[str, Any]] = []
    for candidate in selected:
        entry_calendar_idx = calendar_pos.get(candidate["entry_date"])
        scheduled_calendar_idx = (
            entry_calendar_idx + HOLD_SESSIONS - 1
            if entry_calendar_idx is not None
            else None
        )
        if (
            entry_calendar_idx is None
            or scheduled_calendar_idx is None
            or scheduled_calendar_idx >= len(calendar)
            or calendar[scheduled_calendar_idx] > end_iso
        ):
            unsettled.append(
                {
                    "decision_id": candidate["decision_id"],
                    "release_date": candidate["release_date"],
                    "entry_date": candidate["entry_date"],
                    "eligible_tickers": list(candidate["eligible_tickers"]),
                    "unsettled_reason": "incomplete_shared_10_session_horizon",
                    "paper_status": "unsettled",
                    "trade_enabled": False,
                }
            )
            continue
        holding_dates = calendar[entry_calendar_idx : scheduled_calendar_idx + 1]
        scheduled_exit_date = holding_dates[-1]
        rows_by_ticker_and_date: dict[str, dict[str, Mapping[str, Any]]] = {}
        incomplete: list[dict[str, Any]] = []
        for leg in candidate["legs"]:
            ticker = leg["ticker"]
            index = {row["date"]: row for row in (bars.get(ticker) or [])}
            rows_by_ticker_and_date[ticker] = index
            for session_date in holding_dates:
                row = index.get(session_date)
                missing_fields = [
                    field
                    for field in ("open", "high", "low", "close")
                    if row is None
                    or (value := _finite_float(row.get(field))) is None
                    or value <= 0
                ]
                if missing_fields:
                    incomplete.append(
                        {
                            "ticker": ticker,
                            "date": session_date,
                            "missing_fields": missing_fields,
                        }
                    )
        if incomplete:
            unsettled.append(
                {
                    "decision_id": candidate["decision_id"],
                    "release_date": candidate["release_date"],
                    "entry_date": candidate["entry_date"],
                    "scheduled_exit_date": scheduled_exit_date,
                    "eligible_tickers": list(candidate["eligible_tickers"]),
                    "incomplete_bars": incomplete,
                    "unsettled_reason": "incomplete_shared_session_ohlc",
                    "paper_status": "unsettled",
                    "trade_enabled": False,
                }
            )
            continue

        event_legs: list[dict[str, Any]] = []
        for leg in candidate["legs"]:
            ticker = leg["ticker"]
            index = rows_by_ticker_and_date[ticker]
            target = float(leg["target_price"])
            exit_date = scheduled_exit_date
            exit_reason = "scheduled_10th_session_close"
            exit_raw = _finite_float(index[scheduled_exit_date].get("close"))
            exit_fill = None
            hold_sessions_realized = HOLD_SESSIONS
            for session_number, session_date in enumerate(holding_dates, start=1):
                row = index[session_date]
                high = float(row["high"])
                open_price = float(row["open"])
                if high >= target:
                    exit_date = session_date
                    exit_reason = "atr_3_5x_target"
                    exit_raw = open_price if open_price >= target else target
                    hold_sessions_realized = session_number
                    exit_fill = apply_target_fill(
                        open_price,
                        target,
                        adv_dollar=leg["avg_dollar_volume_20d"],
                        notional=LEG_NOTIONAL_USD,
                    )
                    break
            assert exit_raw is not None
            if exit_fill is None:
                exit_fill = apply_slippage(
                    exit_raw,
                    SLIPPAGE_BPS_TARGET,
                    "sell",
                    adv_dollar=leg["avg_dollar_volume_20d"],
                    notional=LEG_NOTIONAL_USD,
                )
            net_return = float(exit_fill) / float(leg["entry_price"]) - 1.0 - ROUND_TRIP_COST_PCT
            trade = {
                **leg,
                "decision_id": candidate["decision_id"],
                "release_date": candidate["release_date"],
                "week_ending": candidate["week_ending"],
                "exit_date": exit_date,
                "exit_raw_price": round(float(exit_raw), 4),
                "exit_price": round(float(exit_fill), 4),
                "exit_reason": exit_reason,
                "hold_sessions_realized": hold_sessions_realized,
                "scheduled_exit_date": scheduled_exit_date,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(LEG_NOTIONAL_USD * net_return, 2),
                "paper_status": "closed",
                "trade_enabled": False,
                "alters_orders": False,
            }
            event_legs.append(trade)
        trades.extend(event_legs)
        event_trades.append(
            {
                "decision_id": candidate["decision_id"],
                "release_date": candidate["release_date"],
                "entry_date": candidate["entry_date"],
                "exit_date": max(row["exit_date"] for row in event_legs),
                "closed_leg_count": len(event_legs),
                "paper_notional_usd": sum(row["paper_notional_usd"] for row in event_legs),
                "pnl": round(sum(row["pnl"] for row in event_legs), 2),
                "pnl_pct_net": round(sum(row["pnl_pct_net"] for row in event_legs) / len(event_legs), 10),
                "trade_enabled": False,
            }
        )
    return {
        "selected_candidates": selected,
        "trades": trades,
        "event_trades": event_trades,
        "unsettled": unsettled,
        "candidate_audit": audit,
        "reject_totals": audit["reject_totals"],
        "signals_generated": audit["signals_generated"],
        "signals_survived": audit["signals_survived"],
        "survival_rate": audit["survival_rate"],
        "trade_enabled": False,
        "orders": [],
        "production_impact": _production_impact(),
    }


def empty_eia_wpsr_destocking_energy_basket_paper_state() -> dict[str, Any]:
    return {
        "pending_decision_ids": [],
        "seen_decision_ids": [],
        "closed_decision_ids": [],
    }


def build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    trading_dates: Iterable[Any] | None = None,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a daily default-off view from the exact shared event function."""

    as_of = _iso_date(as_of_date)
    if as_of is None:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    records_as_of: list[Mapping[str, Any]] = []
    for record in records:
        release_date = (
            _iso_date(record.get("release_date"))
            if isinstance(record, Mapping)
            else None
        )
        if release_date is None or release_date <= as_of:
            records_as_of.append(record)
    bars_as_of: dict[str, list[Mapping[str, Any]]] = {}
    for ticker, rows in ohlcv_by_ticker.items():
        bars_as_of[str(ticker)] = [
            row
            for row in rows
            if not isinstance(row, Mapping)
            or (day := _iso_date(row.get("date") or row.get("Date"))) is None
            or day <= as_of
        ]
    supplied_calendar_as_of = None
    if trading_dates is not None:
        supplied_calendar_as_of = [
            day
            for value in trading_dates
            if (day := _iso_date(value)) is not None and day <= as_of
        ]
    candidates, audit = build_eia_wpsr_destocking_energy_basket_candidates(
        records=records_as_of,
        ohlcv_by_ticker=bars_as_of,
        end=as_of,
        trading_dates=supplied_calendar_as_of,
    )
    previous_seen = set((state or {}).get("seen_decision_ids") or [])
    todays_candidates = [
        row
        for row in candidates
        if row["entry_date"] == as_of and row["decision_id"] not in previous_seen
    ]
    source_triggers_today = [
        {**row, "decision_id": _event_decision_id(row)}
        for row in audit["event_evaluations"]
        if row["release_date"] == as_of and row["triggered"]
    ]
    normalised_bars_as_of = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in bars_as_of.items()
    }
    calendar_as_of = _trading_dates(
        normalised_bars_as_of,
        supplied_calendar_as_of,
    )
    triggered_by_id = {
        _event_decision_id(row): row
        for row in audit["event_evaluations"]
        if row["triggered"]
    }
    processed_today = {
        decision_id
        for decision_id, event in triggered_by_id.items()
        if _strict_next_session(event["release_date"], calendar_as_of) == as_of
    }
    pending_ids = set((state or {}).get("pending_decision_ids") or [])
    pending_ids.update(row["decision_id"] for row in source_triggers_today)
    pending_ids.difference_update(processed_today)
    pending_source_triggers = [
        {**triggered_by_id[decision_id], "decision_id": decision_id}
        for decision_id in sorted(pending_ids)
        if decision_id in triggered_by_id
    ]
    previous_seen.update(processed_today)
    next_state = {
        "pending_decision_ids": sorted(pending_ids),
        "seen_decision_ids": sorted(previous_seen),
        "closed_decision_ids": sorted(set((state or {}).get("closed_decision_ids") or [])),
    }
    return {
        "schema": "eia_wpsr_destocking_energy_basket_daily_snapshot_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": len(todays_candidates),
        "pending_count": len(pending_source_triggers),
        "source_trigger_count": len(source_triggers_today),
        "source_triggers": source_triggers_today,
        "candidates": todays_candidates,
        "pending_entries": pending_source_triggers,
        "state": next_state,
        "orders": [],
        "audit": audit,
        "strategy_behavior_changed": False,
        "alters_orders": False,
        "production_impact": _production_impact(),
    }
