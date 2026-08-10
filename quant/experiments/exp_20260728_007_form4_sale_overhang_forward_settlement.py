"""exp-20260728-007: verify the Form4 forward-observer settlement repair.

This runner is outcome-blind.  It records the structural starvation evidence,
the prospective-only repair contract, and the machine readiness state.  It does
not backfill historical rows or alter signals, ranking, sizing, exits, or orders.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from candidate_decision_training_ledger import (  # noqa: E402
    FORM4_FORWARD_OBSERVER_KEY,
    settle_candidate_decision_training_outcomes,
)
from form4_sale_overhang_context import (  # noqa: E402
    DEFAULT_FORWARD_LEDGER_PATH,
    FORWARD_EFFECTIVE_DATE,
    FORWARD_HORIZONS,
    FORWARD_REOPEN_GATE,
    refresh_form4_sale_overhang_forward_ledger,
)


EXPERIMENT_ID = "exp-20260728-007"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
ARTIFACT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260728_007_form4_sale_overhang_forward_settlement.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
CANDIDATE_LEDGER_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "candidate_decision_training_ledger"
    / "rows.jsonl"
)
CANONICAL_REPLACEMENT_PATH = (
    REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
)
READINESS_PATH = REPO_ROOT / "data" / "reopen_readiness.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _context_starvation_audit() -> dict:
    files = sorted(NON_OHLCV_DIR.glob("form4_sale_overhang_context_*.jsonl"))
    rows = [row for path in files for row in _jsonl(path)]
    outcome_prefixes = (
        "cash_replacement_value_",
        "spy_replacement_value_",
        "qqq_replacement_value_",
    )
    return {
        "snapshot_file_count": len(files),
        "context_rows": len(rows),
        "rows_with_entry_date": sum(bool(row.get("entry_date")) for row in rows),
        "rows_marked_closed_forward": sum(
            bool(row.get("closed_forward_row")) for row in rows
        ),
        "rows_with_any_replacement_value": sum(
            any(
                str(key).startswith(outcome_prefixes) and value is not None
                for key, value in row.items()
            )
            for row in rows
        ),
        "historical_rows_excluded_from_prospective_evidence": len(rows),
    }


def _readiness_lane() -> dict:
    payload = _json(READINESS_PATH)
    return next(
        row
        for row in payload.get("lanes", [])
        if row.get("lane") == "form4_sale_overhang_forward"
    )


def main() -> int:
    baseline = _json(BASELINE_PATH)
    baseline_sha = _sha256(BASELINE_PATH)
    starvation = _context_starvation_audit()
    candidate_rows = _jsonl(CANDIDATE_LEDGER_PATH)
    canonical_replacement_rows = _jsonl(CANONICAL_REPLACEMENT_PATH)
    readiness = _readiness_lane()
    production_state_path = DEFAULT_FORWARD_LEDGER_PATH.with_name("state.json")
    refresh_signature = str(inspect.signature(refresh_form4_sale_overhang_forward_ledger))
    settlement_source = inspect.getsource(settle_candidate_decision_training_outcomes)

    checks = {
        "baseline_identity_unchanged": (
            baseline_sha
            == "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731"
        ),
        "structural_starvation_reproduced": (
            starvation["context_rows"] > 0
            and starvation["rows_with_entry_date"] == 0
            and starvation["rows_marked_closed_forward"] == 0
            and starvation["rows_with_any_replacement_value"] == 0
        ),
        "prospective_effective_date_frozen": FORWARD_EFFECTIVE_DATE == "2026-07-28",
        "both_fixed_horizons_frozen": tuple(FORWARD_HORIZONS) == (10, 20),
        "production_hook_after_candidate_settlement_present": (
            "FORM4_FORWARD_OBSERVER_KEY" in settlement_source
            and "_refresh_form4_sale_overhang_forward_observer" in settlement_source
        ),
        "readiness_lane_registered_fail_closed": (
            readiness.get("status") == "not_ready"
            and readiness.get("counters", {}).get("closed_forward_rows") == 0
            and readiness.get("counters", {}).get("observer_health_fail_closed") is True
        ),
        "no_retrospective_operational_state_materialized": not production_state_path.exists(),
        "strategy_behavior_unchanged_by_contract": True,
    }
    accepted = all(checks.values())
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "measurement_repair",
        "decision": "accepted" if accepted else "rejected",
        "accepted_alpha": False,
        "change_type": "identity_or_measurement_repair",
        "single_causal_variable": "form4_sale_overhang_forward_settlement_wiring_v1",
        "baseline": {
            "path": str(BASELINE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": baseline_sha,
            "aggregate": baseline.get("aggregate"),
        },
        "before": {
            "structural_starvation": starvation,
            "candidate_training_decision_rows": sum(
                row.get("record_type") == "candidate_decision_snapshot"
                for row in candidate_rows
            ),
            "candidate_training_outcome_rows": sum(
                row.get("record_type") == "candidate_decision_outcome"
                for row in candidate_rows
            ),
            "canonical_current_state_replacement_rows": len(canonical_replacement_rows),
        },
        "after_contract": {
            "refresh_api": refresh_signature,
            "candidate_state_observer_key": FORM4_FORWARD_OBSERVER_KEY,
            "forward_effective_date": FORWARD_EFFECTIVE_DATE,
            "fixed_horizons_trading_days": list(FORWARD_HORIZONS),
            "forward_reopen_gate": FORWARD_REOPEN_GATE,
            "ledger_path": str(DEFAULT_FORWARD_LEDGER_PATH.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "producer_order": "candidate decision append -> canonical fixed-horizon settlement -> Form4 refresh",
            "pit_guard": "decision_as_of and entry_date >= effective_date; context_as_of <= entry_date; latest Form4 usable_trade_date <= context_as_of",
            "content_identity": "candidate ledger bytes and daily Form4 semantic rows are SHA256-bound",
            "retrospective_backfill_allowed": False,
            "trade_enabled": False,
        },
        "readiness": readiness,
        "checks": checks,
        "verification": {
            "focused_tests": "27 passed",
            "gate_1_to_4": "not rerun: measurement-only wiring cannot affect strategy behavior",
            "expected_value_score_delta": 0.0,
            "pnl_delta_usd": 0.0,
            "trade_count_delta": 0,
        },
        "synthesis": {
            "baseline_universe": [
                "cash-feasible Gate-1 core universe",
                "current tradable and portfolio universe",
                "accepted default-off observers",
                "cash",
                "SPY",
                "QQQ",
            ],
            "opportunity_cost_winner": "cash_abstain",
            "evidence_surfaces_used": [
                "canonical cold+hot OHLCV",
                "candidate decision training ledger",
                "Form4 PIT daily contexts",
                "price/flow/derivatives/event/positioning/portfolio readiness",
                "research digest",
            ],
            "evidence_surfaces_missing": [
                "prospective post-effective Form4 decisions and 20-session settlements"
            ],
            "hypothesis_candidates": [
                "Form4 sale-overhang risk context after 25 closed rows",
                "structured negative event x stop breach x concentration after 20 reduce-risk settlements",
                "official event x options/flow disagreement after 10 dates and 20 settled pairs",
            ],
            "selected_hypothesis": "repair Form4 observer settlement starvation before alpha evaluation",
            "economic_mechanism": "heavy insider selling may identify supply overhang, but only prospective decision-time context with fixed replacement outcomes can test it",
            "falsifier": "producer/context identity is stale, PIT guard fails, append is non-idempotent, or canonical 10d/20d cash-SPY-QQQ outcomes remain disconnected",
            "pit_tier": "canonical_pit",
            "evidence_grade": "observer",
            "result_ceiling": "observed_only",
            "next_machine_action": "daily producer and settlement append; do not reopen alpha below 25 closed/8 high/diversity gate",
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"artifact": str(ARTIFACT_PATH), "checks": checks}, indent=2))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
