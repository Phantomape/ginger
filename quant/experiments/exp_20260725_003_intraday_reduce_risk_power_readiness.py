"""exp-20260725-003: bind intraday active-action power to reopen readiness."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "scripts", ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import build_reopen_readiness as readiness  # noqa: E402
from data_paths import atomic_write_json  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260725-003"
SLUG = "intraday_reduce_risk_power_readiness"
RUNNER = f"quant/experiments/exp_20260725_003_{SLUG}.py"
TICKET = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
MANIFEST = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = ROOT / "docs" / "experiment_registry.json"
ARTIFACT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE = ARTIFACT_DIR / "before_readiness.json"
ARTIFACT = ARTIFACT_DIR / f"exp_20260725_003_{SLUG}.json"
REOPEN = ROOT / "data" / "reopen_readiness.json"
OUTCOME_LEDGER = (
    ROOT
    / "data"
    / "daily"
    / "intraday"
    / "backtests"
    / "outcome_ledgers"
    / "intraday_triage_outcomes_20260724.jsonl"
)
SCORECARD = (
    ROOT / "data" / "daily" / "intraday" / "backtests" / "latest_scorecard.json"
)
ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
BUILDER = ROOT / "scripts" / "build_reopen_readiness.py"
TEST_FILE = ROOT / "quant" / "test_build_reopen_readiness.py"

BEFORE_HASHES = {
    "builder": "0520c784b20277ca5351da470d5bbdbfa2d416031670c03fd8b67272f1111248",
    "readiness": "53fd9fdb6400071f194083c879853e816c435fedce9b818a966fdd6969340b07",
    "outcome_ledger": "cff5e825c533d63e98e3cc558a67a689b3e864060db229e78cc695acbe48b78b",
    "scorecard": "fc9536c57c3d33813c37626184ebba0369f23e0c53430c471b44b8ebb31b03df",
    "active_baseline": "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def lane_from_snapshot(payload):
    return next(
        lane
        for lane in payload["lanes"]
        if lane.get("lane") == "intraday_triage_completed_close_settlement"
    )


def fixture_row(index: int, *, final_action: str) -> dict:
    return {
        "outcome_rule_version": "intraday_triage_counterfactual_outcome_v2",
        "observation_id": f"fixture-{index:03d}",
        "ticker": f"T{index:03d}",
        "primary_ticker_day_decision": True,
        "horizon": "next_close",
        "status": "closed",
        "execution_time": f"2026-07-23 13:{index % 60:02d}:00-{index:03d}",
        "decision_timestamp": f"2026-07-{index // 25 + 1:02d} 13:05:00",
        "horizon_time": "2026-07-24 15:55:00",
        "final_action": final_action,
    }


def fixture_lane(reduce_risk_indices: set[int]) -> dict:
    rows = [
        fixture_row(
            index,
            final_action=(
                "REDUCE_RISK" if index in reduce_risk_indices else "HOLD_ONLY"
            ),
        )
        for index in range(100)
    ]
    original_root = readiness.REPO_ROOT
    try:
        with tempfile.TemporaryDirectory(prefix="exp-20260725-003-") as temp_dir:
            root = Path(temp_dir)
            folder = (
                root
                / "data"
                / "daily"
                / "intraday"
                / "backtests"
                / "outcome_ledgers"
            )
            folder.mkdir(parents=True)
            ledger = folder / "intraday_triage_outcomes_20260724.jsonl"
            ledger.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            readiness.REPO_ROOT = str(root)
            return readiness.lane_intraday_triage_completed_close_settlement()
    finally:
        readiness.REPO_ROOT = original_root


def main() -> int:
    now = utc_now()
    ticket = load_json(TICKET)
    before = load_json(BEFORE)
    stored_readiness = load_json(REOPEN)
    stored_lane = lane_from_snapshot(stored_readiness)
    live_lane = readiness.lane_intraday_triage_completed_close_settlement()
    stored_core_lane = {key: stored_lane.get(key) for key in live_lane}
    baseline = load_json(ACTIVE_BASELINE)

    insufficient = fixture_lane(set(range(5)) | set(range(50, 55)))
    balanced = fixture_lane(set(range(10)) | set(range(50, 60)))
    unbalanced = fixture_lane(set(range(18)) | set(range(50, 52)))

    current = live_lane["counters"]
    current_expected = {
        "strict_effective_next_close_settlements": 94,
        "strict_effective_next_close_reduce_risk_settlements": 10,
        "first_half_strict_effective_next_close_reduce_risk_settlements": 8,
        "second_half_strict_effective_next_close_reduce_risk_settlements": 2,
    }
    source_hashes = {
        "outcome_ledger": sha256(OUTCOME_LEDGER),
        "scorecard": sha256(SCORECARD),
        "active_baseline": sha256(ACTIVE_BASELINE),
    }
    after_hashes = {
        "builder": sha256(BUILDER),
        "tests": sha256(TEST_FILE),
        "readiness": sha256(REOPEN),
        **source_hashes,
    }
    checks = {
        "current_lane_matches_rebuilt_lane": stored_core_lane == live_lane,
        "current_counts_match_frozen_preflight": all(
            current.get(key) == value for key, value in current_expected.items()
        ),
        "current_lane_remains_not_ready": live_lane.get("status") == "not_ready",
        "current_outcome_ledger_byte_identical": (
            source_hashes["outcome_ledger"] == BEFORE_HASHES["outcome_ledger"]
        ),
        "current_scorecard_byte_identical": (
            source_hashes["scorecard"] == BEFORE_HASHES["scorecard"]
        ),
        "active_gate1_byte_identical": (
            source_hashes["active_baseline"] == BEFORE_HASHES["active_baseline"]
        ),
        "100_total_10_active_fails_closed": (
            insufficient["counters"]["strict_effective_next_close_settlements"]
            == 100
            and insufficient["counters"][
                "strict_effective_next_close_reduce_risk_settlements"
            ]
            == 10
            and insufficient["status"] == "not_ready"
        ),
        "100_total_20_active_balanced_is_ready": (
            balanced["counters"]["strict_effective_next_close_settlements"] == 100
            and balanced["counters"][
                "strict_effective_next_close_reduce_risk_settlements"
            ]
            == 20
            and balanced["counters"][
                "first_half_strict_effective_next_close_reduce_risk_settlements"
            ]
            == 10
            and balanced["counters"][
                "second_half_strict_effective_next_close_reduce_risk_settlements"
            ]
            == 10
            and balanced["status"] == "ready"
        ),
        "100_total_20_active_unbalanced_fails_closed": (
            unbalanced["counters"][
                "strict_effective_next_close_reduce_risk_settlements"
            ]
            == 20
            and unbalanced["counters"][
                "first_half_strict_effective_next_close_reduce_risk_settlements"
            ]
            == 18
            and unbalanced["counters"][
                "second_half_strict_effective_next_close_reduce_risk_settlements"
            ]
            == 2
            and unbalanced["status"] == "not_ready"
        ),
        "readiness_reads_no_pnl_or_return": (
            "do not read PnL or returns" in live_lane.get("note", "")
        ),
    }
    passed = all(checks.values())
    status = "accepted" if passed else "rejected"
    decision = "accepted_measurement_repair" if passed else "rejected_measurement_repair"
    aggregate = baseline["aggregate"]
    headline_metrics = {
        "expected_value_score": aggregate["expected_value_score_sum"],
        "total_pnl": aggregate["total_pnl_sum"],
        "trade_count": aggregate["trade_count_sum"],
        "minimum_survival_rate": aggregate["minimum_survival_rate"],
        "worst_max_drawdown_pct": aggregate["worst_max_drawdown_pct"],
    }
    changed_files = [
        "scripts/build_reopen_readiness.py",
        "quant/test_build_reopen_readiness.py",
        RUNNER,
        rel(BEFORE),
        rel(ARTIFACT),
        rel(REOPEN),
        rel(LOG),
        rel(CARD),
        rel(MANIFEST),
        rel(TICKET),
        "docs/experiment_registry.json",
        "docs/frozen_families.jsonl",
        "docs/alpha_context_pack.md",
        "docs/current_state_snapshot.md",
    ]
    payload = {
        "schema": "intraday_reduce_risk_power_readiness_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": passed,
        "lane": "measurement_repair",
        "owner": "codex-alpha-automation",
        "hypothesis": ticket["hypothesis"],
        "alpha_hypothesis": (
            "Deterministic machine-default intraday REDUCE_RISK may add positive "
            "next-close replacement value versus semantic override and hold."
        ),
        "change_type": "measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": ticket["mechanism_family"],
        "trial_family": ticket["trial_family"],
        "trial_variant_id": ticket["trial_variant_id"],
        "single_causal_variable": ticket["single_causal_variable"],
        "changed_variable": ticket["changed_variable"],
        "causal_components": ticket["causal_components"],
        "nearby_prior_experiments": ticket["nearby_prior_experiments"],
        "prior_trial_count": ticket["prior_trial_count"],
        "multiple_testing_risk_bucket": ticket["multiple_testing_risk_bucket"],
        "new_evidence_type": ticket["new_evidence_type"],
        "prediction": ticket["prediction"],
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if passed else 0,
            "predicted_success_probability": ticket["prediction"][
                "success_probability"
            ],
            "brier_score": round(
                (
                    ticket["prediction"]["success_probability"]
                    - (1 if passed else 0)
                )
                ** 2,
                6,
            ),
            "calibration_direction": (
                "directionally_calibrated" if passed else "overconfident"
            ),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": ticket["prediction"]["main_failure_modes"],
            "realized_failure_mode": None if passed else "contract_check_failed",
            "predicted_failure_mode_hit": None,
            "surprise_level": "very_low" if passed else "high",
            "surprise_note": (
                "The canonical final_action field reproduced the frozen 94/10/8/2 "
                "preflight and all fail-closed boundary fixtures behaved as predicted."
                if passed
                else "One or more predeclared measurement checks failed."
            ),
        },
        "alpha_synthesis": {
            "baseline_universe": [
                "cash-feasible 47-ticker core",
                "current 12-position broker account",
                "accepted default-off observers and sleeves",
                "cash",
                "SPY",
                "QQQ",
            ],
            "opportunity_cost_winner": "cash / no new executable core entry",
            "evidence_surfaces_used": [
                "canonical price and cash Gate-1",
                "intraday completed-close ledger",
                "Moomoo flow",
                "options and borrow positioning",
                "event and estimate-revision ledgers",
                "portfolio exposure and live controls",
                "research digest and reopen registry",
            ],
            "evidence_surfaces_missing": [
                "100 strict intraday next-close settlements",
                "20 settled REDUCE_RISK actions with at least five per half",
                "mature flow-options paired settlements",
                "actual estimate-revision cash conflicts and H5/H10/H20 outcomes",
                "settled prediction-market outcomes",
                "PIT-bound spread, impact, or LOB history",
            ],
            "hypothesis_candidates": [
                "machine-default intraday REDUCE_RISK versus semantic override and hold",
                "deep-drawdown price stabilization plus flow absorption and put positioning",
                "timestamp-safe estimate-revision expectation gap at actual cash conflicts",
            ],
            "selected_hypothesis": "machine-default intraday REDUCE_RISK, parked",
            "economic_mechanism": (
                "deterministic risk reduction may avoid adverse next-close paths, but "
                "neutral rows cannot identify the active treatment"
            ),
            "falsifier": (
                "fewer than 20 settled active reductions, fewer than five in either "
                "chronological half, nonpositive replacement value, or tail/concentration failure"
            ),
            "evidence_grade": "lead_parked",
            "next_machine_action": (
                "continue routine settlement without IDs; only after 100/20/5/5 build "
                "a fresh outcome-blind D0-D3 scope and promotion request"
            ),
            "research_digest_disposition": (
                "all ten displayed entries were already terminal; no duplicate ledger append"
            ),
        },
        "before": before,
        "after": {
            "intraday_lane": live_lane,
            "insufficient_power_fixture": insufficient,
            "balanced_power_fixture": balanced,
            "unbalanced_power_fixture": unbalanced,
        },
        "checks": checks,
        "gate1": {
            "passed": checks["active_gate1_byte_identical"],
            "baseline_artifact": rel(ACTIVE_BASELINE),
            "baseline_sha256": source_hashes["active_baseline"],
            "note": "Measurement-only repair; the cash-feasible strategy anchor is unchanged.",
        },
        "gate2": {
            "passed": checks["current_counts_match_frozen_preflight"],
            "required_fields": [
                "outcome_rule_version",
                "primary_ticker_day_decision",
                "horizon",
                "status",
                "horizon_time",
                "final_action",
                "decision_timestamp",
                "execution_time",
                "ticker",
                "observation_id",
            ],
            "signal_sentinel_fields": "not_applicable_no_signal_or_position_path_changed",
        },
        "gate3": {
            "passed": True,
            "strategy_filter_changed": False,
            "minimum_survival_rate": aggregate["minimum_survival_rate"],
        },
        "gate4": {
            "passed": passed,
            "evaluation": "measurement_contract_only",
            "before_metrics": headline_metrics,
            "after_metrics": headline_metrics,
            "delta_metrics": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "minimum_survival_rate": 0.0,
                "worst_max_drawdown_pct": 0.0,
            },
            "acceptance_rule": ticket["acceptance_rule"],
        },
        "before_metrics": headline_metrics,
        "after_metrics": headline_metrics,
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "minimum_survival_rate": 0.0,
            "worst_max_drawdown_pct": 0.0,
        },
        "headline_metrics": headline_metrics,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "orders_changed": False,
            "ranking_sizing_exits_or_risk_budget_changed": False,
            "source_ledger_changed": False,
            "replay_only": False,
            "live_ready": False,
            "summary": "Readiness governance only; no trading or outcome semantics changed.",
        },
        "acceptance_basis": (
            "The canonical lane now binds the previously recorded 100/20/5/5 "
            "outcome-blind power contract, reproduces the real 94/10/8/2 counts, "
            "passes balanced and fail-closed boundary fixtures, and preserves every "
            "strategy/source artifact byte-for-byte."
        ),
        "rejection_reason": None if passed else ";".join(
            name for name, ok in checks.items() if not ok
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "The readiness builder carried the original total-cohort threshold but "
                "did not ingest the active-action power bar frozen by the later accepted closeout."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another readiness-only or threshold-retune ID on this "
                "intraday surface, and do not weaken completed-close, active-action, or "
                "chronological-balance checks."
            ),
            "new_evidence_required": (
                "The alpha lane reopens only after the same canonical ledger reaches "
                "at least 100 strict cohorts, 20 settled REDUCE_RISK actions, and five "
                "actions in each chronological half, followed by a fresh verified D0-D3 scope."
            ),
        },
        "next_retry_requires": [
            "No retry of this measurement repair; regression tests own the guard.",
            "Fresh alpha promotion only after the canonical 100/20/5/5 power bars.",
        ],
        "source_hashes": {
            "before": BEFORE_HASHES,
            "after": after_hashes,
        },
        "changed_files": changed_files,
        "related_files": changed_files
        + [rel(OUTCOME_LEDGER), rel(SCORECARD), rel(ACTIVE_BASELINE)],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_build_reopen_readiness.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_reopen_readiness.py",
            ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": passed,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, ARTIFACT, indent=2, ensure_ascii=False)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD.write_text(
        f"# {EXPERIMENT_ID}: Intraday REDUCE_RISK power readiness\n\n"
        f"- Decision: `{decision}`\n"
        "- Canonical strict cohorts: `94 / 100`\n"
        "- Settled REDUCE_RISK actions: `10 / 20`\n"
        "- Chronological halves: `8 / 5`, `2 / 5`\n"
        "- Strategy EV / PnL / trades changed: `0 / 0 / 0`\n"
        "- Accepted alpha: `false`; trade enabled: `false`\n\n"
        "The measurement repair is accepted only as fail-closed readiness governance. "
        "The underlying intraday alpha remains parked until 100/20/5/5.\n",
        encoding="utf-8",
    )
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=ticket.get("prediction"),
        result={
            "accepted": passed,
            "accepted_alpha": False,
            "accepted_measurement_repair": passed,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "gate4": payload["gate4"],
            "headline_metrics": headline_metrics,
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
        status=status,
        fields={
            **payload,
            "artifact": rel(ARTIFACT),
            "log": rel(LOG),
            "card_file": rel(CARD),
            "revision_manifest_file": rel(MANIFEST),
            "ticket_file": rel(TICKET),
            "allowed_write_scope": ticket["allowed_write_scope"],
            "reopen_condition": payload["post_run_reflection"][
                "new_evidence_required"
            ],
        },
    )
    atomic_write_json(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": decision,
            "artifact": rel(ARTIFACT),
            "runner": RUNNER,
            "checks": checks,
            "updated_at": now,
        },
        MANIFEST,
        indent=2,
        ensure_ascii=False,
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "checks": checks,
                "artifact": rel(ARTIFACT),
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
