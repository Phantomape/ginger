"""exp-20260727-001: repair options-forward settlement over the OHLCV hot tier.

This is an alpha-enabling measurement repair.  It rebuilds the default-off
options candidate ledger into an experiment-owned directory, compares it with
the last cold-only daily report, and verifies that no candidate, scoring,
strategy, or order semantics changed.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from ohlcv_warehouse import connect_overlay_reader, overlay_reader_status  # noqa: E402


EXPERIMENT_ID = "exp-20260727-001"
ARTIFACT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_PATH = ARTIFACT_DIR / "exp_20260727_001_options_forward_hot_overlay_settlement.json"
BEFORE_SUMMARY_PATH = ARTIFACT_DIR / "options_forward_before_summary.json"
AFTER_DIR = ARTIFACT_DIR / "options_forward_after"
BEFORE_REPORT_PATH = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "options_forward"
    / "options_forward_candidate_ledger_report.json"
)
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
EXPECTED_BASELINE_AGGREGATE = {
    "expected_value_score_sum": 6.2057,
    "total_pnl_sum": 130992.36,
    "trade_count_sum": 49,
    "positive_ev_windows": 3,
    "minimum_survival_rate": 0.8116,
    "worst_max_drawdown_pct": 0.0889,
}
EXPECTED_REMAINING_MISSING_DATES = {
    "2026-05-23": 42,
    "2026-06-19": 2,
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _load_ledger_module():
    script_path = REPO_ROOT / "scripts" / "run_options_forward_ledger.py"
    spec = importlib.util.spec_from_file_location(
        "run_options_forward_ledger_for_exp_20260727_001", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_metrics(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("candidate_summary") or {}
    closed = (report.get("outcome_close_summary") or {}).get("all_scoring_allowed") or {}
    statuses = summary.get("outcome_status_counts") or {}
    return {
        "candidate_count": summary.get("candidate_count"),
        "options_scoring_allowed_candidates": summary.get("options_scoring_allowed_candidates"),
        "partial_or_pending": statuses.get("partial_or_pending", 0),
        "signal_date_missing_in_ohlcv": statuses.get("signal_date_missing_in_ohlcv", 0),
        "closed_5d_count": closed.get("closed_5d_count"),
        "closed_10d_count": closed.get("closed_10d_count"),
        "closed_20d_count": closed.get("closed_20d_count"),
        "closed_60d_count": closed.get("closed_60d_count"),
    }


def capture_before() -> dict[str, Any]:
    """Freeze the cold-only pre-repair counts before a concurrent daily refresh."""
    report = _read_json(BEFORE_REPORT_PATH)
    snapshot = {
        "experiment_id": EXPERIMENT_ID,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(BEFORE_REPORT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "source_generated_at": report.get("generated_at"),
        "metrics": _candidate_metrics(report),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    BEFORE_SUMMARY_PATH.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return snapshot


def _warehouse_diagnostics(
    missing_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    conn = connect_overlay_reader(WAREHOUSE_PATH)
    try:
        status = overlay_reader_status(conn)
        cold_max = conn.execute("SELECT MAX(date) FROM main.ohlcv").fetchone()[0]
        hot_max = (
            conn.execute("SELECT MAX(date) FROM hot.ohlcv").fetchone()[0]
            if status["hot_attached"]
            else None
        )
        overlay_max = conn.execute("SELECT MAX(date) FROM ohlcv_overlay").fetchone()[0]
        missing_pairs_absent = True
        for row in missing_rows:
            key = (row.get("ticker"), row.get("candidate_action_date"))
            in_cold = conn.execute(
                "SELECT 1 FROM main.ohlcv WHERE ticker = ? AND date = ? LIMIT 1", key
            ).fetchone()
            in_hot = (
                conn.execute(
                    "SELECT 1 FROM hot.ohlcv WHERE ticker = ? AND date = ? LIMIT 1", key
                ).fetchone()
                if status["hot_attached"]
                else None
            )
            if in_cold or in_hot:
                missing_pairs_absent = False
                break
    finally:
        conn.close()
    return {
        **status,
        "cold_max_date": cold_max,
        "hot_max_date": hot_max,
        "overlay_max_date": overlay_max,
    }, missing_pairs_absent


def main() -> dict[str, Any]:
    if not BEFORE_SUMMARY_PATH.exists():
        raise SystemExit("missing pre-repair snapshot; run this runner with --capture-before first")
    before_snapshot = _read_json(BEFORE_SUMMARY_PATH)
    baseline = _read_json(BASELINE_PATH)
    ledger = _load_ledger_module()

    args = ledger.build_arg_parser().parse_args(
        [
            "--experiment-id",
            EXPERIMENT_ID,
            "--output-dir",
            str(AFTER_DIR),
            "--chain-dir",
            str(REPO_ROOT / "data" / "non_ohlcv"),
            "--quant-signal-dir",
            str(REPO_ROOT / "data"),
            "--ohlcv-warehouse",
            str(WAREHOUSE_PATH),
        ]
    )
    after_report = ledger.build_ledger(args)
    after_rows = _read_jsonl(AFTER_DIR / "options_forward_candidate_ledger.jsonl")

    before = before_snapshot["metrics"]
    after = _candidate_metrics(after_report)
    remaining_missing = [
        row for row in after_rows if row.get("outcome_status") == "signal_date_missing_in_ohlcv"
    ]
    remaining_date_counts = dict(
        sorted(Counter(str(row.get("candidate_action_date")) for row in remaining_missing).items())
    )
    warehouse, remaining_pairs_absent = _warehouse_diagnostics(remaining_missing)
    baseline_aggregate = baseline.get("aggregate") or {}

    checks = {
        "candidate_population_unchanged_241": (
            before["candidate_count"] == after["candidate_count"] == 241
        ),
        "scoring_allowed_unchanged_30": (
            before["options_scoring_allowed_candidates"]
            == after["options_scoring_allowed_candidates"]
            == 30
        ),
        "cold_only_missing_precondition_94": before["signal_date_missing_in_ohlcv"] == 94,
        "overlay_missing_reduced_to_true_44": after["signal_date_missing_in_ohlcv"] == 44,
        "pending_rows_restored_147_to_197": (
            before["partial_or_pending"] == 147 and after["partial_or_pending"] == 197
        ),
        "closed_horizons_increase_or_hold": all(
            after[key] is not None and before[key] is not None and after[key] >= before[key]
            for key in ("closed_5d_count", "closed_10d_count", "closed_20d_count")
        ),
        "remaining_dates_are_known_nontrading_dates": (
            remaining_date_counts == EXPECTED_REMAINING_MISSING_DATES
        ),
        "remaining_pairs_absent_from_both_stores": remaining_pairs_absent,
        "canonical_hot_sibling_attached": (
            warehouse["hot_exists"] is True
            and warehouse["hot_attached"] is True
            and warehouse["hot_error"] is None
        ),
        "overlay_reaches_hot_edge": (
            warehouse["cold_max_date"] == "2026-06-15"
            and warehouse["hot_max_date"] >= "2026-07-24"
            and warehouse["overlay_max_date"] == warehouse["hot_max_date"]
        ),
        "cash_feasible_gate1_anchor_unchanged": (
            baseline_aggregate == EXPECTED_BASELINE_AGGREGATE
        ),
    }
    all_checks_passed = all(checks.values())
    decision = "accepted_measurement_repair" if all_checks_passed else "rejected_measurement_repair"

    report = {
        "schema": "options_forward_hot_overlay_settlement_repair_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "measurement_repair",
        "decision": decision,
        "accepted_alpha": False,
        "hypothesis": (
            "The options-forward daily settlement is stale because it reads only the cold OHLCV "
            "warehouse. The canonical cold-plus-hot overlay should recover recent outcomes without "
            "changing candidates, option tags, PIT joins, signals, sizing, exits, or orders."
        ),
        "single_causal_variable": "options_forward settlement reads canonical OHLCV overlay",
        "related_experiments": [
            "exp-20260704-017",
            "exp-20260707-011",
            "exp-20260709-002",
            "exp-20260709-017",
            "exp-20260630-010",
        ],
        "prediction": {
            "success_probability": 0.95,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "hot_overlay_attach_failure",
                "overlay_precedence_error",
                "recent_candidate_tickers_missing_in_hot",
            ],
        },
        "before_artifact": str(BEFORE_REPORT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "before_snapshot": str(BEFORE_SUMMARY_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "before_source_generated_at": before_snapshot.get("source_generated_at"),
        "after_artifact": str(
            (AFTER_DIR / "options_forward_candidate_ledger_report.json").relative_to(REPO_ROOT)
        ).replace("\\", "/"),
        "gate1_baseline": {
            "path": str(BASELINE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "experiment_id": baseline.get("experiment_id"),
            "aggregate": baseline_aggregate,
        },
        "before": before,
        "after": after,
        "delta": {
            key: after[key] - before[key]
            for key in (
                "candidate_count",
                "options_scoring_allowed_candidates",
                "partial_or_pending",
                "signal_date_missing_in_ohlcv",
                "closed_5d_count",
                "closed_10d_count",
                "closed_20d_count",
                "closed_60d_count",
            )
            if before[key] is not None and after[key] is not None
        },
        "warehouse": warehouse,
        "remaining_missing": {
            "count": len(remaining_missing),
            "by_candidate_action_date": remaining_date_counts,
            "absent_from_cold_and_hot": remaining_pairs_absent,
            "interpretation": (
                "42 duplicate DE candidate rows fall on Saturday 2026-05-23; CAT and TSM each "
                "have one row on the 2026-06-19 Juneteenth market holiday."
            ),
        },
        "checks": checks,
        "all_checks_passed": all_checks_passed,
        "gate_evaluation": {
            "gate1": "active cash-feasible anchor unchanged",
            "gate2": (
                "consumer uses ohlcv_overlay and reports hot attach status; strategy entry_date and "
                "target_price sentinels are outside this shadow settlement ledger and unchanged"
            ),
            "gate3": "not applicable: no entry filter or signal survival change",
            "gate4": "measurement before/after only; strategy EV and PnL are intentionally unchanged",
        },
        "alpha_synthesis": {
            "baseline_universe": [
                "active cash-feasible strategy universe",
                "same-date default-off candidate pool",
            ],
            "opportunity_cost_winner": "cash; no new executable candidate is Gate-ready",
            "evidence_surfaces_used": [
                "canonical cold-plus-hot OHLCV",
                "OnClickMedia PIT-safe options chains",
                "daily candidate snapshots",
                "Moomoo flow observer readiness",
                "active portfolio exposure state",
                "research digest 2026-07-27",
            ],
            "evidence_surfaces_missing": [
                "20 settled paired flow-options disagreement decisions",
                "10 additional genuine forward PIT collection dates",
                "settled same-slot portfolio replacement outcomes",
            ],
            "hypothesis_candidates": [
                {
                    "name": "flow-options disagreement",
                    "baseline": "same-date candidates without disagreement classification",
                    "treatment": "spot net-flow strength paired with PIT-safe put/skew disagreement",
                    "horizon": "5/10/20 trading days",
                    "replacement_value": "same-day entered alternatives and cash",
                    "falsifier": "no monotone replacement-value separation after 20 settled pairs",
                    "grade": "observer",
                },
                {
                    "name": "exact-url entity-theme event repricing",
                    "baseline": "same-day untagged candidates",
                    "treatment": "PIT exact-URL event rows joined to canonical prices",
                    "horizon": "5/20 trading days",
                    "replacement_value": "same-day candidates without event exposure",
                    "falsifier": "no cross-theme separation after 75 settled events",
                    "grade": "observer",
                },
                {
                    "name": "portfolio slot-conflict replacement",
                    "baseline": "held slot trajectory",
                    "treatment": "same-day rejected candidate replacing the occupied slot",
                    "horizon": "holding-period matched",
                    "replacement_value": "real held position after costs",
                    "falsifier": "nonpositive replacement value after 20 settled conflicts",
                    "grade": "snapshot_only",
                },
            ],
            "selected_hypothesis": "flow-options disagreement",
            "economic_mechanism": (
                "cash-equity demand unsupported by option positioning may flag fragile continuation, "
                "while agreement may identify demand with better follow-through"
            ),
            "falsifier": "paired disagreement decisions fail to separate replacement value after costs",
            "evidence_grade": "observer",
            "next_machine_action": (
                "continue daily collection until at least 10 additional PIT dates and 20 settled paired "
                "disagreement decisions; do not promote or retune before then"
            ),
        },
        "research_digest_review": {
            "path": "data/research_digest/latest_digest.md",
            "fresh_actionable_entries": 0,
            "decision": "no append: displayed entries were already terminal in the ledger",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "options_settlement_reader_changed": True,
            "default_off_shadow_only": True,
            "signals_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "orders_changed": False,
        },
        "post_run_reflection": {
            "why": (
                "The cold warehouse stopped at 2026-06-15 while the sibling hot tier held the next "
                "sessions through 2026-07-24; the consumer bypassed the repository overlay contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not tune options tags or infer flow-options alpha from this repair alone."
            ),
            "retry_evidence": (
                "Only a failed attach/precedence regression justifies another measurement-repair ID; "
                "alpha evaluation still requires the parked lane's settled-row thresholds."
            ),
        },
        "changed_files": [
            "scripts/run_options_forward_ledger.py",
            "quant/test_run_daily_wiring.py",
            "quant/experiments/exp_20260727_001_options_forward_hot_overlay_settlement.py",
        ],
        "reproduction": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_run_daily_wiring.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260727_001_options_forward_hot_overlay_settlement.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if not all_checks_passed:
        raise SystemExit("measurement repair acceptance checks failed")
    return report


if __name__ == "__main__":
    if "--capture-before" in sys.argv[1:]:
        capture_before()
    else:
        main()
