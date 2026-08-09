"""exp-20260710-009: exit lifecycle outcome settlement daily wiring.

Measurement repair. Exit lifecycle shadow rows have become a plausible
exit-scoring and risk-allocation evidence surface, but the forward outcome
settlement path was still manual. This runner verifies the default-off daily
outcome ledger contract and records the measurement boundary without changing
strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-009"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "exit_lifecycle_outcome_settlement_daily_wiring"
RUNNER = f"quant/experiments/exp_20260710_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import experiment_registry as expreg  # noqa: E402
from exit_lifecycle_outcomes import (  # noqa: E402
    OUTCOME_RULE_VERSION,
    persist_exit_lifecycle_outcome_ledger,
)


DATA_DIR = REPO_ROOT / "data"
SOURCE_DIR = DATA_DIR / "exit_lifecycle"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
PROOF_DATA_DIR = OUT_DIR / "proof_data"
OUT_JSON = OUT_DIR / f"exp_20260710_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
RUN_PY = REPO_ROOT / "quant" / "run.py"
HELPER_PY = REPO_ROOT / "quant" / "exit_lifecycle_outcomes.py"
TEST_PY = REPO_ROOT / "quant" / "test_exit_lifecycle_outcomes.py"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Alpha blocker: exit lifecycle and advisory shadow rows cannot support "
    "future exit scoring, replacement-value gates, or risk allocation while "
    "forward outcome settlement remains trapped in one-off experiment scripts; "
    "wire a default-off daily outcome ledger without changing live exits, "
    "orders, ranking, sizing, or core signal generation."
)
ALPHA_HYPOTHESIS = (
    "Exit lifecycle rows may later support LLM exit scoring or risk allocation "
    "once automatically settled forward replacement-value evidence accumulates."
)
CHANGE_TYPE = "measurement_repair"
IMPLEMENTATION_MODE = "shared_default_off_outcome_ledger_daily_wiring"
MECHANISM_FAMILY = "exit_lifecycle_advisory_outcome"
TRIAL_FAMILY = "exit_lifecycle_outcome_settlement"
TRIAL_VARIANT_ID = "exit_lifecycle_daily_outcome_ledger_v1"
SINGLE_CAUSAL_VARIABLE = "exit_lifecycle_forward_outcome_settlement_daily_wiring_v1"
CAUSAL_COMPONENTS = [
    "exit_lifecycle_outcome_helper",
    "daily_run_py_snapshot_wiring",
    "outcome_contract_tests",
    "no_strategy_or_order_change",
]
ACCEPTANCE_RULE = (
    "Accepted measurement repair if the helper writes closed and pending "
    "default-off outcome snapshots, run.py exposes the summary after the "
    "existing exit lifecycle shadow log, current source rows retain entry_date "
    "and target_price, tests pass, and production impact flags show no strategy "
    "or live-order behavior changed."
)

CHANGED_FILES = [
    RUNNER,
    "quant/exit_lifecycle_outcomes.py",
    "quant/test_exit_lifecycle_outcomes.py",
    "quant/run.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_009_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/proof_data/exit_lifecycle/exit_lifecycle_20260702.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/proof_data/exit_lifecycle/outcome_ledgers/exit_lifecycle_outcomes_20260713.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/proof_data/exit_lifecycle/outcome_summaries/exit_lifecycle_outcome_summary_20260713.json",
    f"data/experiments/{EXPERIMENT_ID}/proof_data/exit_lifecycle/latest_outcome_summary.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\exit_lifecycle_outcomes.py quant\\test_exit_lifecycle_outcomes.py "
    "quant\\run.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_exit_lifecycle_outcomes.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    return value


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    write_text(path, text)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def install_registry_direct_writer() -> None:
    def _direct_write_text(text: str, path: str | Path) -> None:
        write_text(Path(path), text)

    expreg._atomic_write_text = _direct_write_text


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_row(ticker: str, event_type: str) -> dict[str, Any]:
    return {
        "rule_version": "exit_lifecycle_shadow_log_v1",
        "ticker": ticker,
        "as_of_date": "2026-07-02",
        "generated_at": "2026-07-02T23:00:00Z",
        "shares": 10,
        "avg_cost": 90.0,
        "market_value_usd": 1000.0,
        "unrealized_pnl_pct": 0.05,
        "daily_return_pct": 0.01,
        "breach_status": "OK",
        "trailing_stop_from_hwm": 95.0,
        "drawdown_from_hwm_pct": -0.03,
        "entry_date": "2026-06-01",
        "target_price": 120.0,
        "advisory_events": [{"event_type": event_type}],
        "has_advisory_event": event_type != "no_advisory_event",
        "read_only": True,
        "alters_orders": False,
        "trade_enabled": False,
    }


def bars(start: float) -> list[dict[str, Any]]:
    dates = [
        "2026-07-02",
        "2026-07-06",
        "2026-07-07",
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
        "2026-07-13",
    ]
    rows: list[dict[str, Any]] = []
    for index, day in enumerate(dates):
        price = start + index
        rows.append({"date": day, "open": price, "close": price + 0.5})
    return rows


def write_proof_source() -> Path:
    source_path = PROOF_DATA_DIR / "exit_lifecycle" / "exit_lifecycle_20260702.jsonl"
    rows = [
        source_row("AAA", "hard_stop_breach"),
        source_row("BBB", "no_advisory_event"),
    ]
    write_text(
        source_path,
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
    )
    return source_path


def run_proof_writer() -> dict[str, Any]:
    source_path = write_proof_source()
    summary = persist_exit_lifecycle_outcome_ledger(
        today="2026-07-13",
        data_dir=PROOF_DATA_DIR,
        ohlcv_by_ticker={
            "AAA": bars(100.0),
            "BBB": bars(50.0),
            "SPY": bars(400.0),
            "QQQ": bars(500.0),
        },
    )
    ledger_path = PROOF_DATA_DIR / "exit_lifecycle" / "outcome_ledgers" / "exit_lifecycle_outcomes_20260713.jsonl"
    outcome_rows = []
    if ledger_path.exists():
        outcome_rows = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return {
        "source_path": repo_rel(source_path),
        "summary": summary,
        "ledger_path": repo_rel(ledger_path),
        "ledger_row_count": len(outcome_rows),
        "closed_rows": sum(1 for row in outcome_rows if row.get("outcome_status") == "closed"),
        "entry_date_rows": sum(1 for row in outcome_rows if row.get("position_entry_date")),
        "target_price_rows": sum(1 for row in outcome_rows if row.get("target_price") is not None),
        "trade_enabled_rows": sum(1 for row in outcome_rows if row.get("trade_enabled") is True),
        "alters_order_rows": sum(1 for row in outcome_rows if row.get("alters_orders") is True),
    }


def current_source_stats() -> dict[str, Any]:
    files = sorted(SOURCE_DIR.glob("exit_lifecycle_*.jsonl")) if SOURCE_DIR.exists() else []
    rows = 0
    with_entry_date = 0
    with_target_price = 0
    with_market_value = 0
    malformed = 0
    latest_tag = None
    for path in files:
        tag = path.stem.replace("exit_lifecycle_", "", 1)
        latest_tag = max(latest_tag or tag, tag)
        with path.open(encoding="utf-8-sig", errors="replace") as handle:
            for raw in handle:
                text = raw.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                if not isinstance(row, dict):
                    malformed += 1
                    continue
                rows += 1
                if row.get("entry_date"):
                    with_entry_date += 1
                if row.get("target_price") is not None:
                    with_target_price += 1
                if row.get("market_value_usd") is not None:
                    with_market_value += 1
    return {
        "source_dir": repo_rel(SOURCE_DIR),
        "source_file_count": len(files),
        "source_row_count": rows,
        "latest_source_tag": latest_tag,
        "rows_with_entry_date": with_entry_date,
        "rows_with_target_price": with_target_price,
        "rows_with_market_value_usd": with_market_value,
        "malformed_rows": malformed,
        "entry_date_coverage": round(with_entry_date / rows, 4) if rows else None,
        "target_price_coverage": round(with_target_price / rows, 4) if rows else None,
    }


def run_py_wiring_checks() -> dict[str, Any]:
    text = RUN_PY.read_text(encoding="utf-8", errors="replace")
    checks = {
        "imports_helper": "from exit_lifecycle_outcomes import persist_exit_lifecycle_outcome_ledger" in text,
        "calls_helper": "persist_exit_lifecycle_outcome_ledger(today_iso)" in text,
        "exposes_summary": 'trend_signals_dict["exit_lifecycle_outcomes"]' in text,
        "keeps_trade_disabled": '"trade_enabled": False' in text,
    }
    return {
        "run_py": repo_rel(RUN_PY),
        "checks": checks,
        "passed": all(checks.values()),
    }


def build_payload() -> dict[str, Any]:
    proof = run_proof_writer()
    source_stats = current_source_stats()
    wiring = run_py_wiring_checks()
    proof_summary = proof["summary"]
    production_impact = proof_summary.get("production_impact") or {}
    failed = []
    if proof_summary.get("outcome_rule_version") != OUTCOME_RULE_VERSION:
        failed.append("outcome_rule_version_mismatch")
    if proof_summary.get("settled_count") != 2 or proof["closed_rows"] != 2:
        failed.append("proof_rows_not_closed")
    if proof["entry_date_rows"] != 2:
        failed.append("proof_entry_date_missing")
    if proof["target_price_rows"] != 2:
        failed.append("proof_target_price_missing")
    if proof["trade_enabled_rows"] or proof["alters_order_rows"]:
        failed.append("proof_rows_not_default_off")
    if not wiring["passed"]:
        failed.append("run_py_wiring_missing")
    if not source_stats["source_row_count"]:
        failed.append("current_source_rows_missing")
    if source_stats["rows_with_entry_date"] != source_stats["source_row_count"]:
        failed.append("current_entry_date_coverage_gap")
    if source_stats["rows_with_target_price"] != source_stats["source_row_count"]:
        failed.append("current_target_price_coverage_gap")
    for key in (
        "alters_signal_generation",
        "alters_candidate_ranking",
        "alters_sizing",
        "alters_exits",
        "alters_orders",
        "trade_enabled",
    ):
        if production_impact.get(key) is not False:
            failed.append(f"production_impact_{key}_not_false")
    accepted = not failed
    decision = (
        "accepted_measurement_repair_exit_lifecycle_outcome_settlement_daily_wired"
        if accepted
        else "blocked_exit_lifecycle_outcome_settlement_daily_wiring"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": [
            "exp-20260623-011",
            "exp-20260623-018",
            "exp-20260701-012",
            "exp-20260710-008",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_pipeline_wiring",
        "new_evidence_axis": (
            "Routine-materialization guard legal exit: wire the exit_lifecycle "
            "observer to daily outcome settlement so future materially new "
            "settled forward rows accumulate without manual experiment IDs."
        ),
        "proof_writer": proof,
        "current_source_stats": source_stats,
        "run_py_wiring_checks": wiring,
        "headline_metrics": {
            "proof_candidate_rows": proof_summary.get("candidate_outcome_rows"),
            "proof_settled_count": proof_summary.get("settled_count"),
            "proof_unsettled_count": proof_summary.get("unsettled_count"),
            "current_source_rows": source_stats["source_row_count"],
            "current_source_files": source_stats["source_file_count"],
            "entry_date_coverage": source_stats["entry_date_coverage"],
            "target_price_coverage": source_stats["target_price_coverage"],
            "failed_checks": failed,
            "strategy_behavior_delta": 0,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "note": "Measurement repair only; no before/after strategy replay.",
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields": [
                "entry_date",
                "target_price",
                "market_value_usd",
                "ticker",
                "as_of_date",
            ],
            "current_source_stats": source_stats,
            "entry_date_target_price_applicability": (
                "Required for future forward outcome attribution; current "
                "exit_lifecycle source rows retain both sentinel fields."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "note": "No buy/sell/filter/ranking behavior changed.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
            "failed_reasons": failed,
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_snapshot_exposed": True,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_sizing_exits_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The helper can now settle read-only exit lifecycle observations "
                "into fixed-horizon replacement-value rows and run.py exposes "
                "the latest summary after the existing shadow log. This repairs "
                "evidence accumulation, not strategy edge."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run exit lifecycle threshold, response-curve, LLM "
                "scoring, or replacement-value alpha experiments until the "
                "daily ledger has materially more newly settled rows versus "
                "exp-20260701-012, or a separate legal evidence axis exists."
            ),
            "new_evidence_required": (
                "A future alpha iteration needs automatically accumulated "
                "settled forward rows, a distinct gate shape, or a new data "
                "source; this measurement repair alone is not alpha evidence."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    metrics = payload["headline_metrics"]
    failed = ", ".join(metrics["failed_checks"]) or "none"
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Exit Lifecycle Outcome Settlement Daily Wiring",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Proof settled rows: `{metrics['proof_settled_count']}/{metrics['proof_candidate_rows']}`",
            f"- Current source rows: `{metrics['current_source_rows']}`",
            f"- Entry date coverage: `{metrics['entry_date_coverage']}`",
            f"- Target price coverage: `{metrics['target_price_coverage']}`",
            f"- Failed checks: `{failed}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    install_registry_direct_writer()
    atomic_write_json(OUT_JSON, payload)
    expreg.save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    expreg.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": "measurement_repair_exit_lifecycle_outcome_daily_wiring",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    atomic_write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
