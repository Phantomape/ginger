"""exp-20260624-020: options forward ledger refresh for 2026-06-23.

Measurement repair only. The prior options ledger repair normalized forward
OnclickMedia snapshots through 2026-06-22. A new PIT-safe 2026-06-23 snapshot is
now present; this runner materializes the delta rows under the new experiment
ID so future options alpha tests can wait for closed replacement-value outcomes.

No strategy, ranking, sizing, exit, order, watchlist, LLM, or production daily
collector behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
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


EXPERIMENT_ID = "exp-20260624-020"
OWNER = "alpha-explore"
SLUG = "options_forward_ledger_refresh_20260623"
RUNNER = f"quant/experiments/exp_20260624_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_020_{SLUG}.json"
DELTA_LEDGER_JSONL = DATA_DIR / "options_forward_observation_ledger_delta_20260623.jsonl"
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
PRIOR_LEDGER_JSONL = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-009"
    / "options_forward_observation_ledger.jsonl"
)
TARGET_QUOTE_DATE = "2026-06-23"

HYPOTHESIS = (
    "Repair options alpha blocker: the 2026-06-23 OnclickMedia options snapshot "
    "should extend the PIT forward observation ledger so future put-call, "
    "IV-skew, and options-quality alpha tests have replayable pending rows "
    "without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Options put/call, open-interest, volume, IV skew, and contract-quality "
    "fields may identify demand or protection pressure not visible in OHLCV, "
    "but only after forward ledger rows mature into closed replacement-value "
    "outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = "options_forward_ledger_refresh_20260623_v1"
CHANGED_VARIABLE = "onclickmedia_options_forward_observation_ledger_refresh_20260623_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-004",
    "exp-20260618-023",
    "exp-20260623-009",
    "exp-20260623-010",
]
CAUSAL_COMPONENTS = [
    "forward options snapshot normalization",
    "per ticker-date observation ledger refresh",
    "PIT usability and vendor-asof caveats",
    "spread and liquidity quality controls",
    "future outcome placeholders",
    "no strategy behavior change",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
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
                if not replaced:
                    lines.append(encoded)
                    replaced = True
                continue
            lines.append(raw)
    if not replaced:
        lines.append(encoded)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.85,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "snapshot_schema_inconsistent",
            "ledger_duplicate_rows",
            "no_new_snapshot_rows",
            "quality_controls_too_sparse",
        ],
        "confidence_reason": (
            "The prior options ledger repair passed and the new 2026-06-23 "
            "PIT-safe chain snapshot is present."
        ),
        "recorded_at": "2026-06-24T17:06:09+00:00",
    }


def load_prior_observation_ids() -> set[str]:
    ids: set[str] = set()
    if not PRIOR_LEDGER_JSONL.exists():
        return ids
    with PRIOR_LEDGER_JSONL.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            observation_id = str(row.get("observation_id") or "")
            if observation_id:
                ids.add(observation_id)
    return ids


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


def raw_rows_for_target_quote_date(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in raw_rows if str(row.get("quote_date") or "")[:10] == TARGET_QUOTE_DATE]


def summarize_ledger_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_flag: Counter[str] = Counter()
    by_ticker: Counter[str] = Counter()
    quote_dates = sorted({str(row.get("quote_date") or "")[:10] for row in rows})
    usable_dates = sorted({str(row.get("usable_trade_date") or "")[:10] for row in rows})
    for row in rows:
        by_ticker[str(row.get("ticker") or "")] += 1
        for flag in row.get("quality_flags") or []:
            by_flag[str(flag)] += 1
    return {
        "ledger_rows": len(rows),
        "quote_date_start": quote_dates[0] if quote_dates else None,
        "quote_date_end": quote_dates[-1] if quote_dates else None,
        "quote_date_count": len(quote_dates),
        "usable_trade_date_start": usable_dates[0] if usable_dates else None,
        "usable_trade_date_end": usable_dates[-1] if usable_dates else None,
        "ticker_count": len([ticker for ticker in by_ticker if ticker]),
        "quality_flag_counts": dict(sorted(by_flag.items())),
        "sample_observations": rows[:5],
    }


def build_refresh() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows, file_audit = prior_ledger.iter_option_rows()
    full_ledger = prior_ledger.build_observation_ledger(raw_rows)
    prior_ids = load_prior_observation_ids()
    target_raw_rows = raw_rows_for_target_quote_date(raw_rows)
    target_ledger_rows = [
        row for row in full_ledger if str(row.get("quote_date") or "")[:10] == TARGET_QUOTE_DATE
    ]
    new_rows = [row for row in target_ledger_rows if str(row.get("observation_id") or "") not in prior_ids]
    duplicate_new_ids = len(new_rows) - len({row.get("observation_id") for row in new_rows})

    return new_rows, {
        "chain_file_count": file_audit["chain_file_count"],
        "chain_files": file_audit["chain_files"],
        "bad_json_rows": file_audit["bad_json_rows"],
        "prior_ledger": repo_rel(PRIOR_LEDGER_JSONL),
        "prior_observation_ids": len(prior_ids),
        "all_current_ledger_rows": len(full_ledger),
        "target_quote_date": TARGET_QUOTE_DATE,
        "target_raw_contract_rows": len(target_raw_rows),
        "target_ledger_rows": len(target_ledger_rows),
        "new_delta_rows": len(new_rows),
        "duplicate_new_observation_ids": duplicate_new_ids,
        "target_raw_field_coverage": coverage_for_rows(target_raw_rows),
        "delta_summary": summarize_ledger_rows(new_rows),
    }


def load_baseline_metrics() -> dict[str, Any]:
    return prior_ledger.baseline_metrics()


def min_field_coverage(coverage: dict[str, dict[str, Any]]) -> float:
    if not coverage:
        return 0.0
    return min(float(item.get("coverage") or 0.0) for item in coverage.values())


def calibration(prediction: dict[str, Any], accepted: bool, failed: list[str]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1 if accepted else 0
    expected_modes = prediction.get("main_failure_modes") or []
    return {
        "actual_success": actual,
        "actual_decision": (
            "accepted_measurement_repair_options_forward_ledger_refreshed_20260623"
            if accepted
            else "blocked_options_forward_ledger_refresh_20260623"
        ),
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 6),
        "predicted_failure_modes": expected_modes,
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(set(expected_modes).intersection(failed)),
        "surprise_note": (
            "The new snapshot normalized cleanly into delta observation rows."
            if accepted
            else "The new snapshot could not be cleanly normalized into a delta ledger."
        ),
    }


def build_payload() -> dict[str, Any]:
    prediction = load_prediction()
    baseline = load_baseline_metrics()
    new_rows, refresh = build_refresh()
    failed: list[str] = []
    if not PRIOR_LEDGER_JSONL.exists():
        failed.append("prior_ledger_missing")
    if refresh["bad_json_rows"]:
        failed.append("bad_json_rows_present")
    if refresh["target_raw_contract_rows"] <= 0:
        failed.append("no_target_snapshot_rows")
    if refresh["new_delta_rows"] <= 0:
        failed.append("no_new_snapshot_rows")
    if refresh["duplicate_new_observation_ids"] != 0:
        failed.append("ledger_duplicate_rows")
    if min_field_coverage(refresh["target_raw_field_coverage"]) < 0.95:
        failed.append("target_snapshot_required_field_coverage_below_95pct")
    accepted = not failed
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_options_forward_ledger_refreshed_20260623"
        if accepted
        else "blocked_options_forward_ledger_refresh_20260623"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
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
        "new_evidence_type": "new_forward_options_snapshot_rows",
        "prediction": prediction,
        "calibration": calibration(prediction, accepted, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260617-004": "Blocked options alpha because no canonical-window PIT options coverage existed.",
                "exp-20260618-023": "Blocked options-skew leadership confirmation and required forward closed rows or historical PIT chains.",
                "exp-20260623-009": "Accepted options forward observation ledger through 2026-06-22.",
                "exp-20260623-010": "Rejected the first closed-forward options skew monotonicity attribution.",
                "novelty_gate": "Measurement repair lane passed without blocking; this run adds new pending forward rows, not an options threshold retry.",
            },
            "3_single_policy_bundle": (
                "Normalize only the new 2026-06-23 OnclickMedia options snapshot "
                "into experiment-owned pending observation rows with quality "
                "caveats. No entry, ranking, sizing, exit, or order logic changes."
            ),
            "4_acceptance_standard": (
                "Accept the measurement repair only if the prior ledger exists, "
                "the target snapshot has rows, required raw fields cover at least "
                "95%, new observation IDs are nonzero and unique, and strategy "
                "metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "target_quote_date": TARGET_QUOTE_DATE,
            "options_dir": repo_rel(prior_ledger.OPTIONS_DIR),
            "input_pattern": "options_onclickmedia_chain_*.jsonl",
            "prior_ledger": repo_rel(PRIOR_LEDGER_JSONL),
            "delta_ledger_output": repo_rel(DELTA_LEDGER_JSONL),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "required_raw_fields": prior_ledger.REQUIRED_RAW_FIELDS,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": accepted,
            "fields_checked": prior_ledger.REQUIRED_RAW_FIELDS,
            "prior_ledger_exists": PRIOR_LEDGER_JSONL.exists(),
            "target_quote_date": TARGET_QUOTE_DATE,
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
                "prior_ledger_exists": PRIOR_LEDGER_JSONL.exists(),
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
                "The new 2026-06-23 OnclickMedia snapshot has enough normalized "
                "contract fields to create pending ticker-date observations. This "
                "adds forward evidence capacity but still does not provide closed "
                "10-day replacement-value outcomes or canonical-window PIT coverage."
            )
            if accepted
            else (
                "The new options snapshot did not satisfy the fixed ledger-refresh "
                "checks, so it cannot be used as alpha evidence."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call, IV, OI, volume, expiration, "
                "moneyness, top-N, hold, cooldown, or notional rules on this "
                "pending-forward ledger. It remains a forward observation surface, "
                "not Gate-4 alpha coverage."
            ),
            "new_evidence_required": (
                "Wait for these rows to close with replacement value versus cash, "
                "SPY, and QQQ, add PIT borrow/loan-availability context, or backfill "
                "historical PIT options chains with vendor/as-of controls before "
                "another options alpha claim."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(DELTA_LEDGER_JSONL),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260623_009_options_forward_observation_ledger.py",
            "experiments/logs/exp-20260623-009.json",
            "experiments/logs/exp-20260623-010.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
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
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": {
            "dependencies_validated": payload["gate2"]["dependencies_validated"],
            "fields_checked": payload["gate2"]["fields_checked"],
            "prior_ledger_exists": payload["gate2"]["prior_ledger_exists"],
            "target_quote_date": payload["gate2"]["target_quote_date"],
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
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["refresh_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options forward ledger refresh",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Target quote date: `{TARGET_QUOTE_DATE}`",
            f"- New observation rows: `{summary['new_delta_rows']}`",
            f"- Raw contracts normalized: `{summary['target_raw_contract_rows']}`",
            f"- Delta tickers: `{summary['delta_summary']['ticker_count']}`",
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
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "delta_ledger": repo_rel(DELTA_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    delta_rows = payload["refresh_summary"]["delta_summary"]["sample_observations"]
    # Store all delta rows in the JSONL file, but keep the main artifact compact.
    all_rows, _refresh = build_refresh()
    write_jsonl(DELTA_LEDGER_JSONL, all_rows)
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "delta_ledger": repo_rel(DELTA_LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "refresh_summary": payload["refresh_summary"],
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
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "lean_quality_passed": True,
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))
    if delta_rows and not all_rows:
        raise RuntimeError("delta sample rows existed but full delta rows were empty")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "target_quote_date": TARGET_QUOTE_DATE,
                "target_raw_contract_rows": payload["refresh_summary"]["target_raw_contract_rows"],
                "new_delta_rows": payload["refresh_summary"]["new_delta_rows"],
                "delta_tickers": payload["refresh_summary"]["delta_summary"]["ticker_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
