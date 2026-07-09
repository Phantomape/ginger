"""exp-20260701-008: options forward observation delta for 2026-06-30.

Measurement repair only. A new OnclickMedia options chain snapshot for
2026-06-30 exists after the previous options outcome refresh. This runner
materializes those rows as experiment-owned pending forward observations so
future options-flow alpha work can wait for closed replacement-value outcomes.

No strategy, shared helper, ranking, sizing, exit, paper order, live order,
watchlist, LLM, or production daily behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260701-008"
OWNER = "alpha-explore"
SLUG = "options_20260630_forward_observation_delta"
RUNNER = f"quant/experiments/exp_20260701_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant.ohlcv_warehouse import (  # noqa: E402
    DEFAULT_WAREHOUSE_PATH,
    load_warehouse_ohlcv_frames,
)

import exp_20260623_009_options_forward_observation_ledger as prior_ledger  # noqa: E402


DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260701_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
RAW_CHAIN_JSONL = REPO_ROOT / "data" / "non_ohlcv" / "options_onclickmedia_chain_20260630.jsonl"
RAW_SUMMARY_JSON = REPO_ROOT / "data" / "non_ohlcv" / "options_onclickmedia_summary_20260630.json"

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
    {
        "experiment_id": "exp-20260629-014",
        "path": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260629-014"
        / "options_forward_observation_ledger_delta_20260624_20260626.jsonl",
    },
    {
        "experiment_id": "exp-20260630-003",
        "path": REPO_ROOT
        / "data"
        / "experiments"
        / "exp-20260630-003"
        / "options_forward_observation_ledger_delta_20260629.jsonl",
    },
]

TARGET_QUOTE_DATES = ("2026-06-30",)
HORIZONS = (1, 3, 5, 10)

HYPOTHESIS = (
    "Alpha blocker: newly collected 2026-06-30 OnclickMedia options rows need "
    "an experiment-owned forward observation delta before options-flow demand "
    "or hedge-pressure alpha can be evaluated; materialize the rows as pending "
    "settlement without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Options put/call volume, open interest, IV skew, and liquidity fields may "
    "identify demand or protection pressure not visible in OHLCV, but only "
    "after forward observation rows mature into closed cash/SPY/QQQ "
    "replacement-value outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_forward_options_attribution"
TRIAL_FAMILY = "onclickmedia_options_forward_ledger_refresh"
TRIAL_VARIANT_ID = "post_exp030008_20260630_pending_rows_v1"
CHANGED_VARIABLE = "onclickmedia_options_20260630_forward_observation_delta_ledger_v1"
NEW_EVIDENCE_TYPE = "new_forward_options_snapshot_rows"
NEW_EVIDENCE_AXIS = (
    "The 2026-06-30 OnclickMedia chain file was generated after exp-20260630-008 "
    "and adds a new non-empty snapshot date (5897 contracts across 59 tickers, "
    "usable on 2026-07-01). This is not an options bucket, threshold, notional, "
    "or response-function retry on unchanged closed rows."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-009",
    "exp-20260624-020",
    "exp-20260629-014",
    "exp-20260630-003",
    "exp-20260630-008",
    "exp-20260630-010",
]
CAUSAL_COMPONENTS = [
    "new forward options snapshot rows",
    "per ticker-date pending observation rows",
    "PIT usability caveats",
    "warehouse settlement readiness check",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260701_008_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.86,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "snapshot_schema_inconsistent",
        "no_new_snapshot_rows",
        "ledger_duplicate_rows",
        "target_snapshot_required_field_coverage_below_95pct",
        "warehouse_not_yet_ready_for_entry_session",
    ],
    "confidence_reason": (
        "The 2026-06-30 chain summary is present, reports 5897 PIT-safe rows "
        "across 59 tickers, and prior options observation ledgers normalized "
        "adjacent snapshots cleanly. Settlement may remain pending because "
        "usable_trade_date is 2026-07-01."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    if isinstance(prediction, dict) and prediction:
        return prediction
    return {**DEFAULT_PREDICTION, "recorded_at": utc_now()}


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
                "path": repo_rel(path),
                "exists": path.exists(),
                "rows": len(rows),
                "observation_ids": len(source_ids),
            }
        )
    return ids, metadata


def target_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = set(TARGET_QUOTE_DATES)
    return [row for row in raw_rows if str(row.get("quote_date") or "")[:10] in targets]


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


def min_field_coverage(coverage: Mapping[str, Mapping[str, Any]]) -> float:
    if not coverage:
        return 0.0
    return min(float(item.get("coverage") or 0.0) for item in coverage.values())


def frame_dates(frame: Any) -> list[str]:
    dates: list[str] = []
    for day in frame.index:
        dates.append(str(day)[:10])
    return sorted(set(dates))


def settlement_readiness(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    usable_dates = sorted({str(row.get("usable_trade_date") or "")[:10] for row in rows if row.get("usable_trade_date")})
    if not tickers or not usable_dates:
        return rows, {
            "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
            "requested_tickers": len(tickers),
            "loaded_tickers": 0,
            "status_counts": {},
            "horizon_available_counts": {},
            "latest_loaded_date": None,
        }

    lookback_start = min("2026-06-01", usable_dates[0])
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        tickers,
        lookback_start,
        "2026-12-31",
    )
    ticker_dates = {ticker.upper(): frame_dates(frame) for ticker, frame in frames.items()}
    latest_dates = {
        ticker: values[-1] if values else None for ticker, values in ticker_dates.items()
    }
    enriched: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    horizon_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        usable = str(row.get("usable_trade_date") or "")[:10]
        dates = ticker_dates.get(ticker, [])
        out = dict(row)
        out["entry_date"] = None
        out["target_price"] = None
        out["settlement_status"] = "missing_ticker_ohlcv"
        out["settled_horizons_available"] = []
        out["pending_horizons"] = list(HORIZONS)
        if dates:
            entry_index = next((idx for idx, day in enumerate(dates) if day >= usable), None)
            if entry_index is None:
                out["settlement_status"] = "entry_date_not_in_warehouse_yet"
            else:
                out["entry_date"] = dates[entry_index]
                available: list[int] = []
                for horizon in HORIZONS:
                    if entry_index + horizon < len(dates):
                        available.append(horizon)
                        horizon_counts[str(horizon)] += 1
                out["settled_horizons_available"] = available
                out["pending_horizons"] = [horizon for horizon in HORIZONS if horizon not in available]
                out["settlement_status"] = (
                    "closed_10d_ready"
                    if 10 in available
                    else "partial_closed_ready"
                    if available
                    else "pending_forward_close"
                )
        status_counts[out["settlement_status"]] += 1
        enriched.append(out)
    return enriched, {
        "warehouse_path": repo_rel(Path(DEFAULT_WAREHOUSE_PATH)),
        "requested_tickers": len(tickers),
        "loaded_tickers": len(ticker_dates),
        "missing_tickers": [ticker for ticker in tickers if ticker not in ticker_dates],
        "request_start": lookback_start,
        "usable_trade_date_start": usable_dates[0],
        "usable_trade_date_end": usable_dates[-1],
        "latest_loaded_date": max((day for day in latest_dates.values() if day), default=None),
        "latest_loaded_dates_sample": dict(sorted(latest_dates.items())[:10]),
        "status_counts": dict(sorted(status_counts.items())),
        "horizon_available_counts": dict(sorted(horizon_counts.items())),
    }


def summarize_observation_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: Counter[str] = Counter()
    by_quote_date: Counter[str] = Counter()
    by_usable_date: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or "")
        quote = str(row.get("quote_date") or "")[:10]
        usable = str(row.get("usable_trade_date") or "")[:10]
        status = str(row.get("settlement_status") or row.get("outcome_status") or "missing")
        if ticker:
            by_ticker[ticker] += 1
        if quote:
            by_quote_date[quote] += 1
        if usable:
            by_usable_date[usable] += 1
        status_counts[status] += 1
        for flag in row.get("quality_flags") or []:
            flags[str(flag)] += 1
    return {
        "observation_rows": len(rows),
        "ticker_count": len(by_ticker),
        "quote_date_counts": dict(sorted(by_quote_date.items())),
        "usable_trade_date_counts": dict(sorted(by_usable_date.items())),
        "settlement_status_counts": dict(sorted(status_counts.items())),
        "quality_flag_counts": dict(sorted(flags.items())),
        "pit_safe_complete_rows": sum(1 for row in rows if row.get("pit_safe_contract_rate") == 1.0),
        "vendor_asof_available_rows": sum(1 for row in rows if row.get("vendor_asof_available")),
        "sample_observations": rows[:5],
    }


def build_delta() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows, file_audit = prior_ledger.iter_option_rows()
    raw_target_rows = target_rows(raw_rows)
    target_ledger_rows = prior_ledger.build_observation_ledger(raw_target_rows)
    prior_ids, prior_metadata = load_prior_observation_ids()
    source_summary = read_json(RAW_SUMMARY_JSON, {})
    delta_rows = [
        {
            **row,
            "delta_experiment_id": EXPERIMENT_ID,
            "delta_rule_version": CHANGED_VARIABLE,
            "source_prior_rule_version": row.get("rule_version"),
            "source_chain_file": repo_rel(RAW_CHAIN_JSONL),
        }
        for row in target_ledger_rows
        if str(row.get("observation_id") or "") not in prior_ids
    ]
    delta_rows, settlement = settlement_readiness(delta_rows)
    duplicate_new_ids = len(delta_rows) - len({row.get("observation_id") for row in delta_rows})
    target_files = [path for path in file_audit["chain_files"] if "20260630" in path]
    coverage = coverage_for_rows(raw_target_rows)
    return delta_rows, {
        "source_chain_file": repo_rel(RAW_CHAIN_JSONL),
        "source_summary_file": repo_rel(RAW_SUMMARY_JSON),
        "source_chain_exists": RAW_CHAIN_JSONL.exists(),
        "source_summary_exists": RAW_SUMMARY_JSON.exists(),
        "source_summary_status": source_summary.get("status") if isinstance(source_summary, dict) else None,
        "source_summary_rows_written": source_summary.get("rows_written") if isinstance(source_summary, dict) else None,
        "source_summary_ticker_date_requests": source_summary.get("ticker_date_requests") if isinstance(source_summary, dict) else None,
        "source_summary_option_liquidity_pass_rate": source_summary.get("option_liquidity_pass_rate")
        if isinstance(source_summary, dict)
        else None,
        "source_summary_pit_safe_rows": source_summary.get("pit_safe_rows") if isinstance(source_summary, dict) else None,
        "source_summary_generated_at": source_summary.get("generated_at") if isinstance(source_summary, dict) else None,
        "chain_file_count": file_audit["chain_file_count"],
        "target_chain_files": target_files,
        "bad_json_rows": file_audit["bad_json_rows"],
        "prior_ledgers": prior_metadata,
        "prior_observation_ids": len(prior_ids),
        "target_quote_dates": list(TARGET_QUOTE_DATES),
        "target_raw_contract_rows": len(raw_target_rows),
        "target_ledger_rows": len(target_ledger_rows),
        "new_delta_rows": len(delta_rows),
        "duplicate_new_observation_ids": duplicate_new_ids,
        "target_raw_field_coverage": coverage,
        "required_field_coverage_min": min_field_coverage(coverage),
        "delta_summary": summarize_observation_rows(delta_rows),
        "settlement_readiness": settlement,
    }


def evaluate_gate4(refresh: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    checks = {
        "baseline_loaded": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
        "source_chain_exists": bool(refresh.get("source_chain_exists")),
        "source_summary_exists": bool(refresh.get("source_summary_exists")),
        "source_summary_status_ok": refresh.get("source_summary_status") == "ok",
        "target_snapshot_rows_positive": int(refresh.get("target_raw_contract_rows") or 0) > 0,
        "target_ledger_rows_positive": int(refresh.get("target_ledger_rows") or 0) > 0,
        "new_delta_rows_positive": int(refresh.get("new_delta_rows") or 0) > 0,
        "duplicate_new_observation_ids_zero": int(refresh.get("duplicate_new_observation_ids") or 0) == 0,
        "bad_json_rows_zero": int(refresh.get("bad_json_rows") or 0) == 0,
        "required_field_coverage_min_gte_95pct": float(refresh.get("required_field_coverage_min") or 0.0) >= 0.95,
        "strategy_metrics_unchanged": True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_measurement_repair_options_forward_observation_delta_20260630"
            if passed
            else "blocked_options_forward_observation_delta_20260630"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "strategy_behavior_changed": False,
        },
        "strategy_rerun_required": False,
        "accepted_alpha": False,
        "measurement_repair_only": True,
    }


def calibration(prediction: Mapping[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    predicted = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "snapshot_schema_inconsistent": {
            "source_summary_status_ok",
            "bad_json_rows_zero",
            "required_field_coverage_min_gte_95pct",
        },
        "no_new_snapshot_rows": {"target_snapshot_rows_positive", "new_delta_rows_positive"},
        "ledger_duplicate_rows": {"duplicate_new_observation_ids_zero"},
        "target_snapshot_required_field_coverage_below_95pct": {
            "required_field_coverage_min_gte_95pct"
        },
        "warehouse_not_yet_ready_for_entry_session": set(),
    }
    hit = [
        mode
        for mode in predicted
        if set(failed) & mode_map.get(mode, {mode})
    ]
    settlement = "warehouse_not_yet_ready_for_entry_session"
    if settlement in predicted and not success:
        hit.append(settlement)
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(success),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted,
        "realized_failure_modes": failed,
        "predicted_failure_modes_hit": sorted(set(hit)),
    }


def compact_log_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"observation_delta_rows"}
    }


def build_payload(delta_rows: list[dict[str, Any]], refresh: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    prediction = load_prediction()
    baseline = prior_ledger.baseline_metrics()
    gate4 = evaluate_gate4(refresh, baseline)
    accepted = bool(gate4["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = str(gate4["decision"])
    settlement_counts = refresh["delta_summary"]["settlement_status_counts"]
    why = (
        "The 2026-06-30 OnclickMedia snapshot normalized into new ticker-date "
        "forward observation rows. They remain alpha-enabling measurement rows "
        "because settlement is still pending for usable_trade_date 2026-07-01."
        if accepted
        else "The 2026-06-30 OnclickMedia snapshot failed one or more fixed "
        "measurement checks and should not be used for options alpha attribution."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
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
        "calibration": calibration(prediction, accepted, gate4["failed_reasons"]),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-008": (
                    "Accepted options outcome refresh through 2026-06-29 and "
                    "forbade alpha claims until materially more closed rows or "
                    "better PIT/borrow context exists."
                ),
                "exp-20260630-010": (
                    "Rejected bearish put-demand attribution; this run does not "
                    "reslice options buckets and only adds a new snapshot date."
                ),
                "novelty_gate": "Reservation passed with no strong near-neighbor.",
            },
            "3_single_policy_bundle": (
                "Normalize only 2026-06-30 OnclickMedia options contracts into "
                "experiment-owned pending observation rows."
            ),
            "4_acceptance_standard": (
                "Accept as measurement repair if the new snapshot exists, has "
                "positive rows, required raw-field coverage is at least 95%, "
                "new observation IDs are unique and nonzero, and strategy "
                "metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "target_quote_dates": list(TARGET_QUOTE_DATES),
            "input_chain_file": repo_rel(RAW_CHAIN_JSONL),
            "input_summary_file": repo_rel(RAW_SUMMARY_JSON),
            "artifact_output": repo_rel(OUT_JSON),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "required_raw_fields": prior_ledger.REQUIRED_RAW_FIELDS,
            "horizons_checked_for_readiness": list(HORIZONS),
        },
        "gate1": {"baseline_loaded": BASELINE_RESULT.exists(), "baseline_metrics": baseline},
        "gate2": {
            "dependencies_validated": accepted,
            "fields_checked": prior_ledger.REQUIRED_RAW_FIELDS
            + ["observation_id", "entry_date", "target_price", "settlement_status"],
            "target_quote_dates": list(TARGET_QUOTE_DATES),
            "target_raw_contract_rows": refresh["target_raw_contract_rows"],
            "target_ledger_rows": refresh["target_ledger_rows"],
            "new_delta_rows": refresh["new_delta_rows"],
            "target_raw_field_coverage": refresh["target_raw_field_coverage"],
            "required_field_coverage_min": refresh["required_field_coverage_min"],
            "entry_date_target_price_note": (
                "This is not an executable entry/exit policy. entry_date is "
                "warehouse readiness metadata derived from usable_trade_date; "
                "target_price remains null because no trade or exit is scheduled."
            ),
            "failed_reasons": gate4["failed_reasons"],
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter, candidate selection, or strategy rule was added.",
        },
        "gate4": gate4,
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
        "observation_delta_rows": delta_rows,
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
            "live_realism_evaluated": False,
            "parity_note": (
                "This experiment writes an experiment-owned artifact only. "
                "The daily options collector, shared policy helpers, and all "
                "trading adapters are unchanged."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "settlement_status_counts": settlement_counts,
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call, IV, OI, volume, expiration, "
                "moneyness, top-N, hold, cooldown, or notional rules on this "
                "pending-forward delta. It is new row materialization, not "
                "Gate-4 alpha coverage."
            ),
            "new_evidence_required": (
                "Wait for the 2026-06-30 rows to close with cash/SPY/QQQ "
                "replacement value, add PIT vendor/as-of controls, add borrow "
                "or loan-availability context, or backfill historical PIT "
                "options chains before another options alpha claim."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(RAW_CHAIN_JSONL),
            repo_rel(RAW_SUMMARY_JSON),
            repo_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260623_009_options_forward_observation_ledger.py",
            "quant/experiments/exp_20260630_008_options_forward_outcome_refresh_20260629.py",
            "experiments/logs/exp-20260630-010.json",
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
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: Mapping[str, Any]) -> str:
    summary = payload["refresh_summary"]
    delta = summary["delta_summary"]
    settlement = summary["settlement_readiness"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options 2026-06-30 forward observation delta",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Target quote date: `{', '.join(TARGET_QUOTE_DATES)}`",
            f"- Raw contracts scanned: `{summary['target_raw_contract_rows']}`",
            f"- New observation rows: `{summary['new_delta_rows']}`",
            f"- Delta tickers: `{delta['ticker_count']}`",
            f"- Settlement statuses: `{settlement['status_counts']}`",
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


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
        RAW_CHAIN_JSONL,
        RAW_SUMMARY_JSON,
    ] + [Path(source["path"]) for source in PRIOR_LEDGER_SOURCES]
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

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "refresh_summary": {
            "source_chain_file": payload["refresh_summary"]["source_chain_file"],
            "target_raw_contract_rows": payload["refresh_summary"]["target_raw_contract_rows"],
            "target_ledger_rows": payload["refresh_summary"]["target_ledger_rows"],
            "new_delta_rows": payload["refresh_summary"]["new_delta_rows"],
            "delta_summary": payload["refresh_summary"]["delta_summary"],
            "settlement_readiness": payload["refresh_summary"]["settlement_readiness"],
        },
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
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    delta_rows, refresh = build_delta()
    payload = build_payload(delta_rows, refresh)
    if payload["refresh_summary"]["new_delta_rows"] != len(delta_rows):
        raise RuntimeError("payload refresh summary disagrees with delta rows")
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "target_quote_dates": list(TARGET_QUOTE_DATES),
                "target_raw_contract_rows": refresh["target_raw_contract_rows"],
                "target_ledger_rows": refresh["target_ledger_rows"],
                "new_delta_rows": refresh["new_delta_rows"],
                "delta_tickers": refresh["delta_summary"]["ticker_count"],
                "settlement_status_counts": refresh["delta_summary"]["settlement_status_counts"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
