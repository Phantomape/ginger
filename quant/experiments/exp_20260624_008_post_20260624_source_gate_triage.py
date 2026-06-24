"""exp-20260624-008: post-20260624 source gate triage.

Read-only alpha-search triage. This records why the next candidate alpha should
not force another replay when the currently tempting sources are blocked by
source saturation or missing PIT coverage. It changes no strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
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


EXPERIMENT_ID = "exp-20260624-008"
OWNER = "alpha-explore"
SLUG = "post_20260624_source_gate_triage"
RUNNER = f"quant/experiments/exp_20260624_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FROZEN_FAMILIES = REPO_ROOT / "docs" / "frozen_families.jsonl"
MOOMOO_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow" / "manifest.json"
MOOMOO_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "moomoo_capital_flow" / "rows.jsonl"
SEC_13D13G_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_13d13g_holdings" / "rows.json"
FORWARD_REPLACEMENT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"

RECENT_LOGS = {
    "exp-20260624-007": "current alpha surface readiness",
    "exp-20260623-024": "Form4 plus SEC confluence observed-only lead",
    "exp-20260623-025": "Form4 plus SEC confluence shared adapter screen",
    "exp-20260621-017": "Moomoo capital-flow readiness",
    "exp-20260623-008": "broad daily short-volume attribution",
}

HYPOTHESIS = (
    "Gate-driven alpha triage: after exp-20260624-007, the next compliant alpha "
    "should only proceed if novelty/source-saturation gates and local PIT "
    "coverage identify a non-frozen evidence axis; otherwise the correct "
    "alpha_search iteration is to record why Form4/13D confluence and Moomoo "
    "capital-flow are blocked rather than forcing another low-base-rate replay."
)
CHANGE_TYPE = "alpha_source_saturation_triage"
MECHANISM_FAMILY = "alpha_source_saturation_triage"
TRIAL_FAMILY = "alpha_source_saturation_triage"
TRIAL_VARIANT_ID = "post_20260624_source_gate_triage_v1"
CHANGED_VARIABLE = "post_20260624_source_gate_triage_v1"
CAUSAL_COMPONENTS = [
    "novelty gate result",
    "source saturation gate result",
    "local PIT coverage audit",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = list(RECENT_LOGS)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
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
                rows.append(value)
    return rows


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


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction.get("confidence_reason"):
        return prediction
    return {
        "success_probability": 0.18,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "no compliant gate-ready alpha surface",
            "current surfaces repeat saturated sources",
            "only forward-only rows available",
        ],
        "confidence_reason": (
            "Fallback prediction for read-only source-gate triage; the ticket "
            "should normally contain the reservation-time prediction."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": round(signals_survived / signals_generated, 4)
        if signals_generated
        else 0.0,
        "max_drawdown_pct_worst": max(
            [float(row.get("max_drawdown_pct") or 0.0) for row in windows] or [0.0]
        ),
        "window_count": len(windows),
        "windows": windows,
    }


def frozen_form4_saturation() -> dict[str, Any]:
    rows = []
    for row in iter_jsonl(FROZEN_FAMILIES):
        fingerprint = row.get("fingerprint") or {}
        if (
            fingerprint.get("data_source") == "form4_insider"
            and fingerprint.get("gate_shape") == "candidate_pool_top1_10d"
        ):
            rows.append(row)
    trials = sum(int(row.get("trials") or 0) for row in rows)
    accepted = sum(int(row.get("accepted") or 0) for row in rows)
    accept_rate = accepted / trials if trials else 0.0
    return {
        "data_source": "form4_insider",
        "gate_shape": "candidate_pool_top1_10d",
        "family_count": len(rows),
        "trials": trials,
        "accepted": accepted,
        "accept_rate": round(accept_rate, 6),
        "saturation_gate_min_trials": 12,
        "saturation_gate_max_accept_rate": 0.05,
        "saturated": trials >= 12 and accept_rate <= 0.05,
        "representative_families": [
            {
                "family_key": row.get("family_key"),
                "trials": row.get("trials"),
                "accepted": row.get("accepted"),
                "status": row.get("status"),
                "reopen_condition": row.get("reopen_condition"),
            }
            for row in rows
        ],
    }


def moomoo_capital_flow_coverage() -> dict[str, Any]:
    manifest = read_json(MOOMOO_MANIFEST, {})
    rows = iter_jsonl(MOOMOO_ROWS)
    as_of_dates = sorted(
        {
            str(row.get("as_of_date") or "")[:10]
            for row in rows
            if str(row.get("as_of_date") or "")[:10]
        }
    )
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    windows = {
        "old_thin": ("2024-10-02", "2025-04-22"),
        "mid_weak": ("2025-04-23", "2025-10-22"),
        "late_strong": ("2025-10-23", "2026-04-21"),
    }
    by_window = {
        label: sum(1 for day in as_of_dates if start <= day <= end)
        for label, (start, end) in windows.items()
    }
    main_flow_values = [as_float(row.get("main_flow_ratio")) for row in rows]
    main_flow_values = [value for value in main_flow_values if value is not None]
    return {
        "manifest_path": repo_rel(MOOMOO_MANIFEST),
        "rows_path": repo_rel(MOOMOO_ROWS),
        "manifest": manifest,
        "row_count": len(rows),
        "unique_tickers": len(tickers),
        "as_of_date_count": len(as_of_dates),
        "min_as_of_date": as_of_dates[0] if as_of_dates else None,
        "max_as_of_date": as_of_dates[-1] if as_of_dates else None,
        "rows_by_standard_window": by_window,
        "canonical_window_ready": all(count > 0 for count in by_window.values()),
        "main_flow_ratio_min": round(min(main_flow_values), 6) if main_flow_values else None,
        "main_flow_ratio_max": round(max(main_flow_values), 6) if main_flow_values else None,
        "pit_boundary": manifest.get("pit_boundary"),
        "blocked_reason": (
            "current_snapshot_only_forward_accumulation_no_historical_backfill"
            if len(as_of_dates) <= 1
            else None
        ),
    }


def sec_13d13g_coverage() -> dict[str, Any]:
    payload = read_json(SEC_13D13G_ROWS, {})
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        rows = []
    usable_dates = sorted(
        {
            str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
            for row in rows
            if str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
        }
    )
    return {
        "path": repo_rel(SEC_13D13G_ROWS),
        "row_count": len(rows),
        "min_usable_date": usable_dates[0] if usable_dates else None,
        "max_usable_date": usable_dates[-1] if usable_dates else None,
        "by_window": dict(Counter(str(row.get("window") or "unknown") for row in rows)),
        "by_family": dict(Counter(str(row.get("family") or "unknown") for row in rows)),
        "note": (
            "Parsed 13D/13G has standard-window coverage, but direct-entry and "
            "direction experiments are already rejected or observed-only; using "
            "it with Form4 confluence would still be anchored to a saturated "
            "Form4 candidate-pool source unless a new non-Form4 gate appears."
        ),
    }


def recent_closeouts() -> dict[str, Any]:
    out = {}
    for experiment_id, label in RECENT_LOGS.items():
        path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
        row = read_json(path, {})
        out[experiment_id] = {
            "label": label,
            "path": repo_rel(path),
            "status": row.get("status"),
            "decision": row.get("decision"),
            "observed_only_lead": row.get("observed_only_lead"),
            "accepted": row.get("accepted"),
            "gate4_passed": (row.get("gate4") or {}).get("passed")
            if isinstance(row.get("gate4"), dict)
            else None,
            "new_evidence_required": (row.get("post_run_reflection") or {}).get(
                "new_evidence_required"
            )
            if isinstance(row.get("post_run_reflection"), dict)
            else None,
        }
    return out


def forward_replacement_summary() -> dict[str, Any]:
    rows = iter_jsonl(FORWARD_REPLACEMENT)
    closed = [
        row
        for row in rows
        if row.get("replacement_value_vs_cash_usd") is not None
        or row.get("closed_at")
        or row.get("exit_date")
    ]
    by_sleeve = Counter(str(row.get("sleeve_key") or row.get("source") or "unknown") for row in closed)
    return {
        "path": repo_rel(FORWARD_REPLACEMENT),
        "row_count": len(rows),
        "closed_like_rows": len(closed),
        "closed_like_rows_by_sleeve": dict(by_sleeve),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    form4_saturation = frozen_form4_saturation()
    moomoo = moomoo_capital_flow_coverage()
    sec_13d13g = sec_13d13g_coverage()
    closeouts = recent_closeouts()
    forward = forward_replacement_summary()

    failed_reasons = []
    if form4_saturation["saturated"]:
        failed_reasons.append("form4_candidate_pool_source_saturated_0_of_13")
    if not moomoo["canonical_window_ready"]:
        failed_reasons.append("moomoo_capital_flow_current_snapshot_only")
    if closeouts.get("exp-20260623-025", {}).get("status") == "rejected":
        failed_reasons.append("prior_form4_sec_confluence_promotion_rejected")
    if closeouts.get("exp-20260623-008", {}).get("status") == "rejected":
        failed_reasons.append("broad_daily_short_volume_context_rejected")
    failed_reasons.append("no_strategy_after_policy_run")

    decision = "blocked_no_compliant_gate_ready_alpha_surface_after_source_triage"
    status = "blocked"
    timestamp = utc_now()
    after = dict(baseline)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "implementation_mode": "read_only_gate_triage",
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "post_20260624_gate_and_coverage_triage",
        "new_evidence_axis": (
            "Actual source-gate triage after exp-20260624-007: Form4 candidate-pool "
            "family saturation is 0/13 and Moomoo capital-flow remains current-snapshot-only."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 0,
            "brier_score": round(float(prediction.get("success_probability") or 0.0) ** 2, 6),
            "failure_modes_observed": failed_reasons,
            "predicted_failure_mode_hit": True,
            "actual_decision": decision,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "form4_candidate_pool_saturation": "0 accepted / 13 trials in frozen_families.jsonl",
                "exp-20260623-025": "fixed Form4+SEC confluence failed accepted distribution comparator",
                "exp-20260621-017": "Moomoo capital-flow blocked as current snapshot only",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": "Only proceed to alpha replay if a non-saturated source has PIT coverage or closed forward rows; otherwise block.",
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": True,
            "baseline_loaded": True,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": False,
            "runtime_fields_checked": ["entry_date", "target_price"],
            "target_price_scope": "No executable candidate or exit is scheduled; target_price is not consumed.",
            "source_triage": {
                "form4_candidate_pool_saturation": form4_saturation,
                "moomoo_capital_flow": moomoo,
                "sec_13d13g_context_surface": sec_13d13g,
                "recent_closeouts": closeouts,
                "forward_replacement": forward,
            },
            "blocking_reason": (
                "No compliant next alpha surface was found: the tempting Form4/13D "
                "interaction is anchored to a saturated Form4 candidate-pool source, "
                "while Moomoo capital-flow still lacks historical PIT coverage and "
                "closed replacement-value rows."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No entry filter, ranking, sizing, exit, or candidate generator changed.",
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "ran_after_strategy": False,
            "strategy_rerun_required": False,
            "reason_after_not_run": "Blocked before strategy replay by source saturation and PIT coverage checks.",
        },
        "before_metrics": baseline,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "strategy_behavior_changed": False,
            "form4_candidate_pool_trials": form4_saturation["trials"],
            "form4_candidate_pool_accepted": form4_saturation["accepted"],
            "moomoo_as_of_date_count": moomoo["as_of_date_count"],
            "moomoo_rows": moomoo["row_count"],
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "uses_llm": False,
            "parity_note": "Read-only gate triage; no production or backtest behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The next plausible alpha surfaces did not meet the repo's "
                "evidence bar. Form4-derived candidate-pool scans are saturated "
                "at 0 accepted out of 13 trials, so adding 13D/13G context to a "
                "Form4+SEC confluence idea would require a stronger non-Form4 "
                "evidence axis. Moomoo capital-flow remains a single current "
                "snapshot with no standard-window history or closed replacement rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Form4/SEC/13D confluence by sweeping Form4 codes, "
                "SEC form lists, 13D/13G lookbacks, holder types, stake thresholds, "
                "same-day price filters, hold days, top-N, cooldown, or notional."
            ),
            "new_evidence_required": (
                "A valid next alpha needs a non-saturated PIT field such as borrow "
                "fee/utilization, loan availability, historical options with as-of "
                "controls, materially more closed forward replacement rows, or a "
                "true historical Moomoo capital-flow archive."
            ),
        },
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(FROZEN_FAMILIES),
            repo_rel(MOOMOO_MANIFEST),
            repo_rel(MOOMOO_ROWS),
            repo_rel(SEC_13D13G_ROWS),
            repo_rel(FORWARD_REPLACEMENT),
            *[
                f"experiments/logs/{experiment_id}.json"
                for experiment_id in RECENT_LOGS
            ],
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
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
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
        "observed_only_lead",
        "lane",
        "owner",
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
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    source = payload["gate2"]["source_triage"]
    form4 = source["form4_candidate_pool_saturation"]
    moomoo = source["moomoo_capital_flow"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - post-20260624 source gate triage",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- artifact: `{repo_rel(OUT_JSON)}`",
            f"- runner: `{RUNNER_COMMAND}`",
            "",
            "## Gate Findings",
            "",
            f"- Form4 candidate-pool saturation: {form4['accepted']}/{form4['trials']} accepted",
            f"- Moomoo capital-flow rows/as-of dates: {moomoo['row_count']} / {moomoo['as_of_date_count']}",
            f"- Moomoo canonical-window ready: {moomoo['canonical_window_ready']}",
            f"- Failed reasons: {', '.join(payload['gate4']['failed_reasons'])}",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
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
        FROZEN_FAMILIES,
        MOOMOO_MANIFEST,
        MOOMOO_ROWS,
        SEC_13D13G_ROWS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
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
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
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
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "form4_candidate_pool_trials": payload["delta_metrics"][
                    "form4_candidate_pool_trials"
                ],
                "form4_candidate_pool_accepted": payload["delta_metrics"][
                    "form4_candidate_pool_accepted"
                ],
                "moomoo_rows": payload["delta_metrics"]["moomoo_rows"],
                "moomoo_as_of_date_count": payload["delta_metrics"][
                    "moomoo_as_of_date_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
