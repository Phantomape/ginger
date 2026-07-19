"""ORTEX + Moomoo borrow-pressure market-neutral paper sleeve.

The policy in this module is the frozen bundle for exp-20260718-004.  It is
shared by historical replay and the daily paper adapter, but it is always
default-off and never emits an executable order.
"""

from __future__ import annotations

import bisect
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text
except ModuleNotFoundError:  # package-style test/import
    from quant.data_paths import DATA_ROOT, atomic_write_json, atomic_write_text


RULE_VERSION = "ortex_moomoo_borrow_pair_spread_v1"
FIXED_TICKERS = (
    "AAPL", "MSFT", "META", "GOOG", "AMZN",
    "AMD", "AVGO", "MU", "NVDA", "CRDO",
    "COIN", "DDOG", "PLTR", "APP", "SNOW", "TSLA",
    "CVX", "XOM", "JPM", "GS",
)
CLUSTERS = {
    "mega": ("AAPL", "MSFT", "META", "GOOG", "AMZN"),
    "semis": ("AMD", "AVGO", "MU", "NVDA", "CRDO"),
    "growth": ("COIN", "DDOG", "PLTR", "APP", "SNOW", "TSLA"),
    "energy": ("CVX", "XOM"),
    "financial": ("JPM", "GS"),
}
TICKER_CLUSTER = {
    ticker: cluster for cluster, tickers in CLUSTERS.items() for ticker in tickers
}

TOP_N = 4
CORR_LOOKBACK = 20
CORR_MIN = 0.20
HOLD_SESSIONS = 5
SHORT_COOLDOWN_SESSIONS = 10
MAX_CONCURRENT_PAIRS = 5
LEG_NOTIONAL_USD = 1_000.0
INITIAL_CASH_USD = 10_000.0
ROUND_TRIP_COST_RATE_PER_LEG = 0.0045
HALF_TRADE_COST_RATE = ROUND_TRIP_COST_RATE_PER_LEG / 2.0
PAIR_RESERVED_CAPITAL_USD = 2.0 * LEG_NOTIONAL_USD

DEFAULT_DIR = DATA_ROOT / "paper_sleeves" / "ortex_moomoo_borrow_pair"
DEFAULT_STATE_PATH = DEFAULT_DIR / "state.json"
DEFAULT_SNAPSHOT_LEDGER_PATH = DEFAULT_DIR / "daily_snapshots.jsonl"
DEFAULT_PAIR_LEDGER_PATH = DEFAULT_DIR / "pair_lifecycle.jsonl"


def _production_impact() -> dict[str, Any]:
    return {
        "trade_enabled": False,
        "enabled": False,
        "adapter_status": "shared_default_off_paper_helper",
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_core": False,
        "live_locate_verified": False,
    }


def _date10(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _number(value: Any, *, nonnegative: bool = False) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or (nonnegative and result < 0):
        return None
    return result


def _value(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        result = _number(row.get(key))
        if result is not None:
            return result
    return None


def _normalise_prices(payloads: Mapping[str, Any]) -> dict[str, dict[str, dict[str, float]]]:
    result: dict[str, dict[str, dict[str, float]]] = {}
    for raw_ticker, payload in (payloads or {}).items():
        ticker = str(raw_ticker).upper()
        if hasattr(payload, "iterrows"):
            candidates = list(payload.iterrows())
        elif isinstance(payload, Mapping):
            candidates = (
                [(None, row) for row in payload["rows"]]
                if isinstance(payload.get("rows"), list)
                else list(payload.items())
            )
        elif isinstance(payload, list):
            candidates = [(None, row) for row in payload]
        else:
            candidates = []
        bars: dict[str, dict[str, float]] = {}
        for fallback, raw in candidates:
            if not isinstance(raw, Mapping) and hasattr(raw, "to_dict"):
                raw = raw.to_dict()
            if isinstance(raw, Mapping):
                day = next(
                    (
                        _date10(raw.get(key))
                        for key in ("date", "Date", "datetime", "Datetime", "timestamp")
                        if _date10(raw.get(key))
                    ),
                    _date10(fallback),
                )
                open_price = _value(raw, "open", "Open", "price", "Close", "close")
                close_price = _value(raw, "close", "Close", "price", "Open", "open")
            else:
                day = _date10(fallback)
                open_price = close_price = _number(raw)
            if day and open_price and close_price and open_price > 0 and close_price > 0:
                bars[day] = {"open": open_price, "close": close_price}
        result[ticker] = bars
    return result


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    xx = sum((x - mean_x) ** 2 for x in xs)
    yy = sum((y - mean_y) ** 2 for y in ys)
    if xx <= 0 or yy <= 0:
        return None
    xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return xy / math.sqrt(xx * yy)


def _strict_prior_corr(
    left: str,
    right: str,
    source_date: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> float | None:
    left_bars = prices.get(left, {})
    right_bars = prices.get(right, {})
    # Source-close prices are known before the next-session entry.  Twenty
    # returns therefore use twenty-one aligned closes through source_date and
    # exclude only entry/future observations.
    dates = sorted(set(left_bars) & set(right_bars))
    dates = [day for day in dates if day <= source_date]
    if len(dates) < CORR_LOOKBACK + 1:
        return None
    dates = dates[-(CORR_LOOKBACK + 1):]
    left_returns: list[float] = []
    right_returns: list[float] = []
    for previous, current in zip(dates, dates[1:]):
        lp = left_bars[previous]["close"]
        lc = left_bars[current]["close"]
        rp = right_bars[previous]["close"]
        rc = right_bars[current]["close"]
        if min(lp, lc, rp, rc) <= 0:
            return None
        left_returns.append(lc / lp - 1.0)
        right_returns.append(rc / rp - 1.0)
    return pearson(left_returns, right_returns)


def _strict_next_session(source_date: str, sessions: Sequence[str]) -> str | None:
    index = bisect.bisect_right(sessions, source_date)
    return sessions[index] if index < len(sessions) else None


def _source_index(
    rows: Iterable[Mapping[str, Any]],
    *,
    date_field: str,
) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    result: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        day = _date10(row.get(date_field))
        if ticker in FIXED_TICKERS and day:
            result.setdefault((day, ticker), []).append(row)
    return result


def build_joined_ranked_source_days(
    ortex_rows: Iterable[Mapping[str, Any]],
    moomoo_rows: Iterable[Mapping[str, Any]],
    trading_dates: Iterable[Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Exact-date join and deterministic fixed-universe cross-sectional ranks."""
    sessions = sorted({_date10(value) for value in trading_dates if _date10(value)})
    session_set = set(sessions)
    ortex = _source_index(ortex_rows, date_field="provider_date")
    moomoo = _source_index(moomoo_rows, date_field="activity_date")
    source_dates = sorted({day for day, _ in ortex} & {day for day, _ in moomoo})
    joined: dict[str, dict[str, Any]] = {}
    audit = Counter()
    audit["candidate_source_dates"] = len(source_dates)
    for source_date in source_dates:
        if source_date not in session_set:
            audit["off_calendar_source_date_dropped"] += 1
            continue
        usable_date = _strict_next_session(source_date, sessions)
        if usable_date is None:
            audit["missing_next_session_dropped"] += 1
            continue
        rows_by_ticker: dict[str, dict[str, Any]] = {}
        invalid_reason = None
        for ticker in FIXED_TICKERS:
            o_rows = ortex.get((source_date, ticker), [])
            m_rows = moomoo.get((source_date, ticker), [])
            if len(o_rows) != 1 or len(m_rows) != 1:
                invalid_reason = "incomplete_or_duplicate_cross_section"
                break
            o_row, m_row = o_rows[0], m_rows[0]
            # ORTEX can report a negative CTB-new rebate.  It is a finite
            # cross-sectional observation, not missing data, and the fixed
            # borrow accrual preserves its sign.
            ctb = _number(o_row.get("cost_to_borrow_new_pct"))
            short_ratio = _number(m_row.get("short_volume_ratio"), nonnegative=True)
            ortex_usable = _date10(o_row.get("usable_trade_date"))
            moomoo_declared = _date10(m_row.get("usable_trade_date"))
            if ctb is None or short_ratio is None:
                invalid_reason = "missing_signal_value"
                break
            if ortex_usable != usable_date:
                invalid_reason = "ortex_next_session_mismatch"
                break
            if moomoo_declared is not None and moomoo_declared != usable_date:
                invalid_reason = "moomoo_next_session_mismatch"
                break
            rows_by_ticker[ticker] = {
                "ticker": ticker,
                "cluster": TICKER_CLUSTER[ticker],
                "source_date": source_date,
                "provider_date": source_date,
                "activity_date": source_date,
                "usable_trade_date": usable_date,
                "cost_to_borrow_new_pct": ctb,
                "short_volume_ratio": short_ratio,
            }
        if invalid_reason:
            audit[f"{invalid_reason}_dropped"] += 1
            continue
        ctb_order = sorted(
            FIXED_TICKERS,
            key=lambda ticker: (-rows_by_ticker[ticker]["cost_to_borrow_new_pct"], ticker),
        )
        short_order = sorted(
            FIXED_TICKERS,
            key=lambda ticker: (-rows_by_ticker[ticker]["short_volume_ratio"], ticker),
        )
        for rank, ticker in enumerate(ctb_order, start=1):
            rows_by_ticker[ticker]["ctb_rank"] = rank
            rows_by_ticker[ticker]["ctb_rank_score"] = len(FIXED_TICKERS) - rank + 1
        for rank, ticker in enumerate(short_order, start=1):
            row = rows_by_ticker[ticker]
            row["short_volume_rank"] = rank
            row["short_volume_rank_score"] = len(FIXED_TICKERS) - rank + 1
        for row in rows_by_ticker.values():
            row["combined_stress_rank_score"] = (
                row["ctb_rank_score"] + row["short_volume_rank_score"]
            )
            row["raw_stress_product"] = (
                row["cost_to_borrow_new_pct"] * row["short_volume_ratio"]
            )
        intersection = set(ctb_order[:TOP_N]) & set(short_order[:TOP_N])
        candidates = sorted(
            (rows_by_ticker[ticker] for ticker in intersection),
            key=lambda row: (
                -row["combined_stress_rank_score"],
                -row["raw_stress_product"],
                row["ticker"],
            ),
        )
        joined[source_date] = {
            "source_date": source_date,
            "usable_trade_date": usable_date,
            "rows_by_ticker": rows_by_ticker,
            "candidates": candidates,
        }
        audit["joined_source_dates"] += 1
        audit["joined_source_rows"] += len(rows_by_ticker)
        audit["intersection_candidates"] += len(candidates)
    audit["exact_date_join_only"] = 1
    audit["no_carry_forward"] = 1
    return joined, dict(sorted(audit.items()))


def _peer_options(
    short_row: Mapping[str, Any],
    source_day: Mapping[str, Any],
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
    busy_tickers: set[str],
) -> list[dict[str, Any]]:
    short = str(short_row["ticker"])
    source_date = str(short_row["source_date"])
    rows_by_ticker = source_day["rows_by_ticker"]
    options = []
    for ticker in CLUSTERS[TICKER_CLUSTER[short]]:
        if ticker == short or ticker in busy_tickers:
            continue
        corr = _strict_prior_corr(short, ticker, source_date, prices)
        if corr is None or corr < CORR_MIN:
            continue
        row = rows_by_ticker[ticker]
        options.append(
            {
                "ticker": ticker,
                "correlation": corr,
                "combined_stress_rank_score": row["combined_stress_rank_score"],
                "cost_to_borrow_new_pct": row["cost_to_borrow_new_pct"],
                "short_volume_ratio": row["short_volume_ratio"],
            }
        )
    options.sort(
        key=lambda row: (
            row["combined_stress_rank_score"],
            -row["correlation"],
            row["ticker"],
        )
    )
    return options


def _mark_open_pairs(
    open_pairs: Sequence[Mapping[str, Any]],
    day: str,
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
    *,
    cash_usd: float,
    price_field: str,
) -> dict[str, Any]:
    """Mark active legs consistently for replay and the daily adapter."""
    marked_gross = 0.0
    unrealized = 0.0
    accrued_borrow = 0.0
    for pair in open_pairs:
        long_bar = prices.get(str(pair["long_ticker"]), {}).get(day)
        short_bar = prices.get(str(pair["short_ticker"]), {}).get(day)
        if not long_bar or not short_bar:
            return {"status": "missing_mark_price"}
        long_price = float(long_bar[price_field])
        short_price = float(short_bar[price_field])
        marked_gross += float(pair["long_shares"]) * long_price
        marked_gross += float(pair["short_shares"]) * short_price
        unrealized += float(pair["long_shares"]) * (
            long_price - float(pair["long_entry_open"])
        )
        unrealized += float(pair["short_shares"]) * (
            float(pair["short_entry_open"]) - short_price
        )
        inclusive_days = (
            date.fromisoformat(day) - date.fromisoformat(str(pair["entry_date"]))
        ).days + 1
        accrued_borrow += (
            LEG_NOTIONAL_USD
            * float(pair["signal_ctb_new_pct"])
            / 100.0
            * inclusive_days
            / 360.0
        )
    reserved = len(open_pairs) * PAIR_RESERVED_CAPITAL_USD
    nav = float(cash_usd) + reserved + unrealized - accrued_borrow
    return {
        "status": "ok",
        "marked_gross_usd": marked_gross,
        "allocated_gross_usd": reserved,
        "unrealized_pnl_usd": unrealized,
        "accrued_borrow_usd": accrued_borrow,
        "nav_usd": nav,
        "marked_gross_lte_nav": marked_gross <= nav + 1e-7,
    }


def _drawdown(equities: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return worst


def _beta(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    if variance_y <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance_y


def _concentration(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    short_counts = Counter(str(row["short_ticker"]) for row in trades)
    cluster_counts = Counter(str(row["cluster"]) for row in trades)
    count = len(trades)
    shares = [value / count for value in short_counts.values()] if count else []
    return {
        "short_ticker_counts": dict(sorted(short_counts.items())),
        "cluster_counts": dict(sorted(cluster_counts.items())),
        "max_short_ticker_share": max(shares) if shares else None,
        "short_ticker_hhi": sum(value * value for value in shares) if shares else None,
    }


def _replay_window(
    *,
    label: str,
    start: str,
    end: str,
    source_days: Mapping[str, Mapping[str, Any]],
    join_audit: Mapping[str, Any],
    prices: Mapping[str, Mapping[str, Mapping[str, float]]],
    sessions: Sequence[str],
    initial_cash_usd: float,
) -> dict[str, Any]:
    days = [day for day in sessions if start <= day <= end]
    session_index = {day: index for index, day in enumerate(sessions)}
    cash = float(initial_cash_usd)
    open_pairs: list[dict[str, Any]] = []
    last_short_entry_index: dict[str, int] = {}
    trades: list[dict[str, Any]] = []
    daily_equity: list[dict[str, Any]] = []
    pending_by_entry: dict[str, Mapping[str, Any]] = {}
    audit = Counter()
    signals_generated = 0
    signals_survived = 0
    total_realized = 0.0

    for source_date, source_day in source_days.items():
        if not (start <= source_date <= end):
            continue
        entry_date = str(source_day["usable_trade_date"])
        entry_index = session_index.get(entry_date)
        if entry_index is None or entry_index + HOLD_SESSIONS >= len(sessions):
            audit["unsettled_exit_dropped"] += 1
            continue
        exit_date = sessions[entry_index + HOLD_SESSIONS]
        if exit_date > end:
            audit["outside_window_exit_dropped"] += 1
            continue
        pending_by_entry[entry_date] = source_day
        signals_generated += len(source_day["candidates"])

    previous_equity = initial_cash_usd
    for day in days:
        day_index = session_index[day]
        source_day = pending_by_entry.get(day)
        if source_day is not None:
            busy = {
                ticker
                for pair in open_pairs
                for ticker in (pair["long_ticker"], pair["short_ticker"])
            }
            selected = None
            # The registered policy selects the highest rank-sum name only.
            # A blocked top name makes the day silent; there is no fallback to
            # ranks two through four.
            for short_row in source_day["candidates"][:1]:
                short = str(short_row["ticker"])
                if short in busy:
                    audit["short_leg_busy_skips"] += 1
                    continue
                prior_index = last_short_entry_index.get(short)
                if prior_index is not None and day_index - prior_index < SHORT_COOLDOWN_SESSIONS:
                    audit["short_cooldown_skips"] += 1
                    continue
                if len(open_pairs) >= MAX_CONCURRENT_PAIRS:
                    audit["concurrent_cap_skips"] += 1
                    continue
                peers = _peer_options(short_row, source_day, prices, busy)
                if not peers:
                    audit["no_feasible_peer_skips"] += 1
                    continue
                peer = peers[0]
                long = str(peer["ticker"])
                exit_date = sessions[day_index + HOLD_SESSIONS]
                required = PAIR_RESERVED_CAPITAL_USD + 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
                if cash + 1e-9 < required:
                    audit["insufficient_cash_skips"] += 1
                    continue
                long_bar = prices.get(long, {}).get(day)
                short_bar = prices.get(short, {}).get(day)
                if long_bar is None or short_bar is None:
                    audit["missing_atomic_price_skips"] += 1
                    continue
                entry_mark = _mark_open_pairs(
                    open_pairs, day, prices, cash_usd=cash, price_field="open"
                )
                if entry_mark["status"] != "ok":
                    audit["missing_existing_mark_skips"] += 1
                    continue
                nav_after_entry_cost = (
                    entry_mark["nav_usd"]
                    - 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
                )
                marked_gross_after = (
                    entry_mark["marked_gross_usd"] + PAIR_RESERVED_CAPITAL_USD
                )
                if marked_gross_after > nav_after_entry_cost + 1e-9:
                    audit["marked_gross_to_nav_skips"] += 1
                    continue
                selected = (short_row, peer, exit_date, long_bar, short_bar)
                break
            if selected is not None:
                short_row, peer, exit_date, long_bar, short_bar = selected
                short, long = str(short_row["ticker"]), str(peer["ticker"])
                entry_cost = 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
                cash -= PAIR_RESERVED_CAPITAL_USD + entry_cost
                pair = {
                    "pair_id": f"{RULE_VERSION}:{source_day['source_date']}:{long}:{short}",
                    "rule_version": RULE_VERSION,
                    "cluster": TICKER_CLUSTER[short],
                    "source_date": source_day["source_date"],
                    "provider_date": source_day["source_date"],
                    "activity_date": source_day["source_date"],
                    "entry_date": day,
                    "exit_date": exit_date,
                    "long_ticker": long,
                    "short_ticker": short,
                    "long_entry_open": float(long_bar["open"]),
                    "short_entry_open": float(short_bar["open"]),
                    "long_shares": LEG_NOTIONAL_USD / float(long_bar["open"]),
                    "short_shares": LEG_NOTIONAL_USD / float(short_bar["open"]),
                    "leg_notional_usd": LEG_NOTIONAL_USD,
                    "reserved_capital_usd": PAIR_RESERVED_CAPITAL_USD,
                    "entry_trade_cost_usd": entry_cost,
                    "signal_ctb_new_pct": float(short_row["cost_to_borrow_new_pct"]),
                    "signal_short_volume_ratio": float(short_row["short_volume_ratio"]),
                    "short_combined_stress_rank_score": short_row["combined_stress_rank_score"],
                    "long_combined_stress_rank_score": peer["combined_stress_rank_score"],
                    "short_ctb_rank": short_row["ctb_rank"],
                    "short_volume_rank": short_row["short_volume_rank"],
                    "raw_stress_product": short_row["raw_stress_product"],
                    "strict_prior_20d_correlation": peer["correlation"],
                    # Signal-contract sentinel; a pair has a fixed scheduled
                    # close rather than a directional price target.
                    "target_price": None,
                    "target_price_role": "not_applicable_fixed_5_session_exit",
                    "entry_date_sentinel": day,
                    "trade_enabled": False,
                }
                open_pairs.append(pair)
                last_short_entry_index[short] = day_index
                signals_survived += 1
                audit["pairs_funded"] += 1

        # Fixed, atomic close at entry index + five sessions.
        for pair in list(open_pairs):
            if pair["exit_date"] != day:
                continue
            long_exit = float(prices[pair["long_ticker"]][day]["close"])
            short_exit = float(prices[pair["short_ticker"]][day]["close"])
            long_pnl = pair["long_shares"] * (long_exit - pair["long_entry_open"])
            short_pnl = pair["short_shares"] * (pair["short_entry_open"] - short_exit)
            gross_pnl = long_pnl + short_pnl
            exit_cost = 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
            inclusive_days = (date.fromisoformat(day) - date.fromisoformat(pair["entry_date"])).days + 1
            borrow_cost = (
                LEG_NOTIONAL_USD
                * pair["signal_ctb_new_pct"]
                / 100.0
                * inclusive_days
                / 360.0
            )
            trade_cost = pair["entry_trade_cost_usd"] + exit_cost
            net_pnl = gross_pnl - trade_cost - borrow_cost
            cash += PAIR_RESERVED_CAPITAL_USD + gross_pnl - exit_cost - borrow_cost
            total_realized += net_pnl
            closed = {
                **pair,
                "long_exit_close": long_exit,
                "short_exit_close": short_exit,
                "long_gross_pnl_usd": round(long_pnl, 8),
                "short_gross_pnl_usd": round(short_pnl, 8),
                "gross_pnl_usd": round(gross_pnl, 8),
                "entry_trade_cost_usd": round(pair["entry_trade_cost_usd"], 8),
                "exit_trade_cost_usd": round(exit_cost, 8),
                "trade_cost_usd": round(trade_cost, 8),
                "borrow_calendar_days_inclusive": inclusive_days,
                "borrow_cost_usd": round(borrow_cost, 8),
                "net_pnl_usd": round(net_pnl, 8),
                "return_on_pair_gross": net_pnl / PAIR_RESERVED_CAPITAL_USD,
                "holding_sessions": HOLD_SESSIONS,
                "exit_reason": "fixed_5_session_close",
            }
            trades.append(closed)
            open_pairs.remove(pair)

        close_mark = _mark_open_pairs(
            open_pairs, day, prices, cash_usd=cash, price_field="close"
        )
        if close_mark["status"] != "ok":
            raise AssertionError("missing marked close for active pair")
        unrealized = close_mark["unrealized_pnl_usd"]
        accrued_borrow = close_mark["accrued_borrow_usd"]
        marked_gross = close_mark["marked_gross_usd"]
        reserved = close_mark["allocated_gross_usd"]
        equity = close_mark["nav_usd"]
        allocated_gross = reserved
        daily_return = equity / previous_equity - 1.0 if previous_equity else 0.0
        daily_equity.append(
            {
                "date": day,
                "equity_usd": round(equity, 8),
                "daily_pnl_usd": round(equity - previous_equity, 8),
                "daily_return": daily_return,
                "cash_usd": round(cash, 8),
                "reserved_capital_usd": reserved,
                "gross_exposure_usd": round(marked_gross, 8),
                "allocated_gross_exposure_usd": allocated_gross,
                "marked_gross_market_value_usd": round(marked_gross, 8),
                "open_pair_count": len(open_pairs),
                "realized_pnl_to_date_usd": round(total_realized, 8),
                "unrealized_pnl_usd": round(unrealized, 8),
                "accrued_borrow_usd": round(accrued_borrow, 8),
            }
        )
        if cash < -1e-7:
            raise AssertionError("pair sleeve cash became negative")
        if marked_gross > equity + 1e-7:
            raise AssertionError("pair sleeve marked gross exceeded NAV")
        previous_equity = equity

    daily_returns = [{"date": row["date"], "return": row["daily_return"]} for row in daily_equity]
    sleeve_returns: list[float] = []
    spy_returns: list[float] = []
    for row in daily_equity:
        day = row["date"]
        index = session_index[day]
        if index == 0 or sessions[index - 1] not in prices.get("SPY", {}):
            continue
        spy_bar, prior_spy = prices["SPY"].get(day), prices["SPY"].get(sessions[index - 1])
        if spy_bar and prior_spy:
            sleeve_returns.append(row["daily_return"])
            spy_returns.append(spy_bar["close"] / prior_spy["close"] - 1.0)
    equities = [row["equity_usd"] for row in daily_equity]
    total_pnl = (equities[-1] - initial_cash_usd) if equities else 0.0
    summary = {
        "trade_count": len(trades),
        "total_pnl_usd": round(total_pnl, 8),
        "total_return_pct": total_pnl / initial_cash_usd * 100.0,
        "total_trade_cost_usd": round(sum(row["trade_cost_usd"] for row in trades), 8),
        "total_borrow_cost_usd": round(sum(row["borrow_cost_usd"] for row in trades), 8),
        "max_drawdown_pct": _drawdown(equities) * 100.0 if equities else 0.0,
        "ending_cash_usd": round(cash, 8),
        "ending_equity_usd": round(equities[-1], 8) if equities else initial_cash_usd,
        "min_cash_usd": min((row["cash_usd"] for row in daily_equity), default=initial_cash_usd),
        "max_gross_exposure_usd": max((row["gross_exposure_usd"] for row in daily_equity), default=0.0),
        "max_concurrent_pairs": max((row["open_pair_count"] for row in daily_equity), default=0),
        "spy_beta": _beta(sleeve_returns, spy_returns),
        "spy_correlation": pearson(sleeve_returns, spy_returns),
        "concentration": _concentration(trades),
    }
    audit.update(join_audit)
    audit.update(
        {
            "cash_nonnegative": int(all(row["cash_usd"] >= -1e-7 for row in daily_equity)),
            "gross_lte_nav": int(
                all(row["gross_exposure_usd"] <= row["equity_usd"] + 1e-7 for row in daily_equity)
            ),
            "strict_prior_corr_lookback": CORR_LOOKBACK,
            "fixed_hold_sessions": HOLD_SESSIONS,
            "short_cooldown_sessions": SHORT_COOLDOWN_SESSIONS,
        }
    )
    return {
        "rule_version": RULE_VERSION,
        "window": label,
        "start": start,
        "end": end,
        "trades": trades,
        "funded_pairs": trades,
        "daily_equity": daily_equity,
        "daily_returns": daily_returns,
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": signals_survived / signals_generated if signals_generated else 0.0,
        "summary": summary,
        "audit": dict(sorted(audit.items())),
        "trade_enabled": False,
    }


def replay_ortex_moomoo_borrow_pair_sleeve(
    *,
    ortex_rows: Iterable[Mapping[str, Any]],
    moomoo_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Any],
    windows: Mapping[str, Mapping[str, Any]],
    initial_cash_usd: float = INITIAL_CASH_USD,
) -> dict[str, Any]:
    """Replay the frozen policy independently in each supplied window."""
    if initial_cash_usd <= 0:
        raise ValueError("initial_cash_usd must be positive")
    prices = _normalise_prices(ohlcv_by_ticker)
    sessions = sorted(prices.get("SPY", {}))
    if not sessions:
        raise ValueError("SPY price history is required as the trading calendar")
    joined, join_audit = build_joined_ranked_source_days(
        ortex_rows, moomoo_rows, sessions
    )
    results = {}
    for label, bounds in windows.items():
        start = _date10(bounds.get("start"))
        end = _date10(bounds.get("end"))
        if not start or not end or start > end:
            raise ValueError(f"invalid window {label!r}")
        results[str(label)] = _replay_window(
            label=str(label),
            start=start,
            end=end,
            source_days=joined,
            join_audit=join_audit,
            prices=prices,
            sessions=sessions,
            initial_cash_usd=initial_cash_usd,
        )
    all_trades = [trade for result in results.values() for trade in result["trades"]]
    return {
        "rule_version": RULE_VERSION,
        "windows": results,
        "aggregate": {
            "window_count": len(results),
            "trade_count": len(all_trades),
            "total_pnl_usd": round(sum(row["net_pnl_usd"] for row in all_trades), 8),
            "signals_generated": sum(result["signals_generated"] for result in results.values()),
            "signals_survived": sum(result["signals_survived"] for result in results.values()),
            "total_trade_cost_usd": round(sum(row["trade_cost_usd"] for row in all_trades), 8),
            "total_borrow_cost_usd": round(sum(row["borrow_cost_usd"] for row in all_trades), 8),
            "concentration": _concentration(all_trades),
        },
        "join_audit": join_audit,
        "trade_enabled": False,
        "production_impact": _production_impact(),
    }


def empty_ortex_moomoo_borrow_pair_paper_snapshot(
    as_of: Any,
    reason: str = "inputs_unavailable",
) -> dict[str, Any]:
    day = _date10(as_of) or str(as_of)[:10]
    return {
        "record_id": f"{RULE_VERSION}:snapshot:{day}",
        "rule_version": RULE_VERSION,
        "as_of": day,
        "status": "fail_closed",
        "reason": reason,
        "candidate_count": 0,
        "candidates": [],
        "selected_pair": None,
        "new_pending_entries": [],
        "entered_pairs": [],
        "exited_pairs": [],
        "state_summary": {},
        "audit": {"fresh_exact_date_join": False, "no_carry_forward": True},
        "trade_enabled": False,
        "production_impact": _production_impact(),
    }


def empty_ortex_moomoo_borrow_pair_state(
    initial_cash_usd: float = INITIAL_CASH_USD,
) -> dict[str, Any]:
    return {
        "rule_version": RULE_VERSION,
        "cash_usd": float(initial_cash_usd),
        "pending_pairs": [],
        "open_pairs": [],
        "closed_pairs": [],
        "processed_dates": [],
        "last_short_entry_date": {},
        "trade_enabled": False,
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, dict) else None


def _append_jsonl_idempotent(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    key_field: str,
) -> dict[str, int]:
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    keys = {str(row.get(key_field) or "") for row in existing}
    appended = []
    duplicates = 0
    for raw in rows:
        row = dict(raw)
        key = str(row.get(key_field) or "")
        if not key:
            raise ValueError(f"missing {key_field}")
        if key in keys:
            duplicates += 1
            continue
        keys.add(key)
        appended.append(row)
    if appended:
        atomic_write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in existing + appended) + "\n",
            path,
        )
    return {"appended": len(appended), "duplicates": duplicates, "total": len(existing) + len(appended)}


def _state_summary(
    state: Mapping[str, Any],
    mark: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "cash_usd": round(float(state.get("cash_usd") or 0.0), 8),
        "pending_pair_count": len(state.get("pending_pairs") or []),
        "open_pair_count": len(state.get("open_pairs") or []),
        "closed_pair_count": len(state.get("closed_pairs") or []),
    }
    if mark is not None:
        result.update(
            {
                "mark_status": mark.get("status"),
                "marked_gross_usd": mark.get("marked_gross_usd"),
                "allocated_gross_usd": mark.get("allocated_gross_usd"),
                "nav_usd": mark.get("nav_usd"),
                "marked_gross_lte_nav": mark.get("marked_gross_lte_nav"),
            }
        )
    return result


def build_ortex_moomoo_borrow_pair_paper_snapshot(
    *,
    as_of: Any,
    ortex_rows: Iterable[Mapping[str, Any]],
    moomoo_rows: Iterable[Mapping[str, Any]],
    ohlcv_by_ticker: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    state_path: str | Path | None = None,
    snapshot_ledger_path: str | Path | None = None,
    pair_ledger_path: str | Path | None = None,
    persist: bool = False,
    initial_cash_usd: float = INITIAL_CASH_USD,
) -> dict[str, Any]:
    """Advance paper state and consume only source rows dated exactly ``as_of``.

    The adapter never replays a missed historical signal.  Pending/open state
    may advance, while candidate generation is restricted to the fresh exact
    ORTEX-provider/Moomoo-activity date join.
    """
    day = _date10(as_of)
    if not day:
        return empty_ortex_moomoo_borrow_pair_paper_snapshot(as_of, "invalid_as_of")
    state_target = Path(state_path) if state_path is not None else DEFAULT_STATE_PATH
    snapshot_target = (
        Path(snapshot_ledger_path)
        if snapshot_ledger_path is not None
        else DEFAULT_SNAPSHOT_LEDGER_PATH
    )
    pair_target = Path(pair_ledger_path) if pair_ledger_path is not None else DEFAULT_PAIR_LEDGER_PATH
    loaded = _load_json(state_target) if persist and state is None else None
    work = json.loads(json.dumps(state or loaded or empty_ortex_moomoo_borrow_pair_state(initial_cash_usd)))
    if work.get("rule_version") != RULE_VERSION:
        return empty_ortex_moomoo_borrow_pair_paper_snapshot(day, "state_rule_version_mismatch")
    prices = _normalise_prices(ohlcv_by_ticker)
    sessions = sorted(prices.get("SPY", {}))
    if day not in sessions:
        return empty_ortex_moomoo_borrow_pair_paper_snapshot(day, "as_of_not_trading_session")
    if day in set(work.get("processed_dates") or []):
        snapshot = empty_ortex_moomoo_borrow_pair_paper_snapshot(day, "already_processed_idempotent")
        snapshot["status"] = "idempotent"
        snapshot["state_summary"] = _state_summary(work)
        return snapshot

    events: list[dict[str, Any]] = []
    daily_audit = Counter()
    entered: list[dict[str, Any]] = []
    exited: list[dict[str, Any]] = []
    cash = float(work.get("cash_usd") or 0.0)
    open_pairs = list(work.get("open_pairs") or [])
    pending_pairs = list(work.get("pending_pairs") or [])
    still_pending = []
    busy = {ticker for pair in open_pairs for ticker in (pair["long_ticker"], pair["short_ticker"])}
    for pair in pending_pairs:
        if pair.get("entry_date") != day:
            still_pending.append(pair)
            continue
        long_bar = prices.get(pair["long_ticker"], {}).get(day)
        short_bar = prices.get(pair["short_ticker"], {}).get(day)
        required = PAIR_RESERVED_CAPITAL_USD + 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
        if (
            not long_bar
            or not short_bar
            or pair["long_ticker"] in busy
            or pair["short_ticker"] in busy
            or len(open_pairs) >= MAX_CONCURRENT_PAIRS
            or cash + 1e-9 < required
        ):
            events.append({**pair, "event_id": f"{pair['pair_id']}:entry_skip", "event": "entry_skipped", "trade_enabled": False})
            continue
        entry_cost = 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
        entry_mark = _mark_open_pairs(
            open_pairs, day, prices, cash_usd=cash, price_field="open"
        )
        if entry_mark["status"] != "ok":
            daily_audit["missing_existing_mark_entry_skips"] += 1
            events.append({**pair, "event_id": f"{pair['pair_id']}:entry_skip", "event": "entry_skipped_missing_mark", "trade_enabled": False})
            continue
        marked_gross_after = entry_mark["marked_gross_usd"] + PAIR_RESERVED_CAPITAL_USD
        nav_after_cost = entry_mark["nav_usd"] - entry_cost
        if marked_gross_after > nav_after_cost + 1e-9:
            daily_audit["marked_gross_nav_entry_skips"] += 1
            events.append({**pair, "event_id": f"{pair['pair_id']}:entry_skip", "event": "entry_skipped_marked_gross_nav_guard", "trade_enabled": False})
            continue
        cash -= PAIR_RESERVED_CAPITAL_USD + entry_cost
        funded = {
            **pair,
            "long_entry_open": long_bar["open"],
            "short_entry_open": short_bar["open"],
            "long_shares": LEG_NOTIONAL_USD / long_bar["open"],
            "short_shares": LEG_NOTIONAL_USD / short_bar["open"],
            "entry_trade_cost_usd": entry_cost,
            "reserved_capital_usd": PAIR_RESERVED_CAPITAL_USD,
        }
        open_pairs.append(funded)
        entered.append(funded)
        busy.update((funded["long_ticker"], funded["short_ticker"]))
        events.append({**funded, "event_id": f"{funded['pair_id']}:entry", "event": "entered", "trade_enabled": False})

    # Exact five-session close.  A missed invocation is fail-closed rather than
    # silently rewriting the historical exit.
    session_index = {value: index for index, value in enumerate(sessions)}
    for pair in list(open_pairs):
        entry_index = session_index.get(pair["entry_date"])
        if entry_index is None or session_index[day] - entry_index != HOLD_SESSIONS:
            continue
        long_bar = prices.get(pair["long_ticker"], {}).get(day)
        short_bar = prices.get(pair["short_ticker"], {}).get(day)
        if not long_bar or not short_bar:
            continue
        long_pnl = pair["long_shares"] * (long_bar["close"] - pair["long_entry_open"])
        short_pnl = pair["short_shares"] * (pair["short_entry_open"] - short_bar["close"])
        gross_pnl = long_pnl + short_pnl
        exit_cost = 2.0 * LEG_NOTIONAL_USD * HALF_TRADE_COST_RATE
        inclusive_days = (date.fromisoformat(day) - date.fromisoformat(pair["entry_date"])).days + 1
        borrow_cost = LEG_NOTIONAL_USD * pair["signal_ctb_new_pct"] / 100.0 * inclusive_days / 360.0
        trade_cost = pair["entry_trade_cost_usd"] + exit_cost
        net_pnl = gross_pnl - trade_cost - borrow_cost
        cash += PAIR_RESERVED_CAPITAL_USD + gross_pnl - exit_cost - borrow_cost
        closed = {
            **pair,
            "exit_date": day,
            "long_exit_close": long_bar["close"],
            "short_exit_close": short_bar["close"],
            "gross_pnl_usd": gross_pnl,
            "trade_cost_usd": trade_cost,
            "borrow_cost_usd": borrow_cost,
            "borrow_calendar_days_inclusive": inclusive_days,
            "net_pnl_usd": net_pnl,
            "exit_reason": "fixed_5_session_close",
        }
        exited.append(closed)
        work.setdefault("closed_pairs", []).append(closed)
        open_pairs.remove(pair)
        events.append({**closed, "event_id": f"{pair['pair_id']}:exit", "event": "exited", "trade_enabled": False})

    # Current-date-only source consumption; explicitly discard every older row.
    fresh_ortex = [row for row in ortex_rows if _date10(row.get("provider_date")) == day]
    fresh_moomoo = [row for row in moomoo_rows if _date10(row.get("activity_date")) == day]
    joined, join_audit = build_joined_ranked_source_days(fresh_ortex, fresh_moomoo, sessions)
    source_day = joined.get(day)
    candidates = list(source_day["candidates"]) if source_day else []
    selected_pair = None
    new_pending: list[dict[str, Any]] = []
    if source_day and candidates:
        usable_date = source_day["usable_trade_date"]
        planned_index = session_index.get(usable_date)
        busy = {
            ticker
            for pair in open_pairs + still_pending
            for ticker in (pair["long_ticker"], pair["short_ticker"])
        }
        # No fallback: a blocked highest-ranked short makes this source date
        # silent under the registered policy.
        for short_row in candidates[:1]:
            short = short_row["ticker"]
            if short in busy or len(open_pairs) + len(still_pending) >= MAX_CONCURRENT_PAIRS:
                continue
            last_entry = _date10((work.get("last_short_entry_date") or {}).get(short))
            if last_entry and planned_index is not None and last_entry in session_index:
                if planned_index - session_index[last_entry] < SHORT_COOLDOWN_SESSIONS:
                    continue
            peers = _peer_options(short_row, source_day, prices, busy)
            if not peers:
                continue
            peer = peers[0]
            pair_id = f"{RULE_VERSION}:{day}:{peer['ticker']}:{short}"
            selected_pair = {
                "pair_id": pair_id,
                "rule_version": RULE_VERSION,
                "source_date": day,
                "provider_date": day,
                "activity_date": day,
                "entry_date": usable_date,
                "long_ticker": peer["ticker"],
                "short_ticker": short,
                "cluster": TICKER_CLUSTER[short],
                "signal_ctb_new_pct": short_row["cost_to_borrow_new_pct"],
                "signal_short_volume_ratio": short_row["short_volume_ratio"],
                "short_combined_stress_rank_score": short_row["combined_stress_rank_score"],
                "long_combined_stress_rank_score": peer["combined_stress_rank_score"],
                "strict_prior_20d_correlation": peer["correlation"],
                "leg_notional_usd": LEG_NOTIONAL_USD,
                "target_price": None,
                "target_price_role": "not_applicable_fixed_5_session_exit",
                "trade_enabled": False,
            }
            still_pending.append(selected_pair)
            new_pending.append(selected_pair)
            events.append({**selected_pair, "event_id": f"{pair_id}:signal", "event": "signal", "trade_enabled": False})
            break

    work["cash_usd"] = cash
    work["pending_pairs"] = still_pending
    work["open_pairs"] = open_pairs
    work.setdefault("processed_dates", []).append(day)
    for pair in entered:
        work.setdefault("last_short_entry_date", {})[pair["short_ticker"]] = day
    work["trade_enabled"] = False
    close_mark = _mark_open_pairs(
        open_pairs, day, prices, cash_usd=cash, price_field="close"
    )
    snapshot = {
        "record_id": f"{RULE_VERSION}:snapshot:{day}",
        "rule_version": RULE_VERSION,
        "as_of": day,
        "status": "ready" if source_day else "no_fresh_exact_join",
        "reason": None if source_day else "fresh_same_day_sources_unavailable_or_invalid",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "selected_pair": selected_pair,
        "new_pending_entries": new_pending,
        "entered_pairs": entered,
        "exited_pairs": exited,
        "state_summary": _state_summary(work, close_mark),
        "audit": {
            **join_audit,
            **dict(daily_audit),
            "fresh_exact_date_join": bool(source_day),
            "no_carry_forward": True,
            "old_source_rows_consumed": 0,
            "marked_gross_nav_guard": True,
        },
        "trade_enabled": False,
        "production_impact": _production_impact(),
    }
    if persist:
        atomic_write_json(work, state_target, indent=2, ensure_ascii=True)
        snapshot["snapshot_ledger_merge"] = _append_jsonl_idempotent(
            snapshot_target, [snapshot], key_field="record_id"
        )
        snapshot["pair_ledger_merge"] = _append_jsonl_idempotent(
            pair_target, events, key_field="event_id"
        )
    return snapshot


__all__ = [
    "RULE_VERSION",
    "FIXED_TICKERS",
    "CLUSTERS",
    "TOP_N",
    "CORR_LOOKBACK",
    "CORR_MIN",
    "HOLD_SESSIONS",
    "SHORT_COOLDOWN_SESSIONS",
    "MAX_CONCURRENT_PAIRS",
    "LEG_NOTIONAL_USD",
    "INITIAL_CASH_USD",
    "DEFAULT_STATE_PATH",
    "DEFAULT_SNAPSHOT_LEDGER_PATH",
    "DEFAULT_PAIR_LEDGER_PATH",
    "pearson",
    "build_joined_ranked_source_days",
    "replay_ortex_moomoo_borrow_pair_sleeve",
    "empty_ortex_moomoo_borrow_pair_state",
    "empty_ortex_moomoo_borrow_pair_paper_snapshot",
    "build_ortex_moomoo_borrow_pair_paper_snapshot",
]
