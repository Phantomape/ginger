"""exp-20260824-004: exact legal-activation clock validation.

First post-activation outcome access for the hash-frozen 83-row roster.  The
economics are identical to exp-20260824-003; only the decision clock changes
from registration acceptance to exact EFFECT/final-prospectus activation.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.experiments.exp_20260824_003_sec_selling_holder_overhang import (
    ANNUAL_BORROW_RATE,
    BASE_PAIR_COST_RATE,
    BORROW_DAYS,
    NOTIONAL_PER_LEG,
    STRESS_PAIR_COST_RATE,
    TRADING_DAYS,
    bootstrap_overlapping_holds,
    contribution_metrics,
    price_ratio,
    sessions,
    sha256_file,
)


DB = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
ROSTER = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_activation_roster_20260824.json"
)
BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260824-004"
OUT = OUT_DIR / "exp_20260824_004_sec_selling_holder_activation.json"

EXPERIMENT_ID = "exp-20260824-004"
CANDIDATE_ID = "cand-03d8e9f3c30a97e7131d"
POLICY_VERSION = "sec_selling_holder_activation_h10_v1"
ROSTER_SHA256 = "722f71bcf26e37dbfd4755f25a3fd2caf686f95e9c484a3f77537cf99dd18a9a"
EXPECTED_WINDOWS = {"old_thin": 31, "mid_weak": 23, "late_strong": 29}


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
    roster_exact = len(frozen_rows) == 83 and declared_counts == EXPECTED_WINDOWS

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
                    "registration_accession": frozen["registration_accession"],
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
                "registration_accession": frozen["registration_accession"],
                "activation_at": frozen["activation_at"],
                "activation_source": frozen["activation_source"],
                "activation_accessions": frozen["activation_accessions"],
                "window": frozen["window"],
                "entry_session": entry_session,
                "h10_exit_session": exit_session,
                "stock_short_return": round(stock_short_return, 8),
                "spy_long_return": round(spy_long_return, 8),
                "gross_pair_pnl": round(gross_pair_pnl, 4),
                "base_net_pair_pnl": round(base_net, 4),
                "stress_net_pair_pnl": round(stress_net, 4),
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
            "mean_base_net_pair_pnl": round(base_value / len(window_rows), 2)
            if window_rows
            else None,
            "base_positive": base_value > 0,
        }

    aggregate_base = sum(float(row["base_net_pair_pnl"]) for row in evaluated)
    aggregate_stress = sum(
        float(row["stress_net_pair_pnl"]) for row in evaluated
    )
    concentration = contribution_metrics(evaluated)
    bootstrap = (
        bootstrap_overlapping_holds(evaluated, session_index) if evaluated else None
    )
    positive_windows = sum(bool(row["base_positive"]) for row in windows.values())
    all_rows_executed = len(evaluated) == 83 and not voided
    falsifier = {
        "roster_sha256_exact": roster_actual_sha == ROSTER_SHA256,
        "roster_exact_83_and_31_23_29": roster_exact,
        "all_83_rows_executed": all_rows_executed,
        "voided_row_count": len(voided),
        "at_least_20_each_window": all(
            int(row["executed_touches"]) >= 20 for row in windows.values()
        ),
        "positive_window_count": positive_windows,
        "at_least_two_windows_positive": positive_windows >= 2,
        "aggregate_base_positive": aggregate_base > 0,
        "aggregate_stress_positive": aggregate_stress > 0,
        "bootstrap_ci90_lower_positive": bool(
            bootstrap and float(bootstrap["ci90_low"]) > 0
        ),
        "max_single_ticker_positive_share": concentration[
            "max_single_ticker_positive_share"
        ],
        "max_single_ticker_ok": concentration[
            "max_single_ticker_positive_share"
        ]
        <= 0.40,
        "top5_positive_share": concentration["top5_positive_share"],
        "top5_ok": concentration["top5_positive_share"] <= 0.60,
        "absolute_contribution_hhi": concentration["absolute_contribution_hhi"],
        "hhi_ok": concentration["absolute_contribution_hhi"] <= 0.25,
    }
    passes = all(
        falsifier[key]
        for key in (
            "roster_sha256_exact",
            "roster_exact_83_and_31_23_29",
            "all_83_rows_executed",
            "at_least_20_each_window",
            "at_least_two_windows_positive",
            "aggregate_base_positive",
            "aggregate_stress_positive",
            "bootstrap_ci90_lower_positive",
            "max_single_ticker_ok",
            "top5_ok",
            "hhi_ok",
        )
    )
    disposition = (
        "observed_only_positive_lead" if passes else "observed_only_rejected"
    )
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
        "changed_variable_only": "decision clock: SEC acceptance -> exact legal activation",
        "roster": {
            "path": "data/alpha_search/sec_selling_holder_activation_roster_20260824.json",
            "sha256": roster_actual_sha,
            "declared_count": len(frozen_rows),
            "declared_counts_by_window": declared_counts,
        },
        "price_reader": (
            "data/warehouse/massive_history.sqlite daily_bars and stock_splits; "
            "same implementation imported from exp-20260824-003"
        ),
        "economics": {
            "notional_per_leg": NOTIONAL_PER_LEG,
            "base_total_pair_round_trip_cost_rate": BASE_PAIR_COST_RATE,
            "stress_total_pair_round_trip_cost_rate": STRESS_PAIR_COST_RATE,
            "annual_stock_borrow_rate": ANNUAL_BORROW_RATE,
            "borrow_days": BORROW_DAYS,
            "base_pair_cost_dollars_per_row": round(base_cost_dollars, 4),
            "stress_pair_cost_dollars_per_row": round(stress_cost_dollars, 4),
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
            )
            if evaluated
            else None,
        },
        "concentration": concentration,
        "bootstrap": bootstrap,
        "falsifier_checks": falsifier,
        "acceptance_rule_passed": passes,
        "disposition": disposition,
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
    print(
        json.dumps(
            {
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
                    key
                    for key, value in falsifier.items()
                    if isinstance(value, bool) and not value
                ],
                "artifact": str(OUT.relative_to(REPO_ROOT)).replace("\\", "/"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
