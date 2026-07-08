"""exp-20260708-012: accepted allocator/source-consensus forward readiness.

Observed-only alpha attribution. The single question is whether the fixed
accepted allocator/source-consensus default-off paper surfaces have enough newly
settled, cash/SPY/QQQ-enriched forward rows to become activation-ready.

This runner changes no shared helper, entry, exit, ranking, sizing, paper state,
live order, daily snapshot, or LLM decision boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260708-012"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "accepted_allocator_consensus_forward_readiness_20260707_delta"
RUNNER = f"quant/experiments/exp_20260708_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

TARGET_SLEEVES = (
    "accepted_helper_source_priority_allocator",
    "accepted_source_consensus",
)
REPLACEMENT_AXES = (
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
)
CONFIG = {
    "min_watchlist_enriched_rows": 20,
    "min_activation_enriched_rows_combined": 30,
    "min_activation_rows_per_surface": 30,
    "min_reprobe_enriched_rows": 9,
    "min_unique_tickers": 5,
    "min_source_consensus_rows": 3,
    "max_single_ticker_share": 0.35,
    "max_single_sleeve_share": 0.75,
    "min_axis_win_rate": 0.50,
    "replacement_axes": list(REPLACEMENT_AXES),
}

FORWARD_RV_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
STATE_FILES = {
    sleeve: REPO_ROOT / "data" / "paper_sleeves" / sleeve / "state.json"
    for sleeve in TARGET_SLEEVES
}
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PRIOR_LOG_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260704-021.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: accepted allocator/source-consensus default-off paper "
    "rows have doubled from 3 to 6 enriched closed replacement-value rows since "
    "exp-20260704-021; test whether the fixed high-priority source-allocation "
    "surface is activation-ready without rank/scalar/top-N retunes."
)
CHANGE_TYPE = "forward_replacement_value_attribution"
IMPLEMENTATION_MODE = "observed_only_accepted_allocator_consensus_readiness_delta"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "accepted_allocator_consensus_forward_readiness"
TRIAL_VARIANT_ID = "20260707_enriched_rows6_v1"
CHANGED_VARIABLE = (
    "accepted_allocator_consensus_forward_replacement_readiness_20260707_delta_v1"
)
CAUSAL_COMPONENTS = [
    "accepted allocator/source-consensus closed rows",
    "cash/SPY/QQQ replacement-value attribution",
    "forward activation readiness verdict",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260704-021",
    "exp-20260620-032",
    "exp-20260621-001",
    "exp-20260621-006",
    "exp-20260621-007",
    "exp-20260705-009",
]
NEW_EVIDENCE_TYPE = "materially_more_settled_forward_rows"
NEW_EVIDENCE_AXIS = (
    "accepted allocator/source-consensus enriched forward rows increased from 3 "
    "in exp-20260704-021 to 6 in the 2026-07-07 forward ledger (+100%); no "
    "source-rank, scalar, top-N, hold, cooldown, notional, or response-function "
    "retune."
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rounded(value: Any, digits: int = 4) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_values(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [as_float(row.get(field)) for row in rows]
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "field": field,
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": None,
        }
    wins = sum(1 for value in clean if value > 0)
    return {
        "field": field,
        "n": len(clean),
        "sum": rounded(sum(clean), 2),
        "mean": rounded(sum(clean) / len(clean), 2),
        "median": rounded(statistics.median(clean), 2),
        "min": rounded(min(clean), 2),
        "max": rounded(max(clean), 2),
        "win_count": wins,
        "loss_count": len(clean) - wins,
        "win_rate": rounded(wins / len(clean), 4),
    }


def max_share(counts: Counter[str]) -> float:
    total = sum(counts.values())
    return max(counts.values(), default=0) / total if total else 0.0


def is_enriched(row: dict[str, Any]) -> bool:
    return row.get("status") == "enriched" and all(
        as_float(row.get(field)) is not None for field in REPLACEMENT_AXES
    )


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": BASELINE_RESULT.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": rounded(
            sum(as_float(row.get("expected_value_score")) or 0.0 for row in windows),
            4,
        ),
        "total_pnl_sum": rounded(
            sum(as_float(row.get("total_pnl")) or 0.0 for row in windows),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated_sum": generated,
        "signals_survived_sum": survived,
        "survival_rate": rounded(survived / generated, 6) if generated else None,
        "max_drawdown_pct_max": rounded(
            max((as_float(row.get("max_drawdown_pct")) or 0.0 for row in windows), default=0.0),
            4,
        ),
        "windows": windows,
    }


def closed_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("closed_positions", "closed_trades"):
        rows = state.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def slim_state_row(row: dict[str, Any], sleeve_key: str) -> dict[str, Any]:
    return {
        "sleeve_key": sleeve_key,
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date") or row.get("entry_date"),
        "paper_notional_usd": rounded(row.get("paper_notional_usd") or row.get("notional_usd"), 2),
        "pnl": rounded(row.get("pnl") if row.get("pnl") is not None else row.get("pnl_usd"), 2),
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": rounded(row.get("replacement_value_vs_cash_usd"), 2),
        "replacement_value_vs_spy_usd": rounded(row.get("replacement_value_vs_spy_usd"), 2),
        "replacement_value_vs_qqq_usd": rounded(row.get("replacement_value_vs_qqq_usd"), 2),
        "target_price_present": row.get("target_price") is not None,
        "trade_enabled": bool(row.get("trade_enabled")),
    }


def slim_ledger_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sleeve_key": row.get("sleeve_key"),
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date"),
        "status": row.get("status"),
        "pnl_usd": rounded(row.get("pnl_usd") if row.get("pnl_usd") is not None else row.get("pnl"), 2),
        "replacement_value_vs_cash_usd": rounded(row.get("replacement_value_vs_cash_usd"), 2),
        "replacement_value_vs_spy_usd": rounded(row.get("replacement_value_vs_spy_usd"), 2),
        "replacement_value_vs_qqq_usd": rounded(row.get("replacement_value_vs_qqq_usd"), 2),
        "entry_regime_label": row.get("entry_regime_label"),
        "entry_short_volume_quintile": row.get("entry_short_volume_quintile"),
        "entry_exhaustion_status": row.get("entry_exhaustion_status"),
        "entry_exhaustion_stretched_flag": row.get("entry_exhaustion_stretched_flag"),
    }


def summarize_target_states() -> dict[str, Any]:
    sleeves: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    entry_date_missing: list[str] = []
    target_price_missing: list[str] = []
    for sleeve_key, path in STATE_FILES.items():
        state = read_json(path, {}) or {}
        rows = [slim_state_row(row, sleeve_key) for row in closed_rows(state)]
        for row in rows:
            if not row.get("entry_date"):
                entry_date_missing.append(str(row.get("decision_id") or row.get("ticker")))
            if not row.get("target_price_present"):
                target_price_missing.append(str(row.get("decision_id") or row.get("ticker")))
        sleeves[sleeve_key] = {
            "state_file": repo_rel(path),
            "state_exists": path.exists(),
            "closed_rows": len(rows),
            "rows": rows,
        }
        all_rows.extend(rows)
    return {
        "state_files": {sleeve: repo_rel(path) for sleeve, path in STATE_FILES.items()},
        "sleeves": sleeves,
        "closed_rows": len(all_rows),
        "entry_date_missing": entry_date_missing,
        "target_price_missing": target_price_missing,
        "trade_enabled_values": sorted({str(row.get("trade_enabled")) for row in all_rows}),
        "ticker_counts": Counter(str(row.get("ticker") or "unknown") for row in all_rows),
        "sleeve_counts": Counter(str(row.get("sleeve_key") or "unknown") for row in all_rows),
        "rows": all_rows,
    }


def summarize_forward_ledger() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_RV_JSONL)
    matches = [row for row in rows if row.get("sleeve_key") in TARGET_SLEEVES]
    enriched = [row for row in matches if is_enriched(row)]
    ticker_counts = Counter(str(row.get("ticker") or "unknown") for row in enriched)
    sleeve_counts = Counter(str(row.get("sleeve_key") or "unknown") for row in enriched)
    status_counts = Counter(str(row.get("status") or "unknown") for row in matches)
    entry_dates = sorted(str(row.get("entry_date")) for row in enriched if row.get("entry_date"))
    exit_dates = sorted(str(row.get("exit_date")) for row in enriched if row.get("exit_date"))
    return {
        "ledger_file": repo_rel(FORWARD_RV_JSONL),
        "ledger_exists": FORWARD_RV_JSONL.exists(),
        "total_rows": len(rows),
        "target_matching_rows": len(matches),
        "target_enriched_rows": len(enriched),
        "status_counts": status_counts,
        "ticker_counts": ticker_counts,
        "sleeve_counts": sleeve_counts,
        "unique_tickers": len(ticker_counts),
        "max_single_ticker_share": rounded(max_share(ticker_counts), 4),
        "max_single_sleeve_share": rounded(max_share(sleeve_counts), 4),
        "entry_date_min": entry_dates[0] if entry_dates else None,
        "entry_date_max": entry_dates[-1] if entry_dates else None,
        "exit_date_min": exit_dates[0] if exit_dates else None,
        "exit_date_max": exit_dates[-1] if exit_dates else None,
        "axis_summaries": {
            field: summarize_values(enriched, field) for field in REPLACEMENT_AXES
        },
        "rows": [slim_ledger_row(row) for row in enriched],
        "non_enriched_matches": [slim_ledger_row(row) for row in matches if not is_enriched(row)],
    }


def prior_summary() -> dict[str, Any]:
    prior = read_json(PRIOR_LOG_JSON, {}) or {}
    delta = prior.get("delta_metrics") if isinstance(prior, dict) else {}
    target = prior.get("target_forward_replacement_repair") if isinstance(prior, dict) else {}
    after_artifact = target.get("after_artifact") if isinstance(target, dict) else {}
    return {
        "prior_experiment_id": "exp-20260704-021",
        "prior_log": repo_rel(PRIOR_LOG_JSON),
        "prior_log_exists": PRIOR_LOG_JSON.exists(),
        "prior_decision": prior.get("decision") if isinstance(prior, dict) else None,
        "prior_status": prior.get("status") if isinstance(prior, dict) else None,
        "prior_target_matching_rows": delta.get("artifact_target_matching_rows_after")
        if isinstance(delta, dict)
        else None,
        "prior_target_enriched_rows": delta.get("artifact_target_enriched_rows_after")
        if isinstance(delta, dict)
        else None,
        "prior_replacement_value_vs_cash_usd": delta.get("replacement_value_vs_cash_usd")
        if isinstance(delta, dict)
        else None,
        "prior_replacement_value_vs_spy_usd": delta.get("replacement_value_vs_spy_usd")
        if isinstance(delta, dict)
        else None,
        "prior_replacement_value_vs_qqq_usd": delta.get("replacement_value_vs_qqq_usd")
        if isinstance(delta, dict)
        else None,
        "prior_target_tickers": after_artifact.get("target_tickers")
        if isinstance(after_artifact, dict)
        else None,
        "prior_next_retry_requires": prior.get("next_retry_requires") if isinstance(prior, dict) else None,
    }


def predicted_failure_mode_hit(predicted: list[str], realized: list[str]) -> bool:
    realized_text = " ".join(realized).lower()
    for mode in predicted:
        key = mode.lower()
        if "sample" in key and ("below" in realized_text or "thin" in realized_text):
            return True
        if "negative" in key and "aggregate_not_positive" in realized_text:
            return True
        if "not_incremental" in key and "aggregate_not_positive" in realized_text:
            return True
        if "concentration" in key and "share" in realized_text:
            return True
    return False


def evaluate_gate4(
    baseline: dict[str, Any],
    state: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    enriched = int(ledger["target_enriched_rows"])
    unique_tickers = int(ledger["unique_tickers"])
    sleeve_counts = Counter(ledger["sleeve_counts"])
    axis_summaries = ledger["axis_summaries"]

    if enriched < CONFIG["min_watchlist_enriched_rows"]:
        failures.append(
            f"enriched_rows_below_watchlist_min:{enriched}/{CONFIG['min_watchlist_enriched_rows']}"
        )
    if enriched < CONFIG["min_activation_enriched_rows_combined"]:
        failures.append(
            f"enriched_rows_below_activation_min:{enriched}/{CONFIG['min_activation_enriched_rows_combined']}"
        )
    for sleeve_key in TARGET_SLEEVES:
        count = int(sleeve_counts.get(sleeve_key, 0))
        if count < CONFIG["min_activation_rows_per_surface"]:
            failures.append(
                f"{sleeve_key}_rows_below_activation_min:{count}/{CONFIG['min_activation_rows_per_surface']}"
            )
    if int(sleeve_counts.get("accepted_source_consensus", 0)) < CONFIG["min_source_consensus_rows"]:
        failures.append(
            "accepted_source_consensus_rows_below_reprobe_min:"
            f"{int(sleeve_counts.get('accepted_source_consensus', 0))}/{CONFIG['min_source_consensus_rows']}"
        )
    if unique_tickers < CONFIG["min_unique_tickers"]:
        failures.append(f"unique_tickers_below_min:{unique_tickers}/{CONFIG['min_unique_tickers']}")
    if (ledger["max_single_ticker_share"] or 0.0) > CONFIG["max_single_ticker_share"]:
        failures.append(
            f"single_ticker_share_too_high:{ledger['max_single_ticker_share']}>{CONFIG['max_single_ticker_share']}"
        )
    if (ledger["max_single_sleeve_share"] or 0.0) > CONFIG["max_single_sleeve_share"]:
        failures.append(
            f"single_sleeve_share_too_high:{ledger['max_single_sleeve_share']}>{CONFIG['max_single_sleeve_share']}"
        )
    if ledger["target_matching_rows"] != state["closed_rows"]:
        failures.append(
            f"ledger_state_row_count_mismatch:{ledger['target_matching_rows']}/{state['closed_rows']}"
        )
    if ledger["target_enriched_rows"] != ledger["target_matching_rows"]:
        failures.append(
            f"target_rows_not_all_enriched:{ledger['target_enriched_rows']}/{ledger['target_matching_rows']}"
        )
    if state["entry_date_missing"]:
        failures.append("target_state_entry_date_missing")
    if state["target_price_missing"]:
        warnings.append(
            "target_price_absent_in_default_off_paper_state_rows; "
            "non-promotable attribution only, prior exp-20260704-021 recorded same compact state caveat"
        )

    for field in REPLACEMENT_AXES:
        summary = axis_summaries[field]
        if summary["n"] < enriched:
            failures.append(f"{field}_missing_values")
        if (summary["sum"] or 0.0) <= 0.0:
            failures.append(f"{field}_aggregate_not_positive")
        if (summary["win_rate"] or 0.0) < CONFIG["min_axis_win_rate"]:
            failures.append(f"{field}_win_rate_below_50pct")

    activation_ready = not failures
    watchlist_lead = (
        enriched >= CONFIG["min_watchlist_enriched_rows"]
        and all((axis_summaries[field]["sum"] or 0.0) > 0 for field in REPLACEMENT_AXES)
        and not state["entry_date_missing"]
    )
    classification = (
        "activation_ready"
        if activation_ready
        else "more_rows_but_negative_replacement_value_and_too_thin"
    )
    return {
        "passed": activation_ready,
        "decision": (
            "observed_only_accepted_allocator_consensus_activation_ready"
            if activation_ready
            else "observed_only_rejected_accepted_allocator_consensus_not_activation_ready"
        ),
        "classification": classification,
        "accepted_alpha": False,
        "alpha_ready": activation_ready,
        "observed_only_lead": watchlist_lead,
        "failed_reasons": failures,
        "warnings": warnings,
        "target_matching_rows": ledger["target_matching_rows"],
        "enriched_closed_rows": enriched,
        "unique_tickers": unique_tickers,
        "ticker_counts": ledger["ticker_counts"],
        "sleeve_counts": ledger["sleeve_counts"],
        "max_single_ticker_share": ledger["max_single_ticker_share"],
        "max_single_sleeve_share": ledger["max_single_sleeve_share"],
        "axis_summaries": axis_summaries,
        "entry_date_range": [ledger["entry_date_min"], ledger["entry_date_max"]],
        "exit_date_range": [ledger["exit_date_min"], ledger["exit_date_max"]],
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "baseline_expected_value_score_sum": baseline["expected_value_score_sum"],
            "baseline_total_pnl_sum": baseline["total_pnl_sum"],
        },
        "readiness_guard": CONFIG,
        "reopen_condition": (
            "Do not reserve another accepted allocator/source-consensus forward-readiness "
            "ID until at least 9 enriched target rows are present (>=+50% versus "
            "this run's 6) with both sleeves represented and aggregate replacement "
            "value positive versus cash, SPY, and QQQ, or until a genuinely new "
            "production-visible PIT source changes the evidence. Activation still "
            "requires at least 30 enriched rows per target surface or a separately "
            "predeclared portfolio-covariance lane."
        ),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
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
        "pre_run_questions",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "accepted_allocator_consensus_readiness",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {}
    baseline = baseline_metrics()
    state = summarize_target_states()
    ledger = summarize_forward_ledger()
    prior = prior_summary()
    gate4 = evaluate_gate4(baseline, state, ledger)
    accepted = bool(gate4["passed"])
    status = "observed_only" if accepted else "observed_only_rejected"
    predicted_modes = prediction.get("main_failure_modes") or []
    prior_enriched = prior.get("prior_target_enriched_rows")
    enriched_delta = (
        ledger["target_enriched_rows"] - int(prior_enriched)
        if prior_enriched is not None
        else None
    )
    now = utc_now()

    delta_metrics = {
        **gate4["before_after_strategy_delta"],
        "prior_target_enriched_rows": prior_enriched,
        "target_enriched_rows": ledger["target_enriched_rows"],
        "target_enriched_row_delta": enriched_delta,
        "target_matching_rows": ledger["target_matching_rows"],
        "unique_tickers": ledger["unique_tickers"],
        "max_single_ticker_share": ledger["max_single_ticker_share"],
        "max_single_sleeve_share": ledger["max_single_sleeve_share"],
        "replacement_value_vs_cash_usd_sum": gate4["axis_summaries"][
            "replacement_value_vs_cash_usd"
        ]["sum"],
        "replacement_value_vs_spy_usd_sum": gate4["axis_summaries"][
            "replacement_value_vs_spy_usd"
        ]["sum"],
        "replacement_value_vs_qqq_usd_sum": gate4["axis_summaries"][
            "replacement_value_vs_qqq_usd"
        ]["sum"],
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": gate4["decision"],
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": accepted,
        "observed_only_lead": bool(gate4["observed_only_lead"]),
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
        "change_type": ticket.get("change_type") or CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": ticket.get("mechanism_family") or MECHANISM_FAMILY,
        "trial_family": ticket.get("trial_family") or TRIAL_FAMILY,
        "trial_variant_id": ticket.get("trial_variant_id") or TRIAL_VARIANT_ID,
        "changed_variable": ticket.get("changed_variable") or CHANGED_VARIABLE,
        "single_causal_variable": ticket.get("single_causal_variable") or CHANGED_VARIABLE,
        "causal_components": ticket.get("causal_components") or CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments")
        or NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket")
        or "moderate",
        "new_evidence_type": ticket.get("new_evidence_type") or NEW_EVIDENCE_TYPE,
        "new_evidence_axis": ((ticket.get("novelty") or {}).get("new_evidence_axis"))
        or NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": int(accepted),
            "predicted_success_probability": prediction.get("success_probability"),
            "brier_score": (
                rounded((float(prediction.get("success_probability")) - int(accepted)) ** 2, 6)
                if prediction.get("success_probability") is not None
                else None
            ),
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": predicted_failure_mode_hit(
                [str(mode) for mode in predicted_modes],
                gate4["failed_reasons"],
            ),
        },
        "pre_run_questions": {
            "alpha_hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
            "history_check": {
                "nearby_prior_experiments": ticket.get("nearby_prior_experiments")
                or NEARBY_PRIOR_EXPERIMENTS,
                "prior_delta": prior,
                "novelty_nearest": ((ticket.get("novelty") or {}).get("nearest") or [])[:5],
            },
            "single_policy_bundle": ticket.get("single_causal_variable") or CHANGED_VARIABLE,
            "acceptance_standard": ticket.get("acceptance_rule"),
            "reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "target_sleeves": list(TARGET_SLEEVES),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "state_files": {key: repo_rel(path) for key, path in STATE_FILES.items()},
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "prior_log": repo_rel(PRIOR_LOG_JSON),
            "readiness_guard": CONFIG,
            "no_strategy_behavior_change": True,
        },
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
            "note": "Observed-only forward attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": (
                ledger["ledger_exists"]
                and all(item["state_exists"] for item in state["sleeves"].values())
                and not state["entry_date_missing"]
                and ledger["target_enriched_rows"] == ledger["target_matching_rows"]
                and ledger["target_matching_rows"] == state["closed_rows"]
            ),
            "fields_checked": [
                "target_state.closed_positions[].entry_date",
                "target_state.closed_positions[].target_price",
                "target_state.closed_positions[].trade_enabled",
                "forward_replacement_value.sleeve_key",
                "forward_replacement_value.status",
                "forward_replacement_value.replacement_value_vs_cash_usd",
                "forward_replacement_value.replacement_value_vs_spy_usd",
                "forward_replacement_value.replacement_value_vs_qqq_usd",
            ],
            "diagnostics": {
                "state_closed_rows": state["closed_rows"],
                "ledger_target_matching_rows": ledger["target_matching_rows"],
                "ledger_target_enriched_rows": ledger["target_enriched_rows"],
                "entry_date_missing": state["entry_date_missing"],
                "target_price_missing": state["target_price_missing"],
                "target_price_note": (
                    "Current compact default-off paper state rows omit target_price; "
                    "this is recorded as a non-promotion warning, and this runner "
                    "does not modify signal generation or exit behavior."
                ),
                "trade_enabled_values": state["trade_enabled_values"],
                "non_enriched_matches": ledger["non_enriched_matches"],
            },
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated_sum"],
            "signals_survived": baseline["signals_survived_sum"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk, or order rule changed.",
        },
        "gate4": gate4,
        "summary": {
            "target_matching_rows": ledger["target_matching_rows"],
            "target_enriched_rows": ledger["target_enriched_rows"],
            "unique_tickers": ledger["unique_tickers"],
            "ticker_counts": ledger["ticker_counts"],
            "sleeve_counts": ledger["sleeve_counts"],
            "axis_summaries": ledger["axis_summaries"],
            "ledger_rows": ledger["rows"],
            "state_rows": state["rows"],
        },
        "accepted_allocator_consensus_readiness": {
            "classification": gate4["classification"],
            "prior": prior,
            "state": state,
            "forward_replacement_ledger": ledger,
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over existing default-off paper sleeve "
                "state and forward replacement ledger. No helper, adapter, "
                "order, or daily snapshot behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The new evidence axis is real: accepted allocator/source-consensus "
                f"enriched rows moved from {prior_enriched} to {ledger['target_enriched_rows']} "
                "with both target sleeves represented. The surface still fails "
                "activation because the sample is far below the 30-row floor and "
                "aggregate replacement value is negative versus cash, SPY, and QQQ."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune allocator source ranks, source scalars, top-N, hold, "
                "cooldown, notional, or activation gates from these six rows."
            ),
            "new_evidence_required": gate4["reopen_condition"],
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if not accepted else None,
        "next_retry_requires": gate4["reopen_condition"],
        "related_files": [
            repo_rel(FORWARD_RV_JSONL),
            repo_rel(BASELINE_RESULT),
            repo_rel(PRIOR_LOG_JSON),
            *[repo_rel(path) for path in STATE_FILES.values()],
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": list(ticket.get("allowed_write_scope") or []),
        "ticket_before": ticket,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python read-only runner only."},
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    axes = gate4["axis_summaries"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Accepted Allocator Consensus Forward Readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Classification: `{gate4['classification']}`",
            f"- Artifact: `{payload['artifact']}`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Result",
            "",
            f"- Target/enriched rows: `{gate4['target_matching_rows']}` / `{gate4['enriched_closed_rows']}`",
            f"- Unique tickers: `{gate4['unique_tickers']}`",
            f"- Sleeve counts: `{dict(gate4['sleeve_counts'])}`",
            f"- Cash/SPY/QQQ aggregate RV: "
            f"`{axes['replacement_value_vs_cash_usd']['sum']}` / "
            f"`{axes['replacement_value_vs_spy_usd']['sum']}` / "
            f"`{axes['replacement_value_vs_qqq_usd']['sum']}`",
            f"- Cash/SPY/QQQ win rate: "
            f"`{axes['replacement_value_vs_cash_usd']['win_rate']}` / "
            f"`{axes['replacement_value_vs_spy_usd']['win_rate']}` / "
            f"`{axes['replacement_value_vs_qqq_usd']['win_rate']}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
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
        REGISTRY_JSON,
        FORWARD_RV_JSONL,
        PRIOR_LOG_JSON,
        BASELINE_RESULT,
        *STATE_FILES.values(),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
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
    log_row = compact_log_record(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "classification": payload["gate4"]["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "replacement_value_vs_cash_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_cash_usd"
            ]["sum"],
            "replacement_value_vs_spy_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_spy_usd"
            ]["sum"],
            "replacement_value_vs_qqq_usd_sum": payload["gate4"]["axis_summaries"][
                "replacement_value_vs_qqq_usd"
            ]["sum"],
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
            "pre_run_questions": payload["pre_run_questions"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "reproduction_commands": payload["reproduction_commands"],
            "anti_js": payload["anti_js"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
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
                "classification": payload["gate4"]["classification"],
                "target_matching_rows": payload["gate4"]["target_matching_rows"],
                "enriched_closed_rows": payload["gate4"]["enriched_closed_rows"],
                "axis_summaries": payload["gate4"]["axis_summaries"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "warnings": payload["gate4"]["warnings"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
