"""Shared default-off Treasury weak-auction TBT paper helper.

The helper is deliberately pure: callers supply canonical Treasury auction
rows and already-adjusted market bars.  It performs no network access and no
persistence.  Historical replay and the daily snapshot therefore share the
same event and settlement rules without creating an executable order path.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any


SLEEVE_NAME = "TREASURY_AUCTION_WEAK_DEMAND_TBT_PAPER"
RULE_VERSION = "treasury_nominal_coupon_weak_btc_tbt_nextopen_5d_v1"
LOOKBACK_AUCTIONS = 12
HOLD_SESSIONS = 5
NOTIONAL_USD = 16_000.0
ROUND_TRIP_COST_PCT = 0.0035
TICKER = "TBT"
MAX_CONCURRENT_POSITIONS = 1

_ALLOWED_SECURITY_TYPES = {"note", "bond"}
_PENDING_REASONS = {
    "strict_next_session_not_available",
    "entry_after_window",
    "incomplete_5_session_horizon",
    "missing_aligned_adjusted_tbt_or_comparator_bar",
}


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _yes(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _term_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _pick(row: Mapping[str, Any], *names: str) -> Any:
    normalised = {
        "".join(character for character in str(key).lower() if character.isalnum()): value
        for key, value in row.items()
    }
    for name in names:
        key = "".join(character for character in name.lower() if character.isalnum())
        if key in normalised:
            return normalised[key]
    return None


def _normalise_auction_rows(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return fail-closed nominal fixed-coupon Note/Bond auction rows."""

    canonical: dict[tuple[str, str], dict[str, Any]] = {}
    conflicted_keys: set[tuple[str, str]] = set()
    for source in records:
        if not isinstance(source, Mapping):
            continue
        security_type = str(source.get("security_type") or "").strip()
        if security_type.lower() not in _ALLOWED_SECURITY_TYPES:
            continue
        # Fiscal Data uses ``tips=No`` on nominal coupons.  Missing TIPS
        # identity is not accepted because that would silently mix regimes.
        if "tips" not in source or _yes(source.get("tips")):
            continue
        if _yes(source.get("floating_rate")) or _yes(source.get("frn")):
            continue
        auction_date = _iso_date(source.get("auction_date"))
        original_term = str(source.get("original_security_term") or "").strip()
        term_key = _term_key(original_term)
        ratio = _finite_float(source.get("bid_to_cover_ratio"))
        cusip = str(source.get("cusip") or "").strip().upper()
        if (
            auction_date is None
            or not term_key
            or ratio is None
            or ratio <= 0
            or not cusip
        ):
            continue
        explicit_publication = (
            source.get("result_publication_date")
            or source.get("first_public_date")
            or source.get("result_date")
        )
        signal_date = _iso_date(explicit_publication) if explicit_publication else auction_date
        if signal_date is None or signal_date < auction_date:
            continue
        key = (auction_date, cusip)
        if key in conflicted_keys:
            continue
        row = {
            "auction_date": auction_date,
            "signal_date": signal_date,
            "cusip": cusip,
            "security_type": security_type.title(),
            "security_term": str(source.get("security_term") or "").strip(),
            "original_security_term": original_term,
            "term_key": term_key,
            "bid_to_cover_ratio": ratio,
            "tips": "No",
            "availability_semantics": (
                "explicit_result_publication_date"
                if explicit_publication
                else "auction_results_same_day_assumption"
            ),
        }
        previous = canonical.get(key)
        # Conflicting duplicate snapshots are not a canonical first-public row.
        if previous is not None and previous != row:
            canonical.pop(key, None)
            conflicted_keys.add(key)
            continue
        canonical[key] = row
    return sorted(
        canonical.values(),
        key=lambda row: (
            row["signal_date"],
            row["auction_date"],
            row["term_key"],
            row["cusip"],
        ),
    )


def build_weak_auction_events(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build one weak-demand signal per result day without lookahead.

    Every auction is compared with exactly the preceding twelve completed
    auctions of the same ``original_security_term``.  The current auction is
    appended to history only after its decision is frozen.  Multiple weak
    auctions published on one day collapse into a single TBT decision.
    """

    history_by_term: dict[str, list[dict[str, Any]]] = {}
    weak_rows: list[dict[str, Any]] = []
    rows = _normalise_auction_rows(records)
    group_start = 0
    while group_start < len(rows):
        signal_date = rows[group_start]["signal_date"]
        group_end = group_start
        while group_end < len(rows) and rows[group_end]["signal_date"] == signal_date:
            group_end += 1
        release_group = rows[group_start:group_end]

        # Freeze every decision before any same-publication group row is added.
        for row in release_group:
            prior = history_by_term.get(row["term_key"], [])
            trailing = prior[-LOOKBACK_AUCTIONS:]
            if len(trailing) != LOOKBACK_AUCTIONS:
                continue
            values = [float(item["bid_to_cover_ratio"]) for item in trailing]
            trailing_median = statistics.median(values)
            if float(row["bid_to_cover_ratio"]) < trailing_median:
                weak_rows.append(
                    {
                        **row,
                        "lookback_auction_count": LOOKBACK_AUCTIONS,
                        "lookback_bid_to_cover_ratios": values,
                        "trailing_12_bid_to_cover_median": trailing_median,
                        "current_auction_excluded_from_baseline": True,
                        "weak_demand": True,
                    }
                )
        for row in release_group:
            history_by_term.setdefault(row["term_key"], []).append(row)
        group_start = group_end

    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in weak_rows:
        by_day.setdefault(row["signal_date"], []).append(row)

    events: list[dict[str, Any]] = []
    for signal_date in sorted(by_day):
        auctions = sorted(
            by_day[signal_date],
            key=lambda row: (row["term_key"], row["cusip"]),
        )
        tenors = sorted({row["original_security_term"] for row in auctions})
        events.append(
            {
                "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{signal_date}",
                "signal_date": signal_date,
                "auction_dates": sorted({row["auction_date"] for row in auctions}),
                "tenors": tenors,
                "auction_count": len(auctions),
                "weak_auctions": auctions,
                "same_day_merged": len(auctions) > 1,
                "lookback_auctions": LOOKBACK_AUCTIONS,
                "ticker": TICKER,
                "paper_notional_usd": NOTIONAL_USD,
                "target_price": None,
                "target_price_role": "not_applicable_fixed_5_session_close",
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
            }
        )
    return events


def _normalise_adjusted_bars(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalise actual adjusted bars and reject unlabelled raw-only prices."""

    by_date: dict[str, dict[str, Any]] = {}
    for source in rows or []:
        if not isinstance(source, Mapping):
            continue
        day = _iso_date(_pick(source, "date"))
        if day is None:
            continue
        adjusted_open = _finite_float(
            _pick(source, "adjusted_open", "adj_open")
        )
        adjusted_high = _finite_float(
            _pick(source, "adjusted_high", "adj_high")
        )
        adjusted_low = _finite_float(
            _pick(source, "adjusted_low", "adj_low")
        )
        adjusted_close = _finite_float(
            _pick(source, "adjusted_close", "adj_close")
        )
        raw_open = _finite_float(_pick(source, "open"))
        raw_high = _finite_float(_pick(source, "high"))
        raw_low = _finite_float(_pick(source, "low"))
        raw_close = _finite_float(_pick(source, "close"))
        if adjusted_close is not None and adjusted_open is None:
            if raw_open is not None and raw_close is not None and raw_close > 0:
                factor = adjusted_close / raw_close
                adjusted_open = raw_open * factor
                adjusted_high = raw_high * factor if raw_high is not None else None
                adjusted_low = raw_low * factor if raw_low is not None else None
        explicitly_adjusted = _yes(source.get("adjusted")) or str(
            source.get("price_basis") or ""
        ).strip().lower() in {
            "adjusted",
            "split_dividend_adjusted",
            "split_and_distribution_adjusted",
            "yfinance_auto_adjusted_snapshot",
        }
        if explicitly_adjusted:
            adjusted_open = adjusted_open or raw_open
            adjusted_high = adjusted_high or raw_high
            adjusted_low = adjusted_low or raw_low
            adjusted_close = adjusted_close or raw_close
        if (
            adjusted_open is None
            or adjusted_close is None
            or adjusted_open <= 0
            or adjusted_close <= 0
        ):
            continue
        by_date[day] = {
            "date": day,
            "adjusted_open": adjusted_open,
            "adjusted_high": adjusted_high,
            "adjusted_low": adjusted_low,
            "adjusted_close": adjusted_close,
        }
    return [by_date[day] for day in sorted(by_date)]


def _atr_target(
    rows: Sequence[Mapping[str, Any]], signal_date: str, entry_price: float
) -> float:
    """Return the signal-contract 3.5x ATR14 sentinel using only known bars."""

    eligible = [index for index, row in enumerate(rows) if str(row["date"]) <= signal_date]
    true_ranges: list[float] = []
    if eligible:
        last_index = eligible[-1]
        for index in range(max(0, last_index - 13), last_index + 1):
            row = rows[index]
            high = _finite_float(row.get("adjusted_high"))
            low = _finite_float(row.get("adjusted_low"))
            close = _finite_float(row.get("adjusted_close"))
            if high is None or low is None or close is None:
                continue
            previous_close = (
                _finite_float(rows[index - 1].get("adjusted_close"))
                if index > 0
                else close
            )
            if previous_close is None:
                continue
            true_ranges.append(
                max(high - low, abs(high - previous_close), abs(low - previous_close))
            )
    # Synthetic unit tests and an initial observation day may lack high/low.
    # Preserve the required signal-contract sentinel without making it an exit.
    atr = statistics.fmean(true_ranges) if true_ranges else entry_price * 0.02
    return round(entry_price + 3.5 * atr, 8)


def _event_signal_date(event: Mapping[str, Any]) -> str | None:
    return _iso_date(event.get("signal_date") or event.get("auction_date"))


def _event_decision_id(event: Mapping[str, Any], signal_date: str) -> str:
    return str(event.get("decision_id") or f"{SLEEVE_NAME}:{RULE_VERSION}:{signal_date}")


def _event_tenors(event: Mapping[str, Any]) -> list[str]:
    values = event.get("tenors") or []
    if isinstance(values, str):
        values = [values]
    return sorted({str(value) for value in values if str(value).strip()})


def _bar_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(row["date"]): row for row in rows}


def replay_weak_auction_tbt(
    events: Iterable[Mapping[str, Any]],
    price_rows: Iterable[Mapping[str, Any]],
    benchmark_rows: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str,
    end: str,
) -> dict[str, Any]:
    """Replay merged signals at next open through the fifth-session close."""

    start_iso = _iso_date(start)
    end_iso = _iso_date(end)
    if start_iso is None or end_iso is None or start_iso > end_iso:
        raise ValueError(f"invalid replay window: {start!r} -> {end!r}")

    tbt_bars = _normalise_adjusted_bars(price_rows)
    spy_bars = _normalise_adjusted_bars(benchmark_rows.get("SPY") or [])
    qqq_bars = _normalise_adjusted_bars(benchmark_rows.get("QQQ") or [])
    calendar = [row["date"] for row in spy_bars] or [row["date"] for row in tbt_bars]
    calendar = sorted(set(calendar))
    calendar_pos = {day: index for index, day in enumerate(calendar)}
    indexes = {
        TICKER: _bar_index(tbt_bars),
        "SPY": _bar_index(spy_bars),
        "QQQ": _bar_index(qqq_bars),
    }

    normalised_events: list[tuple[str, Mapping[str, Any]]] = []
    for event in events:
        if isinstance(event, Mapping) and (signal_date := _event_signal_date(event)):
            normalised_events.append((signal_date, event))
    normalised_events.sort(
        key=lambda item: (item[0], _event_decision_id(item[1], item[0]))
    )

    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    signals_generated = 0
    active_exit_index = -1
    for signal_date, event in normalised_events:
        if signal_date < start_iso or signal_date > end_iso:
            continue
        signals_generated += 1
        base = {
            "decision_id": _event_decision_id(event, signal_date),
            "signal_date": signal_date,
            "tenors": _event_tenors(event),
            "ticker": TICKER,
            "paper_notional_usd": NOTIONAL_USD,
            "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
            "target_price": None,
            "target_price_role": "pending_entry_atr_signal_contract_sentinel",
            "trade_enabled": False,
        }
        entry_date = next((day for day in calendar if day > signal_date), None)
        if entry_date is None:
            skipped.append({**base, "reason": "strict_next_session_not_available"})
            continue
        entry_index = calendar_pos[entry_date]
        if entry_date > end_iso:
            skipped.append({**base, "entry_date": entry_date, "reason": "entry_after_window"})
            continue
        exit_index = entry_index + HOLD_SESSIONS - 1
        if exit_index >= len(calendar) or calendar[exit_index] > end_iso:
            skipped.append(
                {
                    **base,
                    "entry_date": entry_date,
                    "reason": "incomplete_5_session_horizon",
                }
            )
            continue
        exit_date = calendar[exit_index]
        if entry_index <= active_exit_index:
            skipped.append(
                {
                    **base,
                    "entry_date": entry_date,
                    "scheduled_exit_date": exit_date,
                    "reason": "max_concurrent_position_one",
                }
            )
            continue
        # The paper slot is consumed by the event even if a required bar later
        # proves unavailable.  Missing data must not admit a second position.
        active_exit_index = exit_index

        aligned: dict[str, tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]] = {}
        for ticker in (TICKER, "SPY", "QQQ"):
            aligned[ticker] = (
                indexes[ticker].get(entry_date),
                indexes[ticker].get(exit_date),
            )
        if any(entry is None or exit_ is None for entry, exit_ in aligned.values()):
            skipped.append(
                {
                    **base,
                    "entry_date": entry_date,
                    "scheduled_exit_date": exit_date,
                    "reason": "missing_aligned_adjusted_tbt_or_comparator_bar",
                }
            )
            continue

        tbt_entry = float(aligned[TICKER][0]["adjusted_open"])
        tbt_exit = float(aligned[TICKER][1]["adjusted_close"])
        target_price = _atr_target(tbt_bars, signal_date, tbt_entry)
        gross_return = tbt_exit / tbt_entry - 1.0
        net_return = gross_return - ROUND_TRIP_COST_PCT
        pnl = NOTIONAL_USD * net_return
        comparator_detail: dict[str, dict[str, float]] = {}
        for ticker in ("SPY", "QQQ"):
            entry_bar, exit_bar = aligned[ticker]
            entry_price = float(entry_bar["adjusted_open"])
            exit_price = float(exit_bar["adjusted_close"])
            comparator_return = exit_price / entry_price - 1.0
            comparator_detail[ticker] = {
                "entry_price": round(entry_price, 8),
                "exit_price": round(exit_price, 8),
                "return": round(comparator_return, 10),
                "pnl": round(NOTIONAL_USD * comparator_return, 2),
            }
        trade = {
            **base,
            "entry_date": entry_date,
            "target_price": target_price,
            "target_price_role": "3.5x_atr14_signal_contract_sentinel_not_exit_driver",
            "target_price_atr_as_of": signal_date,
            "exit_date": exit_date,
            "scheduled_exit_date": exit_date,
            "entry_price": round(tbt_entry, 8),
            "exit_price": round(tbt_exit, 8),
            "price_basis": "split_and_distribution_adjusted",
            "hold_sessions_realized": HOLD_SESSIONS,
            "exit_reason": "scheduled_fifth_session_adjusted_close",
            "gross_return": round(gross_return, 10),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "round_trip_cost_usd": round(NOTIONAL_USD * ROUND_TRIP_COST_PCT, 2),
            "net_return": round(net_return, 10),
            "pnl": round(pnl, 2),
            "cash_replacement_usd": round(pnl, 2),
            "spy_replacement_usd": round(pnl - comparator_detail["SPY"]["pnl"], 2),
            "qqq_replacement_usd": round(pnl - comparator_detail["QQQ"]["pnl"], 2),
            "replacement_value_vs_cash_usd": round(pnl, 2),
            "replacement_value_vs_spy_usd": round(pnl - comparator_detail["SPY"]["pnl"], 2),
            "replacement_value_vs_qqq_usd": round(pnl - comparator_detail["QQQ"]["pnl"], 2),
            "comparator_detail": comparator_detail,
            "outcome_status": "settled",
            "paper_status": "closed",
        }
        trades.append(trade)

    return {
        "rule_version": RULE_VERSION,
        "ticker": TICKER,
        "trades": trades,
        "signals_generated": signals_generated,
        "signals_survived": len(trades),
        "survival_rate": round(len(trades) / signals_generated, 6)
        if signals_generated
        else 0.0,
        "skipped": skipped,
        "total_pnl": round(sum(float(row["pnl"]) for row in trades), 2),
        "cash_replacement_usd": round(
            sum(float(row["cash_replacement_usd"]) for row in trades), 2
        ),
        "spy_replacement_usd": round(
            sum(float(row["spy_replacement_usd"]) for row in trades), 2
        ),
        "qqq_replacement_usd": round(
            sum(float(row["qqq_replacement_usd"]) for row in trades), 2
        ),
        "paper_enabled": True,
        "trade_enabled": False,
        "orders": [],
    }


def _split_snapshot_prices(
    price_rows: Any,
) -> tuple[list[Mapping[str, Any]], dict[str, Iterable[Mapping[str, Any]]]]:
    if isinstance(price_rows, Mapping):
        tbt = list(price_rows.get(TICKER) or [])
        benchmarks = {
            "SPY": list(price_rows.get("SPY") or []),
            "QQQ": list(price_rows.get("QQQ") or []),
        }
        return tbt, benchmarks
    return list(price_rows or []), {"SPY": [], "QQQ": []}


def build_treasury_auction_tbt_snapshot(
    as_of_date: str,
    events: Iterable[Mapping[str, Any]],
    price_rows: Any,
    previous_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an idempotent, default-off daily view with no persistence."""

    as_of = _iso_date(as_of_date)
    if as_of is None:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    event_rows = [
        dict(event)
        for event in events
        if isinstance(event, Mapping)
        and (signal_date := _event_signal_date(event)) is not None
        and signal_date <= as_of
    ]
    tbt_rows, benchmarks = _split_snapshot_prices(price_rows)

    def through_as_of(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        return [
            row
            for row in rows
            if isinstance(row, Mapping)
            and (day := _iso_date(_pick(row, "date"))) is not None
            and day <= as_of
        ]

    tbt_as_of = through_as_of(tbt_rows)
    benchmark_as_of = {
        ticker: through_as_of(rows) for ticker, rows in benchmarks.items()
    }
    replay_start = min(
        (_event_signal_date(event) for event in event_rows),
        default=as_of,
    )
    replay = replay_weak_auction_tbt(
        event_rows,
        tbt_as_of,
        benchmark_as_of,
        replay_start,
        as_of,
    )

    previous = dict(previous_state or {})
    previous_seen = {str(value) for value in previous.get("seen_decision_ids") or []}
    current_ids = {
        _event_decision_id(event, _event_signal_date(event) or as_of)
        for event in event_rows
    }
    prior_closed = {
        str(row.get("decision_id")): dict(row)
        for row in previous.get("closed_trades") or []
        if isinstance(row, Mapping) and row.get("decision_id")
    }
    for trade in replay["trades"]:
        prior_closed[str(trade["decision_id"])] = dict(trade)
    closed_trades = sorted(
        prior_closed.values(),
        key=lambda row: (
            str(row.get("exit_date")),
            str(row.get("decision_id")),
        ),
    )
    prior_closed_ids = {
        str(row.get("decision_id"))
        for row in previous.get("closed_trades") or []
        if isinstance(row, Mapping) and row.get("decision_id")
    }
    newly_closed = [
        row for row in replay["trades"] if str(row["decision_id"]) not in prior_closed_ids
    ]

    pending_rows = [
        dict(row) for row in replay["skipped"] if row.get("reason") in _PENDING_REASONS
    ]
    open_positions = [
        row
        for row in pending_rows
        if row.get("entry_date") is not None
        and str(row.get("entry_date")) <= as_of
    ]
    pending_entries = [row for row in pending_rows if row not in open_positions]
    new_decision_ids = sorted(current_ids - previous_seen)
    return {
        "schema_version": 1,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "ticker": TICKER,
        "paper_enabled": True,
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "orders": [],
        "candidate_count": len(event_rows),
        "new_candidate_count": len(new_decision_ids),
        "pending_count": len(pending_entries),
        "open_position_count": len(open_positions),
        "closed_count_today": len(newly_closed),
        "closed_trade_count": len(closed_trades),
        "pending_entries": pending_entries,
        "open_positions": open_positions,
        "closed_trades": closed_trades,
        "new_closed_trades": newly_closed,
        "skipped": [
            row for row in replay["skipped"] if row.get("reason") not in _PENDING_REASONS
        ],
        "seen_decision_ids": sorted(previous_seen | current_ids),
        "new_decision_ids": new_decision_ids,
        "paper_notional_usd": NOTIONAL_USD,
        "hold_sessions": HOLD_SESSIONS,
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
        "price_basis": "split_and_distribution_adjusted",
        "entry_semantics": "strict_next_regular_session_adjusted_open",
        "exit_semantics": "entry_session_is_one_fifth_session_adjusted_close",
        "forward_paper_gate": {
            "passed": False,
            "reason": "historical_or_forward_evidence_not_promoted",
        },
        "production_impact": {
            "enabled": False,
            "paper_enabled": True,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "max_displacement": 0,
        },
    }


__all__ = [
    "HOLD_SESSIONS",
    "LOOKBACK_AUCTIONS",
    "MAX_CONCURRENT_POSITIONS",
    "NOTIONAL_USD",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "TICKER",
    "build_treasury_auction_tbt_snapshot",
    "build_weak_auction_events",
    "replay_weak_auction_tbt",
]
