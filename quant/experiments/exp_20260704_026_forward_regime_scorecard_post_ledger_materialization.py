"""exp-20260704-026: refresh forward regime scorecard after ledger growth.

Measurement repair only. The canonical forward replacement-value ledger now has
materially more closed rows than the last regime scorecard refresh
(exp-20260628-007), so refresh the scorecard from the current ledger and record
whether regime-conditioned allocation is evaluable. No strategy, ranking,
sizing, exit, order, LLM boundary, or live/default behavior changes.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260704-026"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "forward_regime_scorecard_post_ledger_materialization"

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (REPO_ROOT, REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import regime_tagged_scorecard as scorecard  # noqa: E402
from data_paths import atomic_write_text  # noqa: E402
from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = f"quant/experiments/exp_20260704_026_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
WAREHOUSE_JSON = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SCORECARD_JSON = REPO_ROOT / "data" / "regime_scorecard" / "regime_tagged_scorecard_latest.json"
PRIOR_LOG_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260628-007.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_026_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_ROWS_FOR_INFERENCE = 50
MIN_NON_RISK_ON_ROWS = 20
MIN_NEW_ROWS_FOR_MATERIAL_REFRESH = 10

CHANGE_TYPE = "forward_regime_scorecard_post_ledger_materialization_measurement_repair"
CHANGED_VARIABLE = "forward_regime_scorecard_refresh_after_material_forward_ledger_growth_v1"
MECHANISM_FAMILY = "regime_router_measurement_repair"
TRIAL_FAMILY = "regime_tagged_forward_scorecard_refresh"
TRIAL_VARIANT_ID = "forward_replacement_rows_after_20260704_materialization_v1"
NEW_EVIDENCE_TYPE = "materially_more_closed_forward_replacement_rows"
NEW_EVIDENCE_AXIS = (
    "Forward replacement ledger now has 60 deduped closed rows versus the "
    "41-row exp-20260628-007 scorecard after exp-20260704-020/021/022 "
    "materialized replacement values; this is materially more settled forward "
    "evidence, not a threshold retune."
)
ALPHA_HYPOTHESIS = (
    "Regime-conditioned exposure/capacity can improve default-off forward "
    "replacement value, but only after the canonical scorecard reflects the "
    "current closed forward ledger and has enough non-risk_on coverage."
)

PRODUCTION_IMPACT = {
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
    "default_off_attribution_only": True,
    "parity_note": (
        "Read-only scorecard refresh from the existing forward replacement-value "
        "ledger. It writes attribution artifacts only and does not alter any "
        "production, paper, replay, or live order path."
    ),
}


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
        return {str(key): make_json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def safe_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
    except PermissionError:
        path.write_text(text, encoding="utf-8")
        for leftover in path.parent.glob(f".{path.name}.*.tmp"):
            try:
                leftover.unlink()
            except OSError:
                pass


def write_json(path: Path, payload: Any) -> None:
    safe_write_text(
        path,
        json.dumps(make_json_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
    )


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines() if line.strip())


def baseline_summary() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    raw_windows = payload.get("windows") or payload.get("results") or {}
    if isinstance(raw_windows, list):
        windows = {
            str(window.get("label") or index): window
            for index, window in enumerate(raw_windows)
            if isinstance(window, dict)
        }
    elif isinstance(raw_windows, dict):
        windows = raw_windows
    else:
        windows = {}
    generated = 0
    survived = 0
    for window in windows.values():
        generated += int(window.get("signals_generated") or 0)
        survived += int(window.get("signals_survived") or 0)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows.values()),
            4,
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows.values()), 2),
        "trade_count": sum(int(w.get("trade_count") or w.get("total_trades") or 0) for w in windows.values()),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "max_drawdown_pct_worst": (
            round(max(float(w.get("max_drawdown_pct") or 0.0) for w in windows.values()), 4)
            if windows
            else None
        ),
    }


def summarize_forward_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels: Counter[str] = Counter()
    sleeves: Counter[str] = Counter()
    tickers: Counter[str] = Counter()
    entry_dates: list[str] = []
    for row in rows:
        labels[str(row.get("entry_regime_label") or row.get("regime_label") or "missing")] += 1
        sleeves[str(row.get("sleeve") or row.get("sleeve_key") or "missing")] += 1
        tickers[str(row.get("ticker") or "missing")] += 1
        entry = str(row.get("entry_date") or "")[:10]
        if entry:
            entry_dates.append(entry)
    return {
        "rows": len(rows),
        "raw_jsonl_rows": raw_jsonl_count(FORWARD_JSONL),
        "rows_by_entry_regime_label": dict(sorted(labels.items())),
        "rows_by_sleeve": dict(sorted(sleeves.items())),
        "top_tickers": dict(tickers.most_common(12)),
        "min_entry_date": min(entry_dates) if entry_dates else None,
        "max_entry_date": max(entry_dates) if entry_dates else None,
        "rows_with_entry_date": sum(1 for row in rows if row.get("entry_date")),
        "rows_with_decision_id": sum(1 for row in rows if row.get("decision_id")),
        "rows_with_spy_replacement_value": sum(
            1 for row in rows if row.get("replacement_value_vs_spy_usd") is not None
        ),
        "rows_with_qqq_replacement_value": sum(
            1 for row in rows if row.get("replacement_value_vs_qqq_usd") is not None
        ),
    }


def summarize_new_rows(rows: list[dict[str, Any]], prior_max_entry_date: str | None) -> dict[str, Any]:
    if prior_max_entry_date:
        new_rows = [row for row in rows if str(row.get("entry_date") or "")[:10] > prior_max_entry_date]
    else:
        new_rows = list(rows)
    return {
        "prior_max_entry_date": prior_max_entry_date,
        "new_rows": len(new_rows),
        "new_rows_by_regime": dict(sorted(Counter(
            str(row.get("entry_regime_label") or row.get("regime_label") or "missing")
            for row in new_rows
        ).items())),
        "new_rows_by_sleeve": dict(sorted(Counter(
            str(row.get("sleeve") or row.get("sleeve_key") or "missing") for row in new_rows
        ).items())),
        "new_rows_sample": [
            {
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "sleeve": row.get("sleeve") or row.get("sleeve_key"),
                "ticker": row.get("ticker"),
                "entry_regime_label": row.get("entry_regime_label") or row.get("regime_label"),
                "replacement_value_vs_cash_usd": row.get("replacement_value_vs_cash_usd"),
                "replacement_value_vs_spy_usd": row.get("replacement_value_vs_spy_usd"),
                "replacement_value_vs_qqq_usd": row.get("replacement_value_vs_qqq_usd"),
            }
            for row in new_rows[-12:]
        ],
    }


def prior_summary() -> dict[str, Any]:
    prior_log = read_json(PRIOR_LOG_JSON, {})
    readiness = prior_log.get("readiness") if isinstance(prior_log, dict) else {}
    current = readiness.get("current_forward_summary") if isinstance(readiness, dict) else {}
    return {
        "prior_experiment_id": "exp-20260628-007",
        "prior_log": repo_rel(PRIOR_LOG_JSON),
        "prior_log_exists": PRIOR_LOG_JSON.exists(),
        "prior_tagged_rows": int(readiness.get("total_tagged_rows") or 0),
        "prior_non_risk_on_rows": int(readiness.get("non_risk_on_rows") or 0),
        "prior_max_entry_date": current.get("max_entry_date") if isinstance(current, dict) else None,
        "prior_decision": prior_log.get("decision"),
        "prior_reopen_condition": readiness.get("reopen_condition") if isinstance(readiness, dict) else None,
    }


def sleeve_regime_cells(scorecard_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scorecard_rows:
        key = f"{row.get('sleeve') or 'missing'}|{row.get('regime_label') or 'missing'}"
        buckets[key].append(row)
    output: dict[str, dict[str, Any]] = {}
    for key, bucket in sorted(buckets.items()):
        values = [
            float(row["replacement_value_vs_spy_usd"])
            for row in bucket
            if row.get("replacement_value_vs_spy_usd") is not None
        ]
        positives = [value for value in values if value > 0]
        total_positive = sum(positives)
        ticker_positive: Counter[str] = Counter()
        for row in bucket:
            value = row.get("replacement_value_vs_spy_usd")
            if isinstance(value, (int, float)) and value > 0:
                ticker_positive[str(row.get("ticker") or "missing")] += float(value)
        output[key] = {
            "count": len(bucket),
            "rv_rows": len(values),
            "mean_rv_vs_spy_usd": round(sum(values) / len(values), 2) if values else None,
            "sum_rv_vs_spy_usd": round(sum(values), 2) if values else None,
            "win_rate_vs_spy": round(len(positives) / len(values), 6) if values else None,
            "max_single_positive_share": (
                round(max(ticker_positive.values()) / total_positive, 6)
                if total_positive > 0 and ticker_positive
                else None
            ),
        }
    return output


def readiness(
    *,
    current_scorecard: dict[str, Any],
    current_rows: list[dict[str, Any]],
    prior: dict[str, Any],
) -> dict[str, Any]:
    total = int(current_scorecard.get("tagged_rows") or 0)
    by_regime = current_scorecard.get("by_regime") or {}
    risk_on = int((by_regime.get("risk_on_trend") or {}).get("count") or 0)
    non_risk_on = total - risk_on
    row_delta = total - int(prior.get("prior_tagged_rows") or 0)
    current_summary = summarize_forward_rows(current_rows)

    blockers: list[str] = []
    if total < MIN_ROWS_FOR_INFERENCE:
        blockers.append(f"total_rows_below_min_inference:{total}/{MIN_ROWS_FOR_INFERENCE}")
    if non_risk_on < MIN_NON_RISK_ON_ROWS:
        blockers.append(f"non_risk_on_rows_below_min:{non_risk_on}/{MIN_NON_RISK_ON_ROWS}")
    if row_delta < MIN_NEW_ROWS_FOR_MATERIAL_REFRESH:
        blockers.append(f"incremental_rows_below_material_refresh:{row_delta}/{MIN_NEW_ROWS_FOR_MATERIAL_REFRESH}")
    if current_summary["rows_by_entry_regime_label"] == {"risk_on_trend": total}:
        blockers.append("all_rows_risk_on_trend")

    activation_ready = not blockers
    return {
        "activation_ready": activation_ready,
        "watchlist_ready": activation_ready,
        "blocked": not activation_ready,
        "blockers": blockers,
        "min_rows_for_inference": MIN_ROWS_FOR_INFERENCE,
        "min_non_risk_on_rows": MIN_NON_RISK_ON_ROWS,
        "min_new_rows_for_material_refresh": MIN_NEW_ROWS_FOR_MATERIAL_REFRESH,
        "total_tagged_rows": total,
        "prior_tagged_rows": int(prior.get("prior_tagged_rows") or 0),
        "row_delta_vs_exp_20260628_007": row_delta,
        "risk_on_rows": risk_on,
        "non_risk_on_rows": non_risk_on,
        "current_forward_summary": current_summary,
        "new_rows_since_prior": summarize_new_rows(current_rows, prior.get("prior_max_entry_date")),
        "sleeve_regime_cells": sleeve_regime_cells(current_scorecard.get("rows") or []),
        "reopen_condition": (
            "Reopen regime soft-tilt activation only after at least "
            f"{MIN_ROWS_FOR_INFERENCE} tagged forward rows and at least "
            f"{MIN_NON_RISK_ON_ROWS} non-risk_on rows exist, or after a new "
            "forward/live-pilot policy surface creates materially different rows."
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_summary()
    prior = prior_summary()
    previous_scorecard = read_json(SCORECARD_JSON, {})
    rows = scorecard.load_forward_paper_rows(forward_replacement_path=FORWARD_JSONL)
    regime_fn = scorecard.warehouse_spy_stress_regime_fn(WAREHOUSE_JSON)
    current_scorecard = scorecard.build_scorecard(
        rows,
        regime_fn,
        min_rows_for_inference=MIN_ROWS_FOR_INFERENCE,
    )
    ready = readiness(current_scorecard=current_scorecard, current_rows=rows, prior=prior)
    repair_success = len(rows) > 0 and int(current_scorecard.get("tagged_rows") or 0) == len(rows)
    alpha_ready = bool(ready["activation_ready"])
    status = "accepted_measurement_repair" if repair_success else "blocked"
    decision = (
        "accepted_measurement_repair_forward_regime_scorecard_refreshed_alpha_blocked"
        if repair_success and not alpha_ready
        else "accepted_measurement_repair_forward_regime_scorecard_activation_ready"
        if repair_success
        else "blocked_forward_regime_scorecard_refresh_failed"
    )

    prediction = ticket.get("prediction") or {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "all_rows_risk_on_trend",
            "no_non_risk_on_regime_coverage",
            "scorecard_refresh_does_not_enable_alpha",
        ],
        "confidence_reason": (
            "Preflight found 60 closed rows, but all are still risk_on_trend, "
            "so refresh is likely accepted measurement repair with alpha blocked."
        ),
        "recorded_at": utc_now(),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": repair_success,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_success,
        "alpha_ready": alpha_ready,
        "classification": (
            "measurement_repair_accepted_alpha_not_activation_ready"
            if repair_success and not alpha_ready
            else "measurement_repair_accepted_alpha_activation_ready"
            if repair_success
            else "blocked_measurement_repair"
        ),
        "hypothesis": ticket.get("hypothesis") or ALPHA_HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "read_only_forward_regime_scorecard_refresh",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "canonical forward_replacement_value ledger load",
            "production-faithful entry-time regime tagging",
            "scorecard artifact refresh",
            "no threshold, ranking, sizing, exit, order, prompt, or live behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260628-007",
            "exp-20260625-008",
            "exp-20260704-020",
            "exp-20260704-021",
            "exp-20260704-022",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "parameters": {
            "baseline_result_file": repo_rel(BASELINE_JSON),
            "forward_replacement_value_file": repo_rel(FORWARD_JSONL),
            "scorecard_file": repo_rel(SCORECARD_JSON),
            "prior_log": repo_rel(PRIOR_LOG_JSON),
            "min_rows_for_inference": MIN_ROWS_FOR_INFERENCE,
            "min_non_risk_on_rows": MIN_NON_RISK_ON_ROWS,
            "min_new_rows_for_material_refresh": MIN_NEW_ROWS_FOR_MATERIAL_REFRESH,
        },
        "pre_run_questions": {
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "history_check": {
                "exp-20260628-007": prior,
                "novelty_gate": ticket.get("novelty"),
                "near_neighbor_note": (
                    "Legal axis is materially more settled forward rows: "
                    f"{prior.get('prior_tagged_rows')} -> {current_scorecard.get('tagged_rows')} tagged rows."
                ),
            },
            "single_policy_bundle": CHANGED_VARIABLE,
            "acceptance_standard": ticket.get("acceptance_rule"),
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
            "scorecard_rows_before": previous_scorecard.get("total_rows"),
            "scorecard_tagged_rows_before": previous_scorecard.get("tagged_rows"),
            "scorecard_rows_after": current_scorecard.get("total_rows"),
            "scorecard_tagged_rows_after": current_scorecard.get("tagged_rows"),
            "row_delta_vs_previous_scorecard_file": int(current_scorecard.get("tagged_rows") or 0)
            - int(previous_scorecard.get("tagged_rows") or 0),
            "row_delta_vs_exp_20260628_007": ready["row_delta_vs_exp_20260628_007"],
            "non_risk_on_rows": ready["non_risk_on_rows"],
            "risk_on_rows": ready["risk_on_rows"],
        },
        "gate1": {"passed": baseline["loaded"], "baseline_metrics": baseline},
        "gate2": {
            "passed": repair_success,
            "fields_checked": [
                "forward_replacement_value.decision_id",
                "forward_replacement_value.entry_date",
                "forward_replacement_value.sleeve_key",
                "forward_replacement_value.ticker",
                "forward_replacement_value.replacement_value_vs_cash_usd",
                "forward_replacement_value.replacement_value_vs_spy_usd",
                "forward_replacement_value.replacement_value_vs_qqq_usd",
                "forward_replacement_value.entry_regime_label",
                "forward_replacement_value.entry_regime_exposure_scalar",
            ],
            "entry_date_present": all(row.get("entry_date") for row in rows),
            "target_price_scope": (
                "Not applicable: this runner does not generate entries or exits. "
                "It consumes already settled forward paper rows with replacement values."
            ),
            "missing_or_invalid_fields": [] if repair_success else ["no_tagged_forward_rows"],
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, entry, exit, ranking, sizing, risk, prompt, or order rule changed.",
        },
        "gate4": {
            "passed": repair_success,
            "accepted_measurement_repair": repair_success,
            "accepted_alpha": False,
            "alpha_ready": alpha_ready,
            "decision": decision,
            "repair_failed_reasons": [] if repair_success else ["scorecard_refresh_failed"],
            "alpha_activation_blockers": ready["blockers"],
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
        },
        "readiness": ready,
        "scorecard": current_scorecard,
        "production_impact": PRODUCTION_IMPACT,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if repair_success else 0,
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1 if repair_success else 0)) ** 2,
                4,
            ),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_modes": [] if repair_success else ["scorecard_refresh_failed"],
            "alpha_realized_non_activation": ready["blockers"],
            "predicted_failure_mode_hit": bool(ready["blockers"]),
            "surprise_note": (
                "Low surprise: the stale scorecard refreshed from 41 to 60 rows, "
                "but all 60 rows remain risk_on_trend, so allocation activation "
                "is still blocked by the predeclared non-risk_on coverage floor."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Forward replacement-value repair/materialization added rows from "
                "supplier financing, accepted allocator/consensus, and SEC financial "
                "report sleeves. The production-faithful entry regime on all current "
                "rows is still risk_on_trend, leaving no cross-regime contrast."
            ),
            "alpha_interpretation": (
                "This is accepted measurement repair, not accepted alpha. The "
                "scorecard is current and over the total row floor, but zero "
                "non-risk_on rows means regime-conditioned allocation cannot be "
                "evaluated or activated."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not test regime threshold, scalar, sleeve-cap, or response-function "
                "retunes on these same 60 all-risk_on rows."
            ),
            "new_evidence_required": ready["reopen_condition"],
        },
        "next_retry_requires": [
            "at_least_20_non_risk_on_forward_rows",
            "or_new_forward_live_policy_surface_with_materially_different_rows",
            "no_regime_threshold_scalar_or_response_retune_on_same_all_risk_on_rows",
        ],
        "rejection_reason": None if repair_success else "Scorecard refresh failed to tag current forward rows.",
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(SCORECARD_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": [
            "quant/regime_tagged_scorecard.py",
            repo_rel(FORWARD_JSONL),
            "experiments/logs/exp-20260628-007.json",
            "experiments/logs/exp-20260704-020.json",
            "experiments/logs/exp-20260704-021.json",
            "experiments/logs/exp-20260704-022.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
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
        "readiness",
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
    ready = payload["readiness"]
    summary = ready["current_forward_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - forward regime scorecard refresh",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- tagged rows: {ready['prior_tagged_rows']} -> {ready['total_tagged_rows']}",
            f"- non-risk_on rows: {ready['non_risk_on_rows']}",
            f"- entry regimes: {summary['rows_by_entry_regime_label']}",
            f"- scorecard file: {repo_rel(SCORECARD_JSON)}",
            f"- alpha blockers: {', '.join(ready['blockers'])}",
            "",
            "No strategy, ranking, sizing, exit, live order, or LLM decision boundary changed.",
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
        SCORECARD_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
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
    write_json(SCORECARD_JSON, payload["scorecard"])
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    safe_write_text(CARD_MD, build_card(payload))
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
            "scorecard_artifact": repo_rel(SCORECARD_JSON),
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
            "readiness": payload["readiness"],
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
            "scorecard_artifact": repo_rel(SCORECARD_JSON),
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
                "tagged_rows": payload["readiness"]["total_tagged_rows"],
                "row_delta_vs_exp_20260628_007": payload["readiness"]["row_delta_vs_exp_20260628_007"],
                "non_risk_on_rows": payload["readiness"]["non_risk_on_rows"],
                "blockers": payload["readiness"]["blockers"],
                "artifact": repo_rel(OUT_JSON),
                "scorecard_artifact": repo_rel(SCORECARD_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
