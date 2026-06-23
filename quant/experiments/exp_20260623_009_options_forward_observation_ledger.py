"""exp-20260623-009: options forward observation ledger repair.

Prior options alpha attempts were blocked because local OnclickMedia chains are
forward-collected only and do not cover the canonical fixed windows. This
measurement repair normalizes the existing forward snapshots into an
experiment-owned observation ledger with PIT usability and quality caveats.

No strategy, ranking, sizing, exit, order, watchlist, LLM, or production daily
collector behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-009"
OWNER = "alpha-explore"
SLUG = "options_forward_observation_ledger"
RUNNER = f"quant/experiments/exp_20260623_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_009_{SLUG}.json"
LEDGER_JSONL = DATA_DIR / "options_forward_observation_ledger.jsonl"
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
OPTIONS_DIR = REPO_ROOT / "data" / "non_ohlcv"

HYPOTHESIS = (
    "Repair options alpha blocker: OnclickMedia options put-call, volume, "
    "open-interest, and IV-skew may become an orthogonal confirmation signal, "
    "but prior options alpha records are blocked until forward daily snapshots "
    "are normalized into an append-only observation ledger with PIT usability, "
    "vendor-asof caveats, stale-chain/spread controls, and future outcome "
    "placeholders."
)
ALPHA_HYPOTHESIS = (
    "Options put/call, open-interest, volume, and IV skew may identify demand "
    "or protection pressure not visible in OHLCV, but only after forward "
    "ledger rows mature into closed replacement-value outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "onclickmedia_options_forward_observation_ledger_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260617-004", "exp-20260618-023"]
CAUSAL_COMPONENTS = [
    "forward options snapshot normalization",
    "per ticker-date observation ledger",
    "PIT usability and vendor-asof caveats",
    "spread and liquidity quality controls",
    "future outcome placeholders",
    "no strategy behavior change",
]

REQUIRED_RAW_FIELDS = [
    "ticker",
    "quote_date",
    "usable_trade_date",
    "call_put",
    "strike",
    "expiration",
    "implied_vol",
    "volume",
    "open_interest",
    "bid",
    "ask",
    "mid",
    "pit_safe",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
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


def stable_id(parts: list[Any]) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
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


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.72,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "snapshot_schema_inconsistent",
            "ledger_duplicate_rows",
            "quality_controls_too_sparse",
        ],
        "confidence_reason": (
            "Current options snapshots already carry quote_date, usable_trade_date, "
            "PIT-safe flags, bid/ask/mid, volume, open_interest, and liquidity score."
        ),
        "recorded_at": "2026-06-23T06:05:35+00:00",
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(sum(float(window.get("total_pnl") or 0.0) for window in windows), 2),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def iter_option_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = sorted(OPTIONS_DIR.glob("options_onclickmedia_chain_*.jsonl"))
    rows: list[dict[str, Any]] = []
    bad_json = 0
    for path in files:
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    bad_json += 1
                    continue
                ticker = str(row.get("ticker") or "").upper()
                quote_date = str(row.get("quote_date") or row.get("date") or "")[:10]
                usable_trade_date = str(row.get("usable_trade_date") or "")[:10]
                if not ticker or len(quote_date) != 10:
                    continue
                rows.append(
                    {
                        **row,
                        "ticker": ticker,
                        "quote_date": quote_date,
                        "usable_trade_date": usable_trade_date,
                        "source_file": repo_rel(path),
                    }
                )
    return rows, {
        "chain_file_count": len(files),
        "chain_files": [repo_rel(path) for path in files],
        "bad_json_rows": bad_json,
    }


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in REQUIRED_RAW_FIELDS:
        present = sum(1 for row in rows if row.get(field) not in (None, ""))
        out[field] = {
            "present": present,
            "missing": len(rows) - present,
            "coverage": round(present / len(rows), 6) if rows else 0.0,
        }
    return out


def weighted_average(values: list[tuple[float, float]]) -> float | None:
    usable = [(value, weight) for value, weight in values if weight > 0]
    if usable:
        denom = sum(weight for _, weight in usable)
        return sum(value * weight for value, weight in usable) / denom
    plain = [value for value, _ in values]
    if not plain:
        return None
    return sum(plain) / len(plain)


def summarise_contracts(rows: list[dict[str, Any]], option_type: str) -> dict[str, Any]:
    subset = [row for row in rows if str(row.get("call_put") or row.get("type") or "").lower() == option_type]
    volume = sum(int(as_float(row.get("volume")) or 0) for row in subset)
    open_interest = sum(int(as_float(row.get("open_interest")) or 0) for row in subset)
    iv_values: list[tuple[float, float]] = []
    for row in subset:
        iv = as_float(row.get("implied_vol"))
        if iv is None:
            continue
        iv_values.append((iv, float(as_float(row.get("volume")) or 0.0)))
    return {
        "contract_count": len(subset),
        "volume": volume,
        "open_interest": open_interest,
        "volume_weighted_iv": round_or_none(weighted_average(iv_values), 6),
    }


def quality_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    quoted = 0
    liquid = 0
    spread_values: list[float] = []
    wide_spread = 0
    zero_bid_or_ask = 0
    liquidity_scores: list[float] = []
    pit_safe = 0
    vendor_asof = 0
    expirations: set[str] = set()
    retrieved_at_values: list[str] = []
    for row in rows:
        bid = as_float(row.get("bid"))
        ask = as_float(row.get("ask"))
        mid = as_float(row.get("mid") if row.get("mid") is not None else row.get("mark"))
        if bid is not None and ask is not None and mid is not None:
            quoted += 1
            if bid <= 0 or ask <= 0:
                zero_bid_or_ask += 1
            if mid > 0 and ask >= bid:
                spread = (ask - bid) / mid
                spread_values.append(spread)
                if spread > 0.20:
                    wide_spread += 1
        if row.get("option_liquidity_pass") is True:
            liquid += 1
        score = as_float(row.get("option_liquidity_score"))
        if score is not None:
            liquidity_scores.append(score)
        if row.get("pit_safe") is True:
            pit_safe += 1
        if row.get("vendor_asof_available") is True or row.get("vendor_asof"):
            vendor_asof += 1
        expiration = str(row.get("expiration") or row.get("expiry") or "")[:10]
        if len(expiration) == 10:
            expirations.add(expiration)
        retrieved = str(row.get("retrieved_at") or "")
        if retrieved:
            retrieved_at_values.append(retrieved)
    row_count = len(rows)
    spread_values_sorted = sorted(spread_values)
    return {
        "raw_contract_count": row_count,
        "liquid_contract_count": liquid,
        "liquid_contract_rate": round(liquid / row_count, 6) if row_count else 0.0,
        "pit_safe_contract_rate": round(pit_safe / row_count, 6) if row_count else 0.0,
        "vendor_asof_available_rate": round(vendor_asof / row_count, 6) if row_count else 0.0,
        "quoted_contract_count": quoted,
        "zero_bid_or_ask_count": zero_bid_or_ask,
        "avg_spread_pct": round_or_none(sum(spread_values) / len(spread_values), 6)
        if spread_values
        else None,
        "median_spread_pct": round_or_none(median(spread_values_sorted), 6)
        if spread_values_sorted
        else None,
        "wide_spread_contract_count": wide_spread,
        "wide_spread_contract_rate": round(wide_spread / len(spread_values), 6)
        if spread_values
        else None,
        "min_liquidity_score": round_or_none(min(liquidity_scores), 6) if liquidity_scores else None,
        "avg_liquidity_score": round_or_none(sum(liquidity_scores) / len(liquidity_scores), 6)
        if liquidity_scores
        else None,
        "expiration_count": len(expirations),
        "min_expiration": min(expirations) if expirations else None,
        "max_expiration": max(expirations) if expirations else None,
        "first_retrieved_at": min(retrieved_at_values) if retrieved_at_values else None,
        "last_retrieved_at": max(retrieved_at_values) if retrieved_at_values else None,
    }


def quality_flags(summary: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if summary["raw_contract_count"] < 20:
        flags.append("thin_contract_count")
    if summary["liquid_contract_count"] < 10:
        flags.append("thin_liquid_contract_count")
    if summary["pit_safe_contract_rate"] < 1.0:
        flags.append("pit_unsafe_contracts_present")
    if summary["vendor_asof_available_rate"] == 0:
        flags.append("vendor_asof_missing")
    if summary.get("wide_spread_contract_rate") is not None and summary["wide_spread_contract_rate"] > 0.50:
        flags.append("wide_spread_majority")
    if summary["zero_bid_or_ask_count"] > 0:
        flags.append("zero_bid_or_ask_present")
    flags.append("open_interest_reporting_lag_caveat")
    return flags


def build_observation_ledger(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        grouped[(row["ticker"], row["quote_date"], usable)].append(row)

    ledger: list[dict[str, Any]] = []
    for (ticker, quote_date, usable_trade_date), contracts in sorted(grouped.items()):
        calls = summarise_contracts(contracts, "call")
        puts = summarise_contracts(contracts, "put")
        quality = quality_from_rows(contracts)
        put_call_volume_ratio = safe_div(float(puts["volume"]), float(calls["volume"]))
        put_call_oi_ratio = safe_div(float(puts["open_interest"]), float(calls["open_interest"]))
        iv_skew = None
        if puts["volume_weighted_iv"] is not None and calls["volume_weighted_iv"] is not None:
            iv_skew = puts["volume_weighted_iv"] - calls["volume_weighted_iv"]
        flags = quality_flags(quality)
        ledger.append(
            {
                "schema_version": 1,
                "rule_version": CHANGED_VARIABLE,
                "observation_id": stable_id([ticker, quote_date, usable_trade_date, CHANGED_VARIABLE]),
                "source": "onclickmedia_options",
                "ticker": ticker,
                "quote_date": quote_date,
                "usable_trade_date": usable_trade_date or None,
                "alpha_candidate_state": "observation_only_pending_outcome",
                "pit_safe_flag": "forward_collected_next_trade_day_usable",
                "vendor_asof_available": quality["vendor_asof_available_rate"] > 0,
                "vendor_asof_caveat": "vendor_asof_missing" in flags,
                "open_interest_same_day_usable": False,
                "open_interest_lag_caveat": True,
                "raw_contract_count": quality["raw_contract_count"],
                "liquid_contract_count": quality["liquid_contract_count"],
                "liquid_contract_rate": quality["liquid_contract_rate"],
                "pit_safe_contract_rate": quality["pit_safe_contract_rate"],
                "expiration_count": quality["expiration_count"],
                "min_expiration": quality["min_expiration"],
                "max_expiration": quality["max_expiration"],
                "call_volume": calls["volume"],
                "put_volume": puts["volume"],
                "put_call_volume_ratio": round_or_none(put_call_volume_ratio, 6),
                "call_open_interest": calls["open_interest"],
                "put_open_interest": puts["open_interest"],
                "put_call_open_interest_ratio": round_or_none(put_call_oi_ratio, 6),
                "call_volume_weighted_iv": calls["volume_weighted_iv"],
                "put_volume_weighted_iv": puts["volume_weighted_iv"],
                "put_minus_call_volume_weighted_iv": round_or_none(iv_skew, 6),
                "avg_spread_pct": quality["avg_spread_pct"],
                "median_spread_pct": quality["median_spread_pct"],
                "wide_spread_contract_rate": quality["wide_spread_contract_rate"],
                "zero_bid_or_ask_count": quality["zero_bid_or_ask_count"],
                "avg_liquidity_score": quality["avg_liquidity_score"],
                "min_liquidity_score": quality["min_liquidity_score"],
                "first_retrieved_at": quality["first_retrieved_at"],
                "last_retrieved_at": quality["last_retrieved_at"],
                "quality_flags": flags,
                "outcome_status": "pending_forward_close",
                "forward_5d_return_pct": None,
                "forward_10d_return_pct": None,
                "replacement_value_vs_cash_usd": None,
                "replacement_value_vs_spy_usd": None,
                "replacement_value_vs_qqq_usd": None,
            }
        )
    return ledger


def ledger_summary(ledger: list[dict[str, Any]], raw_rows: list[dict[str, Any]], file_audit: dict[str, Any]) -> dict[str, Any]:
    dates = sorted({str(row["quote_date"]) for row in ledger})
    tickers = sorted({str(row["ticker"]) for row in ledger})
    flags: dict[str, int] = defaultdict(int)
    for row in ledger:
        for flag in row.get("quality_flags") or []:
            flags[str(flag)] += 1
    duplicates = len(ledger) - len({row["observation_id"] for row in ledger})
    return {
        "ledger_rows": len(ledger),
        "raw_contract_rows": len(raw_rows),
        "chain_file_count": file_audit["chain_file_count"],
        "bad_json_rows": file_audit["bad_json_rows"],
        "quote_date_start": dates[0] if dates else None,
        "quote_date_end": dates[-1] if dates else None,
        "quote_date_count": len(dates),
        "ticker_count": len(tickers),
        "duplicate_observation_ids": duplicates,
        "quality_flag_counts": dict(sorted(flags.items())),
        "rows_with_pending_outcome": sum(1 for row in ledger if row["outcome_status"] == "pending_forward_close"),
        "vendor_asof_available_rows": sum(1 for row in ledger if row["vendor_asof_available"]),
        "pit_safe_complete_rows": sum(1 for row in ledger if row["pit_safe_contract_rate"] == 1.0),
        "sample_observations": ledger[:10],
        "field_coverage": field_coverage(raw_rows),
    }


def write_ledger(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    predicted = float(prediction.get("success_probability") or 0.0)
    actual = 1 if success else 0
    return {
        "actual_success": actual,
        "actual_decision": (
            "accepted_measurement_repair_options_forward_observation_ledger"
            if success
            else "blocked_options_forward_observation_ledger"
        ),
        "predicted_success_probability": predicted,
        "brier_score": round((predicted - actual) ** 2, 6),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": bool(
            set(prediction.get("main_failure_modes") or []).intersection(failed)
        ),
        "surprise_note": (
            "Existing forward snapshots had enough normalized fields to build the ledger; "
            "the remaining blocker is outcome maturation, not schema shape."
            if success
            else "The current options snapshots were insufficient for a reliable forward ledger."
        ),
    }


def build_payload() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    raw_rows, file_audit = iter_option_rows()
    ledger = build_observation_ledger(raw_rows)
    summary = ledger_summary(ledger, raw_rows, file_audit)
    failed: list[str] = []
    if summary["ledger_rows"] <= 0:
        failed.append("no_ledger_rows")
    if summary["duplicate_observation_ids"] != 0:
        failed.append("ledger_duplicate_rows")
    if summary["bad_json_rows"] != 0:
        failed.append("bad_json_rows_present")
    for field in REQUIRED_RAW_FIELDS:
        coverage = summary["field_coverage"][field]["coverage"]
        if coverage < 0.95:
            failed.append(f"field_{field}_coverage_below_95pct")
    success = not failed
    decision = (
        "accepted_measurement_repair_options_forward_observation_ledger"
        if success
        else "blocked_options_forward_observation_ledger"
    )
    status = "accepted_measurement_repair" if success else "blocked"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": success,
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
        "new_evidence_type": "forward_observation_ledger",
        "prediction": prediction,
        "calibration": calibration(prediction, success, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260617-004": "Blocked options alpha because no canonical-window PIT options coverage existed; required historical PIT backfill or closed forward rows.",
                "exp-20260618-023": "Blocked options-skew leadership confirmation for the same Gate-2 coverage reason; named 20-30 closed forward rows as valid new evidence.",
                "novelty_gate": "Measurement repair lane was not blocked; this run does not retry options thresholds or claim alpha.",
            },
            "3_single_policy_bundle": "Build a per-ticker/date forward options observation ledger with PIT usability, vendor-asof/open-interest caveats, spread controls, and pending outcome placeholders.",
            "4_acceptance_standard": "Accept only if raw snapshot fields validate, the ledger has rows, duplicate observation IDs are zero, and before/after strategy metrics are unchanged.",
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "options_dir": repo_rel(OPTIONS_DIR),
            "input_pattern": "options_onclickmedia_chain_*.jsonl",
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "ledger_output": repo_rel(LEDGER_JSONL),
            "required_raw_fields": REQUIRED_RAW_FIELDS,
            "quality_controls": [
                "pit_safe_contract_rate",
                "vendor_asof_available_rate",
                "open_interest_lag_caveat",
                "liquid_contract_rate",
                "avg_spread_pct",
                "wide_spread_contract_rate",
                "zero_bid_or_ask_count",
            ],
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": success,
            "fields_checked": REQUIRED_RAW_FIELDS,
            "field_coverage": summary["field_coverage"],
            "ledger_rows": summary["ledger_rows"],
            "raw_contract_rows": summary["raw_contract_rows"],
            "quote_date_range": {
                "start": summary["quote_date_start"],
                "end": summary["quote_date_end"],
                "count": summary["quote_date_count"],
            },
            "ticker_count": summary["ticker_count"],
            "entry_date_target_price_note": (
                "No executable entries or target exits are scheduled. The ledger "
                "stores usable_trade_date and pending outcome placeholders only."
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
            "passed": success,
            "decision": decision,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "acceptance_checks": {
                "ledger_rows_positive": summary["ledger_rows"] > 0,
                "duplicate_observation_ids_zero": summary["duplicate_observation_ids"] == 0,
                "bad_json_rows_zero": summary["bad_json_rows"] == 0,
                "required_field_coverage_min": min(
                    item["coverage"] for item in summary["field_coverage"].values()
                )
                if summary["field_coverage"]
                else 0.0,
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
            "ledger_rows_created": summary["ledger_rows"],
            "raw_contract_rows_normalized": summary["raw_contract_rows"],
        },
        "ledger_summary": summary,
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
                "ledger only. The existing daily options snapshot is read-only here; "
                "future promotion still requires shared daily/backtest wiring or "
                "closed forward replacement-value evidence."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Forward options snapshots already contain enough normalized "
                "contract fields to create ticker-date observations, but they remain "
                "forward-only and lack closed outcomes. The repair converts a raw "
                "chain archive into a replayable observation surface without making "
                "an alpha claim."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry options put/call, IV, OI, volume, expiration, "
                "moneyness, top-N, hold, cooldown, or notional rules on the "
                "canonical windows from this ledger. It contains forward observations, "
                "not historical Gate-4 coverage."
            ),
            "new_evidence_required": (
                "Close 20-30 forward ledger observations with replacement value "
                "versus cash, SPY, and QQQ, or backfill PIT-safe historical options "
                "chains with vendor/as-of controls before any options alpha claim."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(LEDGER_JSONL),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260617-004.json",
            "experiments/logs/exp-20260618-023.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }
    return payload, ledger


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "lane": payload["lane"],
        "owner": payload["owner"],
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
            "ledger_rows": payload["gate2"]["ledger_rows"],
            "raw_contract_rows": payload["gate2"]["raw_contract_rows"],
            "quote_date_range": payload["gate2"]["quote_date_range"],
            "ticker_count": payload["gate2"]["ticker_count"],
            "entry_date_target_price_note": payload["gate2"]["entry_date_target_price_note"],
            "failed_reasons": payload["gate2"]["failed_reasons"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "ledger_summary": {
            "ledger_rows": payload["ledger_summary"]["ledger_rows"],
            "raw_contract_rows": payload["ledger_summary"]["raw_contract_rows"],
            "chain_file_count": payload["ledger_summary"]["chain_file_count"],
            "quote_date_start": payload["ledger_summary"]["quote_date_start"],
            "quote_date_end": payload["ledger_summary"]["quote_date_end"],
            "quote_date_count": payload["ledger_summary"]["quote_date_count"],
            "ticker_count": payload["ledger_summary"]["ticker_count"],
            "duplicate_observation_ids": payload["ledger_summary"]["duplicate_observation_ids"],
            "quality_flag_counts": payload["ledger_summary"]["quality_flag_counts"],
            "sample_observations": payload["ledger_summary"]["sample_observations"][:3],
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
    summary = payload["ledger_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: options forward observation ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Ledger rows: `{summary['ledger_rows']}`",
            f"- Raw contracts normalized: `{summary['raw_contract_rows']}`",
            f"- Quote dates: `{summary['quote_date_start']}` to `{summary['quote_date_end']}`",
            f"- Tickers: `{summary['ticker_count']}`",
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
        LEDGER_JSONL,
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
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any], ledger: list[dict[str, Any]]) -> None:
    write_ledger(LEDGER_JSONL, ledger)
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
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "ledger_summary": payload["ledger_summary"],
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
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload, ledger = build_payload()
    persist(payload, ledger)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ledger_rows": payload["ledger_summary"]["ledger_rows"],
                "raw_contract_rows": payload["ledger_summary"]["raw_contract_rows"],
                "quote_date_start": payload["ledger_summary"]["quote_date_start"],
                "quote_date_end": payload["ledger_summary"]["quote_date_end"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
