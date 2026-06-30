"""exp-20260629-014: options forward ledger refresh for 2026-06-24..2026-06-26.

Measurement repair only. The prior options ledger refresh added 2026-06-23
pending rows. Three later OnclickMedia options snapshots are now present; this
runner materializes their delta observation rows so future options demand /
protection tests can wait for closed replacement-value outcomes without
changing strategy behavior.

No strategy, ranking, sizing, exit, order, watchlist, LLM, daily collector, or
production adapter behavior changes in this experiment.
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
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260623_009_options_forward_observation_ledger as prior_ledger  # noqa: E402


EXPERIMENT_ID = "exp-20260629-014"
OWNER = "alpha-explore"
SLUG = "options_forward_ledger_refresh_20260624_20260626"
RUNNER = f"quant/experiments/exp_20260629_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260629_014_{SLUG}.json"
DELTA_LEDGER_JSONL = DATA_DIR / "options_forward_observation_ledger_delta_20260624_20260626.jsonl"
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
PRIOR_LEDGER_SOURCES = [
    {
        "experiment_id": "exp-20260623-009",
        "path": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260623-009"
        / "options_forward_observation_ledger.jsonl",
    },
    {
        "experiment_id": "exp-20260624-020",
        "path": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260624-020"
        / "options_forward_observation_ledger_delta_20260623.jsonl",
    },
]
TARGET_QUOTE_DATES = ("2026-06-24", "2026-06-25", "2026-06-26")

HYPOTHESIS = (
    "Alpha-enabling options forward ledger refresh: 2026-06-24 through "
    "2026-06-26 OnclickMedia snapshots should add new PIT pending rows for "
    "future options demand/protection attribution without changing strategy "
    "behavior."
)
ALPHA_HYPOTHESIS = (
    "Options put/call, open-interest, volume, IV skew, and contract-quality "
    "fields may identify demand or protection pressure not visible in OHLCV, "
    "but only after forward ledger rows mature into closed cash/SPY/QQQ "
    "replacement-value outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_forward_ledger_refresh"
TRIAL_VARIANT_ID = "post_exp020_20260624_20260626_pending_rows_v1"
CHANGED_VARIABLE = "onclickmedia_options_forward_observation_ledger_refresh_20260624_20260626_v1"
NEW_EVIDENCE_TYPE = "new_forward_options_snapshot_rows"
NEW_EVIDENCE_AXIS = (
    "Three new non-empty OnclickMedia options snapshot dates after exp020 "
    "(2026-06-24, 2026-06-25, 2026-06-26) create pending forward observation "
    "rows. This is not a retune of options thresholds or an observed-only "
    "reslice of the same closed rows."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-009",
    "exp-20260624-020",
    "exp-20260624-026",
    "exp-20260625-001",
]
CAUSAL_COMPONENTS = [
    "new forward options snapshot rows",
    "per ticker-date pending observation rows",
    "PIT usability caveats",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260629_014_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/options_forward_observation_ledger_delta_20260624_20260626.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/experiment_log.jsonl",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_path_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.86,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "snapshot_schema_inconsistent",
            "ledger_duplicate_rows",
            "no_new_snapshot_rows",
            "quality_controls_too_sparse",
        ],
        "confidence_reason": (
            "exp-20260624-020 normalized a neighboring daily options snapshot; "
            "the 2026-06-24..2026-06-26 chain files are present and non-empty."
        ),
        "recorded_at": utc_now(),
    }


def load_prior_observation_ids() -> tuple[set[str], list[dict[str, Any]]]:
    ids: set[str] = set()
    metadata: list[dict[str, Any]] = []
    for source in PRIOR_LEDGER_SOURCES:
        path = Path(source["path"])
        rows = read_jsonl(path)
        source_ids = {
            str(row.get("observation_id") or "")
            for row in rows
            if str(row.get("observation_id") or "")
        }
        ids.update(source_ids)
        metadata.append(
            {
                "source_experiment_id": source["experiment_id"],
                "path": repo_path_rel(path),
                "exists": path.exists(),
                "rows": len(rows),
                "observation_ids": len(source_ids),
            }
        )
    return ids, metadata


def coverage_for_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field in prior_ledger.REQUIRED_RAW_FIELDS:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present": present,
            "missing": len(rows) - present,
            "coverage": round(present / len(rows), 6) if rows else 0.0,
        }
    return out


def raw_rows_for_targets(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = set(TARGET_QUOTE_DATES)
    return [row for row in raw_rows if str(row.get("quote_date") or "")[:10] in targets]


def ledger_rows_for_targets(ledger_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = set(TARGET_QUOTE_DATES)
    return [row for row in ledger_rows if str(row.get("quote_date") or "")[:10] in targets]


def min_field_coverage(coverage: dict[str, dict[str, Any]]) -> float:
    if not coverage:
        return 0.0
    return min(float(item.get("coverage") or 0.0) for item in coverage.values())


def summarize_ledger_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_flag: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    by_quote_date: Counter[str] = Counter()
    usable_dates: set[str] = set()
    for row in rows:
        ticker = str(row.get("ticker") or "")
        quote_date = str(row.get("quote_date") or "")[:10]
        usable_date = str(row.get("usable_trade_date") or "")[:10]
        if ticker:
            by_ticker[ticker] += 1
        if quote_date:
            by_quote_date[quote_date] += 1
        if usable_date:
            usable_dates.add(usable_date)
        for flag in row.get("quality_flags") or []:
            by_flag[str(flag)] += 1
    quote_dates = sorted(by_quote_date)
    usable_sorted = sorted(usable_dates)
    return {
        "ledger_rows": len(rows),
        "quote_date_start": quote_dates[0] if quote_dates else None,
        "quote_date_end": quote_dates[-1] if quote_dates else None,
        "quote_date_count": len(quote_dates),
        "quote_date_row_counts": dict(sorted(by_quote_date.items())),
        "usable_trade_date_start": usable_sorted[0] if usable_sorted else None,
        "usable_trade_date_end": usable_sorted[-1] if usable_sorted else None,
        "ticker_count": len(by_ticker),
        "quality_flag_counts": dict(sorted(by_flag.items())),
        "sample_observations": rows[:5],
    }


def build_refresh() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows, file_audit = prior_ledger.iter_option_rows()
    full_ledger = prior_ledger.build_observation_ledger(raw_rows)
    prior_ids, prior_metadata = load_prior_observation_ids()
    target_raw_rows = raw_rows_for_targets(raw_rows)
    target_ledger_rows = ledger_rows_for_targets(full_ledger)
    new_rows = [
        {
            **row,
            "delta_experiment_id": EXPERIMENT_ID,
            "delta_rule_version": CHANGED_VARIABLE,
            "source_prior_rule_version": row.get("rule_version"),
        }
        for row in target_ledger_rows
        if str(row.get("observation_id") or "") not in prior_ids
    ]
    duplicate_new_ids = len(new_rows) - len({row.get("observation_id") for row in new_rows})
    target_files = [
        path
        for path in file_audit["chain_files"]
        if any(day in path for day in TARGET_QUOTE_DATES)
    ]
    return new_rows, {
        "chain_file_count": file_audit["chain_file_count"],
        "target_chain_files": target_files,
        "bad_json_rows": file_audit["bad_json_rows"],
        "prior_ledgers": prior_metadata,
        "prior_observation_ids": len(prior_ids),
        "all_current_ledger_rows": len(full_ledger),
        "target_quote_dates": list(TARGET_QUOTE_DATES),
        "target_raw_contract_rows": len(target_raw_rows),
        "target_ledger_rows": len(target_ledger_rows),
        "new_delta_rows": len(new_rows),
        "duplicate_new_observation_ids": duplicate_new_ids,
        "target_raw_field_coverage": coverage_for_rows(target_raw_rows),
        "delta_summary": summarize_ledger_rows(new_rows),
    }


def calibration(prediction: dict[str, Any], accepted: bool, failed: list[str]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1 if accepted else 0
    expected_modes = prediction.get("main_failure_modes") or []
    return {
        "actual_success": actual,
        "actual_decision": (
            "accepted_measurement_repair_options_forward_ledger_refreshed_20260624_20260626"
            if accepted
            else "blocked_options_forward_ledger_refresh_20260624_20260626"
        ),
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 6),
        "predicted_failure_modes": expected_modes,
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(set(expected_modes).intersection(failed)),
        "surprise_note": (
            "The three new snapshots normalized cleanly into delta observation rows."
            if accepted
            else "The new snapshots could not be cleanly normalized into a delta ledger."
        ),
    }


def build_payload(delta_rows: list[dict[str, Any]], refresh: dict[str, Any]) -> dict[str, Any]:
    prediction = load_prediction()
    baseline = prior_ledger.baseline_metrics()
    failed: list[str] = []

    missing_sources = [
        source["path"] for source in refresh["prior_ledgers"] if not source["exists"]
    ]
    if missing_sources:
        failed.append("prior_ledger_missing")
    if refresh["bad_json_rows"]:
        failed.append("bad_json_rows_present")
    if refresh["target_raw_contract_rows"] <= 0:
        failed.append("no_target_snapshot_rows")
    if refresh["new_delta_rows"] <= 0 or not delta_rows:
        failed.append("no_new_snapshot_rows")
    if refresh["duplicate_new_observation_ids"] != 0:
        failed.append("ledger_duplicate_rows")
    if min_field_coverage(refresh["target_raw_field_coverage"]) < 0.95:
        failed.append("target_snapshot_required_field_coverage_below_95pct")

    accepted = not failed
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_options_forward_ledger_refreshed_20260624_20260626"
        if accepted
        else "blocked_options_forward_ledger_refresh_20260624_20260626"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, accepted, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260623-009": (
                    "Accepted measurement repair created the original options "
                    "forward observation ledger through 2026-06-22."
                ),
                "exp-20260624-020": (
                    "Accepted measurement repair added 2026-06-23 pending delta rows."
                ),
                "exp-20260624-026": (
                    "Accepted reusable outcome settlement for exp009/exp020 rows; "
                    "later rows were not present in its source ledgers."
                ),
                "exp-20260625-001": (
                    "Rejected observed-only options demand quality attribution and "
                    "forbade threshold retries without materially more closed rows."
                ),
                "novelty_gate": (
                    "Reservation passed without override. This run creates new "
                    "pending forward rows from later snapshots, not a threshold "
                    "or same-row attribution retry."
                ),
            },
            "3_single_policy_bundle": (
                "Normalize only the 2026-06-24, 2026-06-25, and 2026-06-26 "
                "OnclickMedia options snapshots into experiment-owned pending "
                "observation rows. No entry, ranking, sizing, exit, or order "
                "logic changes."
            ),
            "4_acceptance_standard": (
                "Accept as measurement repair only if prior ledgers exist, target "
                "snapshots have rows, required raw fields cover at least 95%, new "
                "observation IDs are nonzero and unique, and strategy metrics "
                "remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "target_quote_dates": list(TARGET_QUOTE_DATES),
            "options_dir": repo_path_rel(prior_ledger.OPTIONS_DIR),
            "input_pattern": "options_onclickmedia_chain_*.jsonl",
            "prior_ledgers": [source["path"] for source in refresh["prior_ledgers"]],
            "delta_ledger_output": repo_path_rel(DELTA_LEDGER_JSONL),
            "baseline_result_file": repo_path_rel(BASELINE_RESULT),
            "required_raw_fields": prior_ledger.REQUIRED_RAW_FIELDS,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": accepted,
            "fields_checked": prior_ledger.REQUIRED_RAW_FIELDS,
            "prior_ledgers": refresh["prior_ledgers"],
            "target_quote_dates": list(TARGET_QUOTE_DATES),
            "target_raw_contract_rows": refresh["target_raw_contract_rows"],
            "target_ledger_rows": refresh["target_ledger_rows"],
            "new_delta_rows": refresh["new_delta_rows"],
            "target_raw_field_coverage": refresh["target_raw_field_coverage"],
            "required_field_coverage_min": min_field_coverage(refresh["target_raw_field_coverage"]),
            "entry_date_target_price_note": (
                "No executable entries or target exits are scheduled. The delta "
                "ledger stores usable_trade_date and pending outcome placeholders only."
            ),
            "failed_reasons": failed,
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter, candidate selection, or strategy rule was added.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "acceptance_checks": {
                "prior_ledgers_exist": not missing_sources,
                "target_snapshot_rows_positive": refresh["target_raw_contract_rows"] > 0,
                "new_delta_rows_positive": refresh["new_delta_rows"] > 0,
                "duplicate_new_observation_ids_zero": refresh["duplicate_new_observation_ids"] == 0,
                "bad_json_rows_zero": refresh["bad_json_rows"] == 0,
                "required_field_coverage_min": min_field_coverage(refresh["target_raw_field_coverage"]),
                "strategy_behavior_changed": False,
            },
            "failed_reasons": failed,
            "strategy_rerun_required": False,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "new_delta_rows": refresh["new_delta_rows"],
            "target_raw_contract_rows": refresh["target_raw_contract_rows"],
        },
        "refresh_summary": refresh,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "replay_only": False,
            "live_ready": False,
            "parity_note": (
                "This experiment writes an experiment-owned forward observation "
                "delta only. The existing daily options collector and all trading "
                "adapters are unchanged."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The 2026-06-24 through 2026-06-26 OnclickMedia snapshots have "
                "enough normalized contract fields to create pending ticker-date "
                "observations. This increases future options evidence capacity but "
                "still provides no accepted options alpha because the new rows need "
                "closed replacement-value outcomes."
                if accepted
                else "The later options snapshots did not satisfy the fixed ledger-refresh checks."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call, IV, OI, volume, expiration, "
                "moneyness, top-N, hold, cooldown, or notional rules on this "
                "pending-forward delta. It remains a forward observation surface, "
                "not Gate-4 alpha coverage."
            ),
            "new_evidence_required": (
                "Wait for these 2026-06-24..2026-06-26 rows to close with "
                "cash/SPY/QQQ replacement value, add PIT borrow/loan availability "
                "context, or backfill historical PIT options chains with vendor/as-of "
                "controls before another options alpha claim."
            ),
        },
        "related_files": [
            RUNNER,
            repo_path_rel(DELTA_LEDGER_JSONL),
            repo_path_rel(OUT_JSON),
            repo_path_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260623_009_options_forward_observation_ledger.py",
            "quant/experiments/exp_20260624_020_options_forward_ledger_refresh_20260623.py",
            "experiments/logs/exp-20260625-001.json",
        ],
        "changed_files": ALLOWED_WRITE_SCOPE,
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
        "lean_quality_passed": accepted,
        "artifact": repo_path_rel(OUT_JSON),
        "delta_ledger": repo_path_rel(DELTA_LEDGER_JSONL),
        "log": repo_path_rel(LOG_JSON),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": payload["lane"],
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            "dependencies_validated": payload["gate2"]["dependencies_validated"],
            "fields_checked": payload["gate2"]["fields_checked"],
            "target_quote_dates": payload["gate2"]["target_quote_dates"],
            "target_raw_contract_rows": payload["gate2"]["target_raw_contract_rows"],
            "target_ledger_rows": payload["gate2"]["target_ledger_rows"],
            "new_delta_rows": payload["gate2"]["new_delta_rows"],
            "required_field_coverage_min": payload["gate2"]["required_field_coverage_min"],
            "entry_date_target_price_note": payload["gate2"]["entry_date_target_price_note"],
            "failed_reasons": payload["gate2"]["failed_reasons"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "refresh_summary": {
            "prior_observation_ids": payload["refresh_summary"]["prior_observation_ids"],
            "all_current_ledger_rows": payload["refresh_summary"]["all_current_ledger_rows"],
            "target_raw_contract_rows": payload["refresh_summary"]["target_raw_contract_rows"],
            "target_ledger_rows": payload["refresh_summary"]["target_ledger_rows"],
            "new_delta_rows": payload["refresh_summary"]["new_delta_rows"],
            "duplicate_new_observation_ids": payload["refresh_summary"][
                "duplicate_new_observation_ids"
            ],
            "delta_summary": payload["refresh_summary"]["delta_summary"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": repo_path_rel(OUT_JSON),
        "delta_ledger": repo_path_rel(DELTA_LEDGER_JSONL),
        "log": repo_path_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["refresh_summary"]
    delta = summary["delta_summary"]
    quote_counts = delta["quote_date_row_counts"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options forward ledger refresh",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Target quote dates: `{', '.join(TARGET_QUOTE_DATES)}`",
            f"- New observation rows: `{summary['new_delta_rows']}`",
            f"- New rows by quote date: `{quote_counts}`",
            f"- Raw contracts normalized: `{summary['target_raw_contract_rows']}`",
            f"- Delta tickers: `{delta['ticker_count']}`",
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
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        DELTA_LEDGER_JSONL,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ] + [Path(source["path"]) for source in PRIOR_LEDGER_SOURCES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_path_rel(OUT_JSON),
        "delta_ledger": repo_path_rel(DELTA_LEDGER_JSONL),
        "log": repo_path_rel(LOG_JSON),
        "card": repo_path_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_path_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], delta_rows: list[dict[str, Any]]) -> None:
    write_jsonl(DELTA_LEDGER_JSONL, delta_rows)
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_path_rel(OUT_JSON),
        "delta_ledger": repo_path_rel(DELTA_LEDGER_JSONL),
        "log": repo_path_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "refresh_summary": payload["refresh_summary"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
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
            "baseline_result_file": repo_path_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_path_rel(OUT_JSON),
            "delta_ledger": repo_path_rel(DELTA_LEDGER_JSONL),
            "log": repo_path_rel(LOG_JSON),
            "card_file": repo_path_rel(CARD_MD),
            "revision_manifest_file": repo_path_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    delta_rows, refresh = build_refresh()
    payload = build_payload(delta_rows, refresh)
    if payload["refresh_summary"]["new_delta_rows"] != len(delta_rows):
        raise RuntimeError("payload refresh summary disagrees with delta rows")
    persist(payload, delta_rows)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "target_quote_dates": list(TARGET_QUOTE_DATES),
                "target_raw_contract_rows": refresh["target_raw_contract_rows"],
                "new_delta_rows": refresh["new_delta_rows"],
                "delta_tickers": refresh["delta_summary"]["ticker_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_path_rel(OUT_JSON),
                "delta_ledger": repo_path_rel(DELTA_LEDGER_JSONL),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
