"""exp-20260508-012 SEC 10-K liquidity forward watch adapter.

Observe-only adapter for the exp-20260503-011 / exp-20260508-011 next step:
accumulate PIT-safe, liquidity-gated 10-K candidates before any universe or
production strategy promotion.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from sec_10k_forward_watch import (  # noqa: E402
    build_sec_10k_forward_watch,
    persist_sec_10k_forward_watch,
)


EXPERIMENT_ID = "exp-20260508-012"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUDIT_JSON = OUT_DIR / "sec_10k_forward_watch_adapter_audit.json"
LEDGER_JSONL = OUT_DIR / "sec_10k_liquidity_forward_watch.jsonl"
SUMMARY_JSON = OUT_DIR / "sec_10k_liquidity_forward_watch_summary.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OHLCV_SNAPSHOT = REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260501_with_pilot.json"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _load_ohlcv_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = _load_json(path)
    return payload.get("ohlcv") or {}


def _date_tag(path: Path) -> str:
    match = re.search(r"(\d{8})", path.name)
    if not match:
        return "unknown"
    tag = match.group(1)
    return f"{tag[:4]}-{tag[4:6]}-{tag[6:8]}"


def _load_current_universe(as_of: str) -> set[str]:
    tag = as_of.replace("-", "")
    state_dir = REPO_ROOT / "data"
    exact = state_dir / f"universe_state_{tag}.json"
    paths = [exact] if exact.exists() else []
    if not paths:
        candidates = sorted(state_dir.glob("universe_state_*.json"))
        paths = [
            path for path in candidates
            if path.stem.replace("universe_state_", "") <= tag
        ]
    if not paths:
        return set()
    state = _load_json(paths[-1])
    tickers = set(state.get("core_trade_universe") or [])
    tickers.update(state.get("pilot_trade_universe") or [])
    tickers.update(state.get("governance_tradeable_universe") or [])
    return {str(ticker).upper() for ticker in tickers}


def _load_daily_quant_context(as_of: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tag = as_of.replace("-", "")
    path = REPO_ROOT / "data" / f"quant_signals_{tag}.json"
    if not path.exists():
        return [], {}
    payload = _load_json(path)
    signals = payload.get("signals") or []
    if not isinstance(signals, list):
        signals = []
    plan = payload.get("entry_execution_plan") or {}
    if not isinstance(plan, dict):
        plan = {}
    return signals, plan


def _sec_event_files() -> list[Path]:
    return sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_events_202605*.jsonl"))


def _compact_snapshot(snapshot: dict[str, Any], source_path: Path) -> dict[str, Any]:
    return {
        "asof_date": snapshot.get("asof_date"),
        "source_path": str(source_path),
        "sec_event_count": snapshot.get("sec_event_count", 0),
        "ten_k_event_count": snapshot.get("ten_k_event_count", 0),
        "pit_safe_10k_count": snapshot.get("pit_safe_10k_count", 0),
        "outside_universe_10k_count": snapshot.get("outside_universe_10k_count", 0),
        "ohlcv_covered_10k_count": snapshot.get("ohlcv_covered_10k_count", 0),
        "liquidity_qualified_count": snapshot.get("liquidity_qualified_count", 0),
        "candidate_count": snapshot.get("candidate_count", 0),
        "summary": snapshot.get("summary") or {},
        "candidates": snapshot.get("candidates") or [],
        "all_10k_rows": snapshot.get("all_10k_rows") or [],
    }


def main() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ohlcv_by_ticker = _load_ohlcv_snapshot(OHLCV_SNAPSHOT)
    snapshots = []
    status_counter: Counter[str] = Counter()
    bucket_counter: Counter[str] = Counter()
    for source_path in _sec_event_files():
        as_of = _date_tag(source_path)
        signals, entry_plan = _load_daily_quant_context(as_of)
        snapshot = build_sec_10k_forward_watch(
            as_of=as_of,
            source_path=source_path,
            ohlcv_by_ticker=ohlcv_by_ticker,
            current_universe=_load_current_universe(as_of),
            core_signals=signals,
            entry_execution_plan=entry_plan,
        )
        persisted = persist_sec_10k_forward_watch(
            snapshot,
            ledger_path=LEDGER_JSONL,
            summary_path=SUMMARY_JSON,
        )
        compact = _compact_snapshot(persisted, source_path)
        snapshots.append(compact)
        _write_json(OUT_DIR / f"snapshot_{as_of.replace('-', '')}.json", compact)
        status_counter.update((snapshot.get("summary") or {}).get("by_status") or {})
        bucket_counter.update((snapshot.get("summary") or {}).get("by_liquidity_bucket") or {})

    aggregate = {
        "source_file_count": len(snapshots),
        "sec_event_count": sum(row["sec_event_count"] for row in snapshots),
        "ten_k_event_count": sum(row["ten_k_event_count"] for row in snapshots),
        "pit_safe_10k_count": sum(row["pit_safe_10k_count"] for row in snapshots),
        "outside_universe_10k_count": sum(row["outside_universe_10k_count"] for row in snapshots),
        "ohlcv_covered_10k_count": sum(row["ohlcv_covered_10k_count"] for row in snapshots),
        "liquidity_qualified_count": sum(row["liquidity_qualified_count"] for row in snapshots),
        "candidate_count": sum(row["candidate_count"] for row in snapshots),
        "by_status": dict(sorted(status_counter.items())),
        "by_liquidity_bucket": dict(sorted(bucket_counter.items())),
    }
    persistence = _load_json(SUMMARY_JSON) if SUMMARY_JSON.exists() else {}
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "completed",
        "decision": "observe_only_forward_adapter_added",
        "lane": "measurement_repair_for_alpha_search",
        "hypothesis": (
            "Liquidity-gated 10-K filings outside the current production universe may improve "
            "future candidate-pool quality, but only after an append-only PIT ledger proves "
            "closed forward replacement value."
        ),
        "single_causal_variable": "append_only_pit_10k_liquidity_forward_watch",
        "alpha_hypothesis_category": "candidate_pool / event_quality",
        "history_check": {
            "exp-20260503-011": (
                "Historical 10-K + ADV>=5M shadow scout found positive old/late evidence but "
                "explicitly blocked promotion until PIT eligibility and replacement value exist."
            ),
            "exp-20260508-011": (
                "Direction triage selected 10-K liquidity scouts as best next alpha direction, "
                "with forward ledger and frozen same-day A/B alternatives required first."
            ),
            "guardrail": (
                "This is not broad SEC filing promotion, static universe expansion, or same-sample "
                "threshold tuning; it only creates the forward evidence container."
            ),
        },
        "parameters": {
            "forms": ["10-K"],
            "min_avg_dollar_volume_20d": 5_000_000,
            "adv_lookback_days": 20,
            "min_adv_observations": 20,
            "include_current_universe": False,
            "ohlcv_snapshot": str(OHLCV_SNAPSHOT),
            "source_glob": "data/non_ohlcv/sec_filing_events_202605*.jsonl",
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "exits",
                "core universe",
                "pilot universe",
                "orders",
            ],
        },
        "aggregate": aggregate,
        "snapshots": snapshots,
        "persistence": persistence,
        "gate4": {
            "passed": None,
            "basis": "No strategy rule changed; this is an observe-only forward ledger adapter.",
        },
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "report_adapter_changed": True,
            "parity_test_added": False,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "next_action": (
            "Let the daily ledger accumulate outside-universe eligible 10-K rows; compute 5/10/20d "
            "forward excess and replacement value only after enough candidates close across at least "
            "two regimes."
        ),
        "related_files": [
            str(AUDIT_JSON),
            str(LEDGER_JSONL),
            str(SUMMARY_JSON),
            str(LOG_JSON),
            "quant/sec_10k_forward_watch.py",
            "quant/test_sec_10k_forward_watch.py",
            "quant/run.py",
            "quant/report_generator.py",
        ],
    }
    _write_json(AUDIT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _append_jsonl(EXPERIMENT_LOG, payload)
    return payload


if __name__ == "__main__":
    result = main()
    print(json.dumps({
        "experiment_id": result["experiment_id"],
        "decision": result["decision"],
        "aggregate": result["aggregate"],
        "audit": str(AUDIT_JSON),
    }, indent=2, sort_keys=True))
