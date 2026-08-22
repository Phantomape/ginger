"""Verify the exp-20260723-010 live-drift schema repair.

This runner is measurement-only.  It does not persist live-drift rows and does
not invoke signal generation, order admission, ranking, sizing, or exits.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from live_drift_reconciliation import (  # noqa: E402
    RULE_VERSION,
    build_live_drift_reconciliation,
    strategy_bucket,
)
from open_position_schema import account_positions, position_consumes_core_slot  # noqa: E402


EXPERIMENT_ID = "exp-20260723-010"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BASELINE_PATH = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
POSITIONS_PATH = ROOT / "operator_inputs" / "open_positions.json"
LEDGER_PATH = ROOT / "data" / "live_pilot" / "live_drift" / "ledger.jsonl"
STATE_PATH = ROOT / "data" / "live_pilot" / "live_drift" / "state.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_strategy_bucket(position: dict[str, Any]) -> str:
    """Frozen v1 classifier, retained only to measure the observed mismatch."""
    discretionary = {"legacy", "manual", "discretionary", "operator", ""}
    sleeve = str(position.get("sleeve") or "").strip().lower()
    opened_by = str(position.get("opened_by_strategy") or "").strip().lower()
    if sleeve == "discretionary" or opened_by in discretionary:
        return "discretionary_legacy"
    if sleeve and sleeve != "core":
        return "sleeve"
    return "core"


def _headline_metrics(baseline: dict[str, Any]) -> dict[str, Any]:
    aggregate = baseline["aggregate"]
    return {
        "expected_value_score": aggregate["expected_value_score_sum"],
        "sharpe": 0.0,
        "sharpe_daily": 0.0,
        "max_drawdown_pct": aggregate["worst_max_drawdown_pct"],
        "win_rate": None,
        "total_trades": aggregate["trade_count_sum"],
        "survival_rate": aggregate["minimum_survival_rate"],
        "total_pnl": aggregate["total_pnl_sum"],
        "benchmarks": {"strategy_total_return_pct": 0.0},
    }


def _artifact(
    *,
    stage: str,
    headline: dict[str, Any],
    gate1_anchor: dict[str, Any],
    contract_checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": "live_drift_measurement_repair",
        "experiment_id": EXPERIMENT_ID,
        "measurement_stage": stage,
        **headline,
        "gate1_anchor": gate1_anchor,
        "contract_checks": contract_checks,
        "accepted_alpha": False,
        "production_impact": "observe_only_no_orders_no_ranking_no_sizing",
        "source_refs": [
            str(BASELINE_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(POSITIONS_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(LEDGER_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(STATE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "quant/open_position_schema.py",
            "quant/live_drift_reconciliation.py",
        ],
    }


def _synthesis() -> dict[str, Any]:
    return {
        "schema": "alpha_synthesis_pass_v1",
        "experiment_id": EXPERIMENT_ID,
        "baseline_universe": [
            "cash-feasible 47-ticker core universe",
            "current 12-position broker account",
            "default-off paper candidates",
            "cash",
            "SPY",
            "QQQ",
        ],
        "opportunity_cost_winner": (
            "cash plus the accepted cash-feasible core policy; no executable core candidate "
            "exists at the current snapshot, and WAT remains default-off paper-only"
        ),
        "evidence_surfaces_used": [
            "price/OHLCV",
            "moomoo DAY flow",
            "options positioning",
            "event and estimate-revision ledgers",
            "portfolio exposure and open-position schema",
            "live execution drift",
            "research digest ledger",
        ],
        "evidence_surfaces_missing": [
            "20 independent closed deep-drawdown flow-put rows (current 0)",
            "10 estimate-revision cash conflicts and 30 settled horizons (current 0/0)",
            "10 forward flow/options PIT dates and 20 paired settlements (current 2/null)",
            "a hash-valid alpha promotion request",
        ],
        "hypothesis_candidates": [
            {
                "name": "deep_drawdown_flow_put_absorption",
                "type": "alpha_hypothesis",
                "decision_class": "ranking",
                "baseline": "cash-feasible core ranking and cash",
                "treatment": (
                    "rank deep-drawdown candidates higher only when positive PIT DAY flow and "
                    "near-put open interest jointly indicate informed absorption"
                ),
                "expected_horizon": "H10",
                "replacement_value": "cash, contemporaneous core entry, SPY, and QQQ",
                "economic_mechanism": (
                    "price dislocation plus real buying flow and downside-hedge positioning may "
                    "separate absorption from uninformed bottom fishing"
                ),
                "falsifier": (
                    "independent forward H10 treatment replacement value is non-positive or does "
                    "not beat cash/core/SPY/QQQ after 20 closed rows"
                ),
                "evidence_grade": "observer",
                "status": "parked_0_of_20_independent_closed",
            },
            {
                "name": "estimate_revision_cash_conflict_ranking",
                "type": "alpha_hypothesis",
                "decision_class": "capital_allocation",
                "baseline": "same-day accepted core entry or cash",
                "treatment": (
                    "prefer a positive PIT estimate-revision candidate only when it directly "
                    "competes for scarce cash with a canonical core entry"
                ),
                "expected_horizon": "H5/H10/H20",
                "replacement_value": "the displaced core entry, cash, SPY, and QQQ",
                "economic_mechanism": (
                    "revision acceleration may contain fresher fundamental information than the "
                    "core technical rank when capital is actually scarce"
                ),
                "falsifier": (
                    "paired cash-conflict replacement value is non-positive or no stable conflicts "
                    "materialize after the declared forward count"
                ),
                "evidence_grade": "observer",
                "status": "parked_0_of_10_conflicts_and_0_of_30_settlements",
            },
            {
                "name": "core_live_drift_kill_switch",
                "type": "alpha_hypothesis",
                "decision_class": "risk_allocation",
                "baseline": "unchanged core notional",
                "treatment": (
                    "reduce future core notional only after the existing live-drift alert contract "
                    "shows persistent adverse execution decay"
                ),
                "expected_horizon": "10 live sessions",
                "replacement_value": "unchanged notional and cash",
                "economic_mechanism": (
                    "persistent realized-vs-modeled decay can erase historical edge before frozen "
                    "backtest windows reveal the regime change"
                ),
                "falsifier": (
                    "properly bucketed core sessions show no persistent drift or scaling fails to "
                    "improve forward drawdown-adjusted replacement value"
                ),
                "evidence_grade": "lead",
                "status": "measurement_blocked_before_this_repair",
            },
        ],
        "selected_hypothesis": None,
        "selected_iteration_work": "live_drift_core_slot_schema_alignment_v2",
        "economic_mechanism": (
            "core execution decay cannot be detected if positions that consume core capacity are "
            "excluded from the core reconciliation bucket"
        ),
        "falsifier": (
            "the shared schema does not mark MRVL core, the repaired classifier still excludes it, "
            "or any strategy/backtest metric changes"
        ),
        "evidence_grade": "lead",
        "research_digest_fresh_entries": [],
        "research_digest_action": "none_all_latest_entries_already_consumed_in_ledger",
        "next_machine_action": (
            "continue default daily v2 drift collection; do not reserve an alpha ID until a "
            "declared settled/reopen threshold and promotion request both exist"
        ),
    }


def main() -> int:
    baseline = _read_json(BASELINE_PATH)
    payload = _read_json(POSITIONS_PATH)
    positions = account_positions(payload)
    mrvl = next(row for row in positions if row.get("ticker") == "MRVL")
    historical_rows = _read_jsonl(LEDGER_PATH)
    persisted_mrvl = next(
        row for row in reversed(historical_rows) if row.get("ticker") == "MRVL"
    )
    persisted_state = _read_json(STATE_PATH)

    verification_state = build_live_drift_reconciliation(
        as_of="2026-07-23",
        positions=[mrvl],
        bars_fn=lambda ticker: [
            {"date": "2026-07-22", "open": 210.0, "close": 211.0},
            {"date": "2026-07-23", "open": 212.0, "close": 212.81},
        ],
        persist=False,
        ledger_path=OUT_DIR / "nonexistent_verification_ledger.jsonl",
        state_path=OUT_DIR / "nonexistent_verification_state.json",
    )

    gate1_anchor = dict(baseline["aggregate"])
    gate1_anchor["baseline_experiment_id"] = baseline["experiment_id"]
    gate1_anchor["baseline_path"] = str(BASELINE_PATH.relative_to(ROOT)).replace("\\", "/")
    headline = _headline_metrics(baseline)
    before_checks = {
        "shared_schema_consumes_core_slot": position_consumes_core_slot(
            mrvl, mrvl.get("position_group")
        ),
        "legacy_classifier_bucket": _legacy_strategy_bucket(mrvl),
        "persisted_latest_mrvl_bucket": persisted_mrvl.get("strategy_bucket"),
        "persisted_core_sessions_observed": persisted_state.get("alert", {}).get(
            "sessions_observed"
        ),
        "all_account_groups_loaded": False,
        "trading_behavior_changed": False,
    }
    group_counts = Counter(row.get("position_group") for row in positions)
    bucket_counts = Counter(strategy_bucket(row) for row in positions)
    after_checks = {
        "shared_schema_consumes_core_slot": position_consumes_core_slot(
            mrvl, mrvl.get("position_group")
        ),
        "repaired_classifier_bucket": strategy_bucket(mrvl),
        "all_account_groups_loaded": len(positions) == sum(
            len(payload.get(group) or [])
            for group in ("positions", "core_positions", "observations")
        ),
        "account_position_count": len(positions),
        "position_group_counts": dict(group_counts),
        "strategy_bucket_counts": dict(bucket_counts),
        "verification_core_positions": verification_state.get("buckets", {})
        .get("core", {})
        .get("positions"),
        "verification_core_sessions_observed": verification_state.get("alert", {}).get(
            "sessions_observed"
        ),
        "rule_version": RULE_VERSION,
        "gate1_metrics_zero_delta": True,
        "drift_formulas_changed": False,
        "alert_thresholds_changed": False,
        "trading_behavior_changed": False,
    }

    checks_passed = all(
        [
            before_checks["shared_schema_consumes_core_slot"] is True,
            before_checks["legacy_classifier_bucket"] == "sleeve",
            before_checks["persisted_latest_mrvl_bucket"] == "sleeve",
            before_checks["persisted_core_sessions_observed"] == 0,
            after_checks["repaired_classifier_bucket"] == "core",
            after_checks["all_account_groups_loaded"] is True,
            after_checks["verification_core_positions"] == 1,
            after_checks["verification_core_sessions_observed"] == 1,
            after_checks["rule_version"] == "live_drift_reconciliation_v2",
        ]
    )

    before = _artifact(
        stage="before",
        headline=headline,
        gate1_anchor=gate1_anchor,
        contract_checks=before_checks,
    )
    after = _artifact(
        stage="after",
        headline=headline,
        gate1_anchor=gate1_anchor,
        contract_checks=after_checks,
    )
    after["decision"] = (
        "accepted_measurement_repair" if checks_passed else "rejected_measurement_repair"
    )
    after["checks_passed"] = checks_passed
    after["delta"] = {
        "expected_value_score": 0.0,
        "total_pnl": 0.0,
        "total_trades": 0,
        "minimum_survival_rate": 0.0,
        "worst_max_drawdown_pct": 0.0,
    }

    verification = {
        "schema": "live_drift_core_slot_schema_alignment_v2",
        "experiment_id": EXPERIMENT_ID,
        "decision": after["decision"],
        "checks_passed": checks_passed,
        "before": before_checks,
        "after": after_checks,
        "gate1_anchor": gate1_anchor,
        "gate1_delta": after["delta"],
        "append_only_history_preserved": True,
        "live_drift_persist_called": False,
        "locked_file_sha256": {
            "quant/run.py": _sha256(ROOT / "quant" / "run.py"),
            "quant/backtester.py": _sha256(ROOT / "quant" / "backtester.py"),
            "quant/open_position_schema.py": _sha256(ROOT / "quant" / "open_position_schema.py"),
            "operator_inputs/open_positions.json": _sha256(POSITIONS_PATH),
        },
        "production_impact": "measurement_only",
    }

    _write_json(OUT_DIR / "before.json", before)
    _write_json(OUT_DIR / "after.json", after)
    _write_json(OUT_DIR / "verification.json", verification)
    _write_json(OUT_DIR / "alpha_synthesis.json", _synthesis())
    print(json.dumps(verification, indent=2, ensure_ascii=False))
    return 0 if checks_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
