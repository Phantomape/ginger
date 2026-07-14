"""Shared default-off FDIC Call Report deposit-repair paper sleeve.

The helper consumes plain Python records so the historical experiment runner
and a future daily observer use one policy implementation.  Availability is
fixed to the official Quarterly Banking Profile (QBP) release calendar below;
caller-supplied release dates are deliberately ignored.

This module is research-only.  Every candidate and trade is stamped
``trade_enabled=False`` and the public APIs never construct or submit orders.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Iterable, Mapping, Sequence


SLEEVE_NAME = "FDIC_CALL_REPORT_DEPOSIT_REPAIR_PAPER"
RULE_VERSION = "fdic_call_report_deposit_repair_top5_20d_v1"

# Official QBP publication dates frozen by exp-20260714-003.  A filing-quarter
# row cannot become observable before the corresponding date in this map.
QBP_RELEASE_DATES: dict[str, str] = {
    "2024Q3": "2024-12-12",
    "2024Q4": "2025-02-25",
    "2025Q1": "2025-05-28",
    "2025Q2": "2025-08-26",
    "2025Q3": "2025-11-24",
    "2025Q4": "2026-02-24",
}

MIN_BANK_ASSETS_THOUSANDS = 10_000_000.0
MIN_DOMINANT_BANK_SHARE = 0.80
MAX_ABS_ASSET_GROWTH_YOY = 0.25
QUARTERLY_TOP_N = 5
HOLD_SESSIONS = 20
BASE_NOTIONAL_USD = 4_000.0
ROUND_TRIP_COST_PCT = 0.0035


def _field(row: Mapping[str, Any], *names: str) -> Any:
    """Return the first named field, accepting case-only FDIC variations."""

    for name in names:
        if name in row:
            return row[name]
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso_date(value: Any) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _quarter_from_date(value: Any) -> str | None:
    day = _iso_date(value)
    if day is None:
        return None
    parsed = date.fromisoformat(day)
    return f"{parsed.year}Q{(parsed.month - 1) // 3 + 1}"


def _canonical_quarter(value: Any) -> str | None:
    text = str(value or "").upper().strip().replace("-", "").replace("_", "")
    text = "".join(text.split())
    if len(text) == 6 and text[:4].isdigit() and text[4] == "Q" and text[5] in "1234":
        return text
    if len(text) == 6 and text[0] == "Q" and text[1] in "1234" and text[2:].isdigit():
        return f"{text[2:]}Q{text[1]}"
    return None


def _previous_year_quarter(quarter: str) -> str:
    return f"{int(quarter[:4]) - 1}{quarter[4:]}"


def _record_identity(row: Mapping[str, Any]) -> str:
    raw = _field(row, "bank_id", "CERT", "cert", "fdic_cert")
    text = str(raw or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text:
        return text
    return str(_field(row, "bank_name", "NAME", "name") or "").strip()


def _canonical_identifier(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _normalise_record(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    explicit_quarter = _canonical_quarter(_field(row, "quarter", "reporting_quarter"))
    report_date = _iso_date(_field(row, "report_date", "REPDTE", "repdte"))
    dated_quarter = _quarter_from_date(report_date)
    if explicit_quarter and dated_quarter and explicit_quarter != dated_quarter:
        return None, "inconsistent_quarter_and_report_date"
    quarter = explicit_quarter or dated_quarter
    ticker = str(_field(row, "ticker", "TICKER") or "").strip().upper()
    bank_id = _record_identity(row)
    parent_group_id = ""
    for parent_field in ("parent_group_id", "RSSDHCR", "current_parent_rssd"):
        parent_group_id = _canonical_identifier(_field(row, parent_field))
        if parent_group_id:
            break
    if parent_group_id:
        parent_group_id_source = "regulatory_parent_id"
    elif ticker:
        # Compatibility for legacy fixtures and pre-normalised records only.
        # The audit makes this weaker identity visible to every caller.
        parent_group_id = f"TICKER:{ticker}"
        parent_group_id_source = "ticker_fallback"
    else:
        parent_group_id_source = "missing"
    bank_name = str(_field(row, "bank_name", "NAME", "name") or "").strip()
    bank_assets = _finite_float(
        _field(row, "bank_assets_thousands", "ASSET", "asset")
    )
    parent_assets = _finite_float(
        _field(
            row,
            "parent_group_assets_thousands",
            "parent_group_assets",
            "parent_assets_thousands",
            "PARENT_ASSET",
        )
    )
    core_deposits = _finite_float(
        _field(row, "core_deposits_thousands", "COREDEP", "coredep")
    )
    uninsured_deposits = _finite_float(
        _field(row, "uninsured_deposits_thousands", "DEPUNINS", "depunins")
    )
    domestic_deposits = _finite_float(
        _field(
            row,
            "domestic_deposits_thousands",
            "total_domestic_deposits_thousands",
            "DEPDOM",
            "depdom",
        )
    )
    if not quarter or not ticker or not bank_id or not parent_group_id:
        return None, "missing_identity_or_quarter"
    if any(
        value is None
        for value in (
            bank_assets,
            parent_assets,
            core_deposits,
            uninsured_deposits,
            domestic_deposits,
        )
    ):
        return None, "missing_required_fdic_field"
    assert bank_assets is not None
    assert parent_assets is not None
    assert core_deposits is not None
    assert uninsured_deposits is not None
    assert domestic_deposits is not None
    if (
        bank_assets <= 0
        or parent_assets <= 0
        or core_deposits < 0
        or uninsured_deposits < 0
        or domestic_deposits <= 0
    ):
        return None, "invalid_nonpositive_fdic_field"
    return (
        {
            "quarter": quarter,
            "report_date": report_date,
            "ticker": ticker,
            "parent_group_id": parent_group_id,
            "parent_group_id_source": parent_group_id_source,
            "bank_id": bank_id,
            "bank_name": bank_name,
            "bank_assets_thousands": bank_assets,
            "parent_group_assets_thousands": parent_assets,
            "core_deposits_thousands": core_deposits,
            "uninsured_deposits_thousands": uninsured_deposits,
            "domestic_deposits_thousands": domestic_deposits,
        },
        None,
    )


def _normalise_trading_dates(values: Iterable[Any]) -> list[str]:
    days: set[str] = set()
    for value in values:
        if isinstance(value, Mapping):
            value = _field(value, "date", "Date")
        day = _iso_date(value)
        if day:
            days.add(day)
    return sorted(days)


def _next_trading_date(release_date: str, trading_dates: Sequence[str]) -> str | None:
    # Strictly greater is intentional: same-day availability is never used.
    return next((day for day in trading_dates if day > release_date), None)


def _production_impact() -> dict[str, bool]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "alters_live_orders": False,
        "alters_core_signal_generation": False,
        "alters_core_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }


def build_fdic_call_report_deposit_repair_candidates(
    *,
    records: Iterable[Mapping[str, Any]],
    trading_dates: Iterable[Any],
    start: str | None = None,
    end: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the fixed quarterly top-five candidate set.

    ``records`` must include the current and prior-year quarter for the same
    FDIC bank identity.  When a listed parent maps to multiple insured banks,
    only the largest current bank is considered and it must represent at least
    80% of parent-group assets.
    """

    raw_rows = list(records)
    reject_totals: Counter[str] = Counter()
    normalised: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            reject_totals["invalid_record_type"] += 1
            continue
        row, reason = _normalise_record(raw)
        if row is None:
            reject_totals[reason or "invalid_record"] += 1
            continue
        normalised.append(row)

    dates = _normalise_trading_dates(trading_dates)
    start_iso = _iso_date(start) if start is not None else None
    end_iso = _iso_date(end) if end is not None else None
    if start is not None and start_iso is None:
        raise ValueError(f"invalid start date: {start!r}")
    if end is not None and end_iso is None:
        raise ValueError(f"invalid end date: {end!r}")

    by_quarter_bank: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_quarter_parent: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in normalised:
        by_quarter_bank[(row["quarter"], row["bank_id"])].append(row)
        by_quarter_parent[(row["quarter"], row["parent_group_id"])].append(row)

    tickers_by_parent_group = {
        key: {row["ticker"] for row in rows}
        for key, rows in by_quarter_parent.items()
    }
    parent_groups_by_ticker: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in normalised:
        parent_groups_by_ticker[(row["quarter"], row["ticker"])].add(
            row["parent_group_id"]
        )
    ambiguous_parent_groups = {
        key
        for key, tickers in tickers_by_parent_group.items()
        if key[0] in QBP_RELEASE_DATES and len(tickers) > 1
    }
    ambiguous_tickers = {
        key
        for key, parent_groups in parent_groups_by_ticker.items()
        if key[0] in QBP_RELEASE_DATES and len(parent_groups) > 1
    }
    qualified_by_quarter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    quarter_rows_considered = 0
    out_of_window_parent_quarter_groups = 0
    missing_next_trading_date_parent_quarter_groups = 0
    scoped_ambiguous_parent_groups: set[tuple[str, str]] = set()
    scoped_ambiguous_tickers: set[tuple[str, str]] = set()
    for (quarter, parent_group_id), group in sorted(by_quarter_parent.items()):
        if quarter not in QBP_RELEASE_DATES:
            continue
        release_date = QBP_RELEASE_DATES[quarter]
        entry_date = _next_trading_date(release_date, dates)
        if entry_date is None:
            missing_next_trading_date_parent_quarter_groups += 1
            continue
        if (start_iso and entry_date < start_iso) or (
            end_iso and entry_date > end_iso
        ):
            out_of_window_parent_quarter_groups += 1
            continue
        # Gate 3's generated denominator is window-local and precedes every
        # financial/identity filter.  Groups whose official strict-next-open
        # entry is outside this replay window are measurement context, not
        # generated signals for the window.
        quarter_rows_considered += 1
        if (quarter, parent_group_id) in ambiguous_parent_groups:
            if (quarter, parent_group_id) not in scoped_ambiguous_parent_groups:
                reject_totals["parent_group_multiple_tickers"] += 1
                scoped_ambiguous_parent_groups.add((quarter, parent_group_id))
            continue
        ticker = next(iter(tickers_by_parent_group[(quarter, parent_group_id)]))
        if (quarter, ticker) in ambiguous_tickers:
            if (quarter, ticker) not in scoped_ambiguous_tickers:
                reject_totals["ticker_multiple_parent_groups"] += 1
                scoped_ambiguous_tickers.add((quarter, ticker))
            continue
        # The dominant insured bank is the largest subsidiary at that quarter.
        current = sorted(
            group,
            key=lambda row: (-row["bank_assets_thousands"], row["bank_id"]),
        )[0]
        if current["bank_assets_thousands"] < MIN_BANK_ASSETS_THOUSANDS:
            reject_totals["bank_assets_below_10bn"] += 1
            continue
        dominance_ratio = (
            current["bank_assets_thousands"]
            / current["parent_group_assets_thousands"]
        )
        if dominance_ratio < MIN_DOMINANT_BANK_SHARE:
            reject_totals["dominant_bank_share_below_80pct"] += 1
            continue

        prior_quarter = _previous_year_quarter(quarter)
        prior_rows = by_quarter_bank.get((prior_quarter, current["bank_id"]), [])
        if not prior_rows:
            reject_totals["missing_exact_bank_prior_year"] += 1
            continue
        # Duplicate source rows fail deterministically toward the largest asset
        # observation; source manifests can still expose duplicates upstream.
        prior = sorted(
            prior_rows,
            key=lambda row: (-row["bank_assets_thousands"], row["ticker"]),
        )[0]
        if prior["core_deposits_thousands"] <= 0:
            reject_totals["invalid_prior_core_deposits"] += 1
            continue

        current_share = (
            current["uninsured_deposits_thousands"]
            / current["domestic_deposits_thousands"]
        )
        prior_share = (
            prior["uninsured_deposits_thousands"]
            / prior["domestic_deposits_thousands"]
        )
        if not (0.0 <= current_share <= 1.0 and 0.0 <= prior_share <= 1.0):
            reject_totals["invalid_uninsured_deposit_share"] += 1
            continue
        core_growth = (
            current["core_deposits_thousands"]
            / prior["core_deposits_thousands"]
            - 1.0
        )
        if core_growth <= 0:
            reject_totals["core_deposits_yoy_not_positive"] += 1
            continue
        uninsured_share_delta = current_share - prior_share
        if uninsured_share_delta >= 0:
            reject_totals["uninsured_share_yoy_not_declining"] += 1
            continue
        asset_growth = (
            current["bank_assets_thousands"] / prior["bank_assets_thousands"] - 1.0
        )
        if abs(asset_growth) > MAX_ABS_ASSET_GROWTH_YOY:
            reject_totals["asset_growth_merger_gate"] += 1
            continue

        qualified_by_quarter[quarter].append(
            {
                **current,
                "prior_year_quarter": prior_quarter,
                "release_date": release_date,
                "availability_date": release_date,
                "signal_date": release_date,
                "entry_date": entry_date,
                "dominant_bank_asset_share": round(dominance_ratio, 10),
                "core_deposits_yoy_growth": round(core_growth, 10),
                "uninsured_deposit_share": round(current_share, 10),
                "prior_uninsured_deposit_share": round(prior_share, 10),
                "uninsured_deposit_share_denominator": "DEPDOM",
                "uninsured_deposit_share_formula": "DEPUNINS/DEPDOM",
                "uninsured_share_yoy_delta": round(uninsured_share_delta, 10),
                "asset_growth_yoy": round(asset_growth, 10),
                # More negative is better; retain the raw delta for transparent
                # ascending ranking rather than inventing a tunable score.
                "rank_value": round(uninsured_share_delta, 10),
                "hold_sessions": HOLD_SESSIONS,
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "rule_version": RULE_VERSION,
                "sleeve": SLEEVE_NAME,
                "trade_enabled": False,
                "alters_orders": False,
                "paper_status": "pending",
            }
        )

    selected: list[dict[str, Any]] = []
    eligible_by_quarter: dict[str, int] = {}
    selected_by_quarter: dict[str, int] = {}
    for quarter in sorted(qualified_by_quarter):
        ranked = sorted(
            qualified_by_quarter[quarter],
            key=lambda row: (
                row["uninsured_share_yoy_delta"],
                row["ticker"],
                row["bank_id"],
            ),
        )
        eligible_by_quarter[quarter] = len(ranked)
        chosen = ranked[:QUARTERLY_TOP_N]
        reject_totals["quarterly_top5_limit"] += max(0, len(ranked) - len(chosen))
        for rank, row in enumerate(chosen, start=1):
            decision_id = (
                f"{SLEEVE_NAME}:{RULE_VERSION}:{quarter}:"
                f"{row['parent_group_id']}:{row['ticker']}:{row['bank_id']}"
            )
            selected.append(
                {
                    **row,
                    "quarter_rank": rank,
                    "decision_id": decision_id,
                }
            )
        selected_by_quarter[quarter] = len(chosen)

    audit = {
        "rule_version": RULE_VERSION,
        "input_record_count": len(raw_rows),
        "normalised_record_count": len(normalised),
        "parent_group_id_fallback_record_count": sum(
            row["parent_group_id_source"] == "ticker_fallback"
            for row in normalised
        ),
        "parent_group_id_regulatory_record_count": sum(
            row["parent_group_id_source"] == "regulatory_parent_id"
            for row in normalised
        ),
        "quarter_rows_considered": quarter_rows_considered,
        "out_of_window_parent_quarter_groups": out_of_window_parent_quarter_groups,
        "missing_next_trading_date_parent_quarter_groups": (
            missing_next_trading_date_parent_quarter_groups
        ),
        "fundamental_qualified_count": sum(eligible_by_quarter.values()),
        "selected_count": len(selected),
        "eligible_by_quarter": eligible_by_quarter,
        "selected_by_quarter": selected_by_quarter,
        "ambiguous_parent_groups": [
            {
                "quarter": quarter,
                "parent_group_id": parent_group_id,
                "tickers": sorted(
                    tickers_by_parent_group[(quarter, parent_group_id)]
                ),
            }
            for quarter, parent_group_id in sorted(
                scoped_ambiguous_parent_groups
            )
        ],
        "ambiguous_tickers": [
            {
                "quarter": quarter,
                "ticker": ticker,
                "parent_group_ids": sorted(
                    parent_groups_by_ticker[(quarter, ticker)]
                ),
            }
            for quarter, ticker in sorted(scoped_ambiguous_tickers)
        ],
        "reject_totals": dict(sorted(reject_totals.items())),
        "release_dates": dict(QBP_RELEASE_DATES),
        "uninsured_deposit_share_denominator": "DEPDOM",
        "uninsured_deposit_share_formula": "DEPUNINS/DEPDOM",
        "production_impact": _production_impact(),
    }
    return selected, audit


def _normalise_bars(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        day = _iso_date(_field(row, "date", "Date"))
        open_price = _finite_float(_field(row, "open", "Open"))
        high = _finite_float(_field(row, "high", "High"))
        low = _finite_float(_field(row, "low", "Low"))
        close = _finite_float(_field(row, "close", "Close"))
        if day and open_price and close and open_price > 0 and close > 0:
            output[day] = {
                "date": day,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
            }
    return [output[day] for day in sorted(output)]


def _atr_target(rows: Sequence[Mapping[str, Any]], entry_idx: int, entry_price: float) -> float:
    true_ranges: list[float] = []
    end_idx = max(0, entry_idx - 1)
    for idx in range(max(0, end_idx - 13), end_idx + 1):
        high = _finite_float(rows[idx].get("high"))
        low = _finite_float(rows[idx].get("low"))
        close = _finite_float(rows[idx].get("close"))
        if high is None or low is None or close is None:
            continue
        previous_close = (
            _finite_float(rows[idx - 1].get("close")) if idx > 0 else close
        )
        if previous_close is None:
            continue
        true_ranges.append(
            max(high - low, abs(high - previous_close), abs(low - previous_close))
        )
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry_price * 0.02
    return round(entry_price + 3.5 * atr, 4)


def replay_fdic_call_report_deposit_repair_paper_trades(
    *,
    records: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]],
    start: str,
    end: str,
) -> dict[str, Any]:
    """Replay the shared policy with next-open entry and a 20-session close."""

    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    market = bars.get("SPY") or []
    trading_dates = [row["date"] for row in market]
    if not trading_dates:
        return {
            "selected_candidates": [],
            "trades": [],
            "unsettled": [],
            "reject_totals": {"missing_spy_trading_calendar": 1},
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": 0.0,
            "trade_enabled": False,
            "orders": [],
            "production_impact": _production_impact(),
        }

    selected, audit = build_fdic_call_report_deposit_repair_candidates(
        records=records,
        trading_dates=trading_dates,
        start=start,
        end=end,
    )
    end_iso = _iso_date(end)
    if end_iso is None:
        raise ValueError(f"invalid end date: {end!r}")
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    replay_rejects: Counter[str] = Counter(audit["reject_totals"])
    for candidate in selected:
        rows = bars.get(candidate["ticker"]) or []
        index = {row["date"]: idx for idx, row in enumerate(rows)}
        entry_idx = index.get(candidate["entry_date"])
        if entry_idx is None:
            replay_rejects["missing_ticker_entry_bar"] += 1
            unsettled.append(
                {**candidate, "unsettled_reason": "missing_ticker_entry_bar"}
            )
            continue
        exit_idx = entry_idx + HOLD_SESSIONS - 1
        if exit_idx >= len(rows) or rows[exit_idx]["date"] > end_iso:
            replay_rejects["incomplete_20_session_horizon"] += 1
            unsettled.append(
                {**candidate, "unsettled_reason": "incomplete_20_session_horizon"}
            )
            continue
        entry_price = rows[entry_idx].get("open")
        exit_price = rows[exit_idx].get("close")
        if not entry_price or not exit_price:
            replay_rejects["missing_entry_or_exit_price"] += 1
            unsettled.append(
                {**candidate, "unsettled_reason": "missing_entry_or_exit_price"}
            )
            continue
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                "exit_date": rows[exit_idx]["date"],
                "entry_price": round(float(entry_price), 4),
                "exit_price": round(float(exit_price), 4),
                "target_price": _atr_target(rows, entry_idx, float(entry_price)),
                "hold_sessions_realized": HOLD_SESSIONS,
                "scheduled_exit_date": rows[exit_idx]["date"],
                "exit_reason": "scheduled_20_session_horizon_close",
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(BASE_NOTIONAL_USD * net_return, 2),
                "paper_status": "closed",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    generated = int(audit["quarter_rows_considered"])
    survived = len(selected)
    return {
        "selected_candidates": selected,
        "trades": trades,
        "unsettled": unsettled,
        "candidate_audit": audit,
        "reject_totals": dict(sorted(replay_rejects.items())),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else 0.0,
        "trade_enabled": False,
        "orders": [],
        "production_impact": _production_impact(),
    }


def build_fdic_call_report_deposit_repair_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    records: Iterable[Mapping[str, Any]],
    trading_dates: Iterable[Any],
) -> dict[str, Any]:
    """Return release-day paper candidates without touching an order path."""

    as_of = _iso_date(as_of_date)
    if as_of is None:
        raise ValueError(f"invalid as_of_date: {as_of_date!r}")
    candidates, audit = build_fdic_call_report_deposit_repair_candidates(
        records=records,
        trading_dates=trading_dates,
    )
    released_today = [row for row in candidates if row["release_date"] == as_of]
    return {
        "schema": "fdic_call_report_deposit_repair_paper_snapshot_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "candidate_count": len(released_today),
        "pending_count": len(released_today),
        "candidates": released_today,
        "pending_entries": released_today,
        "orders": [],
        "audit": audit,
        "strategy_behavior_changed": False,
        "alters_orders": False,
        "production_impact": _production_impact(),
    }
