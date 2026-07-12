"""Build daily-return inference evidence for the current working strategy stack.

This is a measurement-repair runner for exp-20260712-006.  It does not create
or select a trial panel. The 2026-06-04 archived champion is audited separately
and must not inherit PSR values from a non-identical current-working-tree replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260712-006"
WAREHOUSE = ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
BASELINE_SUMMARY = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ARCHIVE = ROOT / "data" / "backtests" / "archive" / "20260604_ohlcv_warehouse_replay"
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "current_working_stack_sharpe_inference.json"
)

WINDOWS = (
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "archive": "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "archive": "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "archive": "backtest_results_warehouse_snapshot_old_thin_20260604.json",
    },
)

METRICS = (
    "expected_value_score",
    "total_pnl",
    "total_trades",
    "wins",
    "losses",
    "win_rate",
    "max_drawdown_pct",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "sharpe_daily",
    "sharpe",
)

BEHAVIOR_METRICS = (
    "total_pnl",
    "total_trades",
    "wins",
    "losses",
    "win_rate",
    "signals_generated",
    "signals_survived",
    "survival_rate",
    "sharpe",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _baseline_for_window(label: str) -> dict[str, Any]:
    summary = _load_json(BASELINE_SUMMARY)
    return next(row for row in summary["windows"] if row["label"] == label)


def _run_window(spec: dict[str, str], universe: list[str]) -> dict[str, Any]:
    archived = _load_json(ARCHIVE / spec["archive"])
    baseline_summary = _baseline_for_window(spec["label"])
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_warehouse_path=str(WAREHOUSE),
        ohlcv_warehouse_snapshot_source=spec["snapshot"],
        include_oracle_diagnostics=False,
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{spec['label']}: {result['error']}")

    before_metrics = {key: archived.get(key, baseline_summary.get(key)) for key in METRICS}
    after_metrics = {key: result.get(key) for key in METRICS}
    trade_identity_before = _stable_hash(archived.get("trades", []))
    trade_identity_after = _stable_hash(result.get("trades", []))
    inference = result.get("sharpe_inference")
    if not isinstance(inference, dict):
        raise RuntimeError(f"{spec['label']}: sharpe_inference block missing")
    current_total_pnl_matches_trades = result.get("total_pnl") == round(
        sum(float(trade.get("pnl", 0.0)) for trade in result.get("trades", [])), 2
    )
    current_trade_count_matches_rows = result.get("total_trades") == len(
        result.get("trades", [])
    )
    inference_contract_passed = (
        inference.get("status") == "computable"
        and (inference.get("psr") or {}).get("status") == "computable"
        and (inference.get("dsr") or {}).get("status") == "not_computable"
        and bool(inference.get("return_series_sha256"))
        and inference.get("sample_count") == result.get("trading_days", 0) - 1
        and len(inference.get("return_series") or []) == inference.get("sample_count")
    )

    return {
        "label": spec["label"],
        "start": spec["start"],
        "end": spec["end"],
        "snapshot": spec["snapshot"],
        "before_artifact": str((ARCHIVE / spec["archive"]).relative_to(ROOT)),
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "strategy_behavior_metrics_unchanged": all(
            before_metrics[key] == after_metrics[key] for key in BEHAVIOR_METRICS
        ),
        "trade_identity_unchanged": trade_identity_before == trade_identity_after,
        "trade_identity_hash_before": trade_identity_before,
        "trade_identity_hash_after": trade_identity_after,
        "current_total_pnl_matches_trade_rows": current_total_pnl_matches_trades,
        "current_trade_count_matches_trade_rows": current_trade_count_matches_rows,
        "sharpe_inference_contract_passed": inference_contract_passed,
        "measurement_deltas": {
            key: (
                None
                if before_metrics[key] is None or after_metrics[key] is None
                else after_metrics[key] - before_metrics[key]
            )
            for key in ("sharpe_daily", "expected_value_score", "max_drawdown_pct")
        },
        "sharpe_inference": inference,
    }


def build_artifact() -> dict[str, Any]:
    universe = list(get_universe())
    windows = [_run_window(spec, universe) for spec in WINDOWS]
    baseline_exact_reproduction = all(
        row["strategy_behavior_metrics_unchanged"] and row["trade_identity_unchanged"]
        for row in windows
    )
    dsr_states = [row["sharpe_inference"].get("dsr") for row in windows]
    working_stack_dsr_not_computable = all(
        isinstance(state, dict) and state.get("status") == "not_computable"
        for state in dsr_states
    )
    measurement_contract_passed = working_stack_dsr_not_computable and all(
        row["current_total_pnl_matches_trade_rows"]
        and row["current_trade_count_matches_trade_rows"]
        and row["sharpe_inference_contract_passed"]
        for row in windows
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": (
            "accepted_measurement_repair" if measurement_contract_passed else "blocked"
        ),
        "measurement_contract": "trial_adjusted_sharpe_inference_v1",
        "strategy_or_order_behavior_changed_by_this_patch": False,
        "measurement_contract_passed": measurement_contract_passed,
        "historical_baseline_exact_reproduction": baseline_exact_reproduction,
        "historical_baseline_comparison_role": "diagnostic_only_not_acceptance_gate",
        "historical_baseline_drift_note": (
            None
            if baseline_exact_reproduction
            else (
                "The current working strategy stack does not exactly reproduce every "
                "2026-06-04 archived trade/metric. This pre-existing/current-stack drift "
                "cannot be attributed to a post-simulation equity measurement patch; it "
                "is disclosed separately and is not used to fabricate DSR evidence."
            )
        ),
        "current_working_stack_inference": {
            "psr_status": "computable",
            "dsr_status": (
                "not_computable" if working_stack_dsr_not_computable else "invalid"
            ),
            "window_records_key": "windows",
            "identity": "working_tree_replay_not_archived_champion",
        },
        "archived_20260604_champion_inference": {
            "psr_status": "not_computable",
            "dsr_status": "not_computable",
            "reasons": [
                "archived_artifacts_missing_dated_daily_returns",
                "selection_pool_missing",
                "trial_sharpe_dispersion_missing",
                "effective_trial_count_missing",
                "legacy_artifacts_do_not_retain_aligned_trial_return_panels",
            ],
            "fabricated_numeric_value": None,
            "interpretation": (
                "The archived champion has neither reconstructable PSR inputs nor a "
                "complete comparable historical trial panel. Current-working-stack PSR "
                "must not be relabelled as archived-champion evidence."
            ),
        },
        "baseline_summary": str(BASELINE_SUMMARY.relative_to(ROOT)),
        "warehouse": str(WAREHOUSE.relative_to(ROOT)),
        "windows": windows,
        "production_impact": (
            "No entry, exit, ranking, sizing, or order path changed. The codified "
            "full_stack_candidate_pool Gate 5 now consumes recomputable DSR evidence "
            "before its live_eligible verdict. Other legacy/manual activation paths are "
            "outside this experiment's enforcement scope."
        ),
        "verification_boundary": (
            "Trade/order invariance is locked by focused BacktestEngine regression tests "
            "and the measurement-only code path. Historical archive equality is reported "
            "separately because the working strategy stack has evolved since 2026-06-04."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    artifact = build_artifact()
    _atomic_write_json(args.output, artifact)
    print(json.dumps({
        "output": str(args.output),
        "decision": artifact["decision"],
        "measurement_contract_passed": artifact["measurement_contract_passed"],
        "historical_baseline_exact_reproduction": artifact[
            "historical_baseline_exact_reproduction"
        ],
        "archived_20260604_champion_dsr": artifact[
            "archived_20260604_champion_inference"
        ]["dsr_status"],
    }, ensure_ascii=False, indent=2))
    return 0 if artifact["decision"] == "accepted_measurement_repair" else 2


if __name__ == "__main__":
    raise SystemExit(main())
