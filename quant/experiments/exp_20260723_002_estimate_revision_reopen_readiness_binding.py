"""Materialize exp-20260723-002 estimate-revision readiness counter repair."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_reopen_readiness as readiness  # noqa: E402


EXPERIMENT_ID = "exp-20260723-002"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_PATH = OUT_DIR / "before_estimate_revision_reopen_readiness.json"
AFTER_PATH = OUT_DIR / "after_estimate_revision_reopen_readiness.json"
REPORT_PATH = OUT_DIR / "exp_20260723_002_estimate_revision_reopen_readiness_binding.json"
CANONICAL_PATH = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "estimate_revision_readiness_latest.json"
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _phase2_lane(snapshot: dict) -> dict:
    return next(
        lane for lane in snapshot["lanes"] if lane["lane"] == "phase2_estimate_revision"
    )


def main() -> int:
    canonical = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    before = {
        "experiment_id": EXPERIMENT_ID,
        "artifact_role": "before",
        "implementation": "hard_coded_zero_counters",
        "lane": "phase2_estimate_revision",
        "counters": {
            "qualified_nonflat_decisions": 0,
            "mapped_tickers": 0,
            "actual_cash_conflicts": 0,
            "settled_h5": 0,
            "settled_h10": 0,
            "settled_h20": 0,
        },
        "status": "manual_check_required",
        "production_impact": "measurement_only_no_trading_change",
    }

    snapshot = readiness.build()
    lane = _phase2_lane(snapshot)
    expected_counters = {
        "qualified_nonflat_decisions": canonical["independent_decisions"],
        "mapped_tickers": canonical["mapped_ticker_count"],
        "actual_cash_conflicts": canonical["actual_cash_conflict_decisions"],
        "settled_h5": canonical["settled_independent_decisions_by_horizon"]["h5"],
        "settled_h10": canonical["settled_independent_decisions_by_horizon"]["h10"],
        "settled_h20": canonical["settled_independent_decisions_by_horizon"]["h20"],
    }
    if lane["counters"] != expected_counters:
        raise AssertionError(
            f"builder counters {lane['counters']!r} != canonical {expected_counters!r}"
        )
    if lane["status"] != "not_ready":
        raise AssertionError(f"expected parked lane to remain not_ready, got {lane['status']!r}")

    after = {
        "experiment_id": EXPERIMENT_ID,
        "artifact_role": "after",
        "implementation": "canonical_fail_closed_counter_binding",
        "lane": lane,
        "canonical_generated_at": canonical.get("generated_at"),
        "canonical_surface_id": canonical.get("surface_id"),
        "production_impact": "measurement_only_no_trading_change",
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "decision": "accepted_measurement_repair",
        "changed_variable": "estimate_revision_reopen_readiness_canonical_counter_binding_v1",
        "before": before,
        "after": after,
        "delta": {
            "qualified_nonflat_decisions": (
                expected_counters["qualified_nonflat_decisions"]
                - before["counters"]["qualified_nonflat_decisions"]
            ),
            "mapped_tickers": (
                expected_counters["mapped_tickers"]
                - before["counters"]["mapped_tickers"]
            ),
            "actual_cash_conflicts": expected_counters["actual_cash_conflicts"],
            "settled_h5": expected_counters["settled_h5"],
            "settled_h10": expected_counters["settled_h10"],
            "settled_h20": expected_counters["settled_h20"],
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
        },
        "acceptance_checks": {
            "canonical_counter_match": True,
            "independent_decision_bar_passed": (
                expected_counters["qualified_nonflat_decisions"] >= 30
            ),
            "mapped_ticker_bar_passed": expected_counters["mapped_tickers"] >= 10,
            "cash_conflict_bar_passed": expected_counters["actual_cash_conflicts"] >= 10,
            "h5_bar_passed": expected_counters["settled_h5"] >= 30,
            "h10_bar_passed": expected_counters["settled_h10"] >= 30,
            "h20_bar_passed": expected_counters["settled_h20"] >= 30,
            "lane_remains_not_ready": True,
        },
        "production_impact": {
            "signals_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "orders_changed": False,
            "trade_enabled_changed": False,
        },
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_build_reopen_readiness.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260723_002_estimate_revision_reopen_readiness_binding.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "synthesis_pass": {
            "baseline_universe": [
                "47-name frozen cash-feasible core universe",
                "accepted default-off sleeves",
                "current portfolio exposure and cash",
                "SPY and QQQ replacement benchmarks",
            ],
            "opportunity_cost_winner": "exp-20260715-010 / cash",
            "evidence_surfaces_used": [
                "price",
                "flow",
                "derivatives",
                "event",
                "positioning",
                "portfolio exposure",
                "canonical estimate-revision readiness",
                "research digest",
            ],
            "evidence_surfaces_missing": [
                "10 actual cash-conflict decisions",
                "30 settled independent decisions at H5/H10/H20",
                "fresh outcome-blind D0-D3 scope and verified promotion",
            ],
            "hypothesis_candidates": [
                "estimate-revision x price expectation-gap replacement value",
                "intraday semantic override incremental value",
                "Moomoo flow x options disagreement fragility",
            ],
            "selected_hypothesis": (
                "Bind estimate-revision reopen counters to canonical readiness; "
                "do not test alpha while cash conflicts and settlements are absent."
            ),
            "economic_mechanism": (
                "Analyst consensus revisions versus price-revealed priors may change "
                "scarce-slot replacement value once conflict and horizon outcomes mature."
            ),
            "falsifier": (
                "The builder disagrees with canonical counters, malformed input can report "
                "ready, or the lane becomes ready before every declared bar passes."
            ),
            "evidence_grade": "measurement_repair_underlying_alpha_parked",
            "next_machine_action": (
                "Continue default-off collection without another experiment ID; reopen only "
                "after >=10 cash conflicts and >=30 settled independent decisions at each "
                "of H5/H10/H20, then complete a fresh verified promotion."
            ),
        },
    }
    _write_json(BEFORE_PATH, before)
    _write_json(AFTER_PATH, after)
    _write_json(REPORT_PATH, report)
    print(json.dumps(report["acceptance_checks"], sort_keys=True))
    print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
