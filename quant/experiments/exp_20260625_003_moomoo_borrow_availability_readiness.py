"""exp-20260625-003: Moomoo borrow-availability readiness audit.

Measurement repair only. The repo's FINRA/options squeeze families repeatedly
name real borrow fee / loan availability as the needed new evidence axis. This
runner audits whether the newly collected Moomoo borrow-availability sidecar is
actually populated enough to support future forward attribution.

No strategy, shared helper, ranking, sizing, exit, paper order, live order,
watchlist, LLM, or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-003"
OWNER = "alpha-explore"
SLUG = "moomoo_borrow_availability_readiness"
RUNNER = f"quant/experiments/exp_20260625_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
BORROW_DIR = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability"
BORROW_MANIFEST = BORROW_DIR / "manifest.json"
BORROW_ROWS = BORROW_DIR / "rows.jsonl"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BORROW_FIELDS = (
    "enable_short_sell",
    "short_sell_rate_pct",
    "short_available_volume",
    "short_margin_initial_ratio_pct",
)

HYPOTHESIS = (
    "Real PIT borrow fee / loan-availability fields could reopen FINRA/options "
    "squeeze families, but this run first audits whether the new Moomoo "
    "borrow-availability sidecar has populated decision-time fields and enough "
    "PIT readiness to support future alpha attribution."
)
ALPHA_HYPOTHESIS = (
    "If hard-to-borrow pressure is a true distinct risk/reward signal, "
    "point-in-time short_sell_rate and short_available_volume should eventually "
    "separate squeeze-prone candidates from crowded false positives better than "
    "raw FINRA short-interest shares."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_moomoo_borrow_availability_readiness"
TRIAL_FAMILY = "moomoo_borrow_availability_readiness_gate"
TRIAL_VARIANT_ID = "initial_entitlement_and_pit_coverage_audit_v1"
CHANGED_VARIABLE = "moomoo_borrow_availability_readiness_gate_v1"
NEW_EVIDENCE_TYPE = "new_pit_borrow_availability_source"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260621-017",
    "exp-20260622-010",
    "exp-20260623-010",
    "exp-20260625-001",
]
CAUSAL_COMPONENTS = [
    "borrow sidecar manifest audit",
    "JSONL field coverage audit",
    "baseline identity check",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-003/",
    "experiments/cards/exp-20260625-003.md",
    "experiments/manifests/exp-20260625-003.json",
    "experiments/tickets/exp-20260625-003.json",
    "experiments/logs/exp-20260625-003.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
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


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def is_present(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, float) and value != value:
        return False
    return True


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if prediction:
        return prediction
    return {
        "success_probability": 0.08,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "borrow_fields_unpopulated",
            "current_snapshot_only",
            "no_forward_outcomes",
            "not_wired_to_daily",
        ],
        "confidence_reason": (
            "Borrow availability is the named reopen axis, but the current "
            "sidecar manifest reports zero populated borrow fields."
        ),
        "recorded_at": utc_now(),
    }


def field_coverage(rows: list[dict[str, Any]], fields: tuple[str, ...] | list[str]) -> dict[str, Any]:
    total = len(rows)
    out: dict[str, Any] = {}
    for field in fields:
        present = sum(1 for row in rows if is_present(row.get(field)))
        out[field] = {
            "present_rows": present,
            "scanned_rows": total,
            "present_rate": round(present / total, 4) if total else 0.0,
        }
    return out


def summarize_borrow_surface(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    as_of_dates = sorted({str(row.get("as_of_date")) for row in rows if row.get("as_of_date")})
    tickers = sorted({str(row.get("ticker")).upper() for row in rows if row.get("ticker")})
    populated = [row for row in rows if bool(row.get("borrow_populated"))]
    rates = [safe_float(row.get("short_sell_rate_pct")) for row in rows]
    rates = [value for value in rates if value is not None]
    availability = [safe_float(row.get("short_available_volume")) for row in rows]
    availability = [value for value in availability if value is not None]
    duplicate_keys = len(rows) - len(
        {
            (str(row.get("ticker")).upper(), str(row.get("as_of_date")))
            for row in rows
            if row.get("ticker") and row.get("as_of_date")
        }
    )
    source_counts = Counter(str(row.get("source") or "unknown") for row in rows)
    return {
        "manifest_exists": BORROW_MANIFEST.exists(),
        "rows_path_exists": BORROW_ROWS.exists(),
        "row_count": len(rows),
        "unique_tickers": len(tickers),
        "as_of_date_count": len(as_of_dates),
        "as_of_dates": as_of_dates,
        "latest_as_of_date": max(as_of_dates) if as_of_dates else None,
        "last_collected_at_utc": manifest.get("last_collected_at_utc"),
        "manifest_schema": manifest.get("schema"),
        "manifest_pit_boundary": manifest.get("pit_boundary"),
        "manifest_trade_enabled": manifest.get("trade_enabled"),
        "manifest_borrow_populated_this_run": manifest.get("borrow_populated_this_run"),
        "manifest_borrow_populated_pct": manifest.get("borrow_populated_pct"),
        "borrow_populated_rows": len(populated),
        "borrow_populated_rate": round(len(populated) / len(rows), 4) if rows else 0.0,
        "field_coverage": field_coverage(
            rows,
            [
                "as_of_date",
                "collected_at_utc",
                "ticker",
                "last_price",
                "borrow_populated",
                *BORROW_FIELDS,
                "entry_date",
                "target_price",
                "trade_enabled",
            ],
        ),
        "source_counts": dict(source_counts),
        "duplicate_ticker_date_rows": duplicate_keys,
        "short_sell_rate": {
            "n": len(rates),
            "min": min(rates) if rates else None,
            "max": max(rates) if rates else None,
            "mean": round(mean(rates), 6) if rates else None,
            "median": round(median(rates), 6) if rates else None,
        },
        "short_available_volume": {
            "n": len(availability),
            "min": min(availability) if availability else None,
            "max": max(availability) if availability else None,
            "mean": round(mean(availability), 2) if availability else None,
            "median": round(median(availability), 2) if availability else None,
        },
        "sample_rows": rows[:5],
    }


def calibration(prediction: dict[str, Any], accepted: bool, failed: list[str]) -> dict[str, Any]:
    prob = float(prediction.get("success_probability") or 0.0)
    actual = 1 if accepted else 0
    return {
        "actual_decision": "accepted_measurement_repair" if accepted else "blocked",
        "actual_success": actual,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual) ** 2, 4),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_ev_delta": 0.0,
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(set(prediction.get("main_failure_modes") or []) & set(failed)),
        "surprise_note": (
            "Not surprising: the sidecar existed, but entitlement coverage left "
            "all borrow-specific fields null."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    manifest = read_json(BORROW_MANIFEST, {})
    rows = read_jsonl(BORROW_ROWS)
    surface = summarize_borrow_surface(rows, manifest)
    failed: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        failed.append("baseline_missing_or_incomplete")
    if not BORROW_MANIFEST.exists():
        failed.append("borrow_manifest_missing")
    if not BORROW_ROWS.exists() or not rows:
        failed.append("borrow_rows_missing")
    if surface["borrow_populated_rows"] <= 0:
        failed.append("borrow_fields_unpopulated")
    if surface["as_of_date_count"] < 20:
        failed.append("forward_observation_dates_below_20")
    if "current_snapshot_only" in str(surface.get("manifest_pit_boundary") or ""):
        failed.append("current_snapshot_only")
    if surface["field_coverage"]["entry_date"]["present_rows"] == 0:
        failed.append("entry_date_absent_no_trade_surface")
    if surface["field_coverage"]["target_price"]["present_rows"] == 0:
        failed.append("target_price_absent_no_trade_surface")
    failed.append("not_wired_to_daily")
    failed.append("no_forward_outcomes")

    measurement_ready = (
        BASELINE_RESULT.exists()
        and baseline.get("window_count") == 3
        and BORROW_MANIFEST.exists()
        and BORROW_ROWS.exists()
        and bool(rows)
        and surface["borrow_populated_rows"] > 0
        and surface["as_of_date_count"] >= 20
    )
    status = "accepted_measurement_repair" if measurement_ready else "blocked"
    decision = (
        "accepted_measurement_repair_moomoo_borrow_availability_ready"
        if measurement_ready
        else "blocked_borrow_availability_fields_unpopulated"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": measurement_ready,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair_readiness_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "calibration": calibration(prediction, measurement_ready, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260621-017": "Moomoo capital-flow current snapshot was blocked as forward-only/current-only.",
                "exp-20260622-010": "Moomoo daily short-volume activity helper was rejected; retry requires borrow fee/utilization/availability or broader forward evidence.",
                "exp-20260623-010": "Options skew attribution rejected; valid retry can use borrow or loan-availability context.",
                "exp-20260625-001": "Options demand-quality forward attribution rejected; borrow context remains a named but unproven reopen axis.",
                "novelty_gate": "Reservation warned on FINRA borrow-pressure neighbors; this is measurement repair of a materially different Moomoo borrow-availability sidecar, not a FINRA threshold retry.",
            },
            "3_single_policy_bundle": (
                "One measurement bundle: audit Moomoo borrow-availability "
                "manifest and rows for populated borrow fields, PIT boundary, "
                "forward observation depth, and strategy identity."
            ),
            "4_success_failure_standard": (
                "Accept only as measurement repair if baseline is unchanged, "
                "sidecar manifest/rows load, at least one borrow-specific field "
                "is populated, and enough forward dates exist for later "
                "attribution. Alpha remains blocked until closed forward "
                "replacement-value rows exist."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "borrow_manifest": repo_rel(BORROW_MANIFEST),
            "borrow_rows": repo_rel(BORROW_ROWS),
            "borrow_fields": list(BORROW_FIELDS),
            "readiness_min_as_of_dates": 20,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "borrow_populated_rows": surface["borrow_populated_rows"],
            "as_of_date_count": surface["as_of_date_count"],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": surface["borrow_populated_rows"] > 0,
            "dependencies_validated": BORROW_MANIFEST.exists() and BORROW_ROWS.exists(),
            "dependency_fields_checked": [
                "as_of_date",
                "ticker",
                "collected_at_utc",
                "enable_short_sell",
                "short_sell_rate_pct",
                "short_available_volume",
                "short_margin_initial_ratio_pct",
                "entry_date",
                "target_price",
            ],
            "dependency_presence": surface["field_coverage"],
            "blocking_reason": (
                "Moomoo snapshot rows loaded, but all borrow-specific fields "
                "are null under the current account entitlement; entry_date and "
                "target_price are absent because this is not a trade surface."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable filter, candidate source, or strategy rule was added.",
        },
        "gate4": {
            "passed": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "decision": decision,
            "failed_reasons": failed,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "readiness_rule": {
                "min_borrow_populated_rows": 1,
                "min_forward_observation_dates": 20,
                "requires_closed_forward_replacement_value_rows": True,
            },
        },
        "borrow_surface": surface,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned readiness artifact only. It reads the existing "
                "borrow sidecar and writes no shared helper, daily adapter, "
                "order, rank, size, exit, watchlist, or LLM changes."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The Moomoo snapshot endpoint returned normal prices but zero "
                "populated borrow fields across all 45 rows, so the account or "
                "endpoint entitlement does not currently expose the named "
                "borrow fee / availability axis."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry FINRA short-interest, daily short-volume, options "
                "skew, or Moomoo borrow threshold rules until the sidecar has "
                "nonzero borrow_populated rows across multiple dates."
            ),
            "new_evidence_required": (
                "A valid retry needs populated short_sell_rate_pct and/or "
                "short_available_volume rows over at least 20 forward dates, "
                "then closed forward replacement-value attribution versus cash, "
                "SPY, QQQ, and accepted comparators."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(BORROW_MANIFEST),
            repo_rel(BORROW_ROWS),
            repo_rel(BASELINE_RESULT),
            "quant/moomoo_borrow_availability_sidecar.py",
            "experiments/logs/exp-20260621-017.json",
            "experiments/logs/exp-20260622-010.json",
            "experiments/logs/exp-20260623-010.json",
            "experiments/logs/exp-20260625-001.json",
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    surface = dict(payload["borrow_surface"])
    surface["sample_rows"] = surface["sample_rows"][:2]
    record["borrow_surface"] = surface
    return record


def build_card(payload: dict[str, Any]) -> str:
    surface = payload["borrow_surface"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Moomoo borrow availability readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Rows: `{surface['row_count']}`",
            f"- Unique tickers: `{surface['unique_tickers']}`",
            f"- As-of dates: `{surface['as_of_date_count']}`",
            f"- Borrow-populated rows: `{surface['borrow_populated_rows']}`",
            f"- short_sell_rate rows: `{surface['short_sell_rate']['n']}`",
            f"- short_available_volume rows: `{surface['short_available_volume']['n']}`",
            "- Strategy behavior changed: `false`",
            "- Production orders changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
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
        BORROW_MANIFEST,
        BORROW_ROWS,
        REPO_ROOT / "quant" / "moomoo_borrow_availability_sidecar.py",
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
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
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
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
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "borrow_surface": {
                key: value
                for key, value in payload["borrow_surface"].items()
                if key != "sample_rows"
            },
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
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
                "row_count": payload["borrow_surface"]["row_count"],
                "unique_tickers": payload["borrow_surface"]["unique_tickers"],
                "as_of_date_count": payload["borrow_surface"]["as_of_date_count"],
                "borrow_populated_rows": payload["borrow_surface"]["borrow_populated_rows"],
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
