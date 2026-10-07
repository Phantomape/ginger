"""exp-20260824-003: selling-holder registration overhang private replay.

This is the first outcome access for the hash-frozen 118-row roster selected
before reservation.  It is research-PIT only, has an observed-only result
ceiling, and cannot place or alter orders.
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from fractions import Fraction
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DB = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
ROSTER = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_overhang_roster_20260824.json"
)
BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260824-003"
OUT = OUT_DIR / "exp_20260824_003_sec_selling_holder_overhang.json"

EXPERIMENT_ID = "exp-20260824-003"
CANDIDATE_ID = "cand-396251af1329881f695c"
POLICY_VERSION = "sec_selling_holder_overhang_h10_v1"
ROSTER_SHA256 = "b35b6078b19f3ab0aa90d23a4080e60a3e31ecfdeacff3bc02435882e83bd616"
EXPECTED_WINDOWS = {"old_thin": 38, "mid_weak": 45, "late_strong": 35}

NOTIONAL_PER_LEG = 2_000.0
BASE_PAIR_COST_RATE = 0.009
STRESS_PAIR_COST_RATE = 0.018
ANNUAL_BORROW_RATE = 0.20
BORROW_DAYS = 10
TRADING_DAYS = 252
BOOTSTRAP_N = 10_000
BOOTSTRAP_SEED = 20260824


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sessions(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "select distinct trade_date from daily_bars "
            "where ticker='SPY' order by trade_date"
        )
    ]


def splits_for(
    connection: sqlite3.Connection, ticker: str
) -> list[tuple[str, float]]:
    rows = connection.execute(
        "select execution_date, split_from, split_to from stock_splits "
        "where ticker=?",
        (ticker,),
    ).fetchall()
    return [
        (date, float(Fraction(str(split_to)) / Fraction(str(split_from))))
        for date, split_from, split_to in rows
    ]


def price_ratio(
    connection: sqlite3.Connection,
    ticker: str,
    entry_session: str,
    exit_session: str,
) -> float | None:
    entry = connection.execute(
        "select open from daily_bars where ticker=? and trade_date=?",
        (ticker, entry_session),
    ).fetchone()
    exit_row = connection.execute(
        "select close from daily_bars where ticker=? and trade_date=?",
        (ticker, exit_session),
    ).fetchone()
    if (
        entry is None
        or exit_row is None
        or entry[0] in (None, 0)
        or exit_row[0] in (None, 0)
    ):
        return None
    split_factor = 1.0
    for execution_date, ratio in splits_for(connection, ticker):
        if entry_session < execution_date <= exit_session:
            split_factor *= ratio
    return float(exit_row[0]) * split_factor / float(entry[0])


def contribution_metrics(rows: list[dict[str, object]]) -> dict[str, float]:
    by_ticker: dict[str, float] = {}
    for row in rows:
        ticker = str(row["ticker"])
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + float(
            row["base_net_pair_pnl"]
        )

    positive = {ticker: value for ticker, value in by_ticker.items() if value > 0}
    positive_sum = sum(positive.values())
    positive_shares = (
        sorted((value / positive_sum for value in positive.values()), reverse=True)
        if positive_sum
        else []
    )
    absolute_sum = sum(abs(value) for value in by_ticker.values())
    absolute_hhi = (
        sum((abs(value) / absolute_sum) ** 2 for value in by_ticker.values())
        if absolute_sum
        else 0.0
    )
    positive_hhi = sum(share**2 for share in positive_shares)
    return {
        "positive_contribution_dollars": round(positive_sum, 2),
        "max_single_ticker_positive_share": round(
            positive_shares[0] if positive_shares else 0.0, 6
        ),
        "top5_positive_share": round(sum(positive_shares[:5]), 6),
        "absolute_contribution_hhi": round(absolute_hhi, 6),
        "positive_contribution_hhi_descriptive": round(positive_hhi, 6),
    }


def bootstrap_overlapping_holds(
    rows: list[dict[str, object]], session_index: dict[str, int]
) -> dict[str, object]:
    intervals = sorted(
        (
            session_index[str(row["entry_session"])],
            session_index[str(row["h10_exit_session"])],
            index,
        )
        for index, row in enumerate(rows)
    )
    clusters: list[list[int]] = []
    current: list[int] = []
    current_end = -1
    for start, end, index in intervals:
        if not current or start <= current_end:
            current.append(index)
            current_end = max(current_end, end)
        else:
            clusters.append(current)
            current = [index]
            current_end = end
    if current:
        clusters.append(current)

    cluster_values = [
        sum(float(rows[index]["base_net_pair_pnl"]) for index in cluster)
        for cluster in clusters
    ]
    rng = random.Random(BOOTSTRAP_SEED)
    samples = sorted(
        sum(rng.choice(cluster_values) for _ in cluster_values)
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
        "decision_gate": False,
    }


def main() -> None:
    roster_actual_sha = sha256_file(ROSTER)
    if roster_actual_sha != ROSTER_SHA256:
        raise RuntimeError(
            f"frozen roster hash mismatch: {roster_actual_sha} != {ROSTER_SHA256}"
        )
    baseline_before_sha = sha256_file(BASELINE)
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    frozen_rows = roster["rows"]

    declared_counts = {window: 0 for window in EXPECTED_WINDOWS}
    for row in frozen_rows:
        declared_counts[row["window"]] += 1
    roster_exact = len(frozen_rows) == 118 and declared_counts == EXPECTED_WINDOWS

    connection = sqlite3.connect(str(DB))
    calendar = sessions(connection)
    session_index = {session: index for index, session in enumerate(calendar)}
    borrow_dollars = (
        NOTIONAL_PER_LEG * ANNUAL_BORROW_RATE * BORROW_DAYS / TRADING_DAYS
    )
    base_cost_dollars = NOTIONAL_PER_LEG * BASE_PAIR_COST_RATE
    stress_cost_dollars = NOTIONAL_PER_LEG * STRESS_PAIR_COST_RATE

    evaluated: list[dict[str, object]] = []
    voided: list[dict[str, object]] = []
    for frozen in frozen_rows:
        ticker = frozen["ticker"]
        entry_session = frozen["entry_session"]
        exit_session = frozen["h10_exit_session"]
        stock_ratio = price_ratio(connection, ticker, entry_session, exit_session)
        spy_ratio = price_ratio(connection, "SPY", entry_session, exit_session)
        if stock_ratio is None or spy_ratio is None:
            voided.append(
                {
                    "ticker": ticker,
                    "accession": frozen["accession"],
                    "window": frozen["window"],
                    "entry_session": entry_session,
                    "h10_exit_session": exit_session,
                    "void_reason": "missing_stock_or_spy_entry_open_or_h10_close",
                }
            )
            continue

        stock_short_return = 1.0 - stock_ratio
        spy_long_return = spy_ratio - 1.0
        gross_pair_pnl = NOTIONAL_PER_LEG * (
            stock_short_return + spy_long_return
        )
        base_net = gross_pair_pnl - base_cost_dollars - borrow_dollars
        stress_net = gross_pair_pnl - stress_cost_dollars - borrow_dollars
        evaluated.append(
            {
                "ticker": ticker,
                "accession": frozen["accession"],
                "accepted_at": frozen["accepted_at"],
                "window": frozen["window"],
                "entry_session": entry_session,
                "h10_exit_session": exit_session,
                "stock_short_return": round(stock_short_return, 8),
                "spy_long_return": round(spy_long_return, 8),
                "gross_pair_pnl": round(gross_pair_pnl, 4),
                "base_net_pair_pnl": round(base_net, 4),
                "stress_net_pair_pnl": round(stress_net, 4),
                "base_net_pair_bps_on_one_leg_notional": round(
                    base_net / NOTIONAL_PER_LEG * 10_000, 4
                ),
            }
        )
    connection.close()

    windows: dict[str, dict[str, object]] = {}
    for window, expected_count in EXPECTED_WINDOWS.items():
        window_rows = [row for row in evaluated if row["window"] == window]
        base_value = sum(float(row["base_net_pair_pnl"]) for row in window_rows)
        stress_value = sum(float(row["stress_net_pair_pnl"]) for row in window_rows)
        windows[window] = {
            "declared_touches": expected_count,
            "executed_touches": len(window_rows),
            "base_net_pair_pnl": round(base_value, 2),
            "stress_net_pair_pnl_descriptive": round(stress_value, 2),
            "mean_base_net_pair_pnl": round(
                base_value / len(window_rows), 2
            ) if window_rows else None,
            "base_positive": base_value > 0,
        }

    aggregate_base = sum(float(row["base_net_pair_pnl"]) for row in evaluated)
    aggregate_stress = sum(
        float(row["stress_net_pair_pnl"]) for row in evaluated
    )
    concentration = contribution_metrics(evaluated)
    bootstrap = bootstrap_overlapping_holds(evaluated, session_index) if evaluated else None
    all_rows_executed = len(evaluated) == 118 and not voided

    falsifier = {
        "roster_sha256_exact": roster_actual_sha == ROSTER_SHA256,
        "roster_exact_118_and_38_45_35": roster_exact,
        "all_118_rows_executed": all_rows_executed,
        "voided_row_count": len(voided),
        "at_least_30_each_window": all(
            int(row["executed_touches"]) >= 30 for row in windows.values()
        ),
        "every_window_base_positive": all(
            bool(row["base_positive"]) for row in windows.values()
        ),
        "aggregate_base_positive": aggregate_base > 0,
        "aggregate_stress_positive": aggregate_stress > 0,
        "max_single_ticker_positive_share": concentration[
            "max_single_ticker_positive_share"
        ],
        "max_single_ticker_ok": concentration[
            "max_single_ticker_positive_share"
        ] <= 0.40,
        "top5_positive_share": concentration["top5_positive_share"],
        "top5_ok": concentration["top5_positive_share"] <= 0.60,
        "absolute_contribution_hhi": concentration["absolute_contribution_hhi"],
        "hhi_ok": concentration["absolute_contribution_hhi"] <= 0.25,
    }
    passes = all(
        [
            falsifier["roster_sha256_exact"],
            falsifier["roster_exact_118_and_38_45_35"],
            falsifier["all_118_rows_executed"],
            falsifier["at_least_30_each_window"],
            falsifier["every_window_base_positive"],
            falsifier["aggregate_base_positive"],
            falsifier["aggregate_stress_positive"],
            falsifier["max_single_ticker_ok"],
            falsifier["top5_ok"],
            falsifier["hhi_ok"],
        ]
    )
    if not passes:
        disposition = "observed_only_rejected"
    elif bootstrap and bootstrap["includes_zero"]:
        disposition = "observed_only_descriptive_lead"
    else:
        disposition = "observed_only_positive_lead"

    baseline_after_sha = sha256_file(BASELINE)
    if baseline_after_sha != baseline_before_sha:
        raise RuntimeError("baseline bytes changed during private replay")

    artifact = {
        "schema_version": 1,
        "record_type": "private_replay_scout_result",
        "experiment_id": EXPERIMENT_ID,
        "candidate_id": CANDIDATE_ID,
        "policy_version": POLICY_VERSION,
        "admission_class": "research_replay",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "orders_enabled": False,
        "paper_live_eligible": False,
        "historical_broker_locate_available": False,
        "roster": {
            "path": "data/alpha_search/sec_selling_holder_overhang_roster_20260824.json",
            "sha256": roster_actual_sha,
            "declared_count": len(frozen_rows),
            "declared_counts_by_window": declared_counts,
        },
        "price_reader": (
            "data/warehouse/massive_history.sqlite daily_bars and stock_splits; "
            "identical entry-open/H10-close reader for stock and SPY"
        ),
        "economics": {
            "notional_per_leg": NOTIONAL_PER_LEG,
            "base_total_pair_round_trip_cost_rate": BASE_PAIR_COST_RATE,
            "stress_total_pair_round_trip_cost_rate": STRESS_PAIR_COST_RATE,
            "base_pair_cost_dollars_per_row": round(base_cost_dollars, 4),
            "stress_pair_cost_dollars_per_row": round(stress_cost_dollars, 4),
            "annual_stock_borrow_rate": ANNUAL_BORROW_RATE,
            "borrow_days": BORROW_DAYS,
            "borrow_dollars_per_row": round(borrow_dollars, 4),
        },
        "row_count": len(evaluated),
        "voided_rows": voided,
        "windows": windows,
        "aggregate": {
            "base_net_pair_pnl": round(aggregate_base, 2),
            "stress_net_pair_pnl": round(aggregate_stress, 2),
            "mean_base_net_pair_pnl": round(
                aggregate_base / len(evaluated), 2
            ) if evaluated else None,
            "base_net_pair_bps_on_one_leg_notional": round(
                aggregate_base / (len(evaluated) * NOTIONAL_PER_LEG) * 10_000,
                4,
            ) if evaluated else None,
        },
        "concentration": concentration,
        "bootstrap": bootstrap,
        "falsifier_checks": falsifier,
        "acceptance_rule_passed": passes,
        "disposition": disposition,
        "baseline_result_file": (
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
        ),
        "baseline_sha256_before": baseline_before_sha,
        "baseline_sha256_after": baseline_after_sha,
        "production_impact": {
            "shared_policy_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "paper_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
        },
        "rows": evaluated,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "disposition": disposition,
        "acceptance_rule_passed": passes,
        "row_count": len(evaluated),
        "voided_row_count": len(voided),
        "windows": {
            key: value["base_net_pair_pnl"] for key, value in windows.items()
        },
        "aggregate_base_net_pair_pnl": round(aggregate_base, 2),
        "aggregate_stress_net_pair_pnl": round(aggregate_stress, 2),
        "bootstrap_ci90": (
            [bootstrap["ci90_low"], bootstrap["ci90_high"]]
            if bootstrap
            else None
        ),
        "failed_checks": [
            key for key, value in falsifier.items()
            if isinstance(value, bool) and not value
        ],
        "artifact": str(OUT.relative_to(REPO_ROOT)).replace("\\", "/"),
    }, indent=2))


if __name__ == "__main__":
    main()
