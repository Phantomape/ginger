"""exp-20260630-021: repair estimate-revision candidate-match ordering.

The 2026-06-29 estimate-revision ledger was generated before the same-day
quant signal artifact landed, so the ledger recorded zero candidate matches.
This runner regenerates that one ledger after the artifact exists and records
before/after evidence. It does not change strategy behavior.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from estimate_revision_ledger import (  # noqa: E402
    load_daily_signal_match_records,
    persist_estimate_revision_ledger,
)


EXPERIMENT_ID = "exp-20260630-021"
AS_OF = "2026-06-29"
TAG = "20260629"
BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_PATH = OUT_DIR / "exp_20260630_021_estimate_revision_post_quant_signal_match_rerun.json"
SUMMARY_PATH = REPO_ROOT / "data" / "non_ohlcv" / f"estimate_revision_ledger_summary_{TAG}.json"
LEDGER_PATH = REPO_ROOT / "data" / "non_ohlcv" / f"estimate_revision_ledger_{TAG}.jsonl"


def _repo_rel(path: str | Path) -> str:
    return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _counter(items: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(items).items()))


def _signal_match_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "candidate_record_count": sum(1 for row in records if row.get("is_candidate_record")),
        "selected_signal_count": sum(1 for row in records if row.get("is_selected_signal")),
        "sources": sorted({row.get("source") for row in records if row.get("source")}),
        "record_types": _counter([str(row.get("record_type")) for row in records if row.get("record_type")]),
        "candidate_tickers": sorted(
            {str(row.get("ticker")).upper() for row in records if row.get("is_candidate_record") and row.get("ticker")}
        ),
    }


def _matched_ledger_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_rows = [row for row in rows if row.get("matched_candidate_today")]
    usable_candidate_rows = [
        row for row in candidate_rows if row.get("estimate_revision_usable")
    ]
    return {
        "row_count": len(rows),
        "matched_candidate_rows": len(candidate_rows),
        "estimate_revision_usable_and_matched_candidate_rows": len(usable_candidate_rows),
        "matched_selected_signal_rows": sum(bool(row.get("matched_selected_signal_today")) for row in rows),
        "up_revision_usable_matched_candidate_rows": sum(
            row.get("revision_direction_prev") == "up" for row in usable_candidate_rows
        ),
        "down_revision_usable_matched_candidate_rows": sum(
            row.get("revision_direction_prev") == "down" for row in usable_candidate_rows
        ),
        "candidate_gap_reasons": _counter(
            [str(row.get("candidate_match_gap_reason")) for row in rows if row.get("candidate_match_gap_reason")]
        ),
        "matched_candidate_tickers": sorted({row.get("ticker") for row in candidate_rows if row.get("ticker")}),
        "matched_candidate_sample": [
            {
                "ticker": row.get("ticker"),
                "revision_direction_prev": row.get("revision_direction_prev"),
                "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
                "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
                "estimate_revision_usable": row.get("estimate_revision_usable"),
                "matched_signal_sources": row.get("matched_signal_sources"),
                "matched_signal_record_types": row.get("matched_signal_record_types"),
                "matched_signal_strategies": row.get("matched_signal_strategies"),
                "matched_signal_records": row.get("matched_signal_records"),
            }
            for row in candidate_rows[:10]
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    before_summary = _read_json(SUMMARY_PATH)
    before_rows = _read_jsonl(LEDGER_PATH)
    before_match_records = load_daily_signal_match_records(REPO_ROOT / "data", AS_OF)

    after_summary = persist_estimate_revision_ledger(
        as_of=AS_OF,
        data_dir=REPO_ROOT / "data",
        output_dir=REPO_ROOT / "data" / "non_ohlcv",
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
        signal_data_dir=REPO_ROOT / "data",
        match_daily_signals=True,
    )
    after_rows = _read_jsonl(LEDGER_PATH)
    after_match_records = load_daily_signal_match_records(REPO_ROOT / "data", AS_OF)

    before_candidate_matches = int(before_summary.get("matched_candidate_rows") or 0)
    after_candidate_matches = int(after_summary.get("matched_candidate_rows") or 0)
    production_impact = after_summary.get("production_impact") or {}
    no_strategy_change = not any(
        production_impact.get(key)
        for key in (
            "shared_policy_changed",
            "backtester_adapter_changed",
            "run_adapter_changed",
            "alters_signal_generation",
            "alters_candidate_ranking",
            "alters_sizing",
            "alters_orders",
        )
    )
    accepted = after_candidate_matches > before_candidate_matches and after_candidate_matches > 0 and no_strategy_change
    failed_reasons: list[str] = []
    if after_candidate_matches <= before_candidate_matches:
        failed_reasons.append("matched_candidate_rows_not_increased")
    if after_candidate_matches <= 0:
        failed_reasons.append("no_matched_candidate_rows_after_rerun")
    if not no_strategy_change:
        failed_reasons.append("production_impact_not_data_only")

    artifact: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "lane": "measurement_repair",
        "decision": (
            "accepted_measurement_repair_estimate_revision_post_quant_signal_match_rerun"
            if accepted
            else "blocked_estimate_revision_post_quant_signal_match_rerun"
        ),
        "accepted": accepted,
        "accepted_alpha": False,
        "strategy_behavior_changed": False,
        "hypothesis": (
            "Estimate-revision candidate-match attribution is only testable when the "
            "daily ledger is generated after same-day quant/trend signal artifacts exist."
        ),
        "changed_variable": "estimate_revision_post_quant_signal_match_rerun_v1",
        "single_causal_variable": "estimate_revision_post_quant_signal_match_rerun_v1",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "as_of": AS_OF,
        "before": {
            "summary_path": _repo_rel(SUMMARY_PATH),
            "ledger_path": _repo_rel(LEDGER_PATH),
            "summary": before_summary,
            "signal_match_records_loaded_now": _signal_match_summary(before_match_records),
            "ledger_match_summary": _matched_ledger_summary(before_rows),
        },
        "after": {
            "summary_path": _repo_rel(SUMMARY_PATH),
            "ledger_path": _repo_rel(LEDGER_PATH),
            "summary": after_summary,
            "signal_match_records_loaded_now": _signal_match_summary(after_match_records),
            "ledger_match_summary": _matched_ledger_summary(after_rows),
        },
        "delta": {
            "matched_candidate_rows_delta": after_candidate_matches - before_candidate_matches,
            "daily_signal_match_record_count_delta": int(after_summary.get("daily_signal_match_record_count") or 0)
            - int(before_summary.get("daily_signal_match_record_count") or 0),
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": BASELINE_RESULT_FILE,
            "note": "Measurement repair only; accepted-stack baseline is unchanged.",
        },
        "gate2": {
            "passed": bool(after_match_records),
            "required_fields": ["ticker", "as_of_date", "matched_candidate_today"],
            "daily_signal_match_record_count": len(after_match_records),
        },
        "gate3": {
            "passed": after_candidate_matches > 0,
            "signals_generated_proxy": int(after_summary.get("row_count") or 0),
            "signals_survived_proxy": after_candidate_matches,
            "survival_rate_proxy": round(
                after_candidate_matches / int(after_summary.get("row_count") or 1), 6
            ),
        },
        "gate4": {
            "passed": accepted,
            "strategy_behavior_changed": False,
            "failed_reasons": failed_reasons,
            "decision": (
                "accepted_measurement_repair_estimate_revision_post_quant_signal_match_rerun"
                if accepted
                else "blocked_estimate_revision_post_quant_signal_match_rerun"
            ),
        },
        "production_impact": production_impact,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260630_021_estimate_revision_post_quant_signal_match_rerun.py",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\experiments\\exp_20260630_021_estimate_revision_post_quant_signal_match_rerun.py",
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "The same-day quant signal artifact existed after the previous ledger run, "
                "so the existing matcher could attach candidate records once the ledger was regenerated."
            )
            if accepted
            else "The regenerated ledger still did not produce candidate matches.",
            "forbidden_near_neighbor_retry": (
                "Do not run estimate-revision thresholds, direction gates, top-N, hold, notional, "
                "or observed-only slices from these rows until selected/current matches have closed "
                "3/5/10d replacement-value outcomes."
            ),
            "new_evidence_required": (
                "Next alpha-compliant revision work needs closed replacement-value outcomes for the "
                "matched candidate rows or a different unsaturated PIT expectation field."
            ),
        },
    }
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(artifact, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
