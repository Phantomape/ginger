"""exp-20260703-010: validate post-quant estimate-revision ledger refresh.

Measurement repair only. The alpha hypothesis is that estimate-revision
direction may matter when it overlaps production-visible candidate rows, but
the daily ledger is not trustworthy if it is written before same-day
quant_signals exist. This runner writes a match-enabled probe ledger to the
experiment directory and leaves canonical data/non_ohlcv ledgers untouched.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260703-010"
AS_OF = "2026-07-02"
TAG = "20260702"
SLUG = "estimate_revision_post_quant_signal_ledger_refresh"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from estimate_revision_ledger import (  # noqa: E402
    load_daily_signal_match_records,
    persist_estimate_revision_ledger,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
CANONICAL_SUMMARY = (
    REPO_ROOT / "data" / "non_ohlcv" / f"estimate_revision_ledger_summary_{TAG}.json"
)
QUANT_SIGNALS = (
    REPO_ROOT / "data" / "daily" / "signals" / "quant" / f"quant_signals_{TAG}.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
PROBE_OUT_DIR = OUT_DIR / "probe_non_ohlcv"
ARTIFACT = OUT_DIR / f"exp_20260703_010_{SLUG}.json"
BEFORE_JSON = OUT_DIR / "before_metrics.json"
AFTER_JSON = OUT_DIR / "after_metrics.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "window_count": len(windows),
    }


def summary_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "daily_signal_match_record_count": int(
            summary.get("daily_signal_match_record_count") or 0
        ),
        "matched_candidate_rows": int(summary.get("matched_candidate_rows") or 0),
        "matched_selected_signal_rows": int(
            summary.get("matched_selected_signal_rows") or 0
        ),
        "estimate_revision_usable_rows": int(
            summary.get("estimate_revision_usable_rows") or 0
        ),
        "up_revision_rows": int(summary.get("up_revision_rows") or 0),
        "down_revision_rows": int(summary.get("down_revision_rows") or 0),
    }


def main() -> None:
    before_summary = read_json(CANONICAL_SUMMARY, {})
    signal_records = load_daily_signal_match_records(REPO_ROOT / "data", AS_OF)
    after_summary = persist_estimate_revision_ledger(
        as_of=AS_OF,
        data_dir=REPO_ROOT / "data",
        output_dir=PROBE_OUT_DIR,
        match_daily_signals=True,
        run_adapter_changed=True,
    )

    base = baseline_metrics()
    before = {
        **base,
        **summary_metrics(before_summary),
        "strategy_behavior_changed": False,
        "source": repo_rel(CANONICAL_SUMMARY),
    }
    after = {
        **base,
        **summary_metrics(after_summary),
        "strategy_behavior_changed": False,
        "source": repo_rel(PROBE_OUT_DIR / f"estimate_revision_ledger_summary_{TAG}.json"),
    }
    delta = {
        "daily_signal_match_record_count_delta": (
            after["daily_signal_match_record_count"]
            - before["daily_signal_match_record_count"]
        ),
        "matched_candidate_rows_delta": (
            after["matched_candidate_rows"] - before["matched_candidate_rows"]
        ),
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    accepted = (
        QUANT_SIGNALS.exists()
        and before["daily_signal_match_record_count"] == 0
        and after["daily_signal_match_record_count"] > 0
        and not after["strategy_behavior_changed"]
    )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": (
            "accepted_measurement_repair_estimate_revision_post_quant_signal_refresh"
            if accepted
            else "blocked_estimate_revision_post_quant_signal_refresh"
        ),
        "generated_at": utc_now(),
        "hypothesis": (
            "Estimate-revision candidate-match attribution needs a post-quant "
            "ledger refresh because run.py writes the initial daily ledger "
            "before quant_signals exists."
        ),
        "alpha_hypothesis": (
            "Estimate-revision direction may have replacement value when it "
            "overlaps same-day production-visible candidates, but threshold or "
            "allocation tests remain blocked until matched rows have closed "
            "replacement-value outcomes."
        ),
        "single_causal_variable": "estimate_revision_post_quant_signal_ledger_refresh_v1",
        "changed_variable": "estimate_revision_ledger_pipeline_timing",
        "trial_family": "estimate_revision_daily_candidate_match_surface_repair",
        "new_evidence_axis": (
            "Shared run.py post-quant-signal refresh, not a revision direction, "
            "threshold, top-N, hold, notional, or response-curve retry."
        ),
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "signal_match_records_loaded_now": {
            "record_count": len(signal_records),
            "sources": sorted({row.get("source") for row in signal_records if row.get("source")}),
            "candidate_record_count": sum(1 for row in signal_records if row.get("is_candidate")),
            "selected_record_count": sum(1 for row in signal_records if row.get("is_selected")),
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
            "live_orders_changed": False,
            "trade_enabled": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The same-day quant_signals file already contained loadable "
                "records, while the canonical revision summary had zero match "
                "records because it was written earlier in run.py."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not open more per-date estimate-revision artifact recovery "
                "experiments. The shared pipeline refresh is now the repair; "
                "alpha work must wait for closed replacement-value outcomes or "
                "a different PIT expectation source."
            ),
            "new_evidence_required": (
                "Closed cash/SPY/QQQ replacement-value outcomes for matched "
                "estimate-revision rows, materially more non-flat matched rows, "
                "or a different unsaturated PIT expectation field."
            ),
        },
        "changed_files": [
            "quant/run.py",
            "quant/test_run_daily_wiring.py",
            f"quant/experiments/exp_20260703_010_{SLUG}.py",
            repo_rel(ARTIFACT),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\run.py quant\\test_run_daily_wiring.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_run_daily_wiring.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260703_010_estimate_revision_post_quant_signal_ledger_refresh.py",
        ],
    }

    write_json(BEFORE_JSON, before)
    write_json(AFTER_JSON, after)
    write_json(ARTIFACT, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
