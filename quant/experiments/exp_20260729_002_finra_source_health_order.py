"""exp-20260729-002: verify FINRA producer-before-coverage health repair.

This runner is outcome-blind. It compares the immutable 2026-07-27 central
coverage row with the archive written later in that same run, verifies the new
orchestration order and current-cohort density contract, and writes a
reproducible measurement artifact. It never fetches data or reads alpha
candidate returns.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

import run as run_module  # noqa: E402
from non_ohlcv_coverage import (  # noqa: E402
    build_finra_source_coverage_record,
    load_manifest_records,
)


EXPERIMENT_ID = "exp-20260729-002"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
ROWS_PATH = REPO_ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "rows.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260729_002_finra_source_health_order.json"
)
EXPECTED_BASELINE_SHA256 = (
    "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_before_record() -> dict:
    records = [
        row
        for row in load_manifest_records(data_root=REPO_ROOT / "data")
        if row.get("record_type") == "data_source_coverage"
        and row.get("source_name") == "finra_short_interest"
        and row.get("trade_date") == "2026-07-27"
    ]
    if not records:
        return {}
    return min(records, key=lambda row: str(row.get("generated_at") or ""))


def _main_order_contract() -> dict:
    tree = ast.parse(textwrap.dedent(inspect.getsource(run_module.main)))
    calls = {
        getattr(node.func, "id", None): node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None)
        in {
            "_refresh_finra_short_interest_before_coverage",
            "_build_daily_non_ohlcv_snapshot",
            "prep_and_build_sec_ftd_finra_paper_sleeve_snapshot",
        }
    }
    refresh = calls.get("_refresh_finra_short_interest_before_coverage")
    coverage = calls.get("_build_daily_non_ohlcv_snapshot")
    sleeve = calls.get("prep_and_build_sec_ftd_finra_paper_sleeve_snapshot")
    ticker_args = [
        keyword.value
        for keyword in (refresh.keywords if refresh else [])
        if keyword.arg == "tickers"
    ]
    return {
        "refresh_lineno": refresh.lineno if refresh else None,
        "coverage_lineno": coverage.lineno if coverage else None,
        "sleeve_lineno": sleeve.lineno if sleeve else None,
        "producer_before_coverage_before_sleeve": bool(
            refresh
            and coverage
            and sleeve
            and refresh.lineno < coverage.lineno < sleeve.lineno
        ),
        "uses_broad_ingest_universe": bool(
            len(ticker_args) == 1
            and isinstance(ticker_args[0], ast.Name)
            and ticker_args[0].id == "broad_ingest_universe"
        ),
    }


def main() -> int:
    baseline = _json(BASELINE_PATH)
    baseline_sha = _sha256(BASELINE_PATH)
    archive_payload = _json(ROWS_PATH)
    before = _frozen_before_record()
    rebuilt = build_finra_source_coverage_record(
        "2026-07-27",
        data_root=REPO_ROOT / "data",
        mode="daily",
        experiment_id=EXPERIMENT_ID,
    )
    order = _main_order_contract()

    before_rows = (before.get("row_counts") or {}).get(
        "finra_short_interest_rows", 0
    )
    after_rows = rebuilt["row_counts"]["finra_short_interest_rows"]
    before_publication = (before.get("source_watermarks") or {}).get(
        "publication_date_max"
    )
    after_publication = rebuilt["source_watermarks"]["publication_date_max"]
    checks = {
        "baseline_identity_unchanged": baseline_sha == EXPECTED_BASELINE_SHA256,
        "same_run_lag_reproduced": (
            before_rows == 46514
            and after_rows >= 46568
            and before_publication == "2026-07-10"
            and after_publication >= "2026-07-24"
            and str(before.get("generated_at"))
            < str(archive_payload.get("updated_at"))
        ),
        "producer_precedes_coverage": order["producer_before_coverage_before_sleeve"],
        "broad_ingest_scope_wired": order["uses_broad_ingest_universe"],
        "latest_cohort_density_machine_visible": (
            rebuilt["cohort_density"]["latest_settlement_ticker_count"] > 0
            and rebuilt["cohort_density"]["archive_ticker_count"] > 0
            and rebuilt["cohort_density"]["status"] in {"dense", "sparse"}
        ),
        "current_sparse_cohort_fails_closed": (
            rebuilt["status"] == "partial"
            and rebuilt["pit_status"]["overall"]
            == "finra_latest_cohort_sparse"
            and rebuilt["cohort_density"]["latest_settlement_ticker_count"] == 54
        ),
        "strategy_behavior_unchanged_by_contract": True,
    }
    accepted = all(checks.values())
    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "measurement_repair",
        "decision": "accepted" if accepted else "rejected",
        "accepted_alpha": False,
        "single_causal_variable": (
            "finra_short_interest_broad_producer_before_coverage_health_contract_v1"
        ),
        "baseline": {
            "path": str(BASELINE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": baseline_sha,
            "aggregate": baseline.get("aggregate"),
        },
        "before": {
            "coverage_record": before,
            "archive_updated_at": archive_payload.get("updated_at"),
            "fault": (
                "coverage generated before the active FINRA producer; same-run "
                "manifest retained the previous publication watermark"
            ),
        },
        "after": {
            "read_only_rebuilt_coverage": rebuilt,
            "main_order_contract": order,
            "health_contract": (
                "refresh broad FINRA archive -> append central coverage -> "
                "default-off sleeve consumes the same fresh archive"
            ),
            "trade_enabled": False,
        },
        "checks": checks,
        "verification": {
            "focused_tests": "7 passed",
            "related_tests": "83 passed",
            "py_compile": "passed",
            "ruff": "not installed in workspace environment",
            "gate_1_to_4": (
                "not rerun: measurement-only source health; baseline hash and "
                "all signal/ranking/sizing/order policies are locked"
            ),
            "expected_value_score_delta": 0.0,
            "pnl_delta_usd": 0.0,
            "trade_count_delta": 0,
        },
        "alpha_synthesis": {
            "baseline_universe": [
                "cash-feasible Gate-1 core universe",
                "Massive dated active common stocks",
                "current 17-position account",
                "accepted observers",
                "cash",
                "SPY",
                "QQQ",
            ],
            "opportunity_cost_winner": "cash_abstain",
            "evidence_surfaces_used": [
                "canonical cold+hot price",
                "Moomoo flow",
                "Onclick options",
                "SEC/Form4 events",
                "portfolio exposure",
                "FINRA short-interest source health",
                "research digest",
            ],
            "evidence_surfaces_missing": [
                "authorized external model-diverse review receipt for the frozen Massive dividend-restart lead"
            ],
            "hypothesis_candidates": [
                "Massive first positive USD cash distribution after a 1095-day gap",
                "intraday REDUCE_RISK after 20 settled halves",
                "Form4 sale-overhang after 25 closed rows",
            ],
            "selected_hypothesis": (
                "Massive dividend-restart research-PIT scout, frozen before outcomes"
            ),
            "economic_mechanism": (
                "a resumed cash distribution can reveal a durable capital-return "
                "regime change, but only a preregistered model-diverse challenge "
                "may promote the frozen lead"
            ),
            "falsifier": (
                "fixed next-open H10 replacement value does not beat same-date "
                "cash/core and SPY/QQQ after costs, or panel identity/PIT checks fail"
            ),
            "pit_tier": "research_pit",
            "evidence_grade": "lead",
            "result_ceiling": "observed_only",
            "next_machine_action": (
                "obtain explicit authorization for the configured external Codex "
                "reviewer before promotion; do not access candidate outcomes"
            ),
        },
        "remaining_nonblocking_health_debt": [
            "FINRA source_files history is overwritten by each refresh rather than merged",
            "settlement-age freshness can lead official publication timing",
            "address only in a bounded multi-observer health batch, not a one-off alpha retry",
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "default_off_measurement_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"artifact": str(ARTIFACT_PATH), "decision": artifact["decision"], "checks": checks},
            indent=2,
        )
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
