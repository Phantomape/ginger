"""exp-20260811-001: estimate-revision settlement population repair.

Measurement repair. The run.py-wired daily settlement builder filtered its
population to candidate-overlap ledger rows only, so only 12 of 1299 qualified
independent decisions ever received outcome rows and the exp-20260721-002
phase-2 readiness bar (>=30 settled at each of H5/H10/H20) was mathematically
unreachable. After widening the settlement population to every
decision-identified ledger row (quant/estimate_revision_outcomes.py), this
runner replays the already-wired 45-day catch-up so historical decisions
re-settle from the canonical hot warehouse, then rebuilds the readiness
artifact and records before/after evidence.

No decision vintages are touched: decision rows and their clocks are immutable
ledger facts; settlement is retrospective computation from canonical OHLCV and
is fully reconstructible. Trading policy, signals, sizing, and orders are
unchanged (default-off measurement surface).

Usage:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260811_001_estimate_revision_settlement_population_repair.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from estimate_revision_outcomes import (  # noqa: E402
    persist_estimate_revision_readiness,
    persist_recent_estimate_revision_outcome_catchup,
)

EXPERIMENT_ID = "exp-20260811-001"
ARTIFACT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260811_001_estimate_revision_settlement_population_repair.json"
)
READINESS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_readiness_latest.json"


def _readiness_snapshot() -> dict:
    if not READINESS_PATH.exists():
        return {}
    payload = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    return {
        "generated_at": payload.get("generated_at"),
        "as_of_date": payload.get("as_of_date"),
        "independent_decisions": payload.get("independent_decisions"),
        "mapped_ticker_count": payload.get("mapped_ticker_count"),
        "candidate_overlap_decisions": payload.get("candidate_overlap_decisions"),
        "actual_cash_conflict_decisions": payload.get("actual_cash_conflict_decisions"),
        "settled_independent_decisions": payload.get("settled_independent_decisions"),
        "settled_independent_decisions_by_horizon": payload.get(
            "settled_independent_decisions_by_horizon"
        ),
        "outcome_row_count": payload.get("outcome_row_count"),
        "gate_ready": payload.get("gate_ready"),
    }


def main() -> int:
    as_of = date.today().isoformat()
    generated_at = datetime.now(timezone.utc)
    before = _readiness_snapshot()

    catchup = persist_recent_estimate_revision_outcome_catchup(
        as_of=as_of,
        data_dir="data",
        output_dir="data/non_ohlcv",
        generated_at=generated_at,
    )
    readiness = persist_estimate_revision_readiness(
        as_of=as_of,
        data_dir="data",
        output_dir="data/non_ohlcv",
        generated_at=datetime.now(timezone.utc),
    )
    after = _readiness_snapshot()

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "kind": "measurement_repair_before_after",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "defect": (
            "persist_estimate_revision_outcomes settled only rows with "
            "matched_candidate_today/matched_candidate_count, starving the "
            "phase-2 readiness settled counters that are defined over ALL "
            "qualified independent decisions (exp-20260721-002)."
        ),
        "repair": (
            "settlement population widened to every ledger row carrying a "
            "decision_id (candidate-overlap rows without decision_id remain "
            "included); wired 45-day daily catch-up re-settles history."
        ),
        "before_readiness": before,
        "after_readiness": after,
        "catchup_summary": {
            "status": catchup.get("status"),
            "refreshed_ledger_count": catchup.get("refreshed_ledger_count"),
            "refreshed_ledger_dates": catchup.get("refreshed_ledger_dates"),
            "closed_rows_by_horizon": catchup.get("closed_rows_by_horizon"),
            "pending_rows_by_horizon": catchup.get("pending_rows_by_horizon"),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "trade_enabled": False,
            "scope": "default_off_forward_estimate_revision_outcome_settlement",
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "artifact": str(ARTIFACT_PATH),
        "before_settled": before.get("settled_independent_decisions_by_horizon"),
        "after_settled": after.get("settled_independent_decisions_by_horizon"),
        "after_independent": after.get("independent_decisions"),
        "refreshed_ledgers": catchup.get("refreshed_ledger_count"),
        "gate_ready": after.get("gate_ready"),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
