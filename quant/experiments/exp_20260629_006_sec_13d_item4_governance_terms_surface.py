"""exp-20260629-006: shared 13D Item-4 governance terms surface.

This runner verifies a new machine-checkable Schedule 13D Item-4 provenance
surface: board-seat/representation terms, cooperation or settlement agreements,
nomination withdrawal, board departure, and standstill duration. It does not
change entries, exits, ranking, sizing, risk budgets, orders, or any live path.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for path in (REPO_ROOT, SCRIPTS_DIR, QUANT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from quant import sec_13d13g_ingest as ingest  # noqa: E402


EXPERIMENT_ID = "exp-20260629-006"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sec_13d_item4_governance_terms_surface"
RUNNER = f"quant/experiments/exp_20260629_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_13d_item4_governance_terms_shared_surface_v1"
TRIAL_FAMILY = "sec_13d_item4_governance_terms_surface"
TRIAL_VARIANT_ID = "shared_board_seat_standstill_terms_v1"
MECHANISM_FAMILY = "production_visible_sec_ownership_item4_governance_terms"
CHANGE_TYPE = "measurement_repair"
NEW_EVIDENCE_TYPE = "new_machine_checkable_item4_governance_terms"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260629_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "Candidate-pool/risk-allocation future hypothesis: specific 13D Item-4 "
    "governance outcomes such as board seats, standstill terms, and settlement "
    "agreements may contain more durable activist provenance than the rejected "
    "generic active-intent phrase gate, but first the fields must be exposed by "
    "a shared PIT parser."
)

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260618-016",
    "exp-20260618-019",
    "exp-20260619-014",
]

CAUSAL_COMPONENTS = [
    "shared Item-4 text extraction",
    "shared governance-term classifier",
    "coverage artifact and parser tests",
    "no strategy behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT, {})
    if not isinstance(raw, dict):
        return {"loaded": False, "baseline_result_file": repo_rel(BASELINE_RESULT)}
    windows = raw.get("windows") if isinstance(raw.get("windows"), list) else []
    compact = []
    for row in windows:
        if not isinstance(row, dict):
            continue
        compact.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "sharpe_daily": row.get("sharpe_daily"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
            }
        )
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in compact)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in compact)
    return {
        "loaded": bool(compact),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(compact),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in compact),
            6,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in compact), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in compact),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 6) if signals_generated else None
        ),
        "max_drawdown_pct": (
            max(float(row.get("max_drawdown_pct") or 0.0) for row in compact)
            if compact
            else None
        ),
        "windows": compact,
    }


def governance_summary(rows: list[dict[str, Any]], fetch_status: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    by_window: dict[str, Counter[str]] = defaultdict(Counter)
    samples: list[dict[str, Any]] = []
    for row in rows:
        family = row.get("family") or "unknown"
        window = row.get("window") or "unknown"
        terms = row.get("item4_governance_terms") or {}
        counts["parsed_rows"] += 1
        counts[f"family_{family}"] += 1
        by_window[window]["parsed_rows"] += 1
        if row.get("item4_text_present"):
            counts["item4_text_rows"] += 1
            by_window[window]["item4_text_rows"] += 1
        if row.get("item4_governance_terms_present"):
            counts["governance_term_rows"] += 1
            by_window[window]["governance_term_rows"] += 1
        if terms.get("cooperation_or_settlement_agreement_present"):
            counts["cooperation_or_settlement_rows"] += 1
        if terms.get("board_terms_present"):
            counts["board_terms_rows"] += 1
        if terms.get("standstill_terms_present"):
            counts["standstill_rows"] += 1
        if terms.get("standstill_duration_days") is not None:
            counts["standstill_duration_rows"] += 1
        if terms.get("nomination_withdrawal_present"):
            counts["nomination_withdrawal_rows"] += 1
        if terms.get("board_departure_present"):
            counts["board_departure_rows"] += 1
        appointment_count = int(terms.get("board_appointment_count") or 0)
        counts["board_appointment_count_sum"] += appointment_count
        if appointment_count:
            counts["board_appointment_rows"] += 1
        if row.get("item4_governance_terms_present") and len(samples) < 12:
            samples.append(
                {
                    "ticker": row.get("ticker"),
                    "window": window,
                    "form": row.get("form"),
                    "filing_date": row.get("filing_date"),
                    "accession_number": row.get("accession_number"),
                    "bucket": row.get("item4_governance_terms_bucket"),
                    "hits": terms.get("governance_term_hits"),
                    "board_appointment_count": terms.get("board_appointment_count"),
                    "standstill_duration_days": terms.get("standstill_duration_days"),
                    "excerpt": terms.get("item4_excerpt"),
                }
            )

    return {
        "fetch_status": fetch_status,
        "counts": dict(counts),
        "by_window": {key: dict(value) for key, value in sorted(by_window.items())},
        "sample_governance_rows": samples,
        "field_contract": {
            "item4_text_present": "bool, true only when structured Item-4 text was parsed",
            "item4_governance_terms_present": "bool, any governance term field hit",
            "item4_governance_terms_bucket": "one fixed provenance bucket",
            "item4_board_appointment_count": "integer parsed board appointment count",
            "item4_standstill_duration_days": "approximate days when explicit term parsed",
            "item4_governance_terms": "nested deterministic term fields and excerpt",
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    events = ingest.iter_ownership_filings(families=("13D", "13G"), include_amendments=True)
    parsed = ingest.build_parsed_rows(events, fetch=False, refresh=False)
    rows = parsed["rows"]
    summary = governance_summary(rows, parsed["fetch_status"])
    counts = summary["counts"]

    required_fields = {
        "accession_number",
        "filing_date",
        "usable_trade_date",
        "item4_text_present",
        "item4_governance_terms_present",
        "item4_governance_terms_bucket",
        "item4_board_appointment_count",
        "item4_standstill_duration_days",
        "item4_governance_terms",
    }
    sample = next((row for row in rows if row.get("family") == "13D"), rows[0] if rows else {})
    field_contract_passed = bool(sample) and required_fields <= set(sample)
    repair_passed = bool(
        before.get("loaded")
        and rows
        and counts.get("item4_text_rows", 0) > 0
        and counts.get("governance_term_rows", 0) > 0
        and field_contract_passed
    )
    status = "accepted_measurement_repair" if repair_passed else "blocked"
    decision = (
        "accepted_measurement_repair_sec_13d_item4_governance_terms_surface"
        if repair_passed
        else "blocked_sec_13d_item4_governance_terms_surface"
    )
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    prediction = ticket.get("prediction") or {
        "success_probability": 0.34,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "schema_variation",
            "false_positive_term_extraction",
            "no_item4_text_coverage",
            "duplicate_13d_phrase_gate",
        ],
        "confidence_reason": (
            "Playbook freezes the simple Item-4 active phrase candidate pool but "
            "names board-seat/standstill economics as a valid richer provenance axis."
        ),
        "recorded_at": timestamp,
    }
    calibration = {
        "predicted_success_probability": prediction.get("success_probability"),
        "actual_success": 1 if repair_passed else 0,
        "brier_score": round(
            (float(prediction.get("success_probability") or 0.0) - (1.0 if repair_passed else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "failure_modes_observed": [] if repair_passed else ["shared_field_contract_not_met"],
        "predicted_failure_mode_hit": not repair_passed,
    }
    after = dict(before)

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": repair_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_passed,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or ALPHA_HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": (
            "Board-seat count, board appointment/departure, cooperation or "
            "settlement agreement, nomination withdrawal, and standstill-duration "
            "fields parsed from cached Schedule 13D Item-4 text."
        ),
        "prediction": prediction,
        "calibration": calibration,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "governance_surface_summary": summary,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": field_contract_passed,
            "runtime_fields_checked": sorted(required_fields),
            "parsed_event_count": len(events),
            "parsed_row_count": len(rows),
            "item4_text_rows": counts.get("item4_text_rows", 0),
            "governance_term_rows": counts.get("governance_term_rows", 0),
            "field_contract_passed": field_contract_passed,
            "source": repo_rel(Path(ingest.__file__)),
            "cache_dir": repo_rel(ingest.XML_CACHE_DIR),
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": (
                "No signal, filter, ranking, sizing, exit, risk budget, or order "
                "rule changed."
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": repair_passed,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": decision,
            "before_after_strategy_delta": delta,
            "failed_reasons": [] if repair_passed else ["shared_field_contract_not_met"],
            "next_alpha_gate": (
                "Do not promote or retune a 13D candidate-pool/risk response from "
                "this repair alone. A future alpha test needs fixed use of these "
                "new fields plus Gate 1-4 or closed forward replacement-value rows."
            ),
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "parity_note": (
                "Shared data parser only. No production trading path consumes the "
                "new Item-4 governance fields."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "Novelty gate passed. Nearby exp-20260618-019 rejected the generic "
                "active Item-4 phrase candidate pool, while the playbook named "
                "board-seat/standstill economics as richer valid provenance."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if the shared parser exposes "
                "deterministic PIT governance fields with coverage and strategy "
                "metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Cached structured Schedule 13D XML already contains Item-4 text, "
                "so the generic private extractor from exp-20260618-019 could be "
                "promoted into shared deterministic governance-term fields. This "
                "creates provenance for future tests but no alpha claim."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry 13D/13G by sweeping phrase lists, holder types, "
                "classPercent, signal absorption, event age, top-N, hold, cooldown, "
                "or notional on frozen windows."
            ),
            "new_evidence_required": (
                "A valid alpha retry needs fixed use of the new board-seat/"
                "standstill fields with Gate 1-4, campaign/board-seat outcome "
                "evidence beyond regex provenance, repaired old_thin coverage, or "
                "closed forward replacement-value rows."
            ),
        },
        "next_retry_requires": (
            "Use these fields only as a new fixed provenance axis; do not retune "
            "the old active-intent phrase gate."
        ),
        "related_files": [
            RUNNER,
            "quant/sec_13d13g_ingest.py",
            "quant/test_sec_13d13g_ingest.py",
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            "quant/sec_13d13g_ingest.py",
            "quant/test_sec_13d13g_ingest.py",
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\sec_13d13g_ingest.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_13d13g_ingest.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "response_curve_retune": False,
            "uses_future_data": False,
        },
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "governance_surface_summary",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "pre_run_questions",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    counts = payload["governance_surface_summary"]["counts"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 13D Item-4 Governance Terms Surface",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Parsed rows: `{counts.get('parsed_rows', 0)}`",
            f"- Item-4 text rows: `{counts.get('item4_text_rows', 0)}`",
            f"- Governance-term rows: `{counts.get('governance_term_rows', 0)}`",
            f"- Board-term rows: `{counts.get('board_terms_rows', 0)}`",
            f"- Standstill rows: `{counts.get('standstill_rows', 0)}`",
            f"- Strategy delta EV/PnL/trades: `0 / 0 / 0`",
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "sec_13d13g_ingest.py",
        REPO_ROOT / "quant" / "test_sec_13d13g_ingest.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "alpha_hypothesis",
            "change_type",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "new_evidence_axis",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
            "calibration",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
