"""exp-20260804-003: Massive block-print absorption research replay.

Private replay scout (research_pit; result ceiling observed_only). The frozen
policy, 725-row outcome-blind roster and falsifier come from the v2 panel
(cand-46f8c0461f9275d37527, promotion
data/alpha_search/promotions/massive_block_print_scout_v2_20260804.json).
This runner is the FIRST outcome access for the candidate.

Frozen policy (massive_block_print_absorption_h10_v1):
- touches: the 725 rows of the hash-bound roster
  data/alpha_search/massive_block_print_roster_20260804.json
  (241/242/242 across old_third/mid_third/late_third); entry/exit sessions are
  frozen per row (next open after the signal date, close of the 10th session)
- $4,000 research notional; 0.35% round-trip cost; 0.70% double-cost stress
- primary comparator: zero-return cash per row; SPY / QQQ identical-interval
  costed holds are secondary aggregate hurdles the treatment aggregate must
  also exceed (falsifier condition, not merely reported)
- descriptive overlapping-hold cluster block bootstrap (10,000 resamples,
  seed 20260804) on aggregate replacement value
- falsifier: roster exactly 241/242/242; >=2 of 3 windows AND aggregate
  strictly positive replacement value vs cash; aggregate treatment value >
  aggregate SPY value and > aggregate QQQ value; double-cost aggregate
  positive; max single ticker positive share <= 40%; top-5 <= 60%;
  contribution HHI <= 0.25; >= 5 executed touches per window
"""

from __future__ import annotations

import json
import random
import sqlite3
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
ROSTER = REPO_ROOT / "data" / "alpha_search" / "massive_block_print_roster_20260804.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260804-003"
OUT = OUT_DIR / "exp_20260804_003_massive_block_print_absorption_scout.json"

NOTIONAL = 4000.0
COST = 0.0035
DOUBLE_COST = 0.0070
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20260804
EXPECTED_WINDOWS = {"old_third": 241, "mid_third": 242, "late_third": 242}


def sessions(con) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            "select distinct trade_date from daily_bars where ticker='SPY' order by 1"
        )
    ]


def splits_for(con, ticker: str) -> list[tuple[str, float]]:
    rows = con.execute(
        "select execution_date, split_from, split_to from stock_splits where ticker=?",
        (ticker,),
    ).fetchall()
    return [(d, float(Fraction(str(t)) / Fraction(str(f)))) for d, f, t in rows]


def bar(con, ticker: str, date: str):
    return con.execute(
        "select open, close from daily_bars where ticker=? and trade_date=?",
        (ticker, date),
    ).fetchone()


def leg_return(con, ticker: str, entry_session: str, exit_session: str):
    """Split-normalized gross price return, entry open to exit close."""
    e = bar(con, ticker, entry_session)
    x = bar(con, ticker, exit_session)
    if e is None or e[0] in (None, 0) or x is None or x[1] in (None, 0):
        return None
    factor = 1.0
    for d, ratio in splits_for(con, ticker):
        if entry_session < d <= exit_session:
            factor *= ratio
    return (x[1] * factor) / e[0] - 1.0


def main() -> None:
    con = sqlite3.connect(str(DB))
    cal = sessions(con)
    idx = {d: i for i, d in enumerate(cal)}
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    map_rows = roster["rows"]

    window_counts = {w: 0 for w in EXPECTED_WINDOWS}
    for r in map_rows:
        window_counts[r["window"]] += 1
    roster_exact = window_counts == EXPECTED_WINDOWS

    rows = []
    voided = []
    for r in map_rows:
        entry_s, exit_s = r["entry_session"], r["h10_exit_session"]
        ret = leg_return(con, r["ticker"], entry_s, exit_s)
        if ret is None:
            voided.append({**r, "void_reason": "missing_entry_or_exit_bar"})
            continue
        spy = leg_return(con, "SPY", entry_s, exit_s)
        qqq = leg_return(con, "QQQ", entry_s, exit_s)
        treatment_value = NOTIONAL * (ret - COST)
        rows.append(
            {
                "window": r["window"],
                "ticker": r["ticker"],
                "signal_date": r["signal_date"],
                "entry_session": entry_s,
                "exit_session": exit_s,
                "ats_z": r["ats_z"],
                "gross_return": round(ret, 6),
                "treatment_value": round(treatment_value, 2),
                "replacement_value": round(treatment_value, 2),
                "replacement_value_double_cost": round(
                    NOTIONAL * (ret - DOUBLE_COST), 2
                ),
                "spy_value": None if spy is None else round(NOTIONAL * (spy - COST), 2),
                "qqq_value": None if qqq is None else round(NOTIONAL * (qqq - COST), 2),
            }
        )

    windows = {}
    for wname, expected in EXPECTED_WINDOWS.items():
        wrows = [r for r in rows if r["window"] == wname]
        windows[wname] = {
            "declared_touches": expected,
            "executed_touches": len(wrows),
            "replacement_value": round(sum(r["replacement_value"] for r in wrows), 2),
            "spy_value": round(sum(r["spy_value"] or 0.0 for r in wrows), 2),
            "qqq_value": round(sum(r["qqq_value"] or 0.0 for r in wrows), 2),
            "touch_floor_pass": len(wrows) >= 5,
        }

    aggregate = round(sum(r["replacement_value"] for r in rows), 2)
    aggregate_double = round(sum(r["replacement_value_double_cost"] for r in rows), 2)
    aggregate_spy = round(sum(r["spy_value"] or 0.0 for r in rows), 2)
    aggregate_qqq = round(sum(r["qqq_value"] or 0.0 for r in rows), 2)

    by_ticker: dict[str, float] = {}
    for r in rows:
        by_ticker[r["ticker"]] = by_ticker.get(r["ticker"], 0.0) + r["replacement_value"]
    positives = {t: v for t, v in by_ticker.items() if v > 0}
    pos_sum = sum(positives.values())
    if pos_sum > 0:
        shares = sorted((v / pos_sum for v in positives.values()), reverse=True)
        max_single = shares[0]
        top5 = sum(shares[:5])
    else:
        max_single, top5 = 0.0, 0.0
    abs_sum = sum(abs(v) for v in by_ticker.values())
    hhi = sum((abs(v) / abs_sum) ** 2 for v in by_ticker.values()) if abs_sum else 0.0

    ivals = [
        (idx[r["entry_session"]], idx[r["exit_session"]], i) for i, r in enumerate(rows)
    ]
    ivals.sort()
    clusters: list[list[int]] = []
    cur: list[int] = []
    cur_end = -1
    for a, b, i in ivals:
        if not cur or a <= cur_end:
            cur.append(i)
            cur_end = max(cur_end, b)
        else:
            clusters.append(cur)
            cur, cur_end = [i], b
    if cur:
        clusters.append(cur)
    cluster_sums = [sum(rows[i]["replacement_value"] for i in cl) for cl in clusters]
    rng = random.Random(BOOTSTRAP_SEED)
    boots = []
    for _ in range(BOOTSTRAP_N):
        boots.append(sum(rng.choice(cluster_sums) for _ in cluster_sums))
    boots.sort()
    ci_low = boots[int(0.05 * BOOTSTRAP_N)]
    ci_high = boots[int(0.95 * BOOTSTRAP_N) - 1]

    positive_windows = sum(1 for w in windows.values() if w["replacement_value"] > 0)
    all_floors = all(w["touch_floor_pass"] for w in windows.values())
    all_executed = len(rows) == sum(EXPECTED_WINDOWS.values())
    falsifier = {
        "roster_exact_241_242_242": roster_exact,
        "all_725_rows_executed": all_executed,
        "voided_row_count": len(voided),
        "touch_floor_all_windows": all_floors,
        "positive_windows": positive_windows,
        "at_least_two_windows_positive": positive_windows >= 2,
        "aggregate_replacement_positive": aggregate > 0,
        "aggregate_beats_spy": aggregate > aggregate_spy,
        "aggregate_beats_qqq": aggregate > aggregate_qqq,
        "double_cost_aggregate_positive": aggregate_double > 0,
        "max_single_ticker_positive_share": round(max_single, 4),
        "max_single_ok": max_single <= 0.4,
        "top5_positive_share": round(top5, 4),
        "top5_ok": top5 <= 0.6,
        "contribution_hhi": round(hhi, 4),
        "hhi_ok": hhi <= 0.25,
    }
    passes = all(
        [
            falsifier["roster_exact_241_242_242"],
            falsifier["touch_floor_all_windows"],
            falsifier["at_least_two_windows_positive"],
            falsifier["aggregate_replacement_positive"],
            falsifier["aggregate_beats_spy"],
            falsifier["aggregate_beats_qqq"],
            falsifier["double_cost_aggregate_positive"],
            falsifier["max_single_ok"],
            falsifier["top5_ok"],
            falsifier["hhi_ok"],
        ]
    )
    ci_includes_zero = ci_low <= 0.0 <= ci_high

    if not passes:
        disposition = "observed_only_rejected"
    elif ci_includes_zero:
        disposition = "observed_only_descriptive_lead"
    else:
        disposition = "observed_only_positive_lead"

    artifact = {
        "schema_version": 1,
        "experiment_id": "exp-20260804-003",
        "record_type": "private_replay_scout_result",
        "candidate_id": "cand-46f8c0461f9275d37527",
        "policy_version": "massive_block_print_absorption_h10_v1",
        "admission_class": "research_replay",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "price_reader": "data/warehouse/massive_history.sqlite daily_bars (research_pit Massive warehouse; identical reader for treatment, SPY and QQQ legs)",
        "cost_pct": COST,
        "double_cost_pct": DOUBLE_COST,
        "notional": NOTIONAL,
        "row_count": len(rows),
        "voided_rows": voided,
        "windows": windows,
        "aggregate_replacement_value": aggregate,
        "aggregate_replacement_value_double_cost": aggregate_double,
        "aggregate_spy_value": aggregate_spy,
        "aggregate_qqq_value": aggregate_qqq,
        "cluster_count": len(clusters),
        "bootstrap": {
            "method": "overlapping-hold cluster block bootstrap",
            "resamples": BOOTSTRAP_N,
            "seed": BOOTSTRAP_SEED,
            "ci90_low": round(ci_low, 2),
            "ci90_high": round(ci_high, 2),
            "includes_zero": ci_includes_zero,
        },
        "falsifier_checks": falsifier,
        "disposition": disposition,
        "rows": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    print("wrote", OUT)
    print("disposition:", disposition)
    print("windows:", {k: v["replacement_value"] for k, v in windows.items()})
    print("aggregate:", aggregate, "double-cost:", aggregate_double)
    print("spy:", aggregate_spy, "qqq:", aggregate_qqq)
    print("bootstrap CI90:", ci_low, ci_high)
    print("voided:", len(voided))
    print("falsifier:", {k: v for k, v in falsifier.items() if not isinstance(v, float)})


if __name__ == "__main__":
    main()
