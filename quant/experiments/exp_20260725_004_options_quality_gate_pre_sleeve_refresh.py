"""exp-20260725-004: verify the pre-sleeve options quality gate refresh.

Fault: quant/run.py rebuilt data/non_ohlcv/options_forward/
options_collection_quality_gate.json only AFTER all paper sleeves were built,
so the core drawdown flow-put stabilization observer always read a quality
file missing its own asof quote-date row (missing_quality_row,
options_scoring_allowed=false) and daily_options_complete_signals was
structurally pinned at 0.

This runner reproduces the fault and verifies the repair with persist=False
snapshot builds (no sleeve state or ledger mutation):

  before: quality file with the asof row removed  -> missing_quality_row
  after : quality file rebuilt by the new
          refresh_collection_quality_gate() entrypoint -> usable_for_shadow

Usage:
  .venv/Scripts/python.exe -B quant/experiments/exp_20260725_004_options_quality_gate_pre_sleeve_refresh.py
  .venv/Scripts/python.exe -B quant/experiments/exp_20260725_004_options_quality_gate_pre_sleeve_refresh.py --recover

--recover additionally re-materializes the faulted asof day against the REAL
sleeve state (persist=True) so the lost decision day is recovered before its
next-session entry would price.  The snapshot log is append-only; the reopen
readiness builder canonicalizes retries by keeping the last row per asof
date, and pending-entry admission is decision_id-idempotent, so the retry is
safe.  Run --recover only before the next session open after the faulted
close (PIT: the signal uses only post-close data of the faulted day).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from core_drawdown_flow_put_stabilization_paper_sleeve import (  # noqa: E402
    DEFAULT_OPTIONS_DIR,
    DEFAULT_OPTIONS_QUALITY_PATH,
    NON_COMMON_STOCK_EXCLUSIONS,
    build_core_drawdown_flow_put_snapshot,
    empty_core_drawdown_flow_put_state,
    load_moomoo_capital_flow_rows,
)
from ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402

EXPERIMENT_ID = "exp-20260725-004"
ARTIFACT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
DEFAULT_WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"


def _load_ledger_module():
    script_path = REPO_ROOT / "scripts" / "run_options_forward_ledger.py"
    spec = importlib.util.spec_from_file_location(
        "run_options_forward_ledger_for_exp_20260725_004", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _latest_chain_asof() -> str:
    dated = sorted(
        path.stem.rsplit("_", 1)[-1]
        for path in DEFAULT_OPTIONS_DIR.glob("options_onclickmedia_chain_*.jsonl")
        if path.stem.rsplit("_", 1)[-1].isdigit()
    )
    if not dated:
        raise SystemExit("no local option chain files found")
    tag = dated[-1]
    return f"{tag[:4]}-{tag[4:6]}-{tag[6:]}"


def _chain_universe(as_of: str) -> list[str]:
    path = DEFAULT_OPTIONS_DIR / f"options_onclickmedia_chain_{as_of.replace('-', '')}.jsonl"
    tickers: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            if ticker and ticker not in NON_COMMON_STOCK_EXCLUSIONS:
                tickers.add(ticker)
    return sorted(tickers)


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    data_source = snapshot.get("data_source") or {}
    return {
        "asof_date": snapshot.get("asof_date"),
        "options_quality_status": data_source.get("options_quality_status"),
        "options_scoring_allowed": data_source.get("options_scoring_allowed"),
        "stage_counts": snapshot.get("stage_counts"),
        "candidate_count": snapshot.get("candidate_count"),
        "candidate_reject_counts": snapshot.get("candidate_reject_counts"),
        "error": snapshot.get("error"),
    }


def main() -> dict[str, Any]:
    as_of = _latest_chain_asof()
    universe = _chain_universe(as_of)
    flow_rows = load_moomoo_capital_flow_rows()
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        [*universe, "SPY", "QQQ"],
        "2025-06-01",
        as_of,
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    # BEFORE: reproduce yesterday's sleeve-time state — quality file without
    # the asof quote-date row (that row was only written after the sleeves).
    current_quality = json.loads(
        DEFAULT_OPTIONS_QUALITY_PATH.read_text(encoding="utf-8-sig")
    )
    stale_quality = json.loads(json.dumps(current_quality))
    (stale_quality.get("by_quote_date") or {}).pop(as_of, None)
    if as_of in (stale_quality.get("usable_quote_dates") or []):
        stale_quality["usable_quote_dates"].remove(as_of)
    stale_path = ARTIFACT_DIR / "stale_quality_gate_reproduction.json"
    stale_path.write_text(
        json.dumps(stale_quality, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    before = build_core_drawdown_flow_put_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=frames,
        flow_rows=flow_rows,
        candidate_universe=universe,
        state=empty_core_drawdown_flow_put_state(),
        options_quality_path=stale_path,
        persist=False,
    )

    # AFTER: rebuild the quality gate exactly as the new pre-sleeve hook does
    # (identical thresholds/writer), into an artifact dir, and rebuild.
    ledger = _load_ledger_module()
    refresh_summary = ledger.refresh_collection_quality_gate(
        chain_dir=DEFAULT_OPTIONS_DIR,
        output_dir=ARTIFACT_DIR / "refreshed_options_forward",
    )
    refreshed_path = (
        ARTIFACT_DIR / "refreshed_options_forward" / "options_collection_quality_gate.json"
    )

    after = build_core_drawdown_flow_put_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=frames,
        flow_rows=flow_rows,
        candidate_universe=universe,
        state=empty_core_drawdown_flow_put_state(),
        options_quality_path=refreshed_path,
        persist=False,
    )

    before_summary = _snapshot_summary(before)
    after_summary = _snapshot_summary(after)
    checks = {
        "before_reproduces_missing_quality_row": (
            before_summary["options_quality_status"] == "missing_quality_row"
            and before_summary["options_scoring_allowed"] is False
        ),
        "after_quality_usable_for_shadow": (
            after_summary["options_quality_status"] == "usable_for_shadow"
            and after_summary["options_scoring_allowed"] is True
        ),
        "after_options_complete_stage_nonzero": (
            (after_summary.get("stage_counts") or {}).get("options_complete", 0) > 0
        ),
        "no_state_persisted": True,  # persist=False on both builds
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "mode": "measurement_repair_before_after",
        "as_of": as_of,
        "universe_size": len(universe),
        "refresh_summary": refresh_summary,
        "before": before_summary,
        "after": after_summary,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "default_off_paper_only": True,
            "production_orders_changed": False,
        },
    }
    out_path = ARTIFACT_DIR / "before_after_quality_gate_ordering.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))

    if "--recover" in sys.argv[1:]:
        if not report["all_checks_passed"]:
            raise SystemExit("refusing to recover: before/after checks failed")
        recovered = build_core_drawdown_flow_put_snapshot(
            as_of=as_of,
            ohlcv_by_ticker=frames,
            flow_rows=flow_rows,
            candidate_universe=universe,
            persist=True,
        )
        recovery = {
            "experiment_id": EXPERIMENT_ID,
            "mode": "fault_recovery_rematerialize_lost_asof",
            "as_of": as_of,
            "snapshot": _snapshot_summary(recovered),
            "new_pending_count": recovered.get("new_pending_count"),
            "new_pending_entries": recovered.get("new_pending_entries"),
            "pending_count": recovered.get("pending_count"),
        }
        recovery_path = ARTIFACT_DIR / "recovered_asof_snapshot.json"
        recovery_path.write_text(
            json.dumps(recovery, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(recovery, indent=2, sort_keys=True))
        report["recovery"] = recovery
    return report


if __name__ == "__main__":
    main()
