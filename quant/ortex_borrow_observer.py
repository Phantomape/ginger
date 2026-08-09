"""Default-off ORTEX cost-to-borrow-new observer.

This module turns the key-free, normalised ORTEX sidecar into two generic
measurement surfaces:

* one immutable daily snapshot per ``as_of`` date; and
* H5/H10 cash/SPY/QQQ outcomes for every source row that has aligned prices.

The generic snapshot/outcome populations remain unfiltered.  The daily
snapshot additionally embeds the shared borrow-stress entry-admission policy
as a nested default-off observation; it does not alter generic settlement,
ranking, sizing, orders, or strategy behavior.  Every artifact is
``trade_enabled=False``.  Network refresh is opt-in at this API boundary and
is delegated to the credit-guarded sidecar.
"""

from __future__ import annotations

import bisect
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

try:
    import ortex_data_sidecar as sidecar
    import ortex_borrow_entry_gate as entry_gate
    from data_paths import atomic_write_json, atomic_write_text
except ModuleNotFoundError:  # package import in tooling outside quant/
    from quant import ortex_borrow_entry_gate as entry_gate
    from quant import ortex_data_sidecar as sidecar
    from quant.data_paths import atomic_write_json, atomic_write_text


OBSERVER_NAME = "ortex_cost_to_borrow_new_observer"
OUTCOME_RULE_VERSION = "usable_session_open_to_n_sessions_later_close_v1"
DEFAULT_HORIZONS = (5, 10)
DEFAULT_NOTIONAL_USD = 1000.0
DEFAULT_MAX_PROVIDER_LAG_SESSIONS = 5
DEFAULT_MAX_PROVIDER_LAG_CALENDAR_DAYS = 7
FRESHNESS_RULE_VERSION = "provider_content_age_sessions_v1"

OBSERVER_DIR = sidecar.DEFAULT_OUTPUT_DIR / "borrow_observer"
SNAPSHOT_LEDGER_PATH = OBSERVER_DIR / "daily_snapshots.jsonl"
LATEST_SNAPSHOT_PATH = OBSERVER_DIR / "latest_snapshot.json"
OUTCOME_LEDGER_PATH = OBSERVER_DIR / "generic_outcomes.jsonl"
LATEST_OUTCOME_SUMMARY_PATH = OBSERVER_DIR / "latest_outcome_summary.json"

FIXED_RESEARCH_TICKERS = sidecar.FIXED_RESEARCH_TICKERS
HISTORICAL_BLOCKS = sidecar.HISTORICAL_BLOCKS
materialize_historical_blocks = sidecar.materialize_historical_blocks
materialize_daily_refresh = sidecar.materialize_daily_refresh


def _date_text(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _provider_content_age(
    provider_day: str,
    as_of_day: str,
    trading_sessions: Sequence[Any],
) -> tuple[int, int, str]:
    """Return calendar/session age without counting normal weekends as sessions.

    A complete caller calendar is authoritative (and therefore preserves
    exchange holidays).  Otherwise a weekday-only fallback is intentionally
    conservative: holidays count as possible sessions and the separate
    calendar-day limit prevents an incomplete calendar from claiming freshness
    indefinitely.
    """
    start = date.fromisoformat(provider_day)
    end = date.fromisoformat(as_of_day)
    if start > end:
        raise ValueError("provider content date cannot be after as_of")
    calendar_age = (end - start).days
    supplied = sorted(
        {
            parsed
            for raw in trading_sessions
            if (parsed := _date_text(raw)) is not None
        }
    )
    if supplied and supplied[0] <= provider_day and supplied[-1] >= as_of_day:
        session_age = sum(provider_day < day <= as_of_day for day in supplied)
        return calendar_age, session_age, "caller_supplied_trading_sessions"

    session_age = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            session_age += 1
    return calendar_age, session_age, "weekday_calendar_fallback"


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        target.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSONL at {target}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"non-object JSONL row at {target}:{line_number}")
        rows.append(row)
    return rows


def _append_records_atomic(
    path: str | Path,
    records: Iterable[Mapping[str, Any]],
    *,
    key_field: str = "record_id",
) -> dict[str, int]:
    """Append immutable observer records under the sidecar's ledger lock."""
    target = Path(path)
    incoming = [dict(record) for record in records]
    with sidecar._exclusive_ledger_lock(target):
        existing = _load_jsonl(target)
        by_key = {str(row.get(key_field) or ""): row for row in existing}
        appended: list[dict[str, Any]] = []
        duplicates = 0
        conflicts = 0
        for record in incoming:
            key = str(record.get(key_field) or "")
            if not key:
                raise ValueError(f"observer row missing {key_field}: {record!r}")
            old = by_key.get(key)
            if old is not None:
                duplicates += 1
                if old != record:
                    conflicts += 1
                continue
            by_key[key] = record
            appended.append(record)
        if appended:
            text = "\n".join(
                json.dumps(row, sort_keys=True, ensure_ascii=True)
                for row in existing + appended
            ) + "\n"
            atomic_write_text(text, target)
        return {
            "incoming": len(incoming),
            "appended": len(appended),
            "duplicates": duplicates,
            "conflicts": conflicts,
            "total": len(existing) + len(appended),
        }


def build_daily_snapshot(
    rows: Iterable[Mapping[str, Any]],
    *,
    as_of: Any,
    tickers: Sequence[str] = FIXED_RESEARCH_TICKERS,
    generated_at: str | None = None,
    trading_sessions: Iterable[Any] | None = None,
    max_provider_lag_sessions: int = DEFAULT_MAX_PROVIDER_LAG_SESSIONS,
    max_provider_lag_calendar_days: int = DEFAULT_MAX_PROVIDER_LAG_CALENDAR_DAYS,
) -> dict[str, Any]:
    """Select latest observations and fail health closed on stale content."""
    as_of_day = _date_text(as_of)
    if as_of_day is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    if max_provider_lag_sessions < 0 or max_provider_lag_calendar_days < 0:
        raise ValueError("provider freshness limits must be non-negative")
    universe = tuple(str(ticker).upper() for ticker in tickers)
    source_rows = [dict(raw) for raw in rows]
    sessions = tuple(trading_sessions) if trading_sessions is not None else ()
    latest: dict[str, dict[str, Any]] = {}
    latest_provider_content: dict[str, str] = {}
    for raw in source_rows:
        ticker = str(raw.get("ticker") or "").upper()
        provider_day = _date_text(raw.get("provider_date"))
        usable_day = _date_text(raw.get("usable_trade_date"))
        value = _number(raw.get("cost_to_borrow_new_pct"))
        if (
            ticker in universe
            and provider_day is not None
            and provider_day <= as_of_day
            and value is not None
            and provider_day > latest_provider_content.get(ticker, "")
        ):
            # Content freshness is separate from the conservative usable clock:
            # a Friday provider row is fresh on the weekend even though it is
            # not legally usable until the following session.
            latest_provider_content[ticker] = provider_day
        if (
            ticker not in universe
            or provider_day is None
            or usable_day is None
            or usable_day > as_of_day
            or value is None
        ):
            continue
        incumbent = latest.get(ticker)
        if incumbent is None or provider_day > str(incumbent["provider_date"]):
            latest[ticker] = {
                "ticker": ticker,
                "provider_date": provider_day,
                "usable_trade_date": usable_day,
                "cost_to_borrow_new_pct": value,
                "source_mode": raw.get("source_mode"),
                "source": "ortex_api_cost_to_borrow_new",
                "trade_enabled": False,
            }
    observations = [latest[ticker] for ticker in universe if ticker in latest]
    missing = [ticker for ticker in universe if ticker not in latest]
    freshness_rows: list[dict[str, Any]] = []
    stale_tickers: list[str] = []
    content_missing_tickers: list[str] = []
    for ticker in universe:
        provider_day = latest_provider_content.get(ticker)
        if provider_day is None:
            content_missing_tickers.append(ticker)
            freshness_rows.append(
                {
                    "ticker": ticker,
                    "latest_provider_date": None,
                    "content_age_calendar_days": None,
                    "content_age_sessions": None,
                    "calendar_source": None,
                    "is_fresh": False,
                    "reason": "missing_provider_content",
                }
            )
            continue
        calendar_age, session_age, calendar_source = _provider_content_age(
            provider_day,
            as_of_day,
            sessions,
        )
        # The session limit is primary with a complete trading calendar.  The
        # ~7-day calendar cap is used only by the conservative weekday fallback.
        fresh = session_age <= int(max_provider_lag_sessions)
        if calendar_source == "weekday_calendar_fallback":
            fresh = fresh and calendar_age <= int(max_provider_lag_calendar_days)
        if not fresh:
            stale_tickers.append(ticker)
        freshness_rows.append(
            {
                "ticker": ticker,
                "latest_provider_date": provider_day,
                "content_age_calendar_days": calendar_age,
                "content_age_sessions": session_age,
                "calendar_source": calendar_source,
                "is_fresh": fresh,
                "reason": "within_provider_lag_limit" if fresh else "stale_provider_content",
            }
        )

    if not observations:
        status = "no_usable_rows"
    elif stale_tickers:
        status = "stale_content"
    elif missing or content_missing_tickers:
        status = "partial"
    else:
        status = "ready"
    freshness_status = (
        "stale"
        if stale_tickers
        else ("missing_content" if content_missing_tickers else "fresh")
    )
    entry_admission = entry_gate.build_daily_entry_admission_snapshot(
        source_rows,
        as_of_day,
        sessions,
        universe,
    )
    return {
        "record_id": f"ortex_borrow_snapshot:{as_of_day}",
        "row_type": "daily_snapshot",
        "observer_name": OBSERVER_NAME,
        "as_of": as_of_day,
        "generated_at": generated_at or sidecar.utc_now_iso(),
        "status": status,
        "ready": status == "ready",
        "universe_size": len(universe),
        "coverage_count": len(observations),
        "coverage_rate": round(len(observations) / len(universe), 6) if universe else 0.0,
        "missing_tickers": missing,
        "observations": observations,
        "selection_rule": "latest_provider_row_with_usable_trade_date_lte_as_of",
        "freshness": {
            "rule_version": FRESHNESS_RULE_VERSION,
            "status": freshness_status,
            "max_provider_lag_sessions": int(max_provider_lag_sessions),
            "calendar_fallback_max_days": int(max_provider_lag_calendar_days),
            "fresh_ticker_count": len(universe)
            - len(stale_tickers)
            - len(content_missing_tickers),
            "stale_ticker_count": len(stale_tickers),
            "stale_tickers": stale_tickers,
            "missing_content_tickers": content_missing_tickers,
            "by_ticker": freshness_rows,
        },
        "entry_admission": entry_admission,
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
    }


def _bar_date(raw: Mapping[str, Any], fallback: Any = None) -> str | None:
    for key in ("date", "Date", "datetime", "Datetime", "timestamp", "Timestamp", "_date"):
        day = _date_text(raw.get(key))
        if day:
            return day
    return _date_text(fallback)


def _normalise_price_history(
    price_history_by_ticker: Mapping[str, Any],
    *,
    as_of: str | None,
) -> dict[str, dict[str, dict[str, float | str]]]:
    """Accept list-of-bars or date->bar/price mappings without a provider dependency."""
    cutoff = _date_text(as_of) if as_of is not None else None
    result: dict[str, dict[str, dict[str, float | str]]] = {}
    for ticker_value, payload in (price_history_by_ticker or {}).items():
        ticker = str(ticker_value).upper()
        candidates: list[tuple[Any, Any]] = []
        if hasattr(payload, "iterrows"):
            # pandas.DataFrame and warehouse frame-likes: keep the index as
            # the fallback date without importing pandas here.
            candidates = list(payload.iterrows())
        elif isinstance(payload, Mapping):
            embedded = payload.get("rows")
            if isinstance(embedded, list):
                candidates = [(None, raw) for raw in embedded]
            else:
                candidates = list(payload.items())
        elif isinstance(payload, list):
            candidates = [(None, raw) for raw in payload]
        bars: dict[str, dict[str, float | str]] = {}
        for fallback_day, raw in candidates:
            if not isinstance(raw, Mapping) and hasattr(raw, "to_dict"):
                raw = raw.to_dict()
            if isinstance(raw, Mapping):
                day = _bar_date(raw, fallback_day)
                open_price = next(
                    (_number(raw.get(key)) for key in ("Open", "open", "price") if _number(raw.get(key)) is not None),
                    None,
                )
                close_price = next(
                    (_number(raw.get(key)) for key in ("Close", "close", "price") if _number(raw.get(key)) is not None),
                    None,
                )
            else:
                day = _date_text(fallback_day)
                open_price = close_price = _number(raw)
            if day is None or (cutoff and day > cutoff):
                continue
            # A close-only mapping is an explicit generic price mapping.  Use
            # that value for the entry proxy rather than discarding the row.
            if open_price is None:
                open_price = close_price
            if close_price is None:
                close_price = open_price
            if not open_price or not close_price or open_price <= 0 or close_price <= 0:
                continue
            bars[day] = {"date": day, "open": open_price, "close": close_price}
        result[ticker] = bars
    return result


def build_generic_horizon_outcomes(
    source_rows: Iterable[Mapping[str, Any]],
    price_history_by_ticker: Mapping[str, Any],
    *,
    as_of: Any | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    notional_usd: float = DEFAULT_NOTIONAL_USD,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Settle all source rows at H5/H10 against cash, SPY, and QQQ.

    No CTB threshold or sign is consulted.  The source population itself is
    the population being measured.
    """
    as_of_day = _date_text(as_of) if as_of is not None else None
    if as_of is not None and as_of_day is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    if notional_usd <= 0:
        raise ValueError("notional_usd must be positive")
    horizon_values = tuple(sorted({int(value) for value in horizons if int(value) > 0}))
    if not horizon_values:
        raise ValueError("at least one positive horizon is required")
    bars = _normalise_price_history(price_history_by_ticker, as_of=as_of_day)
    spy_sessions = set(bars.get("SPY", {}))
    qqq_sessions = set(bars.get("QQQ", {}))
    # The horizon calendar must not silently contract when either comparator
    # has a missing bar.  Use the union as the session spine and let the
    # required-bar check classify the gap as missing data.
    sessions = sorted(spy_sessions | qqq_sessions)
    outcomes: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    source_count = 0

    def mark(status: str) -> None:
        status_counts[status] = status_counts.get(status, 0) + 1

    for raw in source_rows:
        ticker = str(raw.get("ticker") or "").upper()
        provider_day = _date_text(raw.get("provider_date"))
        entry_day = _date_text(raw.get("usable_trade_date"))
        ctb = _number(raw.get("cost_to_borrow_new_pct"))
        if not ticker or provider_day is None or entry_day is None or ctb is None:
            continue
        source_count += 1
        entry_index = bisect.bisect_left(sessions, entry_day)
        aligned_entry = entry_index < len(sessions) and sessions[entry_index] == entry_day
        for horizon in horizon_values:
            if not aligned_entry:
                mark("missing_aligned_entry_session")
                continue
            # H5/H10 means the fifth/tenth full session *after* the usable
            # entry session, not an inclusive holding-day count.
            exit_index = entry_index + horizon
            if exit_index >= len(sessions):
                mark("unsettled_horizon")
                continue
            exit_day = sessions[exit_index]
            ticker_entry = bars.get(ticker, {}).get(entry_day)
            ticker_exit = bars.get(ticker, {}).get(exit_day)
            spy_entry = bars.get("SPY", {}).get(entry_day)
            spy_exit = bars.get("SPY", {}).get(exit_day)
            qqq_entry = bars.get("QQQ", {}).get(entry_day)
            qqq_exit = bars.get("QQQ", {}).get(exit_day)
            if any(
                value is None
                for value in (ticker_entry, ticker_exit, spy_entry, spy_exit, qqq_entry, qqq_exit)
            ):
                mark("missing_aligned_price")
                continue
            entry_price = float(ticker_entry["open"])
            exit_price = float(ticker_exit["close"])
            spy_entry_price = float(spy_entry["open"])
            spy_exit_price = float(spy_exit["close"])
            qqq_entry_price = float(qqq_entry["open"])
            qqq_exit_price = float(qqq_exit["close"])
            ticker_return = exit_price / entry_price - 1.0
            spy_return = spy_exit_price / spy_entry_price - 1.0
            qqq_return = qqq_exit_price / qqq_entry_price - 1.0
            pnl = notional_usd * ticker_return
            spy_pnl = notional_usd * spy_return
            qqq_pnl = notional_usd * qqq_return
            outcomes.append(
                {
                    "record_id": f"ortex_borrow_outcome:{ticker}:{provider_day}:h{horizon}",
                    "row_type": "generic_outcome",
                    "observer_name": OBSERVER_NAME,
                    "outcome_rule_version": OUTCOME_RULE_VERSION,
                    "ticker": ticker,
                    "provider_date": provider_day,
                    "usable_trade_date": entry_day,
                    "cost_to_borrow_new_pct": ctb,
                    "source_mode": raw.get("source_mode"),
                    "horizon_trading_days": horizon,
                    "entry_date": entry_day,
                    "entry_open": round(entry_price, 8),
                    "exit_date": exit_day,
                    "exit_close": round(exit_price, 8),
                    "ticker_return_pct": round(100.0 * ticker_return, 8),
                    "cash_return_pct": 0.0,
                    "spy_return_pct": round(100.0 * spy_return, 8),
                    "qqq_return_pct": round(100.0 * qqq_return, 8),
                    "excess_vs_cash_pct": round(100.0 * ticker_return, 8),
                    "excess_vs_spy_pct": round(100.0 * (ticker_return - spy_return), 8),
                    "excess_vs_qqq_pct": round(100.0 * (ticker_return - qqq_return), 8),
                    "notional_usd": float(notional_usd),
                    "pnl_usd": round(pnl, 2),
                    "replacement_value_vs_cash_usd": round(pnl, 2),
                    "replacement_value_vs_spy_usd": round(pnl - spy_pnl, 2),
                    "replacement_value_vs_qqq_usd": round(pnl - qqq_pnl, 2),
                    "comparator_detail": {
                        "SPY": {
                            "entry_open": round(spy_entry_price, 8),
                            "exit_close": round(spy_exit_price, 8),
                            "pnl_usd": round(spy_pnl, 2),
                        },
                        "QQQ": {
                            "entry_open": round(qqq_entry_price, 8),
                            "exit_close": round(qqq_exit_price, 8),
                            "pnl_usd": round(qqq_pnl, 2),
                        },
                    },
                    "outcome_status": "settled",
                    "observer_only": True,
                    "strategy_behavior_changed": False,
                    "trade_enabled": False,
                }
            )
            mark("settled")
    summary = {
        "observer_name": OBSERVER_NAME,
        "outcome_rule_version": OUTCOME_RULE_VERSION,
        "as_of": as_of_day,
        "source_row_count": source_count,
        "candidate_outcome_count": source_count * len(horizon_values),
        "settled_count": len(outcomes),
        "unsettled_count": source_count * len(horizon_values) - len(outcomes),
        "status_counts": dict(sorted(status_counts.items())),
        "horizons": list(horizon_values),
        "notional_usd": float(notional_usd),
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
    }
    return outcomes, summary


def run_ortex_borrow_observer_cycle(
    *,
    as_of: Any,
    price_history_by_ticker: Mapping[str, Any] | None = None,
    refresh_network: bool = False,
    trading_dates: Iterable[Any] | None = None,
    tickers: Sequence[str] = FIXED_RESEARCH_TICKERS,
    rows_path: str | Path = sidecar.NORMALIZED_ROWS_PATH,
    snapshot_ledger_path: str | Path = SNAPSHOT_LEDGER_PATH,
    latest_snapshot_path: str | Path = LATEST_SNAPSHOT_PATH,
    outcome_ledger_path: str | Path = OUTCOME_LEDGER_PATH,
    latest_outcome_summary_path: str | Path = LATEST_OUTCOME_SUMMARY_PATH,
    api_key: str | None = None,
    fetcher: Callable[..., Any] = sidecar.fetch_cost_to_borrow_new_payload,
    max_refresh_tickers: int = 4,
    min_refresh_age_days: int = 5,
    credit_budget: float = 50.0,
    min_credits_left: float = 250.0,
    estimated_credits_per_request: float = sidecar.DEFAULT_ESTIMATED_CREDITS_PER_REQUEST,
    request_interval_s: float = sidecar.DEFAULT_REQUEST_INTERVAL_S,
    max_provider_lag_sessions: int = DEFAULT_MAX_PROVIDER_LAG_SESSIONS,
    max_provider_lag_calendar_days: int = DEFAULT_MAX_PROVIDER_LAG_CALENDAR_DAYS,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    notional_usd: float = DEFAULT_NOTIONAL_USD,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Run one observer cycle; default operation is entirely local/read-only input.

    ``refresh_network=True`` requires a caller-supplied trading calendar and
    refreshes at most four stale fixed-universe names.  The returned object is
    safe to embed in ``run.py`` reports: it contains credit counts but never the
    API key or raw provider response.
    """
    as_of_day = _date_text(as_of)
    if as_of_day is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    network_summary: dict[str, Any]
    if refresh_network:
        if trading_dates is None:
            raise ValueError("refresh_network=True requires caller-supplied trading_dates")
        network_summary = sidecar.materialize_daily_refresh(
            as_of=as_of_day,
            trading_dates=trading_dates,
            tickers=tickers,
            output_path=rows_path,
            api_key=api_key,
            fetcher=fetcher,
            max_refresh_tickers=max_refresh_tickers,
            min_refresh_age_days=min_refresh_age_days,
            credit_budget=credit_budget,
            min_credits_left=min_credits_left,
            estimated_credits_per_request=estimated_credits_per_request,
            request_interval_s=request_interval_s,
            collected_at=collected_at,
        )
    else:
        network_summary = {
            "status": "disabled",
            "requests_made": 0,
            "rows_appended": 0,
            "trade_enabled": False,
        }

    source_rows = sidecar.load_normalised_rows(rows_path)
    snapshot = build_daily_snapshot(
        source_rows,
        as_of=as_of_day,
        tickers=tickers,
        generated_at=collected_at,
        trading_sessions=trading_dates,
        max_provider_lag_sessions=max_provider_lag_sessions,
        max_provider_lag_calendar_days=max_provider_lag_calendar_days,
    )
    snapshot_merge = _append_records_atomic(snapshot_ledger_path, (snapshot,))
    atomic_write_json(snapshot, latest_snapshot_path, indent=2, ensure_ascii=True)

    if price_history_by_ticker is None:
        outcomes: list[dict[str, Any]] = []
        outcome_summary = {
            "observer_name": OBSERVER_NAME,
            "as_of": as_of_day,
            "status": "price_history_not_supplied",
            "source_row_count": len(source_rows),
            "candidate_outcome_count": 0,
            "settled_count": 0,
            "unsettled_count": 0,
            "status_counts": {},
            "horizons": list(horizons),
            "notional_usd": float(notional_usd),
            "observer_only": True,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
        }
    else:
        outcomes, outcome_summary = build_generic_horizon_outcomes(
            source_rows,
            price_history_by_ticker,
            as_of=as_of_day,
            horizons=horizons,
            notional_usd=notional_usd,
        )
    outcome_merge = _append_records_atomic(outcome_ledger_path, outcomes)
    atomic_write_json(
        {**outcome_summary, "ledger_merge": outcome_merge},
        latest_outcome_summary_path,
        indent=2,
        ensure_ascii=True,
    )
    return {
        "observer_name": OBSERVER_NAME,
        "as_of": as_of_day,
        "network_refresh": network_summary,
        "source_row_count": len(source_rows),
        "snapshot": snapshot,
        "snapshot_ledger_merge": snapshot_merge,
        "outcome_summary": outcome_summary,
        "outcome_ledger_merge": outcome_merge,
        "paths": {
            "rows": str(Path(rows_path)),
            "snapshot_ledger": str(Path(snapshot_ledger_path)),
            "latest_snapshot": str(Path(latest_snapshot_path)),
            "outcome_ledger": str(Path(outcome_ledger_path)),
            "latest_outcome_summary": str(Path(latest_outcome_summary_path)),
        },
        "api_key_persisted": False,
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
    }


__all__ = [
    "FIXED_RESEARCH_TICKERS",
    "HISTORICAL_BLOCKS",
    "materialize_historical_blocks",
    "materialize_daily_refresh",
    "build_daily_snapshot",
    "build_generic_horizon_outcomes",
    "run_ortex_borrow_observer_cycle",
]
