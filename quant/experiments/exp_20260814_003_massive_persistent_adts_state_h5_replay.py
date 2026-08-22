"""exp-20260814-003: persistent-ADTS state H5 research replay (observed_only ceiling).

Frozen falsifier (card cand-2a61935d81ccb09ae8fd, promotion v3):
- fixed 183-row roster, >=5 executable treatment touches per standard window;
- treatment net after 35bp total round-trip cost positive vs zero-return cash
  AND above same-clock 35bp-costed USD4000 SPY and QQQ in aggregate;
- >=2 of 3 standard windows positive vs cash;
- treatment stays positive vs cash under 70bp total cost;
- max ticker selection share <=15%, max concurrency <=3;
- every missing execution input fails closed (invalidates the run).

Treatment uses USD4000 target notional with whole-share rounding (execution
envelope). Index comparators use exact USD4000 fractional notional at the
identical clock with the same 35bp round-trip charge: replacement value should
not be flattered by whole-share rounding noise on a USD600 ETF price.
Sources: the hash-bound research warehouse (research_pit) only. No paper/live
path is touched; trade_enabled stays false.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROSTER = REPO / "data/alpha_search/massive_persistent_trade_size_roster_20260814.json"
DB = REPO / "data/warehouse/massive_history.sqlite"
OUT_DIR = REPO / "data/experiments/exp-20260814-003"
NOTIONAL = 4000.0
COST = 0.0035
STRESS = 0.0070
WINDOWS = ("old_thin", "mid_weak", "late_strong")


def bar(cur, ticker: str, date: str):
    row = cur.execute(
        "select open, close from daily_bars where ticker=? and trade_date=?",
        (ticker, date),
    ).fetchone()
    return row


def main() -> None:
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    rows = roster["rows"]
    assert len(rows) == 183, "frozen roster must stay exactly 183 rows"
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()

    contract_failures: list[dict] = []
    per_row: list[dict] = []
    for r in rows:
        entry_d, exit_d, tk = r["entry_session"], r["h5_exit_session"], r["ticker"]
        legs = {}
        ok = True
        for leg in (tk, "SPY", "QQQ"):
            eb, xb = bar(cur, leg, entry_d), bar(cur, leg, exit_d)
            if (
                not eb or not xb
                or eb[0] is None or xb[1] is None
                or eb[0] <= 0 or xb[1] <= 0
            ):
                contract_failures.append(
                    {"ticker": tk, "leg": leg, "entry": entry_d, "exit": exit_d}
                )
                ok = False
                break
            legs[leg] = (float(eb[0]), float(xb[1]))
        if not ok:
            continue
        o, c = legs[tk]
        shares = math.floor(NOTIONAL / o)
        if shares <= 0:
            contract_failures.append(
                {"ticker": tk, "leg": tk, "entry": entry_d, "reason": "zero_shares"}
            )
            continue
        notional = shares * o
        net = shares * (c - o) - notional * COST
        stress_net = shares * (c - o) - notional * STRESS
        comp = {}
        for leg in ("SPY", "QQQ"):
            lo, lc = legs[leg]
            comp[leg] = NOTIONAL * (lc / lo - 1.0) - NOTIONAL * COST
        per_row.append(
            {
                "ticker": tk,
                "window": r["window"],
                "entry_session": entry_d,
                "h5_exit_session": exit_d,
                "entry_open": o,
                "exit_close": c,
                "shares": shares,
                "notional": round(notional, 2),
                "treatment_net_35bp": round(net, 2),
                "treatment_net_70bp": round(stress_net, 2),
                "spy_net_35bp": round(comp["SPY"], 2),
                "qqq_net_35bp": round(comp["QQQ"], 2),
            }
        )

    invalid = bool(contract_failures)
    agg = lambda k: round(sum(x[k] for x in per_row), 2)  # noqa: E731
    by_window = {
        w: round(sum(x["treatment_net_35bp"] for x in per_row if x["window"] == w), 2)
        for w in WINDOWS
    }
    touches = {
        w: sum(1 for x in per_row if x["window"] == w) for w in WINDOWS
    }
    ticker_counts: dict[str, int] = defaultdict(int)
    for x in per_row:
        ticker_counts[x["ticker"]] += 1
    max_share = max(ticker_counts.values()) / len(per_row) if per_row else 1.0

    active: list[tuple[str, str]] = [
        (x["entry_session"], x["h5_exit_session"]) for x in per_row
    ]
    sessions = sorted({d for iv in active for d in iv})
    max_conc = 0
    for s in sessions:
        max_conc = max(max_conc, sum(1 for a, b in active if a <= s <= b))

    checks = {
        "no_contract_failures": not invalid,
        "touch_floor_5_every_window": all(touches[w] >= 5 for w in WINDOWS),
        "aggregate_positive_vs_cash_35bp": agg("treatment_net_35bp") > 0,
        "aggregate_beats_spy": agg("treatment_net_35bp") > agg("spy_net_35bp"),
        "aggregate_beats_qqq": agg("treatment_net_35bp") > agg("qqq_net_35bp"),
        "windows_positive_vs_cash_at_least_2of3": sum(
            1 for w in WINDOWS if by_window[w] > 0
        ) >= 2,
        "aggregate_positive_under_70bp_stress": agg("treatment_net_70bp") > 0,
        "max_ticker_share_le_15pct": max_share <= 0.15,
        "max_concurrency_le_3": max_conc <= 3,
    }
    falsifier_pass = all(checks.values())
    decision = "invalid" if invalid else ("observed_only" if falsifier_pass else "rejected")

    result = {
        "schema_version": 1,
        "record_type": "research_replay_result",
        "experiment_id": "exp-20260814-003",
        "policy": "massive_persistent_adts_state_h5_v1",
        "outcome_blind": False,
        "trade_enabled": False,
        "pit_tier": "research_pit",
        "result_ceiling": "observed_only",
        "row_count": len(per_row),
        "contract_failures": contract_failures,
        "aggregate": {
            "treatment_net_35bp": agg("treatment_net_35bp"),
            "treatment_net_70bp": agg("treatment_net_70bp"),
            "spy_net_35bp": agg("spy_net_35bp"),
            "qqq_net_35bp": agg("qqq_net_35bp"),
            "cash_net": 0.0,
        },
        "by_window_treatment_net_35bp": by_window,
        "touches_by_window": touches,
        "max_ticker_selection_share": round(max_share, 6),
        "max_observed_concurrency": max_conc,
        "checks": checks,
        "falsifier_pass": falsifier_pass,
        "decision": decision,
        "expected_value_score": agg("treatment_net_35bp"),
        "per_row": per_row,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before = {
        "schema_version": 1,
        "record_type": "research_replay_baseline",
        "experiment_id": "exp-20260814-003",
        "policy": "cash_no_new_entry",
        "aggregate": {"cash_net": 0.0},
        "expected_value_score": 0.0,
        "note": "Primary baseline is USD4000 zero-return cash at each frozen entry/exit clock; SPY/QQQ replacement values are recorded on the after side at the identical clock.",
    }
    (OUT_DIR / "scout_before.json").write_text(
        json.dumps(before, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "exp_20260814_003_adts_state_h5_replay.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: result[k] for k in (
        "row_count", "aggregate", "by_window_treatment_net_35bp", "touches_by_window",
        "max_ticker_selection_share", "max_observed_concurrency", "checks",
        "falsifier_pass", "decision",
    )}, indent=2))


if __name__ == "__main__":
    main()
