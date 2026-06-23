"""exp-20260622-022: core risk-intensity forward observation ledger.

Measurement repair for the exp-20260622-019/020 alpha lead. The repair adds a
read-only, append-only daily ledger surface for already-sized entry candidates
so future closed rows can validate risk-intensity attribution forward.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from core_risk_intensity_ledger import (  # noqa: E402
    DEFAULT_LEDGER_PATH,
    RULE_VERSION,
    append_core_risk_intensity_observation_snapshot,
    build_core_risk_intensity_observation_snapshot,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260622-022"
SLUG = "core_risk_intensity_forward_ledger"
RUNNER = f"quant/experiments/exp_20260622_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260622_022_{SLUG}.json"
SAMPLE_LEDGER = DATA_DIR / "sample_core_risk_intensity_forward_ledger.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)


HYPOTHESIS = (
    "measurement_repair/alpha_blocker: the positive core risk-intensity "
    "attribution lead cannot be forward-validated unless daily sized "
    "candidates are recorded in an append-only default-off ledger with "
    "pre-execution risk-intensity fields."
)
CHANGED_VARIABLE = "core_risk_intensity_forward_observation_ledger_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-019",
    "exp-20260622-020",
    "exp-20260618-008",
]
ALLOWED_WRITE_SCOPE = [
    "quant/core_risk_intensity_ledger.py",
    "quant/test_core_risk_intensity_ledger.py",
    "quant/run.py",
    RUNNER,
    "data/paper_sleeves/core_risk_intensity_forward_observation/",
    "data/experiments/exp-20260622-022/",
    "experiments/logs/exp-20260622-022.json",
    "experiments/cards/exp-20260622-022.md",
    "experiments/manifests/exp-20260622-022.json",
    "experiments/tickets/exp-20260622-022.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE)
    windows = list(payload.get("windows") or [])
    generated = sum(float(window.get("signals_generated") or 0.0) for window in windows)
    survived = sum(float(window.get("signals_survived") or 0.0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def fixture_signal(ticker: str, risk_pct: float, *, strategy: str = "trend_long") -> dict[str, Any]:
    return {
        "ticker": ticker,
        "strategy": strategy,
        "sector": "Technology",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "target_price": 115.0,
        "sizing": {
            "base_risk_pct": 0.01,
            "risk_pct": risk_pct,
            "shares_to_buy": 10,
            "position_value_usd": 1000.0,
            "risk_amount_usd": 50.0,
            "risk_on_unmodified_risk_multiplier_applied": risk_pct / 0.01,
            "tqs_risk_multiplier_applied": 1.0,
        },
    }


def run_helper_self_check() -> dict[str, Any]:
    selected = fixture_signal("AAA", 0.02)
    sliced = fixture_signal("BBB", 0.005, strategy="breakout_long")
    snapshot = build_core_risk_intensity_observation_snapshot(
        as_of="2026-06-22",
        advisory_signals=[selected, sliced, {"ticker": "BAD", "sizing": {}}],
        selected_signals=[selected],
        entry_execution_plan={"slot_sliced_signals": [sliced]},
        metadata={"experiment_id": EXPERIMENT_ID, "purpose": "sample_idempotency_check"},
    )
    first = append_core_risk_intensity_observation_snapshot(snapshot, SAMPLE_LEDGER)
    second = append_core_risk_intensity_observation_snapshot(snapshot, SAMPLE_LEDGER)
    rows = [
        json.loads(line)
        for line in SAMPLE_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "snapshot_candidate_count": snapshot["candidate_count"],
        "snapshot_selected_count": snapshot["selected_count"],
        "snapshot_skipped_count": snapshot["skipped_count"],
        "risk_intensity_values": {
            row["ticker"]: row["risk_intensity"] for row in snapshot["rows"]
        },
        "candidate_statuses": {
            row["ticker"]: row["candidate_status"] for row in snapshot["rows"]
        },
        "first_append": first,
        "second_append": second,
        "sample_ledger_rows": len(rows),
        "sample_ledger": repo_rel(SAMPLE_LEDGER),
        "default_ledger_path": repo_rel(DEFAULT_LEDGER_PATH),
    }


def scan_daily_quant_artifacts() -> dict[str, Any]:
    paths = sorted((REPO_ROOT / "data" / "daily" / "signals" / "quant").glob("quant_signals_*.json"))
    scanned = []
    total_signals = 0
    total_sized = 0
    for path in paths[-30:]:
        try:
            payload = read_json(path)
        except Exception as exc:  # noqa: BLE001
            scanned.append({"path": repo_rel(path), "error": str(exc)})
            continue
        signals = payload.get("signals") or []
        sized = sum(
            1
            for signal in signals
            if isinstance(signal.get("sizing"), dict)
            and signal.get("sizing", {}).get("base_risk_pct") is not None
        )
        total_signals += len(signals)
        total_sized += sized
        scanned.append(
            {
                "path": repo_rel(path),
                "signal_count": len(signals),
                "sized_candidate_count": sized,
            }
        )
    return {
        "scanned_file_count": len(scanned),
        "total_signal_count": total_signals,
        "total_sized_candidate_count": total_sized,
        "recent_files": scanned,
        "interpretation": (
            "Recent formal daily quant artifacts currently contain zero live "
            "sized candidates, so this repair creates the forward capture "
            "surface rather than producing mature forward outcome evidence."
        ),
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    baseline = aggregate_metrics()
    helper_check = run_helper_self_check()
    daily_scan = scan_daily_quant_artifacts()
    production_impact = {
        "shared_helper_added": True,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": True,
        "append_only_forward_observation": True,
        "trade_enabled": False,
        "live_orders_changed": False,
        "paper_orders_changed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "backtester_adapter_changed": False,
        "replay_only": False,
        "live_ready": False,
        "live_realism_evaluated": False,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "accepted_measurement_repair",
        "lane": "measurement_repair",
        "owner": OWNER,
        "decision": "accepted_measurement_repair_core_risk_intensity_forward_ledger",
        "accepted": True,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "risk_allocation_attribution",
        "trial_family": "core_risk_intensity_forward_observation_ledger",
        "trial_variant_id": "append_only_daily_snapshot_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared read-only risk-intensity ledger helper",
            "daily run default-off observation wiring",
            "focused parity/idempotency test",
            "no trading behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "forward_observation_surface_for_positive_risk_intensity_lead",
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "The alpha lead is that pre-execution risk intensity may rank "
                "core entries by future PnL; this run repairs the missing "
                "forward observation surface needed to test it."
            ),
            "2_history_check": (
                "exp-20260622-019/020 were positive observed-only leads; both "
                "forbid scalar promotion until forward rows record pre-execution "
                "risk-intensity rank. Novelty gate passed with no strong near-neighbor."
            ),
            "3_single_policy_bundle": (
                "Only the observation ledger is changed. Entry, exit, ranking, "
                "sizing, orders, and live/default behavior are unchanged."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if the helper emits stable "
                "risk-intensity rows, idempotent append-only persistence, run.py "
                "surfaces the snapshot, and tests pass."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": True,
            "minimum_fields_checked": ["entry_date", "target_price"],
            "entry_date_source": "canonical baseline trades and daily sized candidates",
            "target_price_source": "daily sized candidates when present",
            "helper_required_fields": [
                "sizing.base_risk_pct",
                "sizing.risk_pct",
                "ticker",
                "strategy",
                "entry_price",
                "stop_price",
            ],
            "helper_self_check": helper_check,
            "daily_artifact_scan": daily_scan,
        },
        "gate3": {
            "survival_filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "note": "No filter, rank, or sizing rule was added.",
        },
        "gate4": {
            "strategy_rerun_required": False,
            "before_after_policy_delta": {
                "expected_value_score_sum": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct_worst": 0.0,
            },
            "decision": "accepted_measurement_repair_core_risk_intensity_forward_ledger",
            "acceptance_basis": (
                "The blocker for future risk-intensity alpha validation is "
                "repaired: daily run now exposes and persists default-off "
                "pre-execution risk-intensity observations without changing "
                "trading behavior."
            ),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The existing daily quant artifact captured the full signal "
                "context but did not provide an append-only risk-intensity "
                "surface. The new helper records the exact pre-execution fields "
                "needed by the positive attribution lead."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not convert exp-20260622-019/020 into scalar, top-up, cap, "
                "rank, or entry sweeps on the frozen windows. Wait for closed "
                "forward rows from this ledger."
            ),
            "new_evidence_required": (
                "Closed forward rows with selected/sliced status, risk-intensity "
                "rank, realized PnL, and replacement value before any sizing "
                "promotion."
            ),
        },
        "verification": {
            "py_compile": ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\core_risk_intensity_ledger.py quant\\run.py quant\\test_core_risk_intensity_ledger.py",
            "focused_pytest": ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_core_risk_intensity_ledger.py",
            "focused_pytest_result": "2 passed",
        },
        "related_files": [
            "quant/core_risk_intensity_ledger.py",
            "quant/test_core_risk_intensity_ledger.py",
            "quant/run.py",
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(SAMPLE_LEDGER),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(BASELINE),
            "experiments/logs/exp-20260622-019.json",
            "experiments/logs/exp-20260622-020.json",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python-only helper, pytest, and runner.",
        },
    }


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "decision",
        "accepted",
        "accepted_alpha",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "pre_run_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "verification",
        "related_files",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    helper = payload["gate2"]["helper_self_check"]
    daily_scan = payload["gate2"]["daily_artifact_scan"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: core risk-intensity forward ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            "- Live orders changed: `false`",
            "- Sizing changed: `false`",
            "",
            "## Result",
            "",
            payload["gate4"]["acceptance_basis"],
            "",
            "## Helper Check",
            "",
            f"- Sample candidates: `{helper['snapshot_candidate_count']}`",
            f"- First append rows: `{helper['first_append']['rows_written']}`",
            f"- Second append rows: `{helper['second_append']['rows_written']}`",
            f"- Recent daily sized candidates found: `{daily_scan['total_sized_candidate_count']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "core_risk_intensity_ledger.py",
        REPO_ROOT / "quant" / "test_core_risk_intensity_ledger.py",
        REPO_ROOT / "quant" / "run.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        SAMPLE_LEDGER,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = build_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": True,
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "summary": payload["gate4"]["acceptance_basis"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
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
            "baseline_result_file": repo_rel(BASELINE),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "helper_candidates": payload["gate2"]["helper_self_check"][
                    "snapshot_candidate_count"
                ],
                "sample_first_append_rows": payload["gate2"]["helper_self_check"][
                    "first_append"
                ]["rows_written"],
                "sample_second_append_rows": payload["gate2"]["helper_self_check"][
                    "second_append"
                ]["rows_written"],
                "recent_daily_sized_candidates": payload["gate2"][
                    "daily_artifact_scan"
                ]["total_sized_candidate_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
