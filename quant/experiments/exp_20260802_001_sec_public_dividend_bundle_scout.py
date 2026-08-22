"""exp-20260802-001: SEC-public recurring-dividend bundle research replay.

Private replay scout only (research_pit; result ceiling observed_only). The
19-row roster, public decision clocks, coannouncement strata, and one-use
core-or-cash allocation were frozen before this runner accessed returns.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import sqlite3
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
DB = REPO_ROOT / "data/warehouse/massive_history.sqlite"
PREFLIGHT = (
    REPO_ROOT
    / "data/alpha_search/dividend_recurring_public_timestamp_preflight_20260801.json"
)
ALLOCATION = (
    REPO_ROOT
    / "data/alpha_search/dividend_recurring_bundle_comparator_allocation_20260801.json"
)
CANDIDATE = (
    REPO_ROOT
    / "data/alpha_search/dividend_recurring_bundle_candidate_amended_20260801.json"
)
OUT_DIR = REPO_ROOT / "data/experiments/exp-20260802-001"
OUT = OUT_DIR / "exp_20260802_001_sec_public_dividend_bundle_scout.json"

NOTIONAL = 4_000.0
COST = 0.0035
DOUBLE_COST = 0.0070
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20260802
EXPECTED_WINDOWS = {"old_thin": 5, "mid_weak": 5, "late_strong": 9}
NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sessions(con: sqlite3.Connection, ticker: str) -> list[str]:
    return [
        str(row[0])
        for row in con.execute(
            "SELECT trade_date FROM daily_bars WHERE ticker=? ORDER BY trade_date",
            (ticker,),
        )
    ]


def splits_for(con: sqlite3.Connection, ticker: str) -> list[tuple[str, float]]:
    rows = con.execute(
        "SELECT execution_date, split_from, split_to FROM stock_splits WHERE ticker=?",
        (ticker,),
    ).fetchall()
    return [
        (str(date), float(Fraction(str(to_value)) / Fraction(str(from_value))))
        for date, from_value, to_value in rows
    ]


def bar(con: sqlite3.Connection, ticker: str, date: str):
    return con.execute(
        "SELECT open, close FROM daily_bars WHERE ticker=? AND trade_date=?",
        (ticker, date),
    ).fetchone()


def leg_return(
    con: sqlite3.Connection, ticker: str, entry_session: str, exit_session: str
):
    """Split-normalized gross return from entry open through exit close."""

    entry = bar(con, ticker, entry_session)
    exit_bar = bar(con, ticker, exit_session)
    if (
        entry is None
        or entry[0] in (None, 0)
        or exit_bar is None
        or exit_bar[1] in (None, 0)
    ):
        return None
    factor = 1.0
    for date, ratio in splits_for(con, ticker):
        if entry_session < date <= exit_session:
            factor *= ratio
    return (float(exit_bar[1]) * factor) / float(entry[0]) - 1.0


def parse_clock(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def decision_clock_check(
    con: sqlite3.Connection, *, ticker: str, ready_at: str, entry_session: str
) -> dict[str, object]:
    ready = parse_clock(ready_at)
    entry_open = dt.datetime.combine(
        dt.date.fromisoformat(entry_session), dt.time(9, 30), tzinfo=NY
    ).astimezone(UTC)
    prior_sessions = [date for date in sessions(con, ticker) if date < entry_session]
    prior_open = None
    if prior_sessions:
        prior_open = dt.datetime.combine(
            dt.date.fromisoformat(prior_sessions[-1]), dt.time(9, 30), tzinfo=NY
        ).astimezone(UTC)
    return {
        "entry_open_after_ready": entry_open > ready,
        "entry_is_first_open_after_ready": prior_open is None or prior_open <= ready,
    }


def clustered_bootstrap(rows: list[dict[str, object]], calendar: list[str]) -> dict[str, object]:
    index = {date: offset for offset, date in enumerate(calendar)}
    intervals = sorted(
        (
            index[str(row["entry_session"])],
            index[str(row["exit_session"])],
            offset,
        )
        for offset, row in enumerate(rows)
    )
    clusters: list[list[int]] = []
    current: list[int] = []
    current_end = -1
    for start, end, offset in intervals:
        if not current or start <= current_end:
            current.append(offset)
            current_end = max(current_end, end)
        else:
            clusters.append(current)
            current = [offset]
            current_end = end
    if current:
        clusters.append(current)
    cluster_sums = [
        sum(float(rows[offset]["replacement_value"]) for offset in cluster)
        for cluster in clusters
    ]
    rng = random.Random(BOOTSTRAP_SEED)
    samples = sorted(
        sum(rng.choice(cluster_sums) for _ in cluster_sums)
        for _ in range(BOOTSTRAP_N)
    )
    low = samples[int(0.05 * BOOTSTRAP_N)]
    high = samples[int(0.95 * BOOTSTRAP_N) - 1]
    return {
        "method": "overlapping-hold cluster block bootstrap",
        "cluster_count": len(clusters),
        "resamples": BOOTSTRAP_N,
        "seed": BOOTSTRAP_SEED,
        "ci90_low": round(low, 2),
        "ci90_high": round(high, 2),
        "includes_zero": low <= 0.0 <= high,
    }


def main() -> None:
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    allocation = json.loads(ALLOCATION.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    expected_preflight_hash = candidate["treatment"]["preflight_attachment_hash"]
    expected_allocation_hash = candidate["baseline"][
        "comparator_allocation_attachment_hash"
    ]
    input_hash_checks = {
        "preflight_expected": expected_preflight_hash,
        "preflight_actual": sha256_file(PREFLIGHT),
        "allocation_expected": expected_allocation_hash,
        "allocation_actual": sha256_file(ALLOCATION),
    }
    input_hashes_match = (
        input_hash_checks["preflight_expected"]
        == input_hash_checks["preflight_actual"]
        and input_hash_checks["allocation_expected"]
        == input_hash_checks["allocation_actual"]
    )

    treatment_rows = list(preflight["timestamp_verified_bundle_rows"])
    allocation_by_key = {row["decision_key"]: row for row in allocation["rows"]}
    treatment_keys = {row["decision_key"] for row in treatment_rows}
    allocation_keys = set(allocation_by_key)
    roster_keys_match = treatment_keys == allocation_keys

    con = sqlite3.connect(str(DB))
    calendar = sessions(con, "SPY")
    rows: list[dict[str, object]] = []
    voided: list[dict[str, object]] = []
    core_slot_price_checks: list[dict[str, object]] = []
    clock_checks: list[dict[str, object]] = []
    for source in sorted(
        treatment_rows, key=lambda row: (row["entry_session"], row["decision_key"])
    ):
        decision_key = str(source["decision_key"])
        assigned = allocation_by_key[decision_key]
        entry_session = str(source["entry_session"])
        exit_session = str(source["exit_session"])
        ticker = str(source["ticker"])
        clock = decision_clock_check(
            con,
            ticker=ticker,
            ready_at=str(source["decision_ready_at"]),
            entry_session=entry_session,
        )
        clock_checks.append({"decision_key": decision_key, **clock})
        treatment_return = leg_return(con, ticker, entry_session, exit_session)
        if treatment_return is None:
            voided.append(
                {"decision_key": decision_key, "void_reason": "missing_treatment_bar"}
            )
            continue

        core_slot_id = assigned["core_slot_id"]
        core_return = None
        if assigned["comparator_kind"] == "core_slot":
            core_ticker, core_entry_date, recorded_open = str(core_slot_id).split(":")
            core_return = leg_return(con, core_ticker, entry_session, exit_session)
            core_entry_bar = bar(con, core_ticker, core_entry_date)
            core_slot_price_checks.append(
                {
                    "core_slot_id": core_slot_id,
                    "entry_session_matches": core_entry_date == entry_session,
                    "recorded_entry_open": float(recorded_open),
                    "warehouse_entry_open": None
                    if core_entry_bar is None
                    else float(core_entry_bar[0]),
                }
            )
            if core_return is None:
                voided.append(
                    {"decision_key": decision_key, "void_reason": "missing_core_bar"}
                )
                continue

        treatment_value = NOTIONAL * (treatment_return - COST)
        treatment_value_double = NOTIONAL * (treatment_return - DOUBLE_COST)
        baseline_value = (
            0.0 if core_return is None else NOTIONAL * (core_return - COST)
        )
        baseline_value_double = (
            0.0 if core_return is None else NOTIONAL * (core_return - DOUBLE_COST)
        )
        spy_return = leg_return(con, "SPY", entry_session, exit_session)
        qqq_return = leg_return(con, "QQQ", entry_session, exit_session)
        rows.append(
            {
                "decision_key": decision_key,
                "ticker": ticker,
                "window": source["window"],
                "lifecycle_class": source["lifecycle_class"],
                "coannouncement_confounds": source["coannouncement_confounds"],
                "declaration_date": source["declaration_date"],
                "public_known_at": source["public_known_at"],
                "decision_ready_at": source["decision_ready_at"],
                "entry_session": entry_session,
                "exit_session": exit_session,
                "gross_return": round(treatment_return, 6),
                "treatment_value": round(treatment_value, 2),
                "comparator_kind": assigned["comparator_kind"],
                "core_slot_id": core_slot_id,
                "core_comparator_return": None
                if core_return is None
                else round(core_return, 6),
                "baseline_value": round(baseline_value, 2),
                "replacement_value": round(treatment_value - baseline_value, 2),
                "replacement_value_double_cost": round(
                    treatment_value_double - baseline_value_double, 2
                ),
                "spy_value": None
                if spy_return is None
                else round(NOTIONAL * (spy_return - COST), 2),
                "qqq_value": None
                if qqq_return is None
                else round(NOTIONAL * (qqq_return - COST), 2),
            }
        )
    con.close()

    window_counts = {
        window: sum(row["window"] == window for row in treatment_rows)
        for window in EXPECTED_WINDOWS
    }
    windows: dict[str, dict[str, object]] = {}
    for window, declared in EXPECTED_WINDOWS.items():
        subset = [row for row in rows if row["window"] == window]
        windows[window] = {
            "declared_touches": declared,
            "executed_touches": len(subset),
            "touch_floor_pass": len(subset) >= 5,
            "treatment_value": round(
                sum(float(row["treatment_value"]) for row in subset), 2
            ),
            "baseline_value": round(
                sum(float(row["baseline_value"]) for row in subset), 2
            ),
            "replacement_value": round(
                sum(float(row["replacement_value"]) for row in subset), 2
            ),
            "replacement_value_double_cost": round(
                sum(float(row["replacement_value_double_cost"]) for row in subset),
                2,
            ),
            "spy_value": round(sum(float(row["spy_value"] or 0.0) for row in subset), 2),
            "qqq_value": round(sum(float(row["qqq_value"] or 0.0) for row in subset), 2),
        }

    aggregate = round(sum(float(row["replacement_value"]) for row in rows), 2)
    aggregate_double = round(
        sum(float(row["replacement_value_double_cost"]) for row in rows), 2
    )
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        by_ticker[str(row["ticker"])] += float(row["replacement_value"])
    positives = {ticker: value for ticker, value in by_ticker.items() if value > 0}
    positive_sum = sum(positives.values())
    positive_shares = sorted(
        (value / positive_sum for value in positives.values()), reverse=True
    ) if positive_sum else []
    max_single = positive_shares[0] if positive_shares else 0.0
    top_five = sum(positive_shares[:5])
    absolute_sum = sum(abs(value) for value in by_ticker.values())
    hhi = (
        sum((abs(value) / absolute_sum) ** 2 for value in by_ticker.values())
        if absolute_sum
        else 0.0
    )

    strata: dict[str, dict[str, object]] = {}
    strata_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        confounds = list(row["coannouncement_confounds"])
        signature = "+".join(sorted(str(value) for value in confounds)) or "none"
        strata_rows[signature].append(row)
    for signature, subset in sorted(strata_rows.items()):
        strata[signature] = {
            "touches": len(subset),
            "replacement_value": round(
                sum(float(row["replacement_value"]) for row in subset), 2
            ),
        }

    bootstrap = clustered_bootstrap(rows, calendar)
    positive_windows = sum(
        float(metrics["replacement_value"]) > 0 for metrics in windows.values()
    )
    all_clocks_pass = all(
        bool(row["entry_open_after_ready"])
        and bool(row["entry_is_first_open_after_ready"])
        for row in clock_checks
    )
    core_slot_identity_checks_pass = all(
        bool(check["entry_session_matches"])
        and check["warehouse_entry_open"] is not None
        for check in core_slot_price_checks
    )
    falsifier = {
        "input_hashes_match": input_hashes_match,
        "roster_keys_match": roster_keys_match,
        "roster_exact_5_5_9": window_counts == EXPECTED_WINDOWS,
        "all_19_rows_executed": len(rows) == 19 and not voided,
        "decision_clocks_reproduce": all_clocks_pass,
        "core_slot_identity_checks_pass": core_slot_identity_checks_pass,
        "touch_floor_all_windows": all(
            bool(metrics["touch_floor_pass"]) for metrics in windows.values()
        ),
        "positive_windows": positive_windows,
        "at_least_two_windows_positive": positive_windows >= 2,
        "aggregate_replacement_positive": aggregate > 0,
        "double_cost_aggregate_positive": aggregate_double > 0,
        "max_single_ticker_positive_share": round(max_single, 4),
        "max_single_ok": max_single <= 0.40,
        "top5_positive_share": round(top_five, 4),
        "top5_ok": top_five <= 0.65,
        "contribution_hhi": round(hhi, 4),
        "hhi_ok": hhi <= 0.25,
    }
    passes = all(
        falsifier[key]
        for key in (
            "input_hashes_match",
            "roster_keys_match",
            "roster_exact_5_5_9",
            "all_19_rows_executed",
            "decision_clocks_reproduce",
            "core_slot_identity_checks_pass",
            "touch_floor_all_windows",
            "at_least_two_windows_positive",
            "aggregate_replacement_positive",
            "double_cost_aggregate_positive",
            "max_single_ok",
            "top5_ok",
            "hhi_ok",
        )
    )
    if not passes:
        disposition = "observed_only_rejected"
    elif bootstrap["includes_zero"]:
        disposition = "observed_only_descriptive_lead"
    else:
        disposition = "observed_only_positive_lead"

    artifact = {
        "schema_version": 1,
        "experiment_id": "exp-20260802-001",
        "record_type": "private_replay_scout_result",
        "candidate_id": "cand-e58f61d5b842a1cc7173",
        "policy_version": "sec_public_recurring_capital_return_bundle_first_safe_open_h10_v1",
        "admission_class": "research_replay",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "price_reader": "data/warehouse/massive_history.sqlite canonical research warehouse",
        "notional": NOTIONAL,
        "cost_pct": COST,
        "double_cost_pct": DOUBLE_COST,
        "input_hash_checks": input_hash_checks,
        "rows": rows,
        "voided_rows": voided,
        "decision_clock_checks": clock_checks,
        "core_slot_price_checks": core_slot_price_checks,
        "windows": windows,
        "aggregate_replacement_value": aggregate,
        "aggregate_replacement_value_double_cost": aggregate_double,
        "aggregate_spy_value": round(
            sum(float(row["spy_value"] or 0.0) for row in rows), 2
        ),
        "aggregate_qqq_value": round(
            sum(float(row["qqq_value"] or 0.0) for row in rows), 2
        ),
        "coannouncement_strata": strata,
        "bootstrap": bootstrap,
        "falsifier_checks": falsifier,
        "disposition": disposition,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT)
    print("disposition:", disposition)
    print("windows:", {key: value["replacement_value"] for key, value in windows.items()})
    print("aggregate:", aggregate, "double-cost:", aggregate_double)
    print("bootstrap CI90:", bootstrap["ci90_low"], bootstrap["ci90_high"])
    print("falsifier:", falsifier)


if __name__ == "__main__":
    main()
