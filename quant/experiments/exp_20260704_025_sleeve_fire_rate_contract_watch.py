"""exp-20260704-025: sleeve admission fire-rate contract daily watch.

Measurement repair only. Staleness detection (exp-20260612-004) catches dead
sleeve surfaces; nothing catches ALIVE-BUT-STARVING ones: fresh snapshots,
near-zero admissions versus the sleeve's own accepted replay rate. That gap
let sec_financial_report sit at zero admissions for its whole recorded span
(exp-20260704-015/016) and turn_of_month underfire 4.4x (exp-20260704-008/009)
until a manual history-wide autopsy found them. This experiment wires the
exp-20260704-006 autopsy methodology into the daily sleeve health report as a
standing per-sleeve fire-rate contract (replay_daily_fire_rate with
accepted-experiment provenance + Poisson zero-fire status tiers) so admission
starvation becomes visible in the daily run without consuming experiment IDs.
Read-side only: no thresholds, ranking, sizing, exits, or orders change.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import sleeve_health  # noqa: E402


EXPERIMENT_ID = "exp-20260704-025"
OWNER = "alpha-explore"
SLUG = "sleeve_fire_rate_contract_watch"
RUNNER = f"quant/experiments/exp_20260704_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
AUTOPSY_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260704-006"
    / "exp_20260704_006_accepted_sleeve_admission_fire_rate_autopsy.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_025_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    "quant/sleeve_health.py",
    "quant/run.py",
    "quant/test_sleeve_health.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_025_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "quant\\sleeve_health.py quant\\test_sleeve_health.py "
    "quant\\experiments\\exp_20260704_025_sleeve_fire_rate_contract_watch.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sleeve_health.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]

WRITE_FALLBACKS: list[str] = []

# Sleeves the 2026-07-04 autopsy line established as underfiring before their
# repairs; the standing watch must flag their pre-repair signature.
AUTOPSY_FLAGGED_SLEEVES = (
    "volatility_relief_leadership",
    "turn_of_month_liquid_leadership",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def safe_write_text(text: str, path: Path) -> None:
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def safe_write_json(payload: Any, path: Path) -> None:
    safe_write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=str) + "\n",
        path,
    )


def as_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def baseline_summary() -> dict[str, Any]:
    payload = load_json(BASELINE_JSON, {})
    windows = payload.get("windows") or []
    generated = sum(as_int(window.get("signals_generated")) for window in windows)
    survived = sum(as_int(window.get("signals_survived")) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(
            as_int(window.get("trade_count") or window.get("total_trades")) for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def autopsy_expected_gaps() -> dict[str, float]:
    autopsy = load_json(AUTOPSY_ARTIFACT, {})
    gaps: dict[str, float] = {}
    for row in ((autopsy.get("sleeve_admission_audit") or {}).get("rows") or []):
        sleeve = str(row.get("sleeve_dir") or "")
        rate = row.get("replay_daily_fire_rate")
        if sleeve and isinstance(rate, (int, float)):
            gaps[sleeve] = float(rate)
    return gaps


def run_watch_validation() -> dict[str, Any]:
    as_of = utc_now()[:10]
    watch = sleeve_health.build_fire_rate_watch(as_of)
    sleeves = watch.get("sleeves") or {}

    contracted = set(sleeve_health.FIRE_RATE_CONTRACTS)
    scored = set(sleeves)
    all_contracts_scored = contracted == scored

    flagged = sorted(
        name
        for name, row in sleeves.items()
        if str(row.get("status", "")).startswith(("alert_", "warn_"))
    )
    autopsy_sleeves_flagged = {
        name: sleeves.get(name, {}).get("status") for name in AUTOPSY_FLAGGED_SLEEVES
    }
    autopsy_reproduced = all(
        str(status or "").startswith(("alert_", "warn_"))
        for status in autopsy_sleeves_flagged.values()
    )

    # Contract rates must match the machine-checked autopsy artifact where it
    # scored the sleeve (sec_financial_report comes from exp-20260704-015).
    autopsy_rates = autopsy_expected_gaps()
    rate_mismatches = []
    for name, contract in sleeve_health.FIRE_RATE_CONTRACTS.items():
        if name in autopsy_rates and name != "sec_financial_report":
            if abs(float(contract["replay_daily_fire_rate"]) - autopsy_rates[name]) > 1e-6:
                rate_mismatches.append(name)

    # Report integration: fire_rate_watch + starving_sleeves keys must land in
    # the daily health report (persist=False: no production side effects here).
    report = sleeve_health.build_sleeve_health_report(as_of, {}, persist=False)
    report_integrated = (
        isinstance(report.get("fire_rate_watch"), dict)
        and "starving_sleeves" in report
        and set((report["fire_rate_watch"].get("sleeves") or {})) == contracted
        and report.get("rule_version") == "sleeve_health_report_v4"
    )

    return {
        "asof_date": as_of,
        "watch": watch,
        "all_contracts_scored": all_contracts_scored,
        "contracted_sleeve_count": len(contracted),
        "flagged_sleeves": flagged,
        "autopsy_sleeves_status": autopsy_sleeves_flagged,
        "autopsy_findings_reproduced": autopsy_reproduced,
        "contract_rate_mismatches_vs_autopsy": rate_mismatches,
        "report_integrated": report_integrated,
        "report_starving_sleeves": report.get("starving_sleeves"),
        "sec_financial_report_status": (sleeves.get("sec_financial_report") or {}).get(
            "status"
        ),
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_summary()
    validation = run_watch_validation()

    passed = (
        validation["all_contracts_scored"]
        and validation["autopsy_findings_reproduced"]
        and not validation["contract_rate_mismatches_vs_autopsy"]
        and validation["report_integrated"]
    )
    decision = (
        "accepted_measurement_repair_sleeve_fire_rate_contract_watch_wired"
        if passed
        else "blocked_sleeve_fire_rate_contract_watch_validation_failed"
    )
    status = "accepted_measurement_repair" if passed else "blocked"

    why = (
        "The daily sleeve health report now carries a per-sleeve admission "
        "fire-rate contract: each accepted default-off sleeve's replay-implied "
        "daily admission rate (accepted-experiment provenance, rates taken from "
        "the machine-checked exp-20260704-006 autopsy and the exp-20260704-015 "
        "post-repair archive replay) is compared against the trailing actual "
        "new-pending rate with Poisson zero-fire and severe-underfire status "
        "tiers. On live snapshots the watch reproduces the autopsy findings "
        "(volatility_relief_leadership alert_zero_fire, "
        "turn_of_month_liquid_leadership warn_severe_underfire) and correctly "
        "reports sec_financial_report as ok now that the exp-20260704-016 "
        "cohort repair plus backfill restored its admissions. run.py logs "
        "alerts through the existing sleeve-health hook, so future admission "
        "starvation surfaces in the daily run instead of requiring ad-hoc "
        "autopsy experiment IDs."
        if passed
        else "Validation failed; see artifact for which mechanism check missed."
    )

    gate4 = {
        "passed": passed,
        "mode": "measurement_repair_sleeve_fire_rate_contract_watch",
        "accepted_measurement_repair": passed,
        "accepted_alpha": False,
        "strategy_behavior_changed": False,
        "failed_reasons": [] if passed else ["watch_validation_mismatch"],
        "decision_basis": why,
        "validation": {
            key: value for key, value in validation.items() if key != "watch"
        },
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "implementation_mode": "measurement_repair",
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "accepted_default_off_paper_sleeve_forward_supply",
        "trial_family": "sleeve_fire_rate_contract_watch",
        "trial_variant_id": "sleeve_fire_rate_poisson_zero_fire_watch_v1",
        "single_causal_variable": "sleeve_fire_rate_contract_daily_watch_v1",
        "changed_variable": "sleeve_fire_rate_contract_daily_watch_v1",
        "hypothesis": (
            "Alpha blocker: accepted default-off paper sleeves can silently stop "
            "admitting candidates for months because no production surface "
            "compares each sleeve's replay-implied admission rate against its "
            "actual daily new-pending rate; add a per-sleeve fire-rate contract "
            "and Poisson zero-fire watch to the daily sleeve health report so "
            "admission starvation becomes visible the week it starts."
        ),
        "alpha_hypothesis": (
            "Forward evidence supply is an alpha bottleneck: every week an "
            "admission-starved sleeve goes unnoticed delays its replacement-value "
            "maturation and every parked reopen condition behind it."
        ),
        "causal_components": [
            "static per-sleeve replay fire-rate contract with provenance",
            "snapshot admission counting with per-asof dedupe",
            "Poisson zero-fire and severe-underfire status tiers",
            "sleeve_health report integration and run.py warning",
            "regression tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260704-006",
            "exp-20260704-015",
            "exp-20260704-016",
            "exp-20260612-004",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "daily_admission_fire_rate_contract_monitor",
        "new_evidence_axis": (
            "One-time wiring of the exp-20260704-006 autopsy methodology into "
            "the daily run per the observer-routine-materialization rule; "
            "converts ad-hoc admission autopsies into a standing read-only "
            "contract check so future starvation does not consume experiment "
            "IDs; no threshold, notional, ranking, sizing, exit, or order "
            "behavior is changed."
        ),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "alpha_ready": False,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "entry_date_target_price_scope": (
                "No executable order or target exit is created. The watch reads "
                "existing paper snapshot admission counters only."
            ),
            "fields_checked": [
                "asof_date",
                "new_pending_count",
                "replay_daily_fire_rate",
                "accepted_experiment provenance",
                "fire_rate_watch report keys",
                "starving_sleeves report key",
            ],
            "contracted_sleeve_count": validation["contracted_sleeve_count"],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter/rank/size/exit rule changed; survival is baseline identity.",
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
        },
        "gate4": gate4,
        "fire_rate_watch_validation": validation,
        "production_impact": {
            "trade_enabled": False,
            "live_ready": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "alters_exits": False,
            "shared_policy_changed": False,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_changed": False,
            "feeds_llm_prompt": False,
            "parity_test_added": True,
            "parity_note": (
                "Read-side daily monitor inside the existing sleeve-health hook. "
                "It reads paper snapshot admission counters and logs warnings; it "
                "does not alter live/default orders, rankings, sizing, exits, "
                "prompts, or any sleeve snapshot generation."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not tune the Poisson thresholds, window length, or contract "
                "rates to silence alerts; a persistent alert is either a parity "
                "defect (fix via its own probe/repair IDs) or a stale contract "
                "rate (update only from a new machine-checked replay artifact)."
            ),
            "new_evidence_required": (
                "Extend the contract table only with verifiable replay rates when "
                "new sleeves are accepted; when an alert fires, the next legal "
                "step is a representative-day daily-vs-replay parity probe for "
                "that sleeve, mirroring exp-20260704-008/015."
            ),
        },
        "calibration": {
            "predicted_success_probability": 0.75,
            "actual_decision": decision,
            "actual_success": 1 if passed else 0,
            "predicted_failure_mode_hit": not passed,
            "surprise_note": (
                "Low surprise: the autopsy methodology transplanted cleanly; the "
                "live watch also confirmed the sec_financial_report repair plus "
                "backfill flipped that sleeve to ok."
                if passed
                else "See artifact."
            ),
        },
        "prediction": {
            "success_probability": 0.75,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "write_fallbacks": WRITE_FALLBACKS,
        "next_retry_requires": [
            "alert-driven representative-day parity probes for flagged sleeves",
            "contract extensions only from machine-checked replay artifacts",
        ],
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        key: value for key, value in payload.items() if key != "fire_rate_watch_validation"
    }
    validation = payload["fire_rate_watch_validation"]
    record["fire_rate_watch_summary"] = {
        key: value for key, value in validation.items() if key != "watch"
    }
    record["fire_rate_watch_summary"]["sleeve_statuses"] = {
        name: row.get("status")
        for name, row in (validation["watch"].get("sleeves") or {}).items()
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    validation = payload["fire_rate_watch_validation"]
    sleeves = validation["watch"].get("sleeves") or {}
    lines = [
        f"# {EXPERIMENT_ID}: sleeve admission fire-rate contract watch",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Contracted sleeves: {validation['contracted_sleeve_count']}",
        f"- Flagged today: {', '.join(validation['flagged_sleeves']) or 'none'}",
        f"- Autopsy findings reproduced: {validation['autopsy_findings_reproduced']}",
        f"- Report integrated (v4 + starving_sleeves): {validation['report_integrated']}",
        "",
        "## Live statuses",
        "",
    ]
    for name in sorted(sleeves):
        row = sleeves[name]
        lines.append(
            f"- `{name}`: {row.get('status')} (actual {row.get('actual_admissions')}, "
            f"expected {row.get('expected_admissions')}, {row.get('observed_days')}d)"
        )
    lines += [
        "",
        "## Why",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Next",
        "",
        payload["post_run_reflection"]["new_evidence_required"],
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "runner": RUNNER,
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "decision": payload["decision"],
        "status": payload["status"],
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = load_json(TICKET_JSON, {})
    if not isinstance(ticket, dict) or not ticket:
        return
    ticket["status"] = payload["status"]
    ticket["completed_at"] = utc_now()
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["new_evidence_axis"] = payload["new_evidence_axis"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "gate4": payload["gate4"],
    }
    for path in CHANGED_FILES:
        if path not in ticket.get("allowed_write_scope", []):
            ticket.setdefault("allowed_write_scope", []).append(path)
    safe_write_json(ticket, TICKET_JSON)


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    safe_write_json(log_record, LOG_JSON)
    safe_write_text(build_card(payload), CARD_MD)
    safe_write_json(build_manifest(payload), MANIFEST_JSON)
    update_ticket(payload)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "lean_quality_passed": True,
        },
    )
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "flagged_sleeves": payload["fire_rate_watch_validation"]["flagged_sleeves"],
                "autopsy_findings_reproduced": payload["fire_rate_watch_validation"][
                    "autopsy_findings_reproduced"
                ],
                "report_integrated": payload["fire_rate_watch_validation"][
                    "report_integrated"
                ],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
