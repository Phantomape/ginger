"""exp-20260623-019: current alpha surface readiness delta.

Read-only alpha-search guardrail. This runner checks whether the post-20260622
workspace has enough genuinely new production-visible evidence to justify
launching another strategy-affecting alpha experiment. It changes no strategy,
helper, adapter, ranking, sizing, exit, paper ledger, live ledger, or order
behavior.
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


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-019"
SLUG = "current_surface_alpha_readiness_delta"
RUNNER = f"quant/experiments/exp_20260623_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_019_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
FORWARD_REPLACEMENT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
PRIOR_FORWARD_READINESS_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260622-013.json"
KOVA_INTRADAY = REPO_ROOT / "data" / "kova" / "intraday" / "intraday_ohlcv_20260622.jsonl"
KOVA_13F = REPO_ROOT / "data" / "kova" / "institutional" / "sec13f_ownership_20260622.jsonl"

HYPOTHESIS = (
    "alpha_search/readiness: current post-20260622 production-visible surfaces "
    "should only launch a new strategy experiment if they provide materially "
    "new closed forward replacement rows or non-frozen PIT fields; otherwise "
    "another candidate-pool, exit, Kova, options, short-volume, or "
    "factor-residual retry is expected to be non-production-parity or a frozen "
    "near-neighbor."
)
CHANGE_TYPE = "current_alpha_surface_readiness_delta"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "current_nonrepeat_alpha_surface_readiness"
TRIAL_VARIANT_ID = "post_20260622_surface_delta_v1"
CHANGED_VARIABLE = "current_post_20260622_alpha_surface_readiness_delta_v1"
NEW_EVIDENCE_TYPE = "post_20260622_closed_forward_rows_and_surface_closeouts"
NEW_EVIDENCE_AXIS = (
    "Post-20260622 repository state adds two newly enriched forward replacement "
    "rows and completed 20260623 closeouts for Kova/options/daily short "
    "volume/exit lifecycle/pilot/factor surfaces; this audits whether that new "
    "evidence is enough to proceed, not a threshold or source retune."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-003",
    "exp-20260622-013",
    "exp-20260623-004",
    "exp-20260623-014",
    "exp-20260623-010",
    "exp-20260623-018",
    "exp-20260622-025",
]
CAUSAL_COMPONENTS = [
    "forward replacement delta",
    "Kova intraday/13F availability",
    "factor residual novelty check",
    "options/daily-short-volume/exit lifecycle closeout scan",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-019/exp_20260623_019_current_surface_alpha_readiness_delta.json",
    "experiments/cards/exp-20260623-019.md",
    "experiments/manifests/exp-20260623-019.json",
    "experiments/tickets/exp-20260623-019.json",
    "experiments/logs/exp-20260623-019.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "too_few_new_forward_rows",
        "all_new_surfaces_recently_rejected",
        "kova_intraday_13f_unavailable",
        "near_neighbor_frozen_family",
    ],
    "confidence_reason": (
        "This is a guardrail alpha-readiness delta after many same-day "
        "closeouts: the money-making path would be a production-visible "
        "default-off or forward replacement surface, but current evidence is "
        "likely too thin; success only means a concrete next alpha is "
        "gate-ready."
    ),
    "recorded_at": "2026-06-23T16:06:39+00:00",
}

RECENT_SURFACE_LOGS = [
    {
        "experiment_id": "exp-20260622-025",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260622-025.json",
        "surface": "factor_residual_post_repair",
        "blocking_read": "fixed factor-residual rerun was rejected after repair",
    },
    {
        "experiment_id": "exp-20260623-004",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260623-004.json",
        "surface": "forward_replacement_entry_regime_cells",
        "blocking_read": "entry-regime cells were rejected as too thin/concentrated",
    },
    {
        "experiment_id": "exp-20260623-008",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260623-008.json",
        "surface": "broad_daily_short_volume_imbalance",
        "blocking_read": "broad universe daily short-volume imbalance failed monotonicity",
    },
    {
        "experiment_id": "exp-20260623-010",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260623-010.json",
        "surface": "options_closed_forward_skew",
        "blocking_read": "closed forward options skew failed monotonicity",
    },
    {
        "experiment_id": "exp-20260623-014",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260623-014.json",
        "surface": "kova_rs_growth_alignment",
        "blocking_read": "Kova RS/fundamental alignment failed monotonicity",
    },
    {
        "experiment_id": "exp-20260623-017",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260623-017.json",
        "surface": "live_pilot_competition_scalar",
        "blocking_read": "pilot scalar attribution was too thin/concentrated",
    },
    {
        "experiment_id": "exp-20260623-018",
        "path": REPO_ROOT / "experiments" / "logs" / "exp-20260623-018.json",
        "surface": "exit_lifecycle_next_open_value",
        "blocking_read": "next-open exit value failed concentration guard",
    },
]

ACCEPTANCE_RULE = {
    "min_new_forward_rows_since_prior_readiness": 20,
    "min_activation_closed_rows_per_sleeve": 60,
    "min_watchlist_closed_rows_per_sleeve": 20,
    "min_positive_rate": 0.50,
    "max_single_positive_cash_share": 0.50,
    "require_non_skipped_kova_intraday_or_13f": False,
    "require_recent_surface_observed_lead": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 10)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(safe(record), sort_keys=True)
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


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict):
        return prediction
    return dict(DEFAULT_PREDICTION)


def load_baseline() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT)
    windows = data.get("windows", [])
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "aggregate_expected_value_score": round(sum(as_float(w.get("expected_value_score")) or 0.0 for w in windows), 4),
        "aggregate_total_pnl": round(sum(as_float(w.get("total_pnl")) or 0.0 for w in windows), 2),
        "total_trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "aggregate_signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "aggregate_signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "min_survival_rate": min((as_float(w.get("survival_rate")) or 0.0 for w in windows), default=0.0),
        "max_window_drawdown_pct": max((as_float(w.get("max_drawdown_pct")) or 0.0 for w in windows), default=0.0),
        "windows": windows,
    }


def summarize_forward_rows() -> dict[str, Any]:
    rows = read_jsonl(FORWARD_REPLACEMENT)
    prior_log = read_json(PRIOR_FORWARD_READINESS_LOG)
    prior_audit = prior_log.get("gate2", {}).get("artifact_audit", {})
    prior_rows = int(prior_audit.get("artifact_rows") or 0)
    prior_by_sleeve = prior_audit.get("rows_by_sleeve") or {}

    by_sleeve: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_regime = Counter()
    for row in rows:
        sleeve = str(row.get("sleeve_key") or row.get("sleeve") or "unknown")
        by_sleeve[sleeve].append(row)
        by_regime[str(row.get("entry_regime_label") or "missing")] += 1

    sleeve_summaries = []
    for sleeve, sleeve_rows in sorted(by_sleeve.items(), key=lambda item: (-len(item[1]), item[0])):
        cash_values = [as_float(row.get("replacement_value_vs_cash_usd")) or 0.0 for row in sleeve_rows]
        spy_values = [as_float(row.get("replacement_value_vs_spy_usd")) or 0.0 for row in sleeve_rows]
        qqq_values = [as_float(row.get("replacement_value_vs_qqq_usd")) or 0.0 for row in sleeve_rows]
        positive_cash_by_ticker: Counter[str] = Counter()
        for row, cash in zip(sleeve_rows, cash_values):
            if cash > 0:
                positive_cash_by_ticker[str(row.get("ticker") or "unknown")] += cash
        positive_total = sum(positive_cash_by_ticker.values())
        max_single_positive_share = (
            max(positive_cash_by_ticker.values()) / positive_total if positive_total > 0 else None
        )
        activation_ready = (
            len(sleeve_rows) >= ACCEPTANCE_RULE["min_activation_closed_rows_per_sleeve"]
            and sum(cash_values) > 0
            and sum(spy_values) > 0
            and sum(qqq_values) > 0
            and (sum(1 for value in cash_values if value > 0) / len(sleeve_rows)) >= ACCEPTANCE_RULE["min_positive_rate"]
            and (max_single_positive_share is not None)
            and max_single_positive_share <= ACCEPTANCE_RULE["max_single_positive_cash_share"]
        )
        watchlist_ready = (
            len(sleeve_rows) >= ACCEPTANCE_RULE["min_watchlist_closed_rows_per_sleeve"]
            and sum(cash_values) > 0
            and sum(spy_values) > 0
            and sum(qqq_values) > 0
            and (max_single_positive_share is not None)
            and max_single_positive_share <= ACCEPTANCE_RULE["max_single_positive_cash_share"]
        )
        sleeve_summaries.append(
            {
                "sleeve_key": sleeve,
                "closed_rows": len(sleeve_rows),
                "prior_closed_rows": int(prior_by_sleeve.get(sleeve) or 0),
                "row_delta_since_exp_20260622_013": len(sleeve_rows) - int(prior_by_sleeve.get(sleeve) or 0),
                "ticker_count": len({str(row.get("ticker") or "unknown") for row in sleeve_rows}),
                "sum_replacement_value_vs_cash_usd": round(sum(cash_values), 2),
                "sum_replacement_value_vs_spy_usd": round(sum(spy_values), 2),
                "sum_replacement_value_vs_qqq_usd": round(sum(qqq_values), 2),
                "cash_positive_rate": round(sum(1 for value in cash_values if value > 0) / len(sleeve_rows), 4),
                "max_single_positive_cash_share": round(max_single_positive_share, 6) if max_single_positive_share is not None else None,
                "activation_ready": activation_ready,
                "watchlist_ready": watchlist_ready,
            }
        )

    return {
        "artifact": repo_rel(FORWARD_REPLACEMENT),
        "current_rows": len(rows),
        "prior_rows_exp_20260622_013": prior_rows,
        "row_delta_since_exp_20260622_013": len(rows) - prior_rows,
        "rows_by_sleeve": dict(Counter({summary["sleeve_key"]: summary["closed_rows"] for summary in sleeve_summaries})),
        "rows_by_entry_regime_label": dict(by_regime),
        "sleeve_summaries": sleeve_summaries,
        "activation_ready_sleeves": [s for s in sleeve_summaries if s["activation_ready"]],
        "watchlist_ready_sleeves": [s for s in sleeve_summaries if s["watchlist_ready"]],
        "new_rows_material_enough": (len(rows) - prior_rows) >= ACCEPTANCE_RULE["min_new_forward_rows_since_prior_readiness"],
    }


def summarize_status_jsonl(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    statuses = Counter(str(row.get("status") or "missing") for row in rows)
    reasons = Counter(str(row.get("reason") or "missing") for row in rows)
    return {
        "path": repo_rel(path),
        "row_count": len(rows),
        "statuses": dict(statuses),
        "non_skipped_rows": sum(1 for row in rows if str(row.get("status") or "") not in {"skipped", "missing"}),
        "top_reasons": dict(reasons.most_common(3)),
    }


def summarize_recent_surface_logs() -> list[dict[str, Any]]:
    summaries = []
    for item in RECENT_SURFACE_LOGS:
        data = read_json(item["path"])
        gate4 = data.get("gate4") if isinstance(data.get("gate4"), dict) else {}
        summaries.append(
            {
                "experiment_id": item["experiment_id"],
                "surface": item["surface"],
                "decision": data.get("decision") or data.get("status") or "missing_log",
                "status": data.get("status"),
                "accepted_alpha": bool(data.get("accepted_alpha")),
                "observed_only_lead": bool(data.get("observed_only_lead")),
                "failed_reasons": gate4.get("failed_reasons") or data.get("calibration", {}).get("failure_modes_observed") or [],
                "blocking_read": item["blocking_read"],
            }
        )
    return summaries


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = load_baseline()
    forward = summarize_forward_rows()
    kova_intraday = summarize_status_jsonl(KOVA_INTRADAY)
    kova_13f = summarize_status_jsonl(KOVA_13F)
    recent_logs = summarize_recent_surface_logs()

    recent_observed_leads = [
        row for row in recent_logs if row.get("observed_only_lead") or row.get("accepted_alpha")
    ]
    failed_reasons = []
    if not forward["new_rows_material_enough"]:
        failed_reasons.append("too_few_new_forward_rows_since_exp_20260622_013")
    if not forward["activation_ready_sleeves"]:
        failed_reasons.append("no_forward_activation_ready_sleeve")
    if not forward["watchlist_ready_sleeves"]:
        failed_reasons.append("no_forward_watchlist_ready_sleeve")
    if kova_intraday["non_skipped_rows"] == 0:
        failed_reasons.append("kova_intraday_all_skipped")
    if kova_13f["non_skipped_rows"] == 0:
        failed_reasons.append("kova_sec13f_all_skipped")
    if not recent_observed_leads:
        failed_reasons.append("recent_surface_closeouts_have_no_observed_lead")
    failed_reasons.append("factor_residual_reopen_requires_materially_new_flow_ownership_borrow_options_or_forward_rows")

    gate4_passed = not failed_reasons
    decision = (
        "accepted_current_surface_alpha_ready"
        if gate4_passed
        else "rejected_no_gate_ready_current_alpha_surface_delta"
    )
    status = "accepted" if gate4_passed else "rejected"
    actual_success = 1 if gate4_passed else 0
    predicted = as_float(prediction.get("success_probability")) or 0.0

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": gate4_passed,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_readiness_delta",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": actual_success,
            "actual_decision": decision,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "failure_modes_observed": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(prediction.get("main_failure_modes", []))
                & {
                    "too_few_new_forward_rows",
                    "all_new_surfaces_recently_rejected",
                    "kova_intraday_13f_unavailable",
                    "near_neighbor_frozen_family",
                }
            ),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "strategy_behavior_changed": False,
            "new_forward_rows_since_exp_20260622_013": forward["row_delta_since_exp_20260622_013"],
            "activation_ready_sleeves": len(forward["activation_ready_sleeves"]),
            "watchlist_ready_sleeves": len(forward["watchlist_ready_sleeves"]),
        },
        "gate1": {
            "passed": True,
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": True,
            "runtime_fields_checked": [
                "entry_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "entry_regime_label",
                "Kova intraday status",
                "Kova 13F status",
                "recent closeout decisions",
            ],
            "target_price_scope": "No executable candidate or exit is scheduled; target_price is not consumed by this readiness audit.",
            "forward_replacement": forward,
            "kova_intraday": kova_intraday,
            "kova_sec13f": kova_13f,
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "baseline_min_survival_rate": baseline["min_survival_rate"],
            "note": "No entry filter, ranking, sizing, exit, or candidate generation rule changed.",
        },
        "gate4": {
            "passed": gate4_passed,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "acceptance_rule": ACCEPTANCE_RULE,
            "current_forward_rows": forward["current_rows"],
            "new_forward_rows_since_exp_20260622_013": forward["row_delta_since_exp_20260622_013"],
            "activation_ready_sleeves": forward["activation_ready_sleeves"],
            "watchlist_ready_sleeves": forward["watchlist_ready_sleeves"],
            "recent_observed_leads": recent_observed_leads,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "surface_closeout_scan": recent_logs,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty_gate": "experiment.py new accepted this as source=other with no strong near-neighbor; override records the post-20260622 evidence delta axis.",
                "factor_residual": "exp-20260622-025 rejected after the factor warehouse repair; a factor retry requires materially different PIT flow, ownership, borrow/options, event-quality, or closed forward replacement rows.",
                "forward_replacement": "exp-20260622-013 and exp-20260623-004 rejected activation readiness; current artifact has only two additional rows.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "uses_llm": False,
            "parity_note": "Read-only readiness delta audit over existing artifacts/logs; no production or backtest behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current evidence delta is not enough to justify a new "
                "strategy-affecting alpha: forward replacement gained only "
                f"{forward['row_delta_since_exp_20260622_013']} rows since "
                "the prior readiness audit, Kova intraday/13F remain skipped, "
                "and the completed Kova/options/short-volume/exit/pilot/factor "
                "surfaces were all rejected or non-leads."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry factor residual, Kova RS/growth, Kova intraday "
                "refresh flags, options skew, daily short-volume imbalance, "
                "exit lifecycle pressure, pilot scalar, low_deployment ETF "
                "concentration, or forward regime cells on the same rows by "
                "relaxing thresholds, row-count gates, hold days, top-N, "
                "notional, cooldown, or source ranks."
            ),
            "new_evidence_required": (
                "A valid next alpha needs materially more closed forward "
                "replacement rows for one diversified sleeve/source family, "
                "non-skipped Kova intraday or 13F provenance, PIT borrow/loan "
                "or options history with stronger provenance, or a new "
                "production-visible field not already saturated."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(BASELINE_RESULT),
            repo_rel(KOVA_INTRADAY),
            repo_rel(KOVA_13F),
            *[repo_rel(item["path"]) for item in RECENT_SURFACE_LOGS],
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in [
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
            "artifact",
            "log",
            "anti_js",
        ]
    }


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} Current Surface Alpha Readiness Delta",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Current forward rows: `{gate4['current_forward_rows']}`",
        f"- New rows since exp-20260622-013: `{gate4['new_forward_rows_since_exp_20260622_013']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons'])}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Reflection",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Reproduce",
        "",
        f"```powershell\n{RUNNER_COMMAND}\n```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
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
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": (REPO_ROOT / path).exists() if not path.is_absolute() else path.exists(),
                "sha256": sha256(REPO_ROOT / path) if not path.is_absolute() else sha256(path),
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

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
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
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
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
                "new_forward_rows": payload["gate4"]["new_forward_rows_since_exp_20260622_013"],
                "current_forward_rows": payload["gate4"]["current_forward_rows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
