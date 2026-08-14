"""Freeze an outcome-blind Massive persistent trade-size regime roster.

This is a discovery-phase roster builder and consumes no experiment ID.  It
implements the materially different mechanism explicitly left open by
exp-20260804-003: a multi-session change in participant-size mix rather than a
one-day block-print outlier.

Decision contract (policy version massive_persistent_adts_state_h5_v1):

* Average dollar trade size is ``vwap * volume / transactions``.
* At signal close D, the median of the latest five sessions must reach the
  90th percentile of the preceding 126 sessions and at least four of those
  five sessions must exceed the preceding-window median.
* Each of the five recent sessions is standardised against its own immediately
  preceding 126 sessions and the maximum z-score must be below 3.0.  This
  makes every emitted signal mutually exclusive with the prior one-day
  block-outlier family.
* Recent-five median dollar volume must be at least USD 1,000,000 and no lower
  than the prior-20 median ending before the recent window.  Close at D must
  be at least the open at D-4 and at least USD 3.
* Membership is the latest Massive ``reference-asof`` active common-stock
  snapshot whose as-of date is no later than D.
* Rank by a fixed trade-size plus participation score, select top two per signal
  date, impose a ten-session ticker cooldown, and admit no more than three
  simultaneously active research positions under the fixed USD 4,000 ticket.
* Entry is the next SPY session and the research horizon is five sessions.

Only signal-time fields, membership, calendar labels, and EXISTS-only
entry/exit-row checks are read or written. Entry/exit prices, returns, PnL,
benchmark outcomes, and all other post-signal values are intentionally absent.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DB = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
OUT = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "massive_persistent_trade_size_roster_20260814.json"
)

RECENT_SESSIONS = 5
PRIOR_SESSIONS = 126
LIQ_LOOKBACK = 20
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0
MIN_CLOSE = 3.0
TOP_N_PER_DATE = 2
COOLDOWN_SESSIONS = 10
HOLD_SESSIONS = 5
MAX_ACTIVE_POSITIONS = 3

WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}


def _membership_snapshots(con: sqlite3.Connection) -> list[tuple[str, frozenset[str]]]:
    keys = [
        row[0]
        for row in con.execute(
            "select distinct snapshot_key from instrument_master "
            "where snapshot_key like 'reference-asof:%:active=true:type=CS' "
            "order by snapshot_key"
        )
    ]
    snapshots: list[tuple[str, frozenset[str]]] = []
    for key in keys:
        as_of = key.split(":")[1]
        members = frozenset(
            row[0]
            for row in con.execute(
                "select ticker from instrument_master where snapshot_key=?", (key,)
            )
        )
        snapshots.append((as_of, members))
    return snapshots


def _membership_at(
    snapshots: list[tuple[str, frozenset[str]]], date: str
) -> tuple[str | None, frozenset[str] | None]:
    selected_as_of = None
    selected_members = None
    for as_of, members in snapshots:
        if as_of <= date:
            selected_as_of = as_of
            selected_members = members
        else:
            break
    return selected_as_of, selected_members


def _window_for_entry(entry_session: str) -> str | None:
    for label, (start, end) in WINDOWS.items():
        if start <= entry_session <= end:
            return label
    return None


def main() -> None:
    con = sqlite3.connect(str(DB))
    try:
        calendar = [
            row[0]
            for row in con.execute(
                "select distinct trade_date from daily_bars "
                "where ticker='SPY' order by trade_date"
            )
        ]
        calendar_index = {date: i for i, date in enumerate(calendar)}
        snapshots = _membership_snapshots(con)

        bars = pd.read_sql_query(
            "select ticker, trade_date, open, close, volume, vwap, transactions "
            "from daily_bars where trade_date <= '2026-04-21' "
            "and volume > 0 and vwap > 0 and transactions > 0 "
            "and open > 0 and close > 0",
            con,
        )
    finally:
        con.close()

    bars = bars[bars["trade_date"].isin(calendar_index)]
    bars = bars.sort_values(["ticker", "trade_date"], kind="mergesort")
    bars = bars.assign(
        dollar_volume=bars["vwap"] * bars["volume"],
        average_trade_size=(bars["vwap"] * bars["volume"]) / bars["transactions"],
    )

    ticker = bars["ticker"]
    ats = bars["average_trade_size"]
    recent_median = (
        ats.groupby(ticker, sort=False)
        .rolling(RECENT_SESSIONS, min_periods=RECENT_SESSIONS)
        .median()
        .reset_index(level=0, drop=True)
    )
    prior_ats = ats.groupby(ticker, sort=False).shift(RECENT_SESSIONS)
    prior_group = prior_ats.groupby(ticker, sort=False)
    prior_median = (
        prior_group.rolling(PRIOR_SESSIONS, min_periods=PRIOR_SESSIONS)
        .median()
        .reset_index(level=0, drop=True)
    )
    prior_ninetieth = (
        prior_group.rolling(PRIOR_SESSIONS, min_periods=PRIOR_SESSIONS)
        .quantile(0.90)
        .reset_index(level=0, drop=True)
    )
    daily_prior = ats.groupby(ticker, sort=False).shift(1)
    daily_prior_group = daily_prior.groupby(ticker, sort=False)
    daily_prior_mean = (
        daily_prior_group.rolling(PRIOR_SESSIONS, min_periods=PRIOR_SESSIONS)
        .mean()
        .reset_index(level=0, drop=True)
    )
    daily_prior_std = (
        daily_prior_group.rolling(PRIOR_SESSIONS, min_periods=PRIOR_SESSIONS)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )
    daily_dynamic_z = (ats - daily_prior_mean) / daily_prior_std
    recent_dynamic_z_max = (
        daily_dynamic_z.groupby(ticker, sort=False)
        .rolling(RECENT_SESSIONS, min_periods=RECENT_SESSIONS)
        .max()
        .reset_index(level=0, drop=True)
    )
    recent_above_prior_median_count = sum(
        ats.groupby(ticker, sort=False).shift(lag).gt(prior_median).astype(int)
        for lag in range(RECENT_SESSIONS)
    )
    recent_dollar_volume_median = (
        bars["dollar_volume"]
        .groupby(ticker, sort=False)
        .rolling(RECENT_SESSIONS, min_periods=RECENT_SESSIONS)
        .median()
        .reset_index(level=0, drop=True)
    )
    prior_dollar_volume = bars["dollar_volume"].groupby(ticker, sort=False).shift(
        RECENT_SESSIONS
    )
    prior_median_dollar_volume_20 = (
        prior_dollar_volume.groupby(ticker, sort=False)
        .rolling(LIQ_LOOKBACK, min_periods=LIQ_LOOKBACK)
        .median()
        .reset_index(level=0, drop=True)
    )
    five_session_start_open = bars["open"].groupby(ticker, sort=False).shift(
        RECENT_SESSIONS - 1
    )
    regime_score = np.log(recent_median / prior_ninetieth) + 0.25 * np.log(
        recent_dollar_volume_median / prior_median_dollar_volume_20
    )

    bars = bars.assign(
        recent_ats_median_5=recent_median,
        prior_ats_median_126=prior_median,
        prior_ats_ninetieth_126=prior_ninetieth,
        recent_dynamic_z_max_5=recent_dynamic_z_max,
        recent_above_prior_median_count=recent_above_prior_median_count,
        recent_dollar_volume_median_5=recent_dollar_volume_median,
        prior_median_dollar_volume_20=prior_median_dollar_volume_20,
        five_session_start_open=five_session_start_open,
        regime_score=regime_score,
    )

    eligible = bars[
        bars["recent_ats_median_5"].notna()
        & bars["prior_ats_ninetieth_126"].notna()
        & (bars["prior_ats_median_126"] > 0)
        & (bars["recent_ats_median_5"] >= bars["prior_ats_ninetieth_126"])
        & (bars["recent_above_prior_median_count"] >= 4)
        & bars["recent_dynamic_z_max_5"].notna()
        & (bars["recent_dynamic_z_max_5"] < 3.0)
        & (
            bars["recent_dollar_volume_median_5"]
            >= bars["prior_median_dollar_volume_20"]
        )
        & (bars["recent_dollar_volume_median_5"] >= MIN_MEDIAN_DOLLAR_VOLUME)
        & (bars["close"] >= bars["five_session_start_open"])
        & (bars["close"] >= MIN_CLOSE)
    ]

    rows: list[dict] = []
    last_selected: dict[str, int] = {}
    membership_dropped = 0
    calendar_dropped = 0
    capacity_dropped_signal_dates = 0
    missing_execution_rows = 0
    exists_con = sqlite3.connect(str(DB))
    try:
        for signal_date, day in eligible.groupby("trade_date", sort=True):
            signal_index = calendar_index[signal_date]
            entry_index = signal_index + 1
            exit_index = entry_index + HOLD_SESSIONS - 1
            if exit_index >= len(calendar):
                calendar_dropped += len(day)
                continue
            entry_session = calendar[entry_index]
            exit_session = calendar[exit_index]
            window = _window_for_entry(entry_session)
            if window is None:
                continue
            active_at_entry = sum(
                row["entry_session"] <= entry_session <= row["h5_exit_session"]
                for row in rows
            )
            available_slots = MAX_ACTIVE_POSITIONS - active_at_entry
            if available_slots <= 0:
                capacity_dropped_signal_dates += 1
                continue
            membership_as_of, members = _membership_at(snapshots, signal_date)
            if members is None:
                continue
            day = day.sort_values(["regime_score", "ticker"], ascending=[False, True])
            picked = 0
            for row in day.itertuples():
                if picked >= min(TOP_N_PER_DATE, available_slots):
                    break
                if row.ticker not in members:
                    membership_dropped += 1
                    continue
                previous = last_selected.get(row.ticker)
                if previous is not None and signal_index - previous < COOLDOWN_SESSIONS:
                    continue
                entry_exists = exists_con.execute(
                    "select 1 from daily_bars where ticker=? and trade_date=? limit 1",
                    (row.ticker, entry_session),
                ).fetchone()
                exit_exists = exists_con.execute(
                    "select 1 from daily_bars where ticker=? and trade_date=? limit 1",
                    (row.ticker, exit_session),
                ).fetchone()
                if entry_exists is None or exit_exists is None:
                    missing_execution_rows += 1
                    continue
                rows.append(
                    {
                        "ticker": row.ticker,
                        "signal_date": signal_date,
                        "entry_session": entry_session,
                        "h5_exit_session": exit_session,
                        "window": window,
                        "membership_as_of": membership_as_of,
                        "recent_ats_median_5": round(
                            float(row.recent_ats_median_5), 2
                        ),
                        "prior_ats_median_126": round(
                            float(row.prior_ats_median_126), 2
                        ),
                        "prior_ats_ninetieth_126": round(
                            float(row.prior_ats_ninetieth_126), 2
                        ),
                        "recent_dynamic_z_max_5": round(
                            float(row.recent_dynamic_z_max_5), 6
                        ),
                        "recent_above_prior_median_count": int(
                            row.recent_above_prior_median_count
                        ),
                        "recent_dollar_volume_median_5": round(
                            float(row.recent_dollar_volume_median_5), 2
                        ),
                        "prior_median_dollar_volume_20": round(
                            float(row.prior_median_dollar_volume_20), 2
                        ),
                        "regime_score": round(float(row.regime_score), 6),
                    }
                )
                last_selected[row.ticker] = signal_index
                picked += 1
    finally:
        exists_con.close()

    window_counts = {
        label: sum(row["window"] == label for row in rows) for label in WINDOWS
    }
    ticker_counts: dict[str, int] = {}
    for row in rows:
        ticker_counts[row["ticker"]] = ticker_counts.get(row["ticker"], 0) + 1
    max_ticker_count = max(ticker_counts.values(), default=0)
    max_ticker_share = max_ticker_count / len(rows) if rows else 0.0

    artifact = {
        "schema_version": 1,
        "record_type": "outcome_blind_scout_roster",
        "policy_version": "massive_persistent_adts_state_h5_v1",
        "as_of": "2026-08-14T15:16:11Z",
        "outcome_blind": True,
        "predicate": {
            "field": "vwap * volume / transactions",
            "recent_sessions": RECENT_SESSIONS,
            "prior_sessions": PRIOR_SESSIONS,
            "regime_condition": (
                "median(latest 5 ADTS sessions) >= q90(preceding 126); "
                "at least 4/5 recent ADTS exceed prior median; each recent "
                "ADTS dynamic z versus its own prior 126 is below 3.0"
            ),
            "direction_confirmation": "close_D >= open_D_minus_4",
            "liquidity_lookback": LIQ_LOOKBACK,
            "liquidity_condition": (
                "median(latest 5 dollar volume) >= max(USD 1m, "
                "median(prior 20 dollar volume ending D-5))"
            ),
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_close": MIN_CLOSE,
            "top_n_per_date": TOP_N_PER_DATE,
            "cooldown_sessions": COOLDOWN_SESSIONS,
            "hold_sessions": HOLD_SESSIONS,
            "paper_notional_usd": 4000,
            "max_active_positions": MAX_ACTIVE_POSITIONS,
            "cash_reservation_usd": 12000,
            "membership": (
                "latest reference-asof active=true type=CS snapshot <= signal date"
            ),
        },
        "calendar_last_session": calendar[-1],
        "row_count": len(rows),
        "historical_replay_rows": len(rows),
        "forward_settled_rows": 0,
        "execution_rows_exist": True,
        "executable_treatment_touches_by_standard_window": window_counts,
        "required_touches_per_standard_window": 5,
        "touch_density_pass": all(count >= 5 for count in window_counts.values()),
        "unique_tickers": len(ticker_counts),
        "max_ticker_selection_count": max_ticker_count,
        "max_ticker_selection_share": round(max_ticker_share, 6),
        "max_ticker_selection_share_cap": 0.15,
        "concentration_pass": max_ticker_share <= 0.15,
        "membership_dropped_candidate_rows": membership_dropped,
        "calendar_dropped_candidate_rows": calendar_dropped,
        "capacity_dropped_signal_dates": capacity_dropped_signal_dates,
        "missing_execution_rows": missing_execution_rows,
        "rows": rows,
        "no_entry_or_exit_prices_read": True,
        "no_forward_outcome_fields_read": True,
        "known_future_leakage": False,
        "pit_tier": "research_pit",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
    }
    payload = json.dumps(artifact, indent=2, sort_keys=False) + "\n"
    OUT.write_text(payload, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": str(OUT.relative_to(REPO_ROOT)),
                "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "row_count": len(rows),
                "touches": window_counts,
                "unique_tickers": len(ticker_counts),
                "max_ticker_selection_share": round(max_ticker_share, 6),
                "touch_density_pass": artifact["touch_density_pass"],
                "concentration_pass": artifact["concentration_pass"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
