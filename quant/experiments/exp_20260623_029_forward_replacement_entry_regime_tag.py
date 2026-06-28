"""exp-20260623-029: entry-regime tags for forward replacement rows.

Measurement repair for regime-conditioned default-off alpha. The repair adds a
read-only PIT regime_chop_state tag to closed forward replacement rows so future
forward/live-pilot rows can validate state-conditioned sleeve/router policies.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import forward_replacement_value as frv  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-029"
LANE = "measurement_repair"
SLUG = "forward_replacement_entry_regime_tag"
RUNNER = f"quant/experiments/exp_20260623_029_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
ASOF_DATE = "2026-06-23"

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_ARTIFACT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260623_029_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: regime-conditioned default-off sleeve "
    "and router alpha is blocked because closed forward replacement rows do "
    "not carry entry-time PIT regime_chop_state fields."
)
CHANGED_VARIABLE = "forward_replacement_rows_entry_regime_chop_tag_v1"
PREDICTION = {
    "success_probability": 0.7,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "warehouse_spy_bars_missing",
        "regime_helper_insufficient_lookback",
        "dirty_state_write_conflict",
        "artifact_rebuild_mismatch",
    ],
    "confidence_reason": (
        "The shared regime_chop_state helper and forward replacement "
        "enrichment path already exist; the repair only adds read-only "
        "entry-date tags and tests idempotent artifact rebuild."
    ),
    "recorded_at": "2026-06-23T01:10:49+00:00",
}
CHANGED_FILES = [
    "quant/forward_replacement_value.py",
    "quant/test_forward_replacement_value.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260623_029_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    generated = sum(float(window.get("signals_generated") or 0.0) for window in windows)
    survived = sum(float(window.get("signals_survived") or 0.0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "aggregate_expected_value_score": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "total_trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "aggregate_signals_generated": int(generated),
        "aggregate_signals_survived": int(survived),
        "min_survival_rate": min(
            float(window.get("survival_rate") or 0.0) for window in windows
        )
        if windows
        else None,
        "max_window_drawdown_pct": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
    }


def fake_comparator_bars() -> dict[str, dict[str, dict[str, float]]]:
    return {
        "SPY": {
            "2026-05-05": {"open": 100.0, "close": 101.0},
            "2026-05-15": {"open": 102.0, "close": 104.0},
        },
        "QQQ": {
            "2026-05-05": {"open": 200.0, "close": 201.0},
            "2026-05-15": {"open": 208.0, "close": 210.0},
        },
    }


def fake_regime_bars() -> list[dict[str, Any]]:
    start = date(2025, 8, 1)
    rows = []
    for index in range(300):
        current = start + timedelta(days=index)
        close = 100.0 + index * 0.25
        rows.append({"Date": current.isoformat(), "Close": close, "High": close + 1.0})
    return rows


def fixture_closed_row() -> dict[str, Any]:
    return {
        "ticker": "GS",
        "decision_id": "EXP002:fixture:2026-05-05:GS",
        "entry_date": "2026-05-05",
        "exit_date": "2026-05-15",
        "pnl": 390.84,
        "net_return_pct": 3.908409,
        "entry_price": 909.73,
        "exit_price": 948.47,
    }


def run_temp_validation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ginger-exp-20260623-029-") as tmp_raw:
        tmp = Path(tmp_raw)
        root = tmp / "paper_sleeves"
        sleeve_dir = root / "demo_sleeve"
        sleeve_dir.mkdir(parents=True)
        state_path = sleeve_dir / "state.json"
        artifact_path = tmp / "forward_replacement_value.jsonl"
        write_json(state_path, {"closed_positions": [fixture_closed_row()]})

        summary = frv.enrich_all_sleeve_states(
            ASOF_DATE,
            sleeves_root=root,
            bars_by_ticker=fake_comparator_bars(),
            regime_spy_bars=fake_regime_bars(),
            artifact_path=artifact_path,
        )
        saved_state = read_json(state_path)
        artifact_rows = [
            json.loads(line)
            for line in artifact_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        second_summary = frv.enrich_all_sleeve_states(
            "2026-06-24",
            sleeves_root=root,
            bars_by_ticker=fake_comparator_bars(),
            regime_spy_bars=fake_regime_bars(),
            artifact_path=artifact_path,
        )

        row = saved_state["closed_positions"][0]
        artifact_row = artifact_rows[0] if artifact_rows else {}
        return {
            "summary": summary,
            "second_summary": second_summary,
            "state_row_has_entry_regime_tag": bool(row.get("entry_regime_tag_rule_version")),
            "artifact_row_has_entry_regime_tag": bool(
                artifact_row.get("entry_regime_tag_rule_version")
            ),
            "entry_regime_label": row.get("entry_regime_label"),
            "entry_regime_status": row.get("entry_regime_status"),
            "idempotent_second_run": second_summary.get("rows_enriched") == 0,
        }


def audit_current_forward_artifact() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if FORWARD_ARTIFACT.exists():
        for line in FORWARD_ARTIFACT.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return {
        "path": repo_rel(FORWARD_ARTIFACT),
        "rows": len(rows),
        "rows_with_entry_regime_tag": sum(
            1 for row in rows if row.get("entry_regime_tag_rule_version")
        ),
        "rows_by_sleeve": dict(
            sorted(Counter(str(row.get("sleeve_key") or "unknown") for row in rows).items())
        ),
        "rows_by_entry_regime_label": dict(
            sorted(
                Counter(
                    str(row.get("entry_regime_label") or "missing")
                    for row in rows
                ).items()
            )
        ),
    }


def build_result() -> dict[str, Any]:
    before = aggregate_metrics()
    after = dict(before)
    temp_validation = run_temp_validation()
    real_regime_bars = frv.load_regime_spy_bars()
    current_artifact = audit_current_forward_artifact()

    accepted = (
        temp_validation["state_row_has_entry_regime_tag"]
        and temp_validation["artifact_row_has_entry_regime_tag"]
        and temp_validation["idempotent_second_run"]
        and len(real_regime_bars) >= 150
    )
    decision = (
        "accepted_measurement_repair_forward_replacement_entry_regime_tag"
        if accepted
        else "blocked_forward_replacement_entry_regime_tag_incomplete"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "timestamp": utc_now(),
        "hypothesis": HYPOTHESIS,
        "change_type": "forward_replacement_value_regime_tag_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": "regime_router_measurement_repair",
        "trial_family": "default_off_forward_regime_tagging",
        "trial_variant_id": "forward_replacement_entry_regime_chop_tag_v1",
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": before,
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields_checked": [
                "entry_date",
                "replacement_value_*",
                "entry_regime_tag_rule_version",
                "entry_regime_label",
                "entry_regime_exposure_scalar",
            ],
            "real_spy_regime_bar_count": len(real_regime_bars),
            "temp_validation": temp_validation,
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "baseline_min_survival_rate": before["min_survival_rate"],
        },
        "gate4": {
            "passed": accepted,
            "strategy_replay_changed": False,
            "measurement_repair_only": True,
            "decision": decision,
        },
        "calibration": {
            **PREDICTION,
            "actual_success": 1 if accepted else 0,
            "actual_gate4_passed": accepted,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": []
            if accepted
            else [
                "warehouse_spy_bars_missing_or_insufficient",
                "temp_enrichment_validation_failed",
            ],
            "surprise_note": (
                "No surprise; the existing shared helpers supported the tag "
                "without changing strategy behavior."
                if accepted
                else "The measurement repair did not satisfy the preregistered tag checks."
            ),
        },
        "validation": {
            "temp_validation": temp_validation,
            "real_spy_regime_bar_count": len(real_regime_bars),
            "current_forward_artifact_audit": current_artifact,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_off_attribution_only": True,
            "live_ready": False,
            "parity_note": (
                "The shared forward replacement-value enrichment helper now "
                "records entry-time regime tags. It does not alter any paper "
                "or live decision surface."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repair succeeded because forward replacement-value "
                "enrichment already owns the closed-row observation surface "
                "and can compute entry-time regime from the existing shared "
                "regime_chop_state helper."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair as permission to tune regime constants, "
                "chop thresholds, exposure floors, source ranks, notional, hold, "
                "or cooldown on frozen windows."
            ),
            "new_evidence_required": (
                "Next alpha work needs closed forward replacement rows carrying "
                "these entry_regime fields, then a fixed regime-conditioned "
                "sleeve/router policy evaluated against replacement value and "
                "concentration guards."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": accepted,
    }


def write_card(result: dict[str, Any]) -> None:
    lines = [
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        f"- Status: `{result['status']}`",
        f"- Decision: `{result['decision']}`",
        f"- Lane: `{LANE}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "",
        "## Summary",
        "",
        HYPOTHESIS,
        "",
        "## Result",
        "",
        (
            "Accepted measurement repair. Forward replacement-value enrichment "
            "now writes read-only entry-regime tags for closed paper rows."
            if result["accepted"]
            else "Blocked. Entry-regime tag validation failed."
        ),
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py`",
    ]
    write_text(CARD_MD, "\n".join(lines) + "\n")


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "generated_at": result["timestamp"],
            "files": CHANGED_FILES,
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "ticket_file": repo_rel(TICKET_JSON),
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> None:
    result = build_result()
    write_json(OUT_JSON, result)
    write_json(LOG_JSON, result)
    write_card(result)
    write_manifest(result)
    upsert_jsonl(EXPERIMENT_LOG, result)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "decision": result["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "lean_quality_passed": result["lean_quality_passed"],
        },
        status=result["status"],
        fields={
            "owner": "codex-alpha-explore",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": [
                "exp-20260615-019",
                "exp-20260622-017",
                "exp-20260622-013",
                "exp-20260613-001",
            ],
            "new_evidence_type": "shared_forward_entry_regime_observation_field",
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "changed_files": CHANGED_FILES,
        },
    )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
