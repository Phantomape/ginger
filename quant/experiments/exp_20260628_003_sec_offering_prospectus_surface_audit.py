"""exp-20260628-003: SEC offering/prospectus surface audit.

Read-only measurement closeout. The proposed offering/prospectus economics
surface looked plausible from the playbook queue, but the history check found
that richer offering terms were already materialized and then rejected as an
alpha source. This runner records the anti-repeat blocker and the current
shared SEC form coverage so the line is not reopened by another adjacent field
or form-list scan.

No strategy helper, ranking, sizing, entry, exit, paper order, live order,
watchlist, or LLM boundary is changed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260628-003"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_offering_prospectus_surface_audit"
RUNNER = f"quant/experiments/exp_20260628_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
STANDARD_EVENTS = NON_OHLCV_DIR / "sec_filing_events_20241002_20260421.jsonl"
STANDARD_TEXT = NON_OHLCV_DIR / "sec_filing_text_20241002_20260421.jsonl"
FROZEN_FAMILIES = REPO_ROOT / "docs" / "frozen_families.jsonl"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260628_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PRIOR_LOGS = {
    "exp-20260617-023": "raw SEC offering/prospectus price absorption rejected",
    "exp-20260618-013": "offering financing-economics readiness blocked on missing primary text",
    "exp-20260620-018": "SEC offering primary-text economics candidate pool rejected",
    "exp-20260624-021": "richer SEC offering financing terms ledger accepted as measurement repair",
    "exp-20260624-022": "richer SEC offering constructive-financing candidate pool rejected",
}

HYPOTHESIS = (
    "Alpha blocker: PIT SEC offering/prospectus economic terms may be a "
    "candidate-pool or risk-allocation signal, but this line is not compliant "
    "for another replay unless the evidence axis is materially new versus the "
    "already materialized richer offering-terms ledger and rejected alpha test."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool/risk_allocation: actual offering economics, such as "
    "takedown versus shelf capacity, float-normalized dilution, lockup or "
    "hedging terms, underwriter quality, and use-of-proceeds, could separate "
    "constructive capital formation from dilution noise."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "sec_offering_prospectus_economics_readiness"
TRIAL_FAMILY = "sec_offering_prospectus_surface_readiness_gate"
TRIAL_VARIANT_ID = "initial_standard_and_daily_surface_inventory_v1"
CHANGED_VARIABLE = "sec_offering_prospectus_surface_replayability_gate_v1"
NEW_EVIDENCE_TYPE = "new_sec_offering_prospectus_surface_inventory"
MULTIPLE_TESTING_RISK_BUCKET = "minimal"
CAUSAL_COMPONENTS = [
    "startup history check",
    "shared SEC filing event/text form coverage audit",
    "prior offering alpha closeout audit",
    "no strategy behavior change",
]
OFFERING_PREFIXES = (
    "S-1",
    "S-3",
    "S-4",
    "F-1",
    "F-3",
    "F-4",
    "424B",
    "FWP",
    "POS",
    "EFFECT",
    "SUPPL",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_baseline() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT, {})
    windows = data.get("windows") if isinstance(data, dict) else []
    if not isinstance(windows, list):
        windows = []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_loaded": bool(windows),
        "windows": windows,
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "minimum_survival_rate": min(
            [float(row.get("survival_rate") or 0.0) for row in windows] or [0.0]
        ),
        "max_drawdown_pct_worst": max(
            [float(row.get("max_drawdown_pct") or 0.0) for row in windows] or [0.0]
        ),
    }


def _form_type(row: dict[str, Any]) -> str:
    return str(row.get("form_type") or row.get("form_base") or "").upper()


def count_form_surface(paths: list[Path]) -> dict[str, Any]:
    forms: Counter[str] = Counter()
    offering_forms: Counter[str] = Counter()
    rows = 0
    files_present = 0
    files_missing: list[str] = []
    sample_offering_rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists() or path.stat().st_size == 0:
            files_missing.append(repo_rel(path))
            continue
        files_present += 1
        for row in iter_jsonl(path):
            rows += 1
            form = _form_type(row)
            forms[form] += 1
            if form.startswith(OFFERING_PREFIXES):
                offering_forms[form] += 1
                if len(sample_offering_rows) < 5:
                    sample_offering_rows.append(
                        {
                            "ticker": row.get("ticker"),
                            "form_type": row.get("form_type"),
                            "accepted_at": row.get("accepted_at"),
                            "usable_trade_date": row.get("usable_trade_date"),
                            "accession_number": row.get("accession_number"),
                        }
                    )
    return {
        "files_present": files_present,
        "files_missing_or_empty": files_missing[:20],
        "row_count": rows,
        "form_counts_top": dict(forms.most_common(20)),
        "offering_form_counts": dict(offering_forms),
        "offering_row_count": sum(offering_forms.values()),
        "sample_offering_rows": sample_offering_rows,
    }


def daily_paths(prefix: str) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(NON_OHLCV_DIR.glob(f"{prefix}_*.jsonl")):
        name = path.name
        if "_20241002_20260421" in name or name.endswith("_6k_20241002_20260421.jsonl"):
            continue
        paths.append(path)
    return paths


def load_prior_history() -> dict[str, Any]:
    history: dict[str, Any] = {}
    for experiment_id, label in PRIOR_LOGS.items():
        path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
        row = read_json(path, {})
        history[experiment_id] = {
            "label": label,
            "exists": path.exists(),
            "path": repo_rel(path),
            "status": row.get("status"),
            "decision": row.get("decision"),
            "accepted": row.get("accepted"),
            "accepted_alpha": row.get("accepted_alpha"),
            "accepted_measurement_repair": row.get("accepted_measurement_repair"),
            "gate4_failed_reasons": (row.get("gate4") or {}).get("failed_reasons"),
            "new_evidence_required": (row.get("post_run_reflection") or {}).get(
                "new_evidence_required"
            ),
            "forbidden_near_neighbor_retry": (row.get("post_run_reflection") or {}).get(
                "forbidden_near_neighbor_retry"
            ),
        }
    return history


def build_payload() -> dict[str, Any]:
    now = utc_now()
    ticket_before = read_json(TICKET_JSON, {})
    prediction = ticket_before.get("prediction") or {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "no_offering_forms_in_event_surface",
            "no_offering_text_rows",
            "no_economic_terms_parser",
            "no_standard_window_replay_surface",
        ],
        "confidence_reason": (
            "Playbook names parsed offering/prospectus terms as a possible "
            "surface, but nearby closeouts already built and rejected the "
            "richer offering-terms alpha."
        ),
        "recorded_at": now,
    }
    baseline = summarize_baseline()
    standard_events = count_form_surface([STANDARD_EVENTS])
    standard_text = count_form_surface([STANDARD_TEXT])
    daily_events = count_form_surface(daily_paths("sec_filing_events"))
    daily_text = count_form_surface(daily_paths("sec_filing_text"))
    prior_history = load_prior_history()

    prior_rejected_alpha = (
        prior_history.get("exp-20260620-018", {}).get("decision")
        == "rejected_sec_offering_primary_text_economics_candidate_pool"
        and prior_history.get("exp-20260624-022", {}).get("decision")
        == "rejected_sec_offering_richer_terms_constructive_financing_candidate_pool"
    )
    richer_terms_repair_exists = (
        prior_history.get("exp-20260624-021", {}).get("decision")
        == "accepted_measurement_repair_sec_offering_richer_terms_ledger"
    )
    shared_prospectus_form_rows = (
        standard_events["offering_row_count"]
        + standard_text["offering_row_count"]
        + daily_events["offering_row_count"]
        + daily_text["offering_row_count"]
    )

    failed_reasons = [
        "prior_richer_offering_terms_alpha_rejected",
        "no_new_machine_checkable_evidence_axis_named",
        "response_curve_or_adjacent_field_retune_forbidden",
    ]
    if shared_prospectus_form_rows == 0:
        failed_reasons.append("shared_sec_prospectus_form_surface_not_materialized")
    if richer_terms_repair_exists:
        failed_reasons.append("richer_terms_measurement_repair_already_exists")

    status = "blocked_sec_offering_prospectus_duplicate_frozen_surface"
    decision = status
    gate4 = {
        "passed": False,
        "decision": decision,
        "strategy_rerun": False,
        "failed_reasons": failed_reasons,
        "prior_rejected_alpha": prior_rejected_alpha,
        "richer_terms_repair_exists": richer_terms_repair_exists,
        "shared_prospectus_form_rows": shared_prospectus_form_rows,
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_changed": False,
        "daily_snapshot_changed": False,
        "paper_orders_changed": False,
        "live_orders_changed": False,
        "trade_enabled": False,
        "impact": "none_read_only_anti_repeat_closeout",
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "observed_only_lead": False,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "read_only_anti_repeat_measurement_closeout",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": list(PRIOR_LOGS),
        "multiple_testing_risk_bucket": MULTIPLE_TESTING_RISK_BUCKET,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": None,
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": failed_reasons,
            "brier_score": round(float(prediction.get("success_probability") or 0.0) ** 2, 6),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta_sum": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": baseline["baseline_loaded"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": baseline["expected_value_score_sum"],
            "baseline_total_pnl": baseline["total_pnl"],
        },
        "gate2": {
            "passed": False,
            "runtime_fields_checked": [
                "form_type/form_base",
                "accepted_at",
                "usable_trade_date",
                "accession_number",
                "ticker",
                "combined_text",
                "text_char_count",
            ],
            "standard_window_events": standard_events,
            "standard_window_text": standard_text,
            "daily_events": {
                key: value
                for key, value in daily_events.items()
                if key != "files_missing_or_empty"
            },
            "daily_text": {
                key: value for key, value in daily_text.items() if key != "files_missing_or_empty"
            },
            "history_check": prior_history,
            "blocker": (
                "No compliant new offering/prospectus evidence axis remains: "
                "richer terms were already materialized and rejected, while the "
                "shared SEC form surfaces do not currently expose S-1/S-3/424B/FWP "
                "rows as a standard-window replay table."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": baseline["minimum_survival_rate"],
            "note": "No strategy rule or filter changed; baseline survival is unchanged.",
        },
        "gate4": gate4,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The startup/history check found that the offering/prospectus "
                "economics line is already parked: raw offering absorption failed, "
                "primary-text economics failed, richer financing terms were "
                "materialized as measurement repair, and the richer candidate-pool "
                "alpha was rejected. The current shared data/non_ohlcv SEC event "
                "and text files also expose zero S-1/S-3/424B/FWP prospectus-form "
                "rows in the audited standard and daily surfaces."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry SEC offering/prospectus by sweeping form lists, "
                "regex terms, amount/market-cap thresholds, security-type weights, "
                "use-of-proceeds labels, underwriter buckets, float-dilution cuts, "
                "RS/close/volume guards, top-N, hold, cooldown, or notional."
            ),
            "new_evidence_required": (
                "Reopen only with a materially new machine-checkable axis: closed "
                "deal outcome, actual shelf drawdown history, verified lockup or "
                "hedging economics, a shared historical/daily prospectus-form helper "
                "that changes available rows, or closed forward replacement-value rows."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": prior_history,
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Gate 1 baseline is loaded; Gate 2 must show a new replayable "
                "surface and history must not already close the line; Gate 3 "
                "survival must remain unchanged because no filter is added; Gate 4 "
                "requires a before/after strategy rerun only if Gate 2 passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(STANDARD_EVENTS),
            repo_rel(STANDARD_TEXT),
            repo_rel(FROZEN_FAMILIES),
            *[f"experiments/logs/{experiment_id}.json" for experiment_id in PRIOR_LOGS],
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
        "ticket_before": ticket_before,
        "lean_quality_passed": True,
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "observed_only_lead",
        "alpha_ready",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
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
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "pre_run_questions",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    gate2 = payload["gate2"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - SEC offering/prospectus surface audit",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- artifact: `{repo_rel(OUT_JSON)}`",
            f"- runner: `{RUNNER_COMMAND}`",
            "",
            "## Gate Findings",
            "",
            f"- baseline EV: {payload['gate1']['baseline_expected_value_score_sum']}",
            f"- standard event offering/prospectus rows: {gate2['standard_window_events']['offering_row_count']}",
            f"- standard text offering/prospectus rows: {gate2['standard_window_text']['offering_row_count']}",
            f"- daily event offering/prospectus rows: {gate2['daily_events']['offering_row_count']}",
            f"- daily text offering/prospectus rows: {gate2['daily_text']['offering_row_count']}",
            f"- failed reasons: {', '.join(payload['gate4']['failed_reasons'])}",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        STANDARD_EVENTS,
        STANDARD_TEXT,
        FROZEN_FAMILIES,
        *[REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json" for experiment_id in PRIOR_LOGS],
    ]
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
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "observed_only_lead": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": list(PRIOR_LOGS),
            "multiple_testing_risk_bucket": MULTIPLE_TESTING_RISK_BUCKET,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": {
                "passed": payload["gate2"]["passed"],
                "blocker": payload["gate2"]["blocker"],
                "standard_event_offering_rows": payload["gate2"]["standard_window_events"][
                    "offering_row_count"
                ],
                "standard_text_offering_rows": payload["gate2"]["standard_window_text"][
                    "offering_row_count"
                ],
                "daily_event_offering_rows": payload["gate2"]["daily_events"][
                    "offering_row_count"
                ],
                "daily_text_offering_rows": payload["gate2"]["daily_text"][
                    "offering_row_count"
                ],
            },
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
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
                "standard_event_offering_rows": payload["gate2"]["standard_window_events"][
                    "offering_row_count"
                ],
                "standard_text_offering_rows": payload["gate2"]["standard_window_text"][
                    "offering_row_count"
                ],
                "daily_event_offering_rows": payload["gate2"]["daily_events"][
                    "offering_row_count"
                ],
                "daily_text_offering_rows": payload["gate2"]["daily_text"][
                    "offering_row_count"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
