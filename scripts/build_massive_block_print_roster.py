"""Outcome-blind roster builder for the massive block-print absorption scout.

Discovery-phase tool (alpha_search flow, consumes no experiment ID). Scans the
research_pit Massive full-market warehouse for sessions where a liquid active
common stock printed an extreme block-dominated tape and freezes the candidate
roster with entry/exit session labels only.

Outcome-blind contract:
- Selection at signal date D uses only bars with trade_date <= D.
- No entry-open, exit-close, or any post-signal price is read or written; the
  scout runner (first outcome access, post-reservation) resolves prices and
  voids rows with missing bars.

Frozen predicate (massive_block_print_absorption_h10_v1):
- PIT monthly membership: ticker present in the latest
  reference-asof:<date>:active=true:type=CS instrument_master snapshot with
  as-of date <= D.
- >= 126 prior bars with transactions > 0 and vwap > 0 strictly before D.
- Liquidity: trailing-20 median dollar volume (vwap*volume) >= $1,000,000 and
  signal-day close >= $3.
- Signal: avg trade size (vwap*volume/transactions) z-score vs the trailing
  126-session baseline >= 3.0; signal-day dollar volume >= trailing-20 median
  dollar volume; close >= open.
- Rank by z desc, top-2 per signal date; 10-session per-ticker cooldown on
  selection; one decision per ticker-date.
- Entry = next SPY session after D; exit = entry index + 9 (10-session hold
  counting entry); rows whose exit would fall past the warehouse edge are not
  emitted (calendar constraint, not an outcome read).
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
OUT = REPO_ROOT / "data" / "alpha_search" / "massive_block_print_roster_20260804.json"

Z_CUT = 3.0
BASELINE_SESSIONS = 126
LIQ_LOOKBACK = 20
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0
MIN_CLOSE = 3.0
TOP_N_PER_DATE = 2
COOLDOWN_SESSIONS = 10
HOLD_SESSIONS = 10  # exit index = entry index + 9


def load_membership(con: sqlite3.Connection) -> list[tuple[str, frozenset]]:
    """Monthly PIT membership snapshots sorted by as-of date ascending."""
    keys = [
        r[0]
        for r in con.execute(
            "select distinct snapshot_key from instrument_master "
            "where snapshot_key like 'reference-asof:%:active=true:type=CS' "
            "order by snapshot_key"
        )
    ]
    snaps = []
    for k in keys:
        asof = k.split(":")[1]
        members = frozenset(
            r[0]
            for r in con.execute(
                "select ticker from instrument_master where snapshot_key=?", (k,)
            )
        )
        snaps.append((asof, members))
    snaps.sort()
    return snaps


def membership_at(snaps: list[tuple[str, frozenset]], date: str):
    live = None
    for asof, members in snaps:
        if asof <= date:
            live = members
        else:
            break
    return live


def main() -> None:
    con = sqlite3.connect(str(DB))
    cal = [
        r[0]
        for r in con.execute(
            "select distinct trade_date from daily_bars where ticker='SPY' order by 1"
        )
    ]
    idx = {d: i for i, d in enumerate(cal)}
    last_entry_i = len(cal) - HOLD_SESSIONS  # entry index + 9 must exist

    snaps = load_membership(con)

    bars = pd.read_sql_query(
        "select ticker, trade_date, open, close, volume, vwap, transactions "
        "from daily_bars where volume > 0 and vwap > 0 and transactions > 0 "
        "and open > 0 and close > 0",
        con,
    )
    bars = bars[bars["trade_date"].isin(idx)]
    bars = bars.sort_values(["ticker", "trade_date"], kind="mergesort")

    dollar = bars["vwap"] * bars["volume"]
    ats = dollar / bars["transactions"]
    bars = bars.assign(dollar_volume=dollar, avg_trade_size=ats)

    prior_ats = bars.groupby("ticker", sort=False)["avg_trade_size"].shift(1)
    roll = prior_ats.groupby(bars["ticker"], sort=False)
    base_mean = roll.rolling(BASELINE_SESSIONS, min_periods=BASELINE_SESSIONS).mean()
    base_std = roll.rolling(BASELINE_SESSIONS, min_periods=BASELINE_SESSIONS).std(
        ddof=0
    )
    base_mean = base_mean.reset_index(level=0, drop=True)
    base_std = base_std.reset_index(level=0, drop=True)

    prior_dv = bars.groupby("ticker", sort=False)["dollar_volume"].shift(1)
    med_dv = (
        prior_dv.groupby(bars["ticker"], sort=False)
        .rolling(LIQ_LOOKBACK, min_periods=LIQ_LOOKBACK)
        .median()
        .reset_index(level=0, drop=True)
    )

    bars = bars.assign(
        ats_z=(bars["avg_trade_size"] - base_mean) / base_std,
        median_dollar_volume_20=med_dv,
    )

    eligible = bars[
        (base_std > 0)
        & bars["ats_z"].notna()
        & (bars["ats_z"] >= Z_CUT)
        & (bars["median_dollar_volume_20"] >= MIN_MEDIAN_DOLLAR_VOLUME)
        & (bars["dollar_volume"] >= bars["median_dollar_volume_20"])
        & (bars["close"] >= bars["open"])
        & (bars["close"] >= MIN_CLOSE)
    ]

    rows = []
    last_selected: dict[str, int] = {}
    n_membership_dropped = 0
    for date, day in eligible.groupby("trade_date", sort=True):
        i = idx[date]
        if i + 1 > last_entry_i:
            continue  # exit session would fall past the warehouse calendar
        members = membership_at(snaps, date)
        if members is None:
            continue
        day = day.sort_values(["ats_z", "ticker"], ascending=[False, True])
        picked = 0
        for r in day.itertuples():
            if picked >= TOP_N_PER_DATE:
                break
            if r.ticker not in members:
                n_membership_dropped += 1
                continue
            last = last_selected.get(r.ticker)
            if last is not None and i - last < COOLDOWN_SESSIONS:
                continue
            entry_i = i + 1
            rows.append(
                {
                    "ticker": r.ticker,
                    "signal_date": date,
                    "entry_session": cal[entry_i],
                    "h10_exit_session": cal[entry_i + HOLD_SESSIONS - 1],
                    "ats_z": round(float(r.ats_z), 4),
                    "avg_trade_size": round(float(r.avg_trade_size), 2),
                    "dollar_volume": round(float(r.dollar_volume), 2),
                    "median_dollar_volume_20": round(
                        float(r.median_dollar_volume_20), 2
                    ),
                }
            )
            last_selected[r.ticker] = i
            picked += 1

    # Chronological terciles over emitted signal dates (dates only; frozen).
    n = len(rows)
    terc = [rows[: n // 3], rows[n // 3 : 2 * n // 3], rows[2 * n // 3 :]]
    windows = {}
    for name, chunk in zip(("old_third", "mid_third", "late_third"), terc):
        windows[name] = {
            "row_count": len(chunk),
            "first_signal_date": chunk[0]["signal_date"] if chunk else None,
            "last_signal_date": chunk[-1]["signal_date"] if chunk else None,
        }
    for i, r in enumerate(rows):
        r["window"] = (
            "old_third" if i < n // 3 else "mid_third" if i < 2 * n // 3 else "late_third"
        )

    by_month: dict[str, int] = {}
    for r in rows:
        by_month[r["signal_date"][:7]] = by_month.get(r["signal_date"][:7], 0) + 1

    artifact = {
        "schema_version": 1,
        "record_type": "outcome_blind_scout_roster",
        "policy_version": "massive_block_print_absorption_h10_v1",
        "as_of": "2026-08-04",
        "outcome_blind": True,
        "predicate": {
            "ats_z_min": Z_CUT,
            "baseline_sessions": BASELINE_SESSIONS,
            "liquidity_lookback": LIQ_LOOKBACK,
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_close": MIN_CLOSE,
            "volume_confirm": "signal-day dollar volume >= trailing-20 median",
            "pressure_confirm": "close >= open",
            "top_n_per_date": TOP_N_PER_DATE,
            "cooldown_sessions": COOLDOWN_SESSIONS,
            "hold_sessions": HOLD_SESSIONS,
            "membership": "latest reference-asof active=true type=CS snapshot <= signal date",
        },
        "calendar_last_session": cal[-1],
        "row_count": n,
        "membership_dropped_candidate_rows": n_membership_dropped,
        "rows_by_signal_month": dict(sorted(by_month.items())),
        "windows": windows,
        "rows": rows,
        "no_forward_outcome_fields_read": True,
    }
    payload = json.dumps(artifact, indent=1, sort_keys=False)
    OUT.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print("wrote", OUT)
    print("rows:", n, "windows:", {k: v["row_count"] for k, v in windows.items()})
    print("sha256:", digest)


if __name__ == "__main__":
    main()
