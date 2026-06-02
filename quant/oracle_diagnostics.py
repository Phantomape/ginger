"""Observation-only oracle diagnostics for backtest results.

This module intentionally uses future prices. It is not a tradable strategy.
Its job is to estimate how much upside was available after the system had
already entered a trade, so we can separate exit/hold regret from entry alpha.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from constants import MAX_POSITIONS, ROUND_TRIP_COST_PCT
except Exception:  # pragma: no cover - only used if constants import is broken.
    MAX_POSITIONS = 5
    ROUND_TRIP_COST_PCT = 0.0035


def _load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def infer_snapshot_path(backtest_result):
    known = backtest_result.get("known_biases") or {}
    source = known.get("ohlcv_source") or {}
    return source.get("snapshot_path")


def _ohlcv_rows_by_date(snapshot):
    rows_by_ticker = {}
    for ticker, rows in (snapshot.get("ohlcv") or {}).items():
        rows_by_ticker[ticker.upper()] = {
            row.get("Date"): row
            for row in rows or []
            if row.get("Date")
        }
    return rows_by_ticker


def _window_rows(rows_by_date, entry_date, exit_date):
    if not entry_date or not exit_date:
        return []
    return [
        row for day, row in sorted(rows_by_date.items())
        if entry_date <= day <= exit_date
    ]


def _next_rows_after(rows_by_date, signal_date, horizon_days):
    dates = sorted(rows_by_date)
    eligible = [day for day in dates if day > signal_date]
    return [rows_by_date[day] for day in eligible[:horizon_days]]


def _as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _normalize_date(raw_date):
    if raw_date is None:
        return None
    text = str(raw_date)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def _median(values):
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _ticker_rows(snapshot):
    rows_by_ticker = {}
    for ticker, rows_by_date in _ohlcv_rows_by_date(snapshot).items():
        rows_by_ticker[ticker] = [
            rows_by_date[day]
            for day in sorted(rows_by_date)
        ]
    return rows_by_ticker


def _sma(rows, end_idx, period):
    if end_idx + 1 < period:
        return None
    closes = [
        _as_float(row.get("Close"))
        for row in rows[end_idx - period + 1:end_idx + 1]
    ]
    if any(value is None for value in closes):
        return None
    return sum(closes) / len(closes)


def _period_return(rows, end_idx, period):
    if end_idx < period:
        return None
    start_close = _as_float(rows[end_idx - period].get("Close"))
    end_close = _as_float(rows[end_idx].get("Close"))
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1


def _oracle_exit_for_trade(trade, rows):
    entry_price = trade.get("entry_price")
    shares = trade.get("shares")
    if not entry_price or not shares or not rows:
        return None

    best_row = max(rows, key=lambda row: float(row.get("High") or 0))
    best_raw_high = float(best_row.get("High") or 0)
    if best_raw_high <= 0:
        return None

    # Match the backtester convention: entry_price already includes entry
    # slippage; exit cost is applied against the exit raw price.
    oracle_exit_price = best_raw_high * (1 - ROUND_TRIP_COST_PCT)
    oracle_pnl = (oracle_exit_price - entry_price) * shares
    actual_pnl = float(trade.get("pnl") or 0.0)
    regret = oracle_pnl - actual_pnl
    capture_ratio = actual_pnl / oracle_pnl if oracle_pnl > 0 else None

    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "actual_exit_date": trade.get("exit_date"),
        "oracle_exit_date": best_row.get("Date"),
        "entry_price": round(float(entry_price), 4),
        "actual_exit_price": trade.get("exit_price"),
        "oracle_exit_price": round(oracle_exit_price, 4),
        "shares": shares,
        "actual_pnl": round(actual_pnl, 2),
        "oracle_pnl": round(oracle_pnl, 2),
        "regret_vs_oracle": round(regret, 2),
        "capture_ratio": round(capture_ratio, 4) if capture_ratio is not None else None,
        "exit_reason": trade.get("exit_reason"),
    }


def _candidate_sources(backtest_result):
    sources = []
    for key in ("llm_gate_unreplayed", "news_veto_unreplayed"):
        bucket = (backtest_result.get("known_biases") or {}).get(key) or {}
        tickers_by_date = bucket.get("candidate_tickers_by_date") or {}
        if tickers_by_date:
            sources.append((key, tickers_by_date))
    return sources


def _active_trades_on_date(backtest_result, date_str):
    active = []
    for trade in backtest_result.get("trades") or []:
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        if entry_date and exit_date and entry_date <= date_str < exit_date:
            active.append(trade)
    return active


def _collect_candidate_forward_rows(backtest_result, snapshot, horizon_days):
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    actual_trade_keys = {
        (trade.get("entry_date"), (trade.get("ticker") or "").upper())
        for trade in backtest_result.get("trades") or []
    }
    seen = set()
    candidate_rows = []
    missing = []

    for source, tickers_by_date in _candidate_sources(backtest_result):
        for raw_date, tickers in tickers_by_date.items():
            signal_date = (
                f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                if len(raw_date) == 8 and raw_date.isdigit() else raw_date
            )
            for ticker in tickers or []:
                ticker = (ticker or "").upper()
                key = (signal_date, ticker)
                if key in seen:
                    continue
                seen.add(key)
                rows = rows_by_ticker.get(ticker)
                if not rows:
                    missing.append({"signal_date": signal_date, "ticker": ticker, "reason": "missing_ohlcv"})
                    continue
                forward = _next_rows_after(rows, signal_date, horizon_days)
                if not forward:
                    missing.append({"signal_date": signal_date, "ticker": ticker, "reason": "no_forward_rows"})
                    continue

                entry_row = forward[0]
                entry_open = float(entry_row.get("Open") or 0)
                if entry_open <= 0:
                    missing.append({"signal_date": signal_date, "ticker": ticker, "reason": "invalid_entry_open"})
                    continue
                best_row = max(forward, key=lambda row: float(row.get("High") or 0))
                best_high = float(best_row.get("High") or 0)
                max_return = (best_high * (1 - ROUND_TRIP_COST_PCT) / entry_open) - 1
                candidate_rows.append({
                    "signal_date": signal_date,
                    "ticker": ticker,
                    "source": source,
                    "entry_date": entry_row.get("Date"),
                    "oracle_exit_date": best_row.get("Date"),
                    "entry_open": round(entry_open, 4),
                    "oracle_exit_price": round(best_high * (1 - ROUND_TRIP_COST_PCT), 4),
                    "max_forward_return_pct": round(max_return, 6),
                    "became_actual_trade_same_entry_day": (
                        (entry_row.get("Date"), ticker) in actual_trade_keys
                    ),
                })

    return candidate_rows, missing


def build_candidate_forward_oracle(backtest_result, snapshot, horizon_days=20):
    candidate_rows, missing = _collect_candidate_forward_rows(
        backtest_result,
        snapshot,
        horizon_days,
    )

    if not candidate_rows:
        return {
            "oracle_type": "candidate_forward_upper_bound",
            "is_tradable": False,
            "lookahead_warning": "Uses future highs after candidate dates; diagnostic only.",
            "horizon_days": horizon_days,
            "candidate_count": 0,
            "missing_candidate_count": len(missing),
            "missing_candidates": missing,
        }

    returns = [row["max_forward_return_pct"] for row in candidate_rows]
    top = sorted(candidate_rows, key=lambda row: row["max_forward_return_pct"], reverse=True)[:10]
    actual_overlap = sum(1 for row in candidate_rows if row["became_actual_trade_same_entry_day"])
    positive = sum(1 for r in returns if r > 0)

    return {
        "oracle_type": "candidate_forward_upper_bound",
        "is_tradable": False,
        "lookahead_warning": (
            "Uses future highs after candidate dates. This estimates candidate-pool opportunity, "
            "not achievable strategy PnL."
        ),
        "horizon_days": horizon_days,
        "candidate_count": len(candidate_rows),
        "missing_candidate_count": len(missing),
        "positive_candidate_fraction": round(positive / len(candidate_rows), 4),
        "actual_trade_overlap_count": actual_overlap,
        "actual_trade_overlap_fraction": round(actual_overlap / len(candidate_rows), 4),
        "avg_max_forward_return_pct": round(sum(returns) / len(returns), 6),
        "median_max_forward_return_pct": round(sorted(returns)[len(returns) // 2], 6),
        "best_max_forward_return_pct": round(max(returns), 6),
        "top_candidate_opportunities": top,
        "missing_candidates": missing,
    }


def _build_skip_lookup(entry_skip_oracle_data):
    """Build a (signal_date, ticker) → list[skip_event] lookup from entry_skip_oracle JSON.

    entry_skip_oracle_data is the parsed content of an entry_skip_oracle_*.json
    file produced by quant/entry_skip_oracle.py.  Each skip event in
    ``entry_skip_oracle.top_skipped_opportunities`` (and sub-lists) carries:
      - date        : signal date (YYYY-MM-DD)
      - ticker      : ticker symbol
      - decision    : gap_cancel | no_shares | slot_sliced | stop_breach_cancel
      - details     : dict with mechanism-specific context

    Returns dict[(signal_date, ticker)] = list of skip event dicts.
    """
    lookup: dict[tuple[str, str], list[dict]] = {}
    if not entry_skip_oracle_data:
        return lookup

    oracle = entry_skip_oracle_data.get("entry_skip_oracle") or {}

    # Collect from top_skipped_opportunities (covers all decision types)
    top = oracle.get("top_skipped_opportunities") or []
    for event in top:
        date = event.get("date")
        ticker = (event.get("ticker") or "").upper()
        if date and ticker:
            key = (date, ticker)
            lookup.setdefault(key, []).append(event)

    # Also collect from gap_cancel_audit.rows (may include events not in top 10)
    for event in (oracle.get("gap_cancel_audit") or {}).get("rows") or []:
        date = event.get("date")
        ticker = (event.get("ticker") or "").upper()
        if date and ticker:
            key = (date, ticker)
            existing = [e.get("decision") for e in lookup.get(key, [])]
            if event.get("decision") not in existing:
                lookup.setdefault(key, []).append(event)

    # Also collect from no_shares_multiplier_audit sub-lists
    for _bucket, bucket_data in (oracle.get("no_shares_multiplier_audit") or {}).items():
        for event in (bucket_data or {}).get("rows") or []:
            date = event.get("date")
            ticker = (event.get("ticker") or "").upper()
            if date and ticker:
                key = (date, ticker)
                existing = [e.get("decision") for e in lookup.get(key, [])]
                if event.get("decision") not in existing:
                    lookup.setdefault(key, []).append(event)

    return lookup


def _skip_reason_from_events(skip_events):
    """Summarise a list of skip events for one (signal_date, ticker) into a
    compact attribution string and a list of detail dicts.

    Returns (attribution: str, skip_details: list[dict]).
    """
    if not skip_events:
        return None, []

    decisions = [e.get("decision") or "unknown" for e in skip_events]
    unique_decisions = sorted(set(decisions))
    attribution = "|".join(unique_decisions)

    details = []
    for event in skip_events:
        detail = {
            "decision": event.get("decision"),
            "candidate_rank": event.get("candidate_rank"),
            "strategy": event.get("strategy"),
        }
        raw = event.get("details") or {}
        if event.get("decision") == "gap_cancel":
            # gap_pct is stored as a top-level field on the skip event;
            # fall back to recomputing from fill_price / signal_entry if absent.
            gap_pct = event.get("gap_pct") or raw.get("gap_pct") or (
                round(
                    raw.get("fill_price", 0) / raw.get("signal_entry", 1) - 1, 4
                ) if raw.get("fill_price") and raw.get("signal_entry") else None
            )
            detail["gap_pct"] = gap_pct
            detail["signal_entry"] = raw.get("signal_entry")
            detail["cancel_gap_pct_threshold"] = raw.get("cancel_gap_pct")
        elif event.get("decision") == "no_shares":
            detail["zero_multiplier"] = (
                [k for k, v in (raw.get("risk_multipliers") or {}).items() if v == 0.0]
                or None
            )
            detail["shares_to_buy"] = raw.get("shares_to_buy")
        elif event.get("decision") == "stop_breach_cancel":
            detail["fill_price"] = raw.get("fill_price")
            detail["stop_price"] = raw.get("stop_price")
        elif event.get("decision") == "slot_sliced":
            detail["signal_count"] = raw.get("signal_count")
        details.append(detail)

    return attribution, details


def build_no_trade_attribution_oracle(
    backtest_result,
    snapshot,
    horizon_days=20,
    entry_skip_oracle_data=None,
):
    """Build the no-trade attribution table.

    Parameters
    ----------
    backtest_result:
        Parsed backtest JSON.
    snapshot:
        Parsed OHLCV snapshot JSON.
    horizon_days:
        Lookahead window for oracle forward-return estimation.
    entry_skip_oracle_data:
        Optional parsed entry_skip_oracle JSON (output of
        ``quant/entry_skip_oracle.py``).  When provided, rows that would
        otherwise be labelled ``needs_entry_skip_logging`` are enriched with
        the actual skip decision (``gap_cancel``, ``no_shares``,
        ``stop_breach_cancel``, ``slot_sliced``) and mechanism details, and
        the label ``needs_entry_skip_logging`` is replaced by the real reason.
        Rows with no matching skip event keep the label to indicate genuine
        gaps that still require investigation.
    """
    skip_lookup = _build_skip_lookup(entry_skip_oracle_data)
    skip_oracle_source = None
    if entry_skip_oracle_data:
        skip_oracle_source = entry_skip_oracle_data.get("source_backtest") or "provided"

    candidate_rows, missing = _collect_candidate_forward_rows(
        backtest_result,
        snapshot,
        horizon_days,
    )
    if not candidate_rows:
        return {
            "oracle_type": "candidate_no_trade_attribution",
            "is_tradable": False,
            "lookahead_warning": "Uses saved candidates and future rows for diagnostics only.",
            "horizon_days": horizon_days,
            "candidate_days": 0,
            "missing_candidate_count": len(missing),
            "entry_skip_oracle_source": skip_oracle_source,
            "missing_candidates": missing,
        }

    by_signal_date = {}
    for row in candidate_rows:
        by_signal_date.setdefault(row["signal_date"], []).append(row)

    rows = []
    reason_counts = {}
    for signal_date, candidates in sorted(by_signal_date.items()):
        actual = [row for row in candidates if row["became_actual_trade_same_entry_day"]]
        if actual:
            continue

        active = _active_trades_on_date(backtest_result, signal_date)
        active_tickers = {
            (trade.get("ticker") or "").upper()
            for trade in active
        }
        candidate_tickers = {
            (row.get("ticker") or "").upper()
            for row in candidates
        }
        slots_available = max(0, MAX_POSITIONS - len(active))
        already_holding = sorted(candidate_tickers & active_tickers)

        if already_holding:
            reason = "already_holding_candidate"
            skip_details = []
        elif slots_available < len(candidates):
            reason = "slot_competition_possible"
            skip_details = []
        else:
            # Try to resolve from entry_skip_oracle before falling back to
            # needs_entry_skip_logging.
            matched_events = []
            for candidate in candidates:
                ticker = (candidate.get("ticker") or "").upper()
                key = (signal_date, ticker)
                matched_events.extend(skip_lookup.get(key) or [])

            if matched_events:
                reason, skip_details = _skip_reason_from_events(matched_events)
            else:
                reason = "needs_entry_skip_logging"
                skip_details = []

        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        top_candidate = max(candidates, key=lambda row: row["max_forward_return_pct"])

        entry = {
            "signal_date": signal_date,
            "candidate_count": len(candidates),
            "top_candidate": top_candidate["ticker"],
            "top_candidate_return_pct": top_candidate["max_forward_return_pct"],
            "active_position_count_on_signal_date": len(active),
            "slots_available_on_signal_date": slots_available,
            "already_holding_candidate_tickers": already_holding,
            "attribution": reason,
        }
        if skip_details:
            entry["skip_details"] = skip_details
        rows.append(entry)

    missed_returns = [row["top_candidate_return_pct"] for row in rows]

    unresolved = sum(
        1 for row in rows if row["attribution"] == "needs_entry_skip_logging"
    )
    resolved = sum(
        1 for row in rows
        if row["attribution"] not in ("needs_entry_skip_logging", "already_holding_candidate", "slot_competition_possible")
    )

    lookahead_warning = (
        "This is a conservative reconstruction from saved candidates and closed trades. "
        "Rows marked needs_entry_skip_logging require explicit backtester skip-reason logs."
    )
    if skip_oracle_source:
        lookahead_warning += (
            f" entry_skip_oracle_source was joined: {resolved} row(s) resolved, "
            f"{unresolved} row(s) still unresolved."
        )

    return {
        "oracle_type": "candidate_no_trade_attribution",
        "is_tradable": False,
        "lookahead_warning": lookahead_warning,
        "horizon_days": horizon_days,
        "entry_skip_oracle_source": skip_oracle_source,
        "skip_resolution": {
            "resolved_count": resolved,
            "unresolved_count": unresolved,
            "note": (
                "resolved = attribution came from entry_skip_oracle; "
                "unresolved = still needs_entry_skip_logging"
            ),
        } if skip_oracle_source else None,
        "candidate_days": len(by_signal_date),
        "no_actual_selection_days": len(rows),
        "missing_candidate_count": len(missing),
        "reason_counts": dict(sorted(reason_counts.items())),
        "avg_missed_top_candidate_return_pct": (
            round(sum(missed_returns) / len(missed_returns), 6)
            if missed_returns else None
        ),
        "largest_no_trade_opportunities": sorted(
            rows,
            key=lambda row: row["top_candidate_return_pct"],
            reverse=True,
        )[:10],
        "missing_candidates": missing,
    }


def build_candidate_selection_oracle(backtest_result, snapshot, horizon_days=20, k_values=(1, 2, 3)):
    candidate_rows, missing = _collect_candidate_forward_rows(
        backtest_result,
        snapshot,
        horizon_days,
    )
    if not candidate_rows:
        return {
            "oracle_type": "candidate_selection_upper_bound",
            "is_tradable": False,
            "lookahead_warning": "Uses future candidate returns for ranking; diagnostic only.",
            "horizon_days": horizon_days,
            "candidate_days": 0,
            "missing_candidate_count": len(missing),
            "missing_candidates": missing,
        }

    by_signal_date = {}
    for row in candidate_rows:
        by_signal_date.setdefault(row["signal_date"], []).append(row)

    actual_rows = [
        row for row in candidate_rows
        if row["became_actual_trade_same_entry_day"]
    ]
    actual_returns = [row["max_forward_return_pct"] for row in actual_rows]

    daily_rank_regrets = []
    missed_top1 = []
    top1_actual_hits = 0
    days_with_actual = 0

    for signal_date, rows in sorted(by_signal_date.items()):
        ranked = sorted(rows, key=lambda row: row["max_forward_return_pct"], reverse=True)
        top1 = ranked[0]
        actual_for_day = [
            row for row in rows
            if row["became_actual_trade_same_entry_day"]
        ]
        if top1["became_actual_trade_same_entry_day"]:
            top1_actual_hits += 1
        else:
            missed_top1.append(top1)
        if actual_for_day:
            days_with_actual += 1
            best_actual = max(actual_for_day, key=lambda row: row["max_forward_return_pct"])
            daily_rank_regrets.append({
                "signal_date": signal_date,
                "top_candidate": top1["ticker"],
                "top_candidate_return_pct": top1["max_forward_return_pct"],
                "best_actual_candidate": best_actual["ticker"],
                "best_actual_return_pct": best_actual["max_forward_return_pct"],
                "selection_regret_pct": round(
                    top1["max_forward_return_pct"] - best_actual["max_forward_return_pct"],
                    6,
                ),
            })

    top_k_summary = {}
    for k in k_values:
        selected = []
        for rows in by_signal_date.values():
            ranked = sorted(rows, key=lambda row: row["max_forward_return_pct"], reverse=True)
            selected.extend(ranked[:k])
        returns = [row["max_forward_return_pct"] for row in selected]
        top_k_summary[f"top_{k}"] = {
            "selected_candidate_count": len(selected),
            "equal_weight_avg_max_forward_return_pct": (
                round(sum(returns) / len(returns), 6) if returns else None
            ),
            "best_selected_return_pct": round(max(returns), 6) if returns else None,
            "worst_selected_return_pct": round(min(returns), 6) if returns else None,
        }

    regret_values = [row["selection_regret_pct"] for row in daily_rank_regrets]
    missed_top1 = sorted(
        missed_top1,
        key=lambda row: row["max_forward_return_pct"],
        reverse=True,
    )[:10]
    all_missed_top1 = [
        sorted(rows, key=lambda row: row["max_forward_return_pct"], reverse=True)[0]
        for rows in by_signal_date.values()
        if not any(row["became_actual_trade_same_entry_day"] for row in rows)
    ]
    missed_top1_returns = [
        row["max_forward_return_pct"]
        for row in all_missed_top1
    ]

    return {
        "oracle_type": "candidate_selection_upper_bound",
        "is_tradable": False,
        "lookahead_warning": (
            "Ranks candidates by future returns. Use only to estimate selection/ranking headroom, "
            "never as a tradable ranking rule."
        ),
        "horizon_days": horizon_days,
        "candidate_days": len(by_signal_date),
        "candidate_count": len(candidate_rows),
        "missing_candidate_count": len(missing),
        "days_with_actual_selection": days_with_actual,
        "days_without_actual_selection": len(by_signal_date) - days_with_actual,
        "top1_actual_hit_fraction": round(top1_actual_hits / len(by_signal_date), 4),
        "actual_selected_candidate_count": len(actual_rows),
        "actual_equal_weight_avg_max_forward_return_pct": (
            round(sum(actual_returns) / len(actual_returns), 6)
            if actual_returns else None
        ),
        "missed_top1_avg_max_forward_return_pct": (
            round(sum(missed_top1_returns) / len(missed_top1_returns), 6)
            if missed_top1_returns else None
        ),
        "avg_top1_vs_actual_selection_regret_pct": (
            round(sum(regret_values) / len(regret_values), 6)
            if regret_values else None
        ),
        "top_k_summary": top_k_summary,
        "largest_daily_selection_regrets": sorted(
            daily_rank_regrets,
            key=lambda row: row["selection_regret_pct"],
            reverse=True,
        )[:10],
        "missed_top1_opportunities": missed_top1,
        "missing_candidates": missing,
    }


def _entry_state_candidate_events(backtest_result, candidate_events=None):
    if candidate_events is None:
        rows = []
        for source, tickers_by_date in _candidate_sources(backtest_result):
            for raw_date, tickers in tickers_by_date.items():
                signal_date = _normalize_date(raw_date)
                for ticker in tickers or []:
                    ticker = (ticker or "").upper()
                    if signal_date and ticker:
                        rows.append({
                            "signal_date": signal_date,
                            "ticker": ticker,
                            "strategy": None,
                            "decision": "unknown",
                            "candidate_rank": None,
                            "source": source,
                            "details": {},
                            "signal_snapshot": {},
                        })
        return rows

    if isinstance(candidate_events, dict):
        candidate_events = (
            candidate_events.get("candidate_events")
            or candidate_events.get("events")
            or []
        )

    rows = []
    for event in candidate_events or []:
        signal_date = _normalize_date(
            event.get("date")
            or event.get("signal_date")
            or event.get("as_of_date")
            or event.get("decision_date")
        )
        ticker = (event.get("ticker") or "").upper()
        if not signal_date or not ticker:
            continue
        rows.append({
            "signal_date": signal_date,
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "decision": event.get("decision") or "unknown",
            "candidate_rank": event.get("candidate_rank"),
            "source": event.get("source") or "entry_candidate_events",
            "details": event.get("details") or {},
            "signal_snapshot": event.get("signal_snapshot") or {},
        })
    return rows


def _earnings_for_candidate(earnings_by_date, signal_date, ticker):
    if not earnings_by_date:
        return {}
    bucket = (
        earnings_by_date.get(signal_date)
        or earnings_by_date.get(signal_date.replace("-", ""))
        or {}
    )
    return bucket.get(ticker) or bucket.get(ticker.upper()) or {}


def _entry_row_index(rows, signal_date, details):
    date_to_index = {
        row.get("Date"): idx
        for idx, row in enumerate(rows)
        if row.get("Date")
    }
    fill_date = _normalize_date((details or {}).get("fill_date"))
    if fill_date and fill_date in date_to_index and fill_date > signal_date:
        return date_to_index[fill_date]
    for idx, row in enumerate(rows):
        row_date = row.get("Date")
        if row_date and row_date > signal_date:
            return idx
    return None


def _entry_timing_tags(rows, signal_idx, spy_rows, signal_date, earnings):
    tags = []
    metrics = {}
    if signal_idx is None or signal_idx >= len(rows):
        return tags, metrics

    row = rows[signal_idx]
    prev_row = rows[signal_idx - 1] if signal_idx > 0 else None
    row_open = _as_float(row.get("Open"))
    row_close = _as_float(row.get("Close"))
    prev_close = _as_float(prev_row.get("Close")) if prev_row else None

    if row_open is not None and prev_close:
        gap_pct = (row_open / prev_close) - 1
        metrics["gap_pct"] = round(gap_pct, 6)
        if gap_pct >= 0.03:
            tags.append("gap_up_3pct")
        elif gap_pct <= -0.03:
            tags.append("gap_down_3pct")

    dte = earnings.get("days_to_earnings")
    try:
        dte = int(dte) if dte is not None else None
    except (TypeError, ValueError):
        dte = None
    if dte is not None:
        metrics["days_to_earnings"] = dte
        if 0 <= dte <= 7:
            tags.append("pre_earnings_0_7")
        elif 8 <= dte <= 21:
            tags.append("pre_earnings_8_21")
        elif 22 <= dte <= 45:
            tags.append("pre_earnings_22_45")
        elif dte >= 46:
            tags.append("pre_earnings_46_plus")
        elif -10 <= dte <= -1:
            tags.append("post_earnings_drift_1_10")

    for period in (20, 50):
        current_sma = _sma(rows, signal_idx, period)
        prev_sma = _sma(rows, signal_idx - 1, period) if signal_idx > 0 else None
        if row_close is not None and current_sma:
            metrics[f"sma{period}"] = round(current_sma, 4)
            if row_close > current_sma:
                tags.append(f"above_sma{period}")
            if prev_close is not None and prev_sma and prev_close <= prev_sma < row_close:
                tags.append(f"sma{period}_reclaim")

    spy_return_20 = None
    if spy_rows:
        spy_index = {
            row.get("Date"): idx
            for idx, row in enumerate(spy_rows)
            if row.get("Date")
        }
        spy_idx = spy_index.get(signal_date)
        if spy_idx is not None:
            spy_return_20 = _period_return(spy_rows, spy_idx, 20)
    stock_return_20 = _period_return(rows, signal_idx, 20)
    if stock_return_20 is not None:
        metrics["stock_return_20d"] = round(stock_return_20, 6)
    if spy_return_20 is not None:
        metrics["spy_return_20d"] = round(spy_return_20, 6)
    if stock_return_20 is not None and spy_return_20 is not None:
        excess = stock_return_20 - spy_return_20
        metrics["excess_spy_return_20d"] = round(excess, 6)
        if excess >= 0.05:
            tags.append("rs20_leader")
        elif excess <= -0.05:
            tags.append("rs20_laggard")

    if not tags:
        tags.append("untagged")
    return sorted(set(tags)), metrics


def _summarize_entry_state_tags(candidate_rows):
    by_tag = {}
    for row in candidate_rows:
        for tag in row["tags"]:
            rec = by_tag.setdefault(tag, {
                "candidate_count": 0,
                "entered_count": 0,
                "decision_counts": {},
                "strategy_counts": {},
                "_returns": [],
                "_mfe": [],
                "_mae": [],
            })
            rec["candidate_count"] += 1
            if row["decision"] == "entered":
                rec["entered_count"] += 1
            rec["decision_counts"][row["decision"]] = (
                rec["decision_counts"].get(row["decision"], 0) + 1
            )
            strategy = row.get("strategy") or "unknown"
            rec["strategy_counts"][strategy] = rec["strategy_counts"].get(strategy, 0) + 1
            if row.get("forward_return_pct") is not None:
                rec["_returns"].append(row["forward_return_pct"])
            if row.get("mfe_pct") is not None:
                rec["_mfe"].append(row["mfe_pct"])
            if row.get("mae_pct") is not None:
                rec["_mae"].append(row["mae_pct"])

    summary = {}
    for tag, rec in by_tag.items():
        returns = rec.pop("_returns")
        mfe = rec.pop("_mfe")
        mae = rec.pop("_mae")
        rec["avg_forward_return_pct"] = (
            round(sum(returns) / len(returns), 6) if returns else None
        )
        rec["median_forward_return_pct"] = (
            round(_median(returns), 6) if returns else None
        )
        rec["win_rate"] = (
            round(sum(1 for value in returns if value > 0) / len(returns), 4)
            if returns else None
        )
        rec["best_forward_return_pct"] = round(max(returns), 6) if returns else None
        rec["worst_forward_return_pct"] = round(min(returns), 6) if returns else None
        rec["avg_mfe_pct"] = round(sum(mfe) / len(mfe), 6) if mfe else None
        rec["avg_mae_pct"] = round(sum(mae) / len(mae), 6) if mae else None
        rec["decision_counts"] = dict(sorted(rec["decision_counts"].items()))
        rec["strategy_counts"] = dict(sorted(rec["strategy_counts"].items()))
        summary[tag] = rec
    return dict(sorted(
        summary.items(),
        key=lambda item: (
            item[1]["avg_forward_return_pct"] is not None,
            item[1]["avg_forward_return_pct"] or -999,
            item[1]["candidate_count"],
        ),
        reverse=True,
    ))


def build_entry_state_oracle(
    backtest_result,
    snapshot,
    candidate_events=None,
    earnings_by_date=None,
    horizon_days=20,
):
    rows_by_ticker = _ticker_rows(snapshot)
    spy_rows = rows_by_ticker.get("SPY")
    events = _entry_state_candidate_events(backtest_result, candidate_events)
    actual_trade_keys = {
        (trade.get("entry_date"), (trade.get("ticker") or "").upper())
        for trade in backtest_result.get("trades") or []
    }
    candidate_rows = []
    missing = []
    seen = set()

    for event in events:
        signal_date = event["signal_date"]
        ticker = event["ticker"]
        key = (
            signal_date,
            ticker,
            event.get("source"),
            event.get("candidate_rank"),
            event.get("decision"),
        )
        if key in seen:
            continue
        seen.add(key)

        rows = rows_by_ticker.get(ticker)
        if not rows:
            missing.append({
                "signal_date": signal_date,
                "ticker": ticker,
                "reason": "missing_ohlcv",
            })
            continue

        signal_idx = None
        for idx, row in enumerate(rows):
            if row.get("Date") == signal_date:
                signal_idx = idx
                break
        entry_idx = _entry_row_index(rows, signal_date, event.get("details"))
        if signal_idx is None:
            missing.append({
                "signal_date": signal_date,
                "ticker": ticker,
                "reason": "missing_signal_row",
            })
            continue
        if entry_idx is None:
            missing.append({
                "signal_date": signal_date,
                "ticker": ticker,
                "reason": "no_entry_row_after_signal",
            })
            continue

        forward = rows[entry_idx:entry_idx + horizon_days]
        entry_open = _as_float(forward[0].get("Open")) if forward else None
        if not entry_open:
            missing.append({
                "signal_date": signal_date,
                "ticker": ticker,
                "reason": "invalid_entry_open",
            })
            continue
        closes = [_as_float(row.get("Close")) for row in forward]
        highs = [_as_float(row.get("High")) for row in forward]
        lows = [_as_float(row.get("Low")) for row in forward]
        closes = [value for value in closes if value is not None]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]
        if not closes:
            missing.append({
                "signal_date": signal_date,
                "ticker": ticker,
                "reason": "missing_forward_close",
            })
            continue

        earnings = _earnings_for_candidate(earnings_by_date, signal_date, ticker)
        tags, metrics = _entry_timing_tags(
        rows,
        signal_idx,
        spy_rows,
        signal_date,
        earnings,
    )
        entry_date = forward[0].get("Date")
        decision = event.get("decision") or "unknown"
        row = {
            "signal_date": signal_date,
            "entry_date": entry_date,
            "ticker": ticker,
            "strategy": event.get("strategy"),
            "decision": decision,
            "candidate_rank": event.get("candidate_rank"),
            "source": event.get("source"),
            "tags": tags,
            "timing_metrics": metrics,
            "entry_open": round(entry_open, 4),
            "horizon_days": horizon_days,
            "horizon_end_date": forward[-1].get("Date"),
            "forward_return_pct": round((closes[-1] / entry_open) - 1, 6),
            "mfe_pct": round((max(highs) / entry_open) - 1, 6) if highs else None,
            "mae_pct": round((min(lows) / entry_open) - 1, 6) if lows else None,
            "became_actual_trade_same_entry_day": (
                (entry_date, ticker) in actual_trade_keys
            ),
        }
        candidate_rows.append(row)

    if not candidate_rows:
        return {
            "oracle_type": "entry_state_candidate_oracle",
            "is_tradable": False,
            "lookahead_warning": "Uses future returns after candidate entry dates; diagnostic only.",
            "horizon_days": horizon_days,
            "candidate_count": 0,
            "raw_candidate_count": len(events),
            "missing_candidate_count": len(missing),
            "missing_candidates": missing,
        }

    decision_counts = {}
    for row in candidate_rows:
        decision_counts[row["decision"]] = decision_counts.get(row["decision"], 0) + 1
    tag_summary = _summarize_entry_state_tags(candidate_rows)
    tag_counts = {
        tag: rec["candidate_count"]
        for tag, rec in tag_summary.items()
    }

    returns = [row["forward_return_pct"] for row in candidate_rows]
    return {
        "oracle_type": "entry_state_candidate_oracle",
        "is_tradable": False,
        "lookahead_warning": (
            "Tags use only signal-date state, but tag returns use future prices. "
            "Use this to prioritize hypotheses, not as a live ranking rule."
        ),
        "horizon_days": horizon_days,
        "candidate_count": len(candidate_rows),
        "raw_candidate_count": len(events),
        "missing_candidate_count": len(missing),
        "entered_count": sum(1 for row in candidate_rows if row["decision"] == "entered"),
        "decision_counts": dict(sorted(decision_counts.items())),
        "avg_forward_return_pct": round(sum(returns) / len(returns), 6),
        "median_forward_return_pct": round(_median(returns), 6),
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 4),
        "tag_counts": dict(sorted(tag_counts.items())),
        "by_tag": tag_summary,
        "top_tagged_candidates": sorted(
            candidate_rows,
            key=lambda row: row["forward_return_pct"],
            reverse=True,
        )[:10],
        "weakest_tagged_candidates": sorted(
            candidate_rows,
            key=lambda row: row["forward_return_pct"],
        )[:10],
        "missing_candidates": missing,
    }


def build_perfect_exit_oracle(backtest_result, snapshot):
    rows_by_ticker = _ohlcv_rows_by_date(snapshot)
    trade_oracles = []
    missing = []

    for trade in backtest_result.get("trades") or []:
        ticker = (trade.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker)
        if not rows:
            missing.append({"ticker": ticker, "reason": "missing_ohlcv"})
            continue
        window = _window_rows(rows, trade.get("entry_date"), trade.get("exit_date"))
        oracle = _oracle_exit_for_trade(trade, window)
        if oracle is None:
            missing.append({"ticker": ticker, "reason": "insufficient_trade_or_price_data"})
            continue
        trade_oracles.append(oracle)

    actual_pnl = sum(t["actual_pnl"] for t in trade_oracles)
    oracle_pnl = sum(t["oracle_pnl"] for t in trade_oracles)
    regret = oracle_pnl - actual_pnl
    capture_ratio = actual_pnl / oracle_pnl if oracle_pnl > 0 else None

    by_strategy = {}
    for row in trade_oracles:
        rec = by_strategy.setdefault(row["strategy"], {
            "trade_count": 0,
            "actual_pnl": 0.0,
            "oracle_pnl": 0.0,
            "regret_vs_oracle": 0.0,
        })
        rec["trade_count"] += 1
        rec["actual_pnl"] += row["actual_pnl"]
        rec["oracle_pnl"] += row["oracle_pnl"]
        rec["regret_vs_oracle"] += row["regret_vs_oracle"]

    for rec in by_strategy.values():
        rec["actual_pnl"] = round(rec["actual_pnl"], 2)
        rec["oracle_pnl"] = round(rec["oracle_pnl"], 2)
        rec["regret_vs_oracle"] = round(rec["regret_vs_oracle"], 2)
        rec["capture_ratio"] = (
            round(rec["actual_pnl"] / rec["oracle_pnl"], 4)
            if rec["oracle_pnl"] > 0 else None
        )

    top_regrets = sorted(
        trade_oracles,
        key=lambda row: row["regret_vs_oracle"],
        reverse=True,
    )[:10]

    return {
        "oracle_type": "perfect_exit_after_actual_entry",
        "is_tradable": False,
        "lookahead_warning": (
            "Uses future intratrade highs. Use only as an upper-bound/regret diagnostic, "
            "never as a strategy acceptance metric."
        ),
        "trade_count": len(trade_oracles),
        "missing_trade_count": len(missing),
        "actual_pnl": round(actual_pnl, 2),
        "oracle_pnl": round(oracle_pnl, 2),
        "regret_vs_oracle": round(regret, 2),
        "capture_ratio": round(capture_ratio, 4) if capture_ratio is not None else None,
        "by_strategy": dict(sorted(by_strategy.items())),
        "top_regret_trades": top_regrets,
        "missing_trades": missing,
    }


def build_oracle_diagnostics(
    backtest_path,
    snapshot_path=None,
    candidate_horizon_days=20,
    entry_skip_oracle_path=None,
):
    """Build all oracle diagnostic sections for a backtest result.

    Parameters
    ----------
    backtest_path:
        Path to the backtest result JSON.
    snapshot_path:
        Path to the OHLCV snapshot JSON.  Inferred from known_biases if omitted.
    candidate_horizon_days:
        Forward lookahead window in trading days for candidate oracle sections.
    entry_skip_oracle_path:
        Optional path to an ``entry_skip_oracle_*.json`` file produced by
        ``quant/entry_skip_oracle.py``.  When provided, the
        ``no_trade_attribution`` section joins skip reasons from that file so
        that rows previously labelled ``needs_entry_skip_logging`` show the
        actual backtester decision (``gap_cancel``, ``no_shares``,
        ``stop_breach_cancel``, ``slot_sliced``) instead.

        Typical usage::

            python quant/oracle_diagnostics.py \\
                --backtest data/backtests/backtest_results_20260531.json \\
                --entry-skip-oracle data/diagnostics/entry_skip_oracle_20260426.json \\
                --out data/diagnostics/oracle_diagnostics_20260531.json
    """
    backtest = _load_json(backtest_path)
    snapshot_path = snapshot_path or infer_snapshot_path(backtest)
    if not snapshot_path:
        raise ValueError("No OHLCV snapshot path found; pass --snapshot explicitly.")
    snapshot = _load_json(snapshot_path)

    entry_skip_oracle_data = None
    if entry_skip_oracle_path:
        entry_skip_oracle_data = _load_json(entry_skip_oracle_path)

    return {
        "diagnostic_only": True,
        "source_backtest": os.path.abspath(backtest_path),
        "source_snapshot": os.path.abspath(snapshot_path),
        "source_entry_skip_oracle": (
            os.path.abspath(entry_skip_oracle_path)
            if entry_skip_oracle_path else None
        ),
        "period": backtest.get("period"),
        "acceptance_boundary": (
            "Oracle diagnostics use future prices. They may generate hypotheses "
            "or field ideas, but they are not Gate 4 acceptance evidence."
        ),
        "oracle_metrics": {
            "perfect_exit": build_perfect_exit_oracle(backtest, snapshot),
            "candidate_forward": build_candidate_forward_oracle(
                backtest,
                snapshot,
                horizon_days=candidate_horizon_days,
            ),
            "candidate_selection": build_candidate_selection_oracle(
                backtest,
                snapshot,
                horizon_days=candidate_horizon_days,
            ),
            "no_trade_attribution": build_no_trade_attribution_oracle(
                backtest,
                snapshot,
                horizon_days=candidate_horizon_days,
                entry_skip_oracle_data=entry_skip_oracle_data,
            ),
            "entry_state": build_entry_state_oracle(
                backtest,
                snapshot,
                horizon_days=candidate_horizon_days,
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest", required=True, help="Backtest result JSON.")
    parser.add_argument("--snapshot", help="OHLCV snapshot JSON. Defaults to known_biases path.")
    parser.add_argument(
        "--candidate-horizon-days",
        type=int,
        default=20,
        help="Trading-day horizon for candidate forward upper-bound diagnostics.",
    )
    parser.add_argument(
        "--entry-skip-oracle",
        help=(
            "Path to an entry_skip_oracle_*.json file (output of "
            "quant/entry_skip_oracle.py). When provided, no_trade_attribution "
            "rows are enriched with the actual backtester skip reason instead "
            "of being labelled needs_entry_skip_logging."
        ),
    )
    parser.add_argument("--out", help="Optional output JSON path.")
    args = parser.parse_args()

    result = build_oracle_diagnostics(
        args.backtest,
        args.snapshot,
        candidate_horizon_days=args.candidate_horizon_days,
        entry_skip_oracle_path=args.entry_skip_oracle,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
