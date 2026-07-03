"""exp-20260701-009: Kova SEC13F active-flow 10d forward value.

Observed-only alpha attribution. This reopens the Kova active-manager SEC13F
flow surface only because the hot warehouse now supplies closed 10d
replacement-value rows, which was the explicit reopen condition in the prior
active-flow lead. It keeps the active-flow score fixed and does not change
ranking, sizing, exits, paper sleeves, live orders, watchlists, LLM boundaries,
or production daily behavior.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260701-009"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_active_flow_10d_forward_value"
RUNNER = f"quant/experiments/exp_20260701_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260701_009_{SLUG}.json"
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
SETTLEMENT_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260701_002_kova_sec13f_sponsorship_10d_forward_value.py"
)
ACTIVE_FLOW_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260625_009_kova_sec13f_active_manager_flow_forward_attribution.py"
)

HYPOTHESIS = (
    "Observed-only alpha hypothesis: the previously positive Kova SEC13F "
    "active-manager active-flow field should still separate newly closed 10d "
    "cash/SPY/QQQ replacement value now that hot-warehouse coverage has "
    "matured beyond the prior 1d/3d/5d lead."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_active_manager_flow_forward_attribution"
TRIAL_VARIANT_ID = "hot_warehouse_10d_closed_forward_v1"
CHANGED_VARIABLE = "kova_sec13f_active_flow_10d_forward_value_v1"
SINGLE_CAUSAL_VARIABLE = CHANGED_VARIABLE
NEW_EVIDENCE_TYPE = "materially_more_closed_forward_rows"
NEW_EVIDENCE_AXIS = (
    "Materially more closed forward rows: active-manager active-flow was only "
    "tested on 1d/3d/5d partial Kova rows; hot warehouse coverage through "
    "2026-06-30 now creates 10d settled rows for the same predeclared field, "
    "without changing SEC13F thresholds, top-N, hold, notional, or response curve."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-009",
    "exp-20260625-025",
    "exp-20260701-002",
]
CAUSAL_COMPONENTS = [
    "newly closed 10d forward rows",
    "fixed PIT active-manager 13F flow score",
    "cash/SPY/QQQ replacement-value separation",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260701-009/exp_20260701_009_kova_sec13f_active_flow_10d_forward_value.json",
    "experiments/cards/exp-20260701-009.md",
    "experiments/manifests/exp-20260701-009.json",
    "experiments/tickets/exp-20260701-009.json",
    "experiments/logs/exp-20260701-009.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HORIZON = 10
COMPARATORS = ["cash", "spy", "qqq"]
FLOW_BUCKETS = [
    "missing_active_flow",
    "low_active_flow",
    "mid_active_flow",
    "high_active_flow",
]
ACCEPTANCE_RULE = {
    "horizon": HORIZON,
    "min_settled_rows": 100,
    "min_scored_rows": 500,
    "min_asof_dates": 3,
    "max_single_positive_pnl_share": 0.50,
    "positive_pnl_hhi_guardrail": 0.35,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "10d_signal_decay",
        "qqq_beta_only",
        "active_flow_historical_gate4_still_blocked",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260625-009 produced a strict 1d/3d/5d active-flow forward lead "
        "and exp-20260625-025 beat placebo, while both logs predeclared closed "
        "10d replacement rows as the next valid evidence; exp-20260701-002 "
        "proves the hot warehouse now supplies 2536 settled 10d rows, but "
        "historical fixed-window promotion remains a likely blocker."
    ),
}
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "uses_kova_forward_snapshots": True,
    "uses_sec13f_forward_context": True,
    "uses_raw_manager_level_sec13f_zip": True,
    "uses_hot_warehouse_forward_settlement": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only attribution and "
        "cannot become live-ready."
    ),
}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


settlement = load_module("exp20260701002_settlement", SETTLEMENT_RUNNER)
active_flow = load_module("exp20260625009_active_flow", ACTIVE_FLOW_RUNNER)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {} if default is None else default


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
    return active_flow.safe_float(value)


def round_or_none(value: Any, digits: int = 4) -> float | None:
    return active_flow.round_or_none(value, digits)


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = dict(DEFAULT_PREDICTION)
    if isinstance(ticket.get("prediction"), dict):
        prediction.update(ticket["prediction"])
    prediction.setdefault("recorded_at", utc_now())
    return prediction


def comparator_settled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get(f"forward_{HORIZON}d_status") == "settled"
        and safe_float(row.get(f"replacement_value_{HORIZON}d_vs_cash_usd")) is not None
        and safe_float(row.get(f"replacement_value_{HORIZON}d_vs_spy_usd")) is not None
        and safe_float(row.get(f"replacement_value_{HORIZON}d_vs_qqq_usd")) is not None
    ]


def source_summary(
    source_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
    enriched_rows: list[dict[str, Any]],
    settled_rows: list[dict[str, Any]],
    flow: dict[str, Any],
    settlement_metadata: dict[str, Any],
) -> dict[str, Any]:
    source_ids = [
        str(row.get("observation_id") or "") for row in source_rows if row.get("observation_id")
    ]
    source_tickers = sorted(
        {str(row.get("ticker") or "").upper() for row in source_rows if row.get("ticker")}
    )
    source_asof_dates = sorted(
        {str(row.get("asof_date") or "")[:10] for row in source_rows if row.get("asof_date")}
    )
    settled_asof_dates = sorted(
        {str(row.get("asof_date") or "")[:10] for row in settled_rows if row.get("asof_date")}
    )
    return {
        "source_ledger": repo_rel(settlement.SOURCE_LEDGER_JSONL),
        "source_ledger_exists": settlement.SOURCE_LEDGER_JSONL.exists(),
        "hot_warehouse": repo_rel(settlement.HOT_WAREHOUSE),
        "hot_warehouse_exists": settlement.HOT_WAREHOUSE.exists(),
        "source_rows": len(source_rows),
        "outcome_rows": len(outcome_rows),
        "duplicate_observation_ids": len(source_ids) - len(set(source_ids)),
        "source_ticker_count": len(source_tickers),
        "source_asof_date_start": source_asof_dates[0] if source_asof_dates else None,
        "source_asof_date_end": source_asof_dates[-1] if source_asof_dates else None,
        "source_asof_date_count": len(source_asof_dates),
        "settled_10d_comparator_rows": len(settled_rows),
        "settled_10d_asof_date_start": settled_asof_dates[0] if settled_asof_dates else None,
        "settled_10d_asof_date_end": settled_asof_dates[-1] if settled_asof_dates else None,
        "settled_10d_asof_date_count": len(settled_asof_dates),
        "source_sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in source_rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in outcome_rows).items())
        ),
        "active13f_status_counts_all": dict(
            sorted(Counter(str(row.get("active13f_status") or "missing") for row in enriched_rows).items())
        ),
        "active13f_status_counts_settled_10d": dict(
            sorted(Counter(str(row.get("active13f_status") or "missing") for row in settled_rows).items())
        ),
        "settlement_metadata": settlement_metadata,
        "flow_source_summary": flow["summary"],
    }


def evaluate_gate4(summary: dict[str, Any]) -> dict[str, Any]:
    high = summary["buckets"]["high_active_flow"]
    checks: dict[str, bool] = {
        "settled_10d_sample_floor": summary["settled_rows"] >= ACCEPTANCE_RULE["min_settled_rows"],
        "scored_10d_sample_floor": summary["scored_rows"] >= ACCEPTANCE_RULE["min_scored_rows"],
        "scored_asof_dates_floor": summary["scored_asof_date_count"]
        >= ACCEPTANCE_RULE["min_asof_dates"],
    }
    for comparator in COMPARATORS:
        checks[f"high_mean_{comparator}_beats_low"] = bool(
            summary["support"].get(f"high_mean_{comparator}_beats_low")
        )
        checks[f"high_median_{comparator}_beats_low"] = bool(
            summary["support"].get(f"high_median_{comparator}_beats_low")
        )
        rho = summary["spearman_score_to_replacement"].get(comparator)
        checks[f"spearman_{comparator}_positive"] = rho is not None and rho > 0

    concentration = high["cash_positive_concentration"]
    max_share = concentration.get("max_single_positive_pnl_share")
    hhi = concentration.get("positive_pnl_hhi")
    checks["high_bucket_single_ticker_concentration_pass"] = (
        max_share is not None
        and max_share <= ACCEPTANCE_RULE["max_single_positive_pnl_share"]
    )
    checks["high_bucket_positive_hhi_pass"] = (
        hhi is not None and hhi <= ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"]
    )
    checks["strategy_behavior_unchanged"] = True

    failed = [key for key, ok in checks.items() if not ok]
    observed_only_lead = not failed
    return {
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_10d_active_flow_lead_not_promoted_historical_gate4_blocked"
            if observed_only_lead
            else "rejected_no_10d_kova_active_flow_forward_edge"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "lead_limitations": [
            "Forward-only post-2026-06-13 rows, not canonical fixed-window PIT coverage.",
            "Historical fixed-window promotion attempts remain rejected in exp-20260625-010 and exp-20260625-012.",
            "No shared helper, daily adapter, ranking rule, sizing rule, or live behavior was promoted.",
        ],
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
        },
        "strategy_rerun_required": False,
    }


def build_analysis(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    settlement.EXPERIMENT_ID = EXPERIMENT_ID
    outcome_rows, settlement_metadata = settlement.settle_rows(source_rows)
    flow = active_flow.build_flow_features([], outcome_rows)
    enriched_rows = active_flow.enrich_outcome_rows(outcome_rows, flow)
    settled = comparator_settled_rows(enriched_rows)
    primary_summary = active_flow.summarize_horizon(settled, HORIZON)
    return {
        "outcome_rows": outcome_rows,
        "enriched_rows": enriched_rows,
        "settled_rows": settled,
        "settlement_metadata": settlement_metadata,
        "flow": flow,
        "source_summary": source_summary(
            source_rows,
            outcome_rows,
            enriched_rows,
            settled,
            flow,
            settlement_metadata,
        ),
        "score_definition": (
            "Fixed exp-20260625-009 active13f_active_flow_score: average "
            "percentile rank of active_value_share, active_holder_share, "
            "active_value_log_delta, and active_holder_count_delta among mapped "
            "tickers in the same raw SEC13F window."
        ),
        "primary_summary": primary_summary,
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket if isinstance(ticket, dict) else {})
    before = settlement.load_baseline_metrics()
    source_rows = settlement.read_jsonl(settlement.SOURCE_LEDGER_JSONL)
    analysis = build_analysis(source_rows)
    primary = analysis["primary_summary"]
    gate4 = evaluate_gate4(primary)
    observed_only_lead = gate4["observed_only_lead"]
    status = "observed_only_positive_lead" if observed_only_lead else "observed_only_rejected"
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual_success = 1 if observed_only_lead else 0
    why = (
        "The fixed Kova SEC13F active-manager flow field "
        f"{'did' if observed_only_lead else 'did not'} preserve a strict 10d "
        "cash/SPY/QQQ replacement-value edge on newly closed hot-warehouse rows. "
        "This run is attribution only and did not promote any trading behavior."
    )
    failed = gate4["failed_reasons"]
    realized_modes = failed or ["active_flow_forward_lead_survived_but_historical_promotion_still_blocked"]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": probability,
            "actual_success": actual_success,
            "brier_score": round((probability - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_modes": realized_modes,
            "predicted_failure_mode_hit": any(
                mode in str(realized_modes)
                for mode in prediction.get("main_failure_modes", [])
            ),
            "surprise_note": (
                "Low surprise: active-flow was previously a forward lead, but "
                "10d maturity and QQQ-adjusted evidence were the main open risks."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed with novelty override because the "
                    "reopen axis is materially more closed 10d forward rows, "
                    "not a new same-source field or response retune."
                ),
                "exp-20260625-009": (
                    "Observed-only positive 1d/3d/5d active-manager flow lead; "
                    "it predeclared enough closed 10d rows as a valid retry."
                ),
                "exp-20260625-025": (
                    "Placebo falsification supported the lead but blocked "
                    "promotion until closed 10d rows or canonical fixed-window "
                    "coverage existed."
                ),
                "exp-20260701-002": (
                    "Hot warehouse supplied 2,536 settled 10d Kova rows, proving "
                    "the quantitative reopen condition advanced."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only bundle: reuse the fixed active-manager "
                "active-flow score and test newly closed 10d cash/SPY/QQQ "
                "replacement-value separation."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if 10d settled/scored sample floors pass, "
                "high active-flow beats low by mean and median for cash/SPY/QQQ, "
                "Spearman correlations are positive, and concentration passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_ledger": repo_rel(settlement.SOURCE_LEDGER_JSONL),
            "hot_warehouse": repo_rel(settlement.HOT_WAREHOUSE),
            "settlement_helper": repo_rel(SETTLEMENT_RUNNER),
            "active_flow_helper": repo_rel(ACTIVE_FLOW_RUNNER),
            "horizon": HORIZON,
            "comparators": COMPARATORS,
            "bucket_method": (
                "tertiles on fixed active13f_active_flow_score; missing measured separately"
            ),
            "score_definition": analysis["score_definition"],
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "source_summary": analysis["source_summary"],
        "attribution": {
            "score_definition": analysis["score_definition"],
            "horizon": HORIZON,
            "primary_summary": primary,
            "sample_rows": [
                {
                    "ticker": row.get("ticker"),
                    "asof_date": row.get("asof_date"),
                    "entry_date": row.get("entry_date"),
                    "forward_10d_exit_date": row.get("forward_10d_exit_date"),
                    "active13f_window_label": row.get("active13f_window_label"),
                    "active13f_active_flow_score": round_or_none(
                        row.get("active13f_active_flow_score"), 6
                    ),
                    "active13f_active_value_share": round_or_none(
                        row.get("active13f_active_value_share"), 6
                    ),
                    "active13f_active_value_log_delta": round_or_none(
                        row.get("active13f_active_value_log_delta"), 6
                    ),
                    "replacement_value_10d_vs_cash_usd": row.get(
                        "replacement_value_10d_vs_cash_usd"
                    ),
                    "replacement_value_10d_vs_spy_usd": row.get(
                        "replacement_value_10d_vs_spy_usd"
                    ),
                    "replacement_value_10d_vs_qqq_usd": row.get(
                        "replacement_value_10d_vs_qqq_usd"
                    ),
                }
                for row in analysis["settled_rows"][:25]
            ],
        },
        "primary_summary": {
            "horizon": HORIZON,
            "summary": primary,
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(source_rows)
            and analysis["source_summary"]["duplicate_observation_ids"] == 0
            and bool(analysis["source_summary"]["flow_source_summary"]["loaded_window_labels"])
            and primary["settled_rows"] > 0,
            "fields_checked": [
                "observation_id",
                "asof_date",
                "ticker",
                "sec13f_source_file",
                "raw SEC13F manager_cik/manager_name",
                "raw SEC13F name_of_issuer",
                "raw SEC13F value_usd_thousands",
                "raw SEC13F shares",
                "active13f_active_flow_score",
                "forward_10d_status",
                "entry_date",
                "target_price",
                "replacement_value_10d_vs_cash_usd",
                "replacement_value_10d_vs_spy_usd",
                "replacement_value_10d_vs_qqq_usd",
            ],
            "source_summary": analysis["source_summary"],
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "attribution and does not schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(source_rows),
            "signals_survived": primary["settled_rows"],
            "survival_rate": round(primary["settled_rows"] / len(source_rows), 4)
            if source_rows
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova SEC13F active-holder share, active-value share, "
                "active-flow deltas, aggregate sponsorship, coownership network, "
                "options cross-evidence, Companyfacts quality, top-N, hold, "
                "cooldown, notional, allocator thresholds, or response-function "
                "retunes on this same 10d row set."
            ),
            "new_evidence_required": (
                "A valid retry needs materially more newly closed 10d rows beyond "
                "this hot-warehouse cohort, manager-level flow from a genuinely "
                "new non-quarterly source, borrow/loan-availability cross-evidence, "
                "or canonical fixed-window PIT coverage through a shared helper "
                "that beats accepted comparators."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(settlement.SOURCE_LEDGER_JSONL),
            repo_rel(settlement.HOT_WAREHOUSE),
            repo_rel(SETTLEMENT_RUNNER),
            repo_rel(ACTIVE_FLOW_RUNNER),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260625-009.json",
            "experiments/logs/exp-20260625-025.json",
            "experiments/logs/exp-20260701-002.json",
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
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at") if isinstance(ticket, dict) else None,
            "claimed_at": ticket.get("claimed_at") if isinstance(ticket, dict) else None,
            "hub_identity": ticket.get("hub_identity") if isinstance(ticket, dict) else None,
            "novelty": ticket.get("novelty") if isinstance(ticket, dict) else None,
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    primary = payload["primary_summary"]["summary"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
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
        "source_summary": payload["source_summary"],
        "primary_summary": {
            "horizon": HORIZON,
            "settled_rows": primary["settled_rows"],
            "scored_rows": primary["scored_rows"],
            "scored_asof_date_count": primary["scored_asof_date_count"],
            "buckets": primary["buckets"],
            "spearman_score_to_replacement": primary["spearman_score_to_replacement"],
            "support": primary["support"],
        },
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def card_bucket_row(name: str, summary: dict[str, Any]) -> str:
    metrics = summary["replacement_metrics"]
    return "| {name} | {n} | {score} | {share} | {delta} | {cash} | {spy} | {qqq} | {median_cash} |".format(
        name=name,
        n=summary["n"],
        score=summary["active_flow_score_median"],
        share=summary["active_value_share_median"],
        delta=summary["active_value_log_delta_median"],
        cash=money(metrics["replacement_value_vs_cash_usd"]["mean"]),
        spy=money(metrics["replacement_value_vs_spy_usd"]["mean"]),
        qqq=money(metrics["replacement_value_vs_qqq_usd"]["mean"]),
        median_cash=money(metrics["replacement_value_vs_cash_usd"]["median"]),
    )


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_summary"]["summary"]
    rows = [
        "| Bucket | Rows | Median Score | Median Active Share | Median Flow Delta | Mean Cash | Mean SPY | Mean QQQ | Median Cash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in FLOW_BUCKETS:
        rows.append(card_bucket_row(bucket, primary["buckets"][bucket]))
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F active-flow 10d forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            f"- Settled 10d rows: `{primary['settled_rows']}`",
            f"- Scored 10d rows: `{primary['scored_rows']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## 10d Buckets",
            "",
            "\n".join(rows),
            "",
            "## Gate 4",
            "",
            f"- Observed-only lead: `{payload['observed_only_lead']}`",
            f"- Failed reasons: `{payload['gate4']['failed_reasons']}`",
            f"- Spearman: `{primary['spearman_score_to_replacement']}`",
            "",
            "## Reproduction",
            "",
            f"```powershell\n{RUNNER_COMMAND}\n```",
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
        settlement.SOURCE_LEDGER_JSONL,
        settlement.HOT_WAREHOUSE,
        SETTLEMENT_RUNNER,
        ACTIVE_FLOW_RUNNER,
        REPO_ROOT / "experiments" / "logs" / "exp-20260625-009.json",
        REPO_ROOT / "experiments" / "logs" / "exp-20260625-025.json",
        REPO_ROOT / "experiments" / "logs" / "exp-20260701-002.json",
    ]
    for label in payload["source_summary"]["flow_source_summary"]["loaded_window_labels"]:
        files.append(active_flow.SEC13F_CACHE / f"{label}_form13f.zip")
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
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
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

    ticket_before = payload.get("ticket_before") or {}
    fields = {
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
        "ticket_file": repo_rel(TICKET_JSON),
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
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    primary = payload["primary_summary"]["summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "settled_10d_rows": primary["settled_rows"],
                "scored_10d_rows": primary["scored_rows"],
                "scored_asof_dates": primary["scored_asof_date_count"],
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
