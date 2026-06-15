"""exp-20260615-018: accruals / cash-conversion improvement quality.

Replay-only alpha search. This tests a materially different SEC Companyfacts
quality field from exp-20260614-020: not static low accruals, but improving
annual cash conversion / falling accruals versus the prior fiscal year. The
intent is to keep the prior accruals gross edge while avoiding the broad,
drawdown-heavy momentum sleeve that failed Gate 4.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260614_020_accruals_cash_conversion_quality as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260615-018"
STEM = "accruals_cash_conversion_improvement_quality"
TRIAL_FAMILY = "accruals_cash_conversion_improvement_quality_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_annual_accruals_improvement_top1_next_open_10d_v1"
CHANGED_VARIABLE = "accruals_cash_conversion_improvement_quality_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"
SCRIPT_PATH = Path(__file__)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_CASH_CONVERSION_IMPROVEMENT = 0.15
MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT = 0.005

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 4000.0,
    "main_failure_modes": [
        "thin_prior_year_sample",
        "static_accruals_edge_lost",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Static annual accruals had strong gross all-window EV but drawdown "
        "failed; requiring prior-year improvement is a distinct PIT "
        "quality-momentum field that may cut broad deployment, but annual data "
        "cadence and recent Companyfacts fragility keep prior low."
    ),
    "recorded_at": "2026-06-15T17:10:54+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production path. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "annual current/prior-year accruals and cash-conversion improvement "
        "gate, liquid SPY-relative confirmation, cooldown, next-open paper "
        "entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: annual cash-conversion improvement and falling "
        "accruals versus the prior fiscal year should identify durable "
        "earnings-quality leaders, reducing the drawdown-heavy breadth of the "
        "static accruals sleeve while preserving its gross edge."
    ),
    "2_history_check": {
        "exp-20260614-020": (
            "Static annual accruals/cash conversion had EV +0.9921 and PnL "
            "+$21,322.65, positive in all three windows, but failed drawdown "
            "drift at +5.22pp."
        ),
        "exp-20260614-021": (
            "Low-deployment redesign cut sample but still regressed old_thin "
            "and exceeded drawdown drift."
        ),
        "exp-20260614-023": (
            "Daily-close protective stop preserved positive aggregate EV but "
            "regressed two windows and still exceeded drawdown drift."
        ),
        "exp-20260615-008/016": (
            "FCF/capex and operating-leverage quality variants were positive "
            "but failed window/drawdown/comparator gates, so this avoids "
            "another static quality threshold and tests a prior-year "
            "improvement field."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least 20 paper "
        "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted compression/distribution "
        "candidate-pool comparators beaten. Replay-only positives are leads "
        "until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_018_accruals_cash_conversion_improvement_quality.py"
    ),
}

_ORIGINAL_ACCRUALS_QUALITY = base._accruals_quality
_ORIGINAL_CANDIDATE_ROWS = base._candidate_rows_for_window
_ORIGINAL_BUILD_PAYLOAD = base._build_payload
_ORIGINAL_BUILD_LOG_RECORD = base._build_log_record


def _previous_annual_before(
    facts: list[dict[str, Any]], asof: str, current_end: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof and fact["end"] < current_end:
            chosen = fact
    return chosen


def _accruals_improvement_quality(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current = _ORIGINAL_ACCRUALS_QUALITY(ticker, asof, facts)
    if current is None:
        return None
    ni = base._latest_on_or_before(facts["net_income"], asof)
    if ni is None:
        return None
    ocf = base._matched_on_or_before(facts["operating_cash_flow"], asof, ni["end"])
    assets = base._latest_on_or_before(facts["assets"], asof)
    prior_ni = _previous_annual_before(facts["net_income"], asof, ni["end"])
    if ocf is None or assets is None or prior_ni is None:
        return None
    prior_ocf = base._matched_on_or_before(
        facts["operating_cash_flow"], asof, prior_ni["end"]
    )
    if prior_ocf is None or assets["value"] <= 0.0:
        return None
    ni_val = float(ni["value"])
    ocf_val = float(ocf["value"])
    prior_ni_val = float(prior_ni["value"])
    prior_ocf_val = float(prior_ocf["value"])
    if ni_val <= 0.0 or ocf_val <= 0.0 or prior_ni_val <= 0.0 or prior_ocf_val <= 0.0:
        return None
    current_cash_conversion = ocf_val / ni_val
    current_accruals_to_assets = (ni_val - ocf_val) / float(assets["value"])
    prior_cash_conversion = prior_ocf_val / prior_ni_val
    prior_accruals_to_assets = (prior_ni_val - prior_ocf_val) / float(assets["value"])
    cash_conversion_improvement = current_cash_conversion - prior_cash_conversion
    accruals_to_assets_improvement = prior_accruals_to_assets - current_accruals_to_assets
    if (
        cash_conversion_improvement < MIN_CASH_CONVERSION_IMPROVEMENT
        and accruals_to_assets_improvement < MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT
    ):
        return None
    return {
        **current,
        "prior_fiscal_year_end": prior_ni["end"],
        "prior_net_income_filed": prior_ni["filed"],
        "prior_operating_cash_flow_filed": prior_ocf["filed"],
        "prior_net_income": base._round(prior_ni_val, 2),
        "prior_operating_cash_flow": base._round(prior_ocf_val, 2),
        "prior_cash_conversion_ratio": base._round(prior_cash_conversion, 6),
        "prior_accruals_to_assets": base._round(prior_accruals_to_assets, 6),
        "cash_conversion_improvement": base._round(cash_conversion_improvement, 6),
        "accruals_to_assets_improvement": base._round(
            accruals_to_assets_improvement, 6
        ),
    }


def _candidate_rows_for_window(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = _ORIGINAL_CANDIDATE_ROWS(*args, **kwargs)
    for row in rows:
        cash_improvement = float(row.get("quality_cash_conversion_improvement") or 0.0)
        accrual_improvement = float(row.get("quality_accruals_to_assets_improvement") or 0.0)
        score = float(row.get("candidate_score") or 0.0)
        row["source"] = "ACCRUALS_CASH_CONVERSION_IMPROVEMENT_QUALITY_PAPER"
        row["rule_version"] = RULE_VERSION
        row["source_rule_version"] = RULE_VERSION
        row["candidate_score"] = base._round(
            score
            + 0.80 * min(max(cash_improvement, 0.0), 1.0)
            + 4.00 * min(max(accrual_improvement, 0.0), 0.10),
            6,
        )
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("quality_cash_conversion_improvement") or 0.0),
            -float(row.get("quality_accruals_to_assets_improvement") or 0.0),
            float(row.get("quality_accruals_to_assets") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan = {
        **scan,
        "rule_version": RULE_VERSION,
        "min_cash_conversion_improvement": MIN_CASH_CONVERSION_IMPROVEMENT,
        "min_accruals_to_assets_improvement": MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT,
        "improvement_candidate_rows": len(rows),
        "improvement_candidate_tickers": len({row["ticker"] for row in rows}),
    }
    return rows, scan


def _decision_for_gate(passed: bool) -> str:
    if passed:
        return "positive_replay_lead_not_promoted_accruals_cash_conversion_improvement_quality"
    return "rejected_accruals_cash_conversion_improvement_quality_candidate_pool"


def _build_payload() -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    target_count = payload["target_trade_summary"]["total_trade_count"]
    gate4 = payload["gate4"]
    gate4["decision"] = _decision_for_gate(bool(gate4.get("passed")))
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": (
                "positive_replay_lead_not_promoted"
                if gate4.get("passed")
                else "rejected"
            ),
            "decision": gate4["decision"],
            "hypothesis": (
                "Annual cash-conversion improvement and falling accruals versus "
                "the prior fiscal year may identify durable SEC Companyfacts "
                "earnings-quality leaders and avoid the broad drawdown-heavy "
                "static accruals sleeve."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "new_evidence_type": (
                "free_sec_companyfacts_prior_year_accruals_improvement_plus_ohlcv"
            ),
            "nearby_prior_experiments": [
                "exp-20260614-020",
                "exp-20260614-021",
                "exp-20260614-023",
                "exp-20260615-008",
                "exp-20260615-016",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "rejection_reason": (
                None
                if gate4.get("passed")
                else "; ".join(gate4.get("failed_reasons") or [])
            ),
            "interpretation": (
                "The prior-year accruals/cash-conversion improvement source "
                "cleared Gate 4 as a replay-only lead; production remains "
                "unchanged until a shared daily/backtest helper reproduces it."
                if gate4.get("passed")
                else (
                    "The prior-year accruals/cash-conversion improvement source "
                    "did not clear Gate 4. Do not promote it or tune the "
                    "improvement/static quality thresholds on these frozen "
                    "windows."
                )
            ),
            "next_evidence_needed": (
                "A retry needs materially richer PIT earnings-quality evidence "
                "such as quarterly same-period operating-cash-flow accruals, "
                "analyst-count/dispersion confirmation, or closed forward "
                "replacement rows; do not sweep the current/prior improvement, "
                "static accruals, price-confirmation, top-N, hold, cooldown, or "
                "notional thresholds."
            ),
            "related_files": [
                base._repo_rel(SCRIPT_PATH),
                base._repo_rel(OUT_JSON),
                base._repo_rel(LOG_JSON),
                base._repo_rel(TICKET_JSON),
                base._repo_rel(CARD_MD),
                base._repo_rel(MANIFEST_JSON),
                base._repo_rel(EXPERIMENT_LOG),
                base._repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload["parameters"].update(
        {
            "min_cash_conversion_improvement": MIN_CASH_CONVERSION_IMPROVEMENT,
            "min_accruals_to_assets_improvement": MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual net_income and operating_cash_flow are known by SEC filed date "
        "(<= signal date), matched on current and prior fiscal-year period ends, "
        "and compared using the latest filed assets denominator. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            (
                "Gate 4 passed: prior-year cash-conversion/accruals improvement "
                "kept enough of the static accruals gross edge while passing "
                "drawdown, concentration, sample, and accepted comparator guards."
            )
            if gate4.get("passed")
            else (
                "Gate 4 failed. The improvement discriminator either made the "
                "sample too thin or still behaved like a price-confirmed "
                "Companyfacts momentum overlay. Failed reasons: "
                + (", ".join(gate4.get("failed_reasons") or []) or "none")
                + "."
            )
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                target_count,
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping current/prior cash-conversion improvement, "
            "accruals-improvement, static accruals, annual fact freshness, "
            "RS/close/volume/vol guards, top-N, hold days, cooldown, or notional "
            "on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accruals / Cash-Conversion Improvement Quality",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": payload["decision"],
            "status": payload["status"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "related_files": payload["related_files"],
        }
    )
    return record


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket_file": base._repo_rel(TICKET_JSON),
        "card_file": base._repo_rel(CARD_MD),
        "revision_manifest_file": base._repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            base._repo_rel(SCRIPT_PATH),
            base._repo_rel(OUT_JSON),
            base._repo_rel(CARD_MD),
            base._repo_rel(MANIFEST_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(EXPERIMENT_LOG),
            base._repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            base._repo_rel(SCRIPT_PATH): base.framework._sha256(SCRIPT_PATH),
            base._repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            base._repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            base._repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            base._repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _patch_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._accruals_quality = _accruals_improvement_quality
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._build_payload = _build_payload
    base._build_log_record = _build_log_record
    base._build_card = _build_card
    base._persist = _persist
    base._write_manifest = _write_manifest


def main() -> None:
    _patch_base()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
