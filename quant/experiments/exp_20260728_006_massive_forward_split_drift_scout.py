"""exp-20260728-006: Massive forward-split execution-date drift research replay.

Private replay scout (research_pit; result ceiling observed_only). The frozen
policy, touches, comparator and falsifier come from the debated v2.2 panel
(cand-18ea7bbda2c85f2ad14a, promotion
data/alpha_search/promotions/massive_split_drift_scout_20260728.json). This
runner is the FIRST outcome access for the candidate.

Frozen policy (massive_forward_split_execution_drift_v2):
- touches: the 21 purified rows in
  data/alpha_search/massive_split_drift_touch_preflight_v2_20260728.json
- entry: next session open after execution_date; exit: close of the 10th
  session after entry; split-local normalization through the hold
- $4,000 paper notional per position; ROUND_TRIP_COST_PCT (0.35%) per leg pair
- primary comparator: the cash-feasible core trade entered the same session
  (from the frozen Gate-1 anchor window artifacts), measured over the
  identical next-open-to-10-session interval at identical notional/cost;
  cash (zero) when the core admitted nothing that session
- SPY / QQQ same-interval secondary comparators (reported, never primary)
- descriptive date-cluster block bootstrap (overlapping hold windows form a
  cluster; 10,000 resamples, seed 20260728) on aggregate replacement value
- double-cost stress at 0.70% round trip
"""

from __future__ import annotations

import json
import random
import sqlite3
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
TOUCH = REPO_ROOT / "data" / "alpha_search" / "massive_split_drift_touch_preflight_v2_20260728.json"
ANCHOR = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260728-006"
OUT = OUT_DIR / "exp_20260728_006_massive_forward_split_drift_scout.json"

NOTIONAL = 4000.0
COST = 0.0035
DOUBLE_COST = 0.0070
HOLD_SESSIONS = 10
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20260728


def sessions(con) -> list[str]:
    return [r[0] for r in con.execute(
        "select distinct trade_date from daily_bars where ticker='SPY' order by 1")]


def splits_for(con, ticker: str) -> list[tuple[str, float]]:
    rows = con.execute(
        "select execution_date, split_from, split_to from stock_splits where ticker=?",
        (ticker,)).fetchall()
    return [(d, float(Fraction(str(t)) / Fraction(str(f)))) for d, f, t in rows]


def bar(con, ticker: str, date: str):
    return con.execute(
        "select open, close from daily_bars where ticker=? and trade_date=?",
        (ticker, date)).fetchone()


def leg_return(con, ticker: str, entry_session: str, exit_session: str):
    """Split-normalized gross return, next-open to 10th-session close."""
    e = bar(con, ticker, entry_session)
    x = bar(con, ticker, exit_session)
    if e is None or e[0] in (None, 0) or x is None or x[1] in (None, 0):
        return None
    factor = 1.0
    for d, ratio in splits_for(con, ticker):
        if entry_session < d <= exit_session:
            factor *= ratio
    return (x[1] * factor) / e[0] - 1.0


def core_entries_by_session(anchor: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for w in anchor["windows"]:
        art = json.loads((REPO_ROOT / w["path"]).read_text(encoding="utf-8"))
        for tr in art.get("trades", []):
            parts = str(tr.get("trade_key", "")).split(":")
            if len(parts) >= 2:
                result.setdefault(parts[1], []).append(str(tr["ticker"]))
    return result


def main() -> None:
    con = sqlite3.connect(str(DB))
    cal = sessions(con)
    idx = {d: i for i, d in enumerate(cal)}
    touch = json.loads(TOUCH.read_text(encoding="utf-8"))
    anchor = json.loads(ANCHOR.read_text(encoding="utf-8"))
    core_by_session = core_entries_by_session(anchor)

    rows = []
    voided = []
    for wname, wd in touch["windows"].items():
        for r in wd["selected"]:
            d = r["execution_date"]
            later = [s for s in cal if s > d]
            if len(later) < HOLD_SESSIONS + 1:
                voided.append({**r, "window": wname, "void_reason": "insufficient_calendar"})
                continue
            entry_s, exit_s = later[0], later[HOLD_SESSIONS]
            ret = leg_return(con, r["ticker"], entry_s, exit_s)
            if ret is None:
                voided.append({**r, "window": wname, "void_reason": "missing_entry_or_exit_bar"})
                continue
            core_tickers = core_by_session.get(entry_s, [])
            core_rets = [
                cr for cr in (leg_return(con, ct, entry_s, exit_s) for ct in core_tickers)
                if cr is not None
            ]
            base_ret = sum(core_rets) / len(core_rets) if core_rets else None
            spy = leg_return(con, "SPY", entry_s, exit_s)
            qqq = leg_return(con, "QQQ", entry_s, exit_s)
            treatment_value = NOTIONAL * (ret - COST)
            baseline_value = NOTIONAL * (base_ret - COST) if base_ret is not None else 0.0
            rows.append({
                "window": wname,
                "ticker": r["ticker"],
                "execution_date": d,
                "entry_session": entry_s,
                "exit_session": exit_s,
                "gross_return": round(ret, 6),
                "treatment_value": round(treatment_value, 2),
                "core_comparator_tickers": core_tickers,
                "core_comparator_return": None if base_ret is None else round(base_ret, 6),
                "baseline_value": round(baseline_value, 2),
                "replacement_value": round(treatment_value - baseline_value, 2),
                "replacement_value_double_cost": round(
                    NOTIONAL * (ret - DOUBLE_COST)
                    - (NOTIONAL * (base_ret - DOUBLE_COST) if base_ret is not None else 0.0), 2),
                "spy_value": None if spy is None else round(NOTIONAL * (spy - COST), 2),
                "qqq_value": None if qqq is None else round(NOTIONAL * (qqq - COST), 2),
            })

    # per-window metrics
    windows = {}
    for wname, wd in touch["windows"].items():
        wrows = [r for r in rows if r["window"] == wname]
        windows[wname] = {
            "declared_touches": wd["selected_touches"],
            "executed_touches": len(wrows),
            "replacement_value": round(sum(r["replacement_value"] for r in wrows), 2),
            "treatment_value": round(sum(r["treatment_value"] for r in wrows), 2),
            "baseline_value": round(sum(r["baseline_value"] for r in wrows), 2),
            "spy_value": round(sum(r["spy_value"] or 0.0 for r in wrows), 2),
            "qqq_value": round(sum(r["qqq_value"] or 0.0 for r in wrows), 2),
            "touch_floor_pass": len(wrows) >= 5,
        }

    aggregate = round(sum(r["replacement_value"] for r in rows), 2)
    aggregate_double = round(sum(r["replacement_value_double_cost"] for r in rows), 2)

    # concentration on positive replacement contributions
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

    # overlapping-hold clusters (union by interval overlap on session index)
    ivals = [(idx[r["entry_session"]], idx[r["exit_session"]], i) for i, r in enumerate(rows)]
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

    all_windows_positive = all(w["replacement_value"] > 0 for w in windows.values())
    all_floors = all(w["touch_floor_pass"] for w in windows.values())
    falsifier = {
        "touch_floor_all_windows": all_floors,
        "every_window_replacement_positive": all_windows_positive,
        "aggregate_replacement_positive": aggregate > 0,
        "double_cost_aggregate_positive": aggregate_double > 0,
        "max_single_ticker_positive_share": round(max_single, 4),
        "max_single_ok": max_single <= 0.5,
        "top5_positive_share": round(top5, 4),
        "top5_ok": top5 <= 0.6,
        "contribution_hhi": round(hhi, 4),
        "hhi_ok": hhi <= 0.35,
    }
    passes = all([
        falsifier["touch_floor_all_windows"],
        falsifier["every_window_replacement_positive"],
        falsifier["aggregate_replacement_positive"],
        falsifier["double_cost_aggregate_positive"],
        falsifier["max_single_ok"],
        falsifier["top5_ok"],
        falsifier["hhi_ok"],
    ])
    ci_includes_zero = ci_low <= 0.0 <= ci_high

    if not passes:
        disposition = "observed_only_rejected"
    elif ci_includes_zero:
        disposition = "observed_only_descriptive_lead"
    else:
        disposition = "observed_only_positive_lead"

    artifact = {
        "schema_version": 1,
        "experiment_id": "exp-20260728-006",
        "record_type": "private_replay_scout_result",
        "candidate_id": "cand-18ea7bbda2c85f2ad14a",
        "policy_version": "massive_forward_split_execution_drift_v2",
        "admission_class": "research_replay",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "cost_pct": COST,
        "double_cost_pct": DOUBLE_COST,
        "notional": NOTIONAL,
        "rows": rows,
        "voided_rows": voided,
        "windows": windows,
        "aggregate_replacement_value": aggregate,
        "aggregate_replacement_value_double_cost": aggregate_double,
        "aggregate_spy_value": round(sum(r["spy_value"] or 0.0 for r in rows), 2),
        "aggregate_qqq_value": round(sum(r["qqq_value"] or 0.0 for r in rows), 2),
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
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    print("wrote", OUT)
    print("disposition:", disposition)
    print("windows:", {k: v["replacement_value"] for k, v in windows.items()})
    print("aggregate:", aggregate, "double-cost:", aggregate_double)
    print("bootstrap CI90:", ci_low, ci_high)
    print("falsifier:", falsifier)


if __name__ == "__main__":
    main()
