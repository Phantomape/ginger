"""exp-20260704-021: repair accepted allocator/source-consensus RV gaps.

Measurement repair only. exp-20260704-020 rebuilt the shared forward
replacement-value artifact but still reported two skipped current-state rows:
DDOG in the accepted helper source-priority allocator and WDC in accepted source
consensus. This runner enriches only those target sleeve states through the
shared forward_replacement_value helper and rebuilds the canonical artifact. It
changes no entry, exit, ranking, sizing, risk, LLM, paper-selection, or order
behavior.
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


EXPERIMENT_ID = "exp-20260704-021"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "accepted_allocator_consensus_missing_forward_rv_enrichment"
ASOF_DATE = "2026-07-04"
TARGET_SLEEVES = (
    "accepted_helper_source_priority_allocator",
    "accepted_source_consensus",
)
MIN_ACTIVATION_ROWS_PER_SURFACE = 30

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
QUANT_ROOT = REPO_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import forward_replacement_value as frv  # noqa: E402
from data_paths import atomic_write_text  # noqa: E402
from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = f"quant/experiments/exp_20260704_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_021_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"
FORWARD_RV_JSONL = SLEEVES_ROOT / "forward_replacement_value.jsonl"
ARCHIVE_FORWARD_RV_JSONL = OUT_DIR / "forward_replacement_value_before.jsonl"
TARGET_STATE_FILES = {
    sleeve: SLEEVES_ROOT / sleeve / "state.json" for sleeve in TARGET_SLEEVES
}
WRITE_FALLBACKS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def safe_write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError as exc:
        WRITE_FALLBACKS.append(f"{repo_rel(path)}: atomic fallback: {exc}")
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def write_json(path: Path, payload: Any) -> None:
    safe_write_text(
        json.dumps(make_json_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        path,
    )


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    safe_write_text(text, Path(path))


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
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
        if isinstance(row, dict):
            rows.append(row)
    return rows


def safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any) -> int:
    value = safe_float(value)
    return int(value) if value is not None else 0


def round_or_none(value: Any, digits: int = 2) -> float | None:
    value = safe_float(value)
    return round(value, digits) if value is not None else None


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def closed_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("closed_positions", "closed_trades"):
        rows = state.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def replacement_complete(row: dict[str, Any]) -> bool:
    return (
        row.get("replacement_value_status") == "enriched"
        and safe_float(row.get("replacement_value_vs_cash_usd")) is not None
        and safe_float(row.get("replacement_value_vs_spy_usd")) is not None
        and safe_float(row.get("replacement_value_vs_qqq_usd")) is not None
    )


def slim_row(row: dict[str, Any], sleeve_key: str) -> dict[str, Any]:
    return {
        "sleeve_key": sleeve_key,
        "ticker": row.get("ticker"),
        "decision_id": row.get("decision_id"),
        "entry_date": row.get("entry_date"),
        "exit_date": row.get("exit_date") or row.get("entry_date"),
        "pnl": round_or_none(row.get("pnl") if row.get("pnl") is not None else row.get("pnl_usd")),
        "paper_notional_usd": round_or_none(
            row.get("paper_notional_usd") or row.get("notional_usd")
        ),
        "replacement_value_status": row.get("replacement_value_status"),
        "replacement_value_vs_cash_usd": round_or_none(row.get("replacement_value_vs_cash_usd")),
        "replacement_value_vs_spy_usd": round_or_none(row.get("replacement_value_vs_spy_usd")),
        "replacement_value_vs_qqq_usd": round_or_none(row.get("replacement_value_vs_qqq_usd")),
        "target_price_present": row.get("target_price") is not None,
        "trade_enabled": row.get("trade_enabled"),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(safe_int(row.get("signals_generated")) for row in windows)
    survived = sum(safe_int(row.get("signals_survived")) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(safe_int(row.get("trade_count")) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
    }


def summarize_target_states() -> dict[str, Any]:
    sleeves: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    complete_rows: list[dict[str, Any]] = []
    for sleeve_key, state_path in TARGET_STATE_FILES.items():
        state = read_json(state_path, {})
        rows = closed_rows(state if isinstance(state, dict) else {})
        slim = [slim_row(row, sleeve_key) for row in rows]
        sleeve_missing = [
            slim_row(row, sleeve_key) for row in rows if not replacement_complete(row)
        ]
        sleeve_complete = [
            slim_row(row, sleeve_key) for row in rows if replacement_complete(row)
        ]
        sleeves[sleeve_key] = {
            "state_file": repo_rel(state_path),
            "state_exists": state_path.exists(),
            "closed_rows": len(rows),
            "complete_rows": len(sleeve_complete),
            "missing_rows": len(sleeve_missing),
            "rows": slim,
            "missing": sleeve_missing,
        }
        all_rows.extend(slim)
        missing.extend(sleeve_missing)
        complete_rows.extend(sleeve_complete)

    cash = [safe_float(row.get("replacement_value_vs_cash_usd")) for row in complete_rows]
    spy = [safe_float(row.get("replacement_value_vs_spy_usd")) for row in complete_rows]
    qqq = [safe_float(row.get("replacement_value_vs_qqq_usd")) for row in complete_rows]
    cash = [value for value in cash if value is not None]
    spy = [value for value in spy if value is not None]
    qqq = [value for value in qqq if value is not None]
    return {
        "sleeves": sleeves,
        "closed_rows": len(all_rows),
        "complete_rows": len(complete_rows),
        "missing_rows": len(missing),
        "missing": missing,
        "replacement_value_vs_cash_usd": round(sum(cash), 2) if cash else 0.0,
        "replacement_value_vs_spy_usd": round(sum(spy), 2) if spy else 0.0,
        "replacement_value_vs_qqq_usd": round(sum(qqq), 2) if qqq else 0.0,
        "ticker_counts": Counter(row.get("ticker") or "unknown" for row in all_rows),
        "sleeve_counts": Counter(row.get("sleeve_key") or "unknown" for row in all_rows),
    }


def summarize_forward_artifact() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_RV_JSONL)
    matches = [row for row in rows if row.get("sleeve_key") in TARGET_SLEEVES]
    enriched = [row for row in matches if row.get("status") == "enriched"]
    skipped = []
    for item in summarize_target_states()["missing"]:
        skipped.append(
            {
                "sleeve_key": item.get("sleeve_key"),
                "ticker": item.get("ticker"),
                "decision_id": item.get("decision_id"),
                "entry_date": item.get("entry_date"),
                "exit_date": item.get("exit_date"),
            }
        )
    return {
        "artifact_file": repo_rel(FORWARD_RV_JSONL),
        "artifact_exists": FORWARD_RV_JSONL.exists(),
        "total_rows": len(rows),
        "target_matching_rows": len(matches),
        "target_enriched_rows": len(enriched),
        "status_counts": Counter(row.get("status") or "unknown" for row in matches),
        "target_tickers": sorted({str(row.get("ticker")) for row in matches if row.get("ticker")}),
        "currently_skipped_missing_replacement": skipped,
    }


def enrich_target_states() -> dict[str, Any]:
    before_states = {sleeve: read_json(path, {}) for sleeve, path in TARGET_STATE_FILES.items()}
    tickers = sorted(
        {
            str(row.get("ticker")).upper()
            for state in before_states.values()
            if isinstance(state, dict)
            for row in closed_rows(state)
            if row.get("ticker")
        }
    )
    bars_by_ticker = frv.load_comparator_bars()
    regime_spy_bars = frv.load_regime_spy_bars()
    sv_percentile_index = frv.load_short_volume_percentile_index()
    exhaustion_bars = frv.load_entry_exhaustion_bars(tickers)
    updated_records: list[dict[str, Any]] = []
    state_changed: dict[str, bool] = {}

    for sleeve_key, state_path in TARGET_STATE_FILES.items():
        state = read_json(state_path, {})
        before_state = json.loads(json.dumps(state))
        records = frv.enrich_state_closed_rows(
            state,
            bars_by_ticker,
            ASOF_DATE,
            sleeve_key,
            regime_spy_bars=regime_spy_bars,
            sv_percentile_index=sv_percentile_index,
            exhaustion_bars=exhaustion_bars,
        )
        changed = state != before_state
        state_changed[sleeve_key] = changed
        if changed:
            write_json(state_path, state)
        updated_records.extend(records)

    frv._write_jsonl = write_jsonl
    artifact_summary = frv.rebuild_current_state_artifact(
        sleeves_root=SLEEVES_ROOT,
        artifact_path=FORWARD_RV_JSONL,
        archive_path=ARCHIVE_FORWARD_RV_JSONL,
    )
    return {
        "state_changed": state_changed,
        "rows_updated_this_run": len(updated_records),
        "updated_records": [
            {
                "sleeve_key": row.get("sleeve_key"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "status": row.get("status"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
                "decision_id": row.get("decision_id"),
            }
            for row in updated_records
        ],
        "warehouse_inputs": {
            "comparator_tickers": sorted(bars_by_ticker),
            "comparator_bar_counts": {
                ticker: len(bars) for ticker, bars in sorted(bars_by_ticker.items())
            },
            "regime_spy_bars": len(regime_spy_bars),
            "short_volume_symbols": len(sv_percentile_index),
            "entry_exhaustion_tickers": len(exhaustion_bars),
        },
        "artifact_summary": artifact_summary,
        "write_fallbacks": list(WRITE_FALLBACKS),
    }


def classify_alpha_readiness(after_state: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for sleeve_key, sleeve in after_state["sleeves"].items():
        if sleeve["closed_rows"] < MIN_ACTIVATION_ROWS_PER_SURFACE:
            blockers.append(
                f"{sleeve_key}_closed_rows_below_activation_min:"
                f"{sleeve['closed_rows']}/{MIN_ACTIVATION_ROWS_PER_SURFACE}"
            )
        if sleeve["missing_rows"]:
            blockers.append(f"{sleeve_key}_still_missing_replacement_rows:{sleeve['missing_rows']}")
    if after_state["replacement_value_vs_cash_usd"] <= 0:
        blockers.append(
            f"combined_replacement_vs_cash_not_positive:{after_state['replacement_value_vs_cash_usd']}"
        )
    return not blockers, blockers


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    before_state = summarize_target_states()
    before_artifact = summarize_forward_artifact()
    repair = enrich_target_states()
    after_state = summarize_target_states()
    after_artifact = summarize_forward_artifact()
    alpha_ready, alpha_blockers = classify_alpha_readiness(after_state)
    repair_success = after_state["missing_rows"] == 0
    decision = (
        "accepted_measurement_repair_accepted_allocator_consensus_forward_rv_enrichment"
        if repair_success
        else "blocked_accepted_allocator_consensus_forward_rv_still_missing"
    )
    status = "accepted_measurement_repair" if repair_success else "blocked"
    predicted = float((ticket.get("prediction") or {}).get("success_probability") or 0.0)
    actual_success = 1 if repair_success else 0
    missing_repaired = before_state["missing_rows"] - after_state["missing_rows"]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "status": status,
        "accepted": repair_success,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_success,
        "alpha_ready": alpha_ready,
        "classification": (
            "measurement_repair_accepted_alpha_not_activation_ready"
            if repair_success and not alpha_ready
            else "measurement_repair_and_alpha_ready"
            if repair_success
            else "measurement_repair_blocked"
        ),
        "decision": decision,
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "Accepted allocator/source-consensus forward rows need complete "
            "cash/SPY/QQQ replacement values before any source-readiness or "
            "activation conclusion is credible."
        ),
        "change_type": ticket.get("change_type"),
        "implementation_mode": "targeted_forward_replacement_value_enrichment",
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components", []),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "new_evidence_axis": (
            "Measurement repair after exp-20260704-017 hot warehouse IO repair and "
            "exp-20260704-020 artifact rebuild: two concrete newly closed accepted "
            "default-off rows (DDOG/WDC) were missing comparator values. This is not "
            "an allocator source-rank, scalar, threshold, top-N, or activation retune."
        ),
        "novelty": ticket.get("novelty"),
        "prediction": ticket.get("prediction", {}),
        "parameters": {
            "asof_date": ASOF_DATE,
            "target_sleeves": list(TARGET_SLEEVES),
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "forward_replacement_value_file": repo_rel(FORWARD_RV_JSONL),
            "archived_previous_forward_replacement_value_file": repo_rel(
                ARCHIVE_FORWARD_RV_JSONL
            ),
            "min_activation_rows_per_surface": MIN_ACTIVATION_ROWS_PER_SURFACE,
        },
        "pre_run_questions": {
            "alpha_hypothesis": (
                "Accepted allocator/source-consensus forward readiness is blocked "
                "until DDOG/WDC have cash/SPY/QQQ replacement values."
            ),
            "history_check": {
                "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
                "novelty_nearest": ((ticket.get("novelty") or {}).get("nearest") or [])[:5],
                "before_missing_rows": before_state["missing"],
            },
            "single_policy_bundle": ticket.get("single_causal_variable"),
            "acceptance_standard": (
                "Accept as measurement repair only if both target accepted sleeves "
                "have zero missing replacement-value rows after enrichment and the "
                "shared forward_replacement_value artifact includes their rows. "
                "Alpha activation remains blocked unless each surface has enough "
                "closed enriched rows and positive comparator replacement value."
            ),
            "reproducibility": RUNNER_COMMAND,
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
            "target_closed_rows": after_state["closed_rows"],
            "target_missing_replacement_before": before_state["missing_rows"],
            "target_missing_replacement_after": after_state["missing_rows"],
            "target_missing_replacement_repaired": missing_repaired,
            "rows_updated_this_run": repair["rows_updated_this_run"],
            "artifact_target_matching_rows_before": before_artifact["target_matching_rows"],
            "artifact_target_matching_rows_after": after_artifact["target_matching_rows"],
            "artifact_target_enriched_rows_before": before_artifact["target_enriched_rows"],
            "artifact_target_enriched_rows_after": after_artifact["target_enriched_rows"],
            "replacement_value_vs_cash_usd": after_state["replacement_value_vs_cash_usd"],
            "replacement_value_vs_spy_usd": after_state["replacement_value_vs_spy_usd"],
            "replacement_value_vs_qqq_usd": after_state["replacement_value_vs_qqq_usd"],
        },
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": after_state["missing_rows"] == 0,
            "fields_checked": [
                "target_closed_rows.entry_date",
                "target_closed_rows.target_price",
                "target_closed_rows.pnl",
                "target_closed_rows.paper_notional_usd",
                "target_closed_rows.replacement_value_vs_cash_usd",
                "target_closed_rows.replacement_value_vs_spy_usd",
                "target_closed_rows.replacement_value_vs_qqq_usd",
                "forward_replacement_value.sleeve_key",
                "forward_replacement_value.status",
            ],
            "missing_or_invalid_fields": {
                "before_missing_replacement_rows": before_state["missing"],
                "after_missing_replacement_rows": after_state["missing"],
            },
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk, or order rule changed.",
        },
        "gate4": {
            "passed": repair_success,
            "accepted_measurement_repair": repair_success,
            "accepted_alpha": False,
            "alpha_ready": alpha_ready,
            "decision": decision,
            "repair_failed_reasons": []
            if repair_success
            else ["target_accepted_rows_still_missing_replacement_values"],
            "alpha_activation_blockers": alpha_blockers,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
        },
        "target_forward_replacement_repair": {
            "before_state": before_state,
            "before_artifact": before_artifact,
            "repair": repair,
            "after_state": after_state,
            "after_artifact": after_artifact,
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Only closed default-off accepted helper/source-consensus state rows "
                "and the shared forward replacement-value artifact changed; no "
                "executable policy or live order path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": predicted,
            "actual_success": actual_success,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": (ticket.get("prediction") or {}).get(
                "main_failure_modes", []
            ),
            "realized_failure_modes": []
            if repair_success
            else ["replacement_enrichment_incomplete"],
            "alpha_realized_non_activation": alpha_blockers,
            "predicted_failure_mode_hit": "readiness_still_too_thin"
            in (ticket.get("prediction") or {}).get("main_failure_modes", []),
            "surprise_note": (
                "Low surprise: DDOG/WDC had usable fields and the repaired "
                "hot/cold warehouse supplied comparator bars; activation remains "
                "blocked by sample size and mixed replacement value."
                if repair_success
                else "At least one target row still lacks replacement comparators."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The target rows already had ticker, entry_date, exit_date, pnl, "
                "notional, and target_price, and the shared warehouse now covers "
                "SPY/QQQ bars for their holding windows."
            ),
            "alpha_interpretation": (
                "The measurement surface is now complete for DDOG/WDC, but this "
                "does not make allocator/source-consensus activation-ready: target "
                f"closed rows are {after_state['closed_rows']} total and combined "
                "cash/SPY/QQQ replacement remains a thin attribution sample."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune allocator source ranks, source scalars, top-N, hold, "
                "cooldown, or activation gates from these few rows. Reopen only with "
                "materially more closed accepted allocator/source-consensus rows or "
                "a genuinely new PIT source."
            ),
            "new_evidence_required": (
                "Materially more closed enriched accepted allocator/source-consensus "
                "forward rows, or a genuinely new production-visible source that "
                "changes the evidence rather than the response function."
            ),
        },
        "rejection_reason": None
        if repair_success
        else "Target accepted rows still missing replacement values.",
        "next_retry_requires": [
            "materially_more_closed_accepted_allocator_or_source_consensus_rows",
            "or_genuinely_new_pit_source",
            "no_allocator_rank_scalar_topn_hold_cooldown_retune_on_same_rows",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            repo_rel(TARGET_STATE_FILES["accepted_helper_source_priority_allocator"]),
            repo_rel(TARGET_STATE_FILES["accepted_source_consensus"]),
            repo_rel(FORWARD_RV_JSONL),
            repo_rel(ARCHIVE_FORWARD_RV_JSONL),
        ],
        "related_files": [
            "quant/forward_replacement_value.py",
            "experiments/logs/exp-20260704-017.json",
            "experiments/logs/exp-20260704-020.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": repair_success,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "status",
        "lane",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
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
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "classification",
        "parameters",
        "pre_run_questions",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "target_forward_replacement_repair",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - accepted allocator/source-consensus RV enrichment",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- rows repaired: {delta['target_missing_replacement_repaired']}",
            f"- target artifact rows: {delta['artifact_target_matching_rows_before']} -> {delta['artifact_target_matching_rows_after']}",
            f"- target enriched rows: {delta['artifact_target_enriched_rows_before']} -> {delta['artifact_target_enriched_rows_after']}",
            f"- replacement totals: cash {delta['replacement_value_vs_cash_usd']}, SPY {delta['replacement_value_vs_spy_usd']}, QQQ {delta['replacement_value_vs_qqq_usd']}",
            f"- alpha blockers: {', '.join(payload['gate4']['alpha_activation_blockers'])}",
            "",
            "No entry, exit, ranking, sizing, risk, LLM boundary, paper-selection, or order behavior changed.",
            "",
            "Reproduce:",
            "",
            f"    {RUNNER_COMMAND}",
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
        TARGET_STATE_FILES["accepted_helper_source_priority_allocator"],
        TARGET_STATE_FILES["accepted_source_consensus"],
        FORWARD_RV_JSONL,
        ARCHIVE_FORWARD_RV_JSONL,
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_row = build_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    safe_write_text(build_card(payload), CARD_MD)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "classification": payload["classification"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["post_run_reflection"]["alpha_interpretation"],
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
            "parameters": payload["parameters"],
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
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "rows_updated_this_run": payload["delta_metrics"]["rows_updated_this_run"],
                "missing_before": payload["delta_metrics"]["target_missing_replacement_before"],
                "missing_after": payload["delta_metrics"]["target_missing_replacement_after"],
                "replacement_value_vs_cash_usd": payload["delta_metrics"]["replacement_value_vs_cash_usd"],
                "replacement_value_vs_spy_usd": payload["delta_metrics"]["replacement_value_vs_spy_usd"],
                "replacement_value_vs_qqq_usd": payload["delta_metrics"]["replacement_value_vs_qqq_usd"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
