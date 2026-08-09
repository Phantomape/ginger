"""Revalidate the unchanged accruals-quality candidate pool under MTM v1.

The decision policy is byte-for-byte inherited from exp-20260614-020.  This
runner changes only the evaluation surface: both the current core baseline and
the paper overlay use the schema-v1 dated daily-return contract introduced by
exp-20260712-006.  It deliberately does not retune any Companyfacts, OHLCV,
selection, holding-period, cooldown, or notional input.
"""

from __future__ import annotations

import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260614_020_accruals_cash_conversion_quality as prior  # noqa: E402
import exp_20260712_009_dod_contract_revenue_materiality as mtm_v1  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260712-011"
STEM = "accruals_cash_conversion_schema_v1"
TRIAL_FAMILY = "accruals_cash_conversion_quality_schema_v1_revalidation"
TRIAL_VARIANT_ID = "unchanged_annual_accruals_top1_10d_schema_v1"
CHANGED_VARIABLE = "unchanged_accruals_cash_conversion_quality_v1_under_schema_v1_daily_mtm"
RULE_VERSION = prior.RULE_VERSION
OWNER = "alpha-explore"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_011_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CURRENT_BASELINE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260712-006"
    / "current_working_stack_sharpe_inference.json"
)
PRIOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260614-020"
    / "exp_20260614_020_accruals_cash_conversion_quality.json"
)

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.60,
    "expected_pnl_delta": 18_000.0,
    "main_failure_modes": [
        "drawdown_drift_persists",
        "current_mtm_reveals_window_regression",
        "accruals_relabels_momentum",
        "current_schema_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The unchanged prior policy added about $21.3k with positive EV/PnL in "
        "all three windows and failed only drawdown. The signal is credible, "
        "but its broad 369-trade deployment likely remains too risky after the "
        "schema-v1 MTM repair."
    ),
    "recorded_at": "2026-07-12T14:11:12+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "protocol_revalidation_no_policy_retained_unless_numeric_gate4_passes",
    "trade_enabled": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "replay_only": True,
    "live_ready": False,
    "parity_note": (
        "The policy is unchanged and experiment-local. A numeric pass remains "
        "only a positive replay lead until a current-schema accepted comparator "
        "and the unchanged shared historical/daily helper are present."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/protocol revalidation: the unchanged annual accruals "
        "and cash-conversion quality source may retain positive all-window "
        "after-cost value without violating drawdown when measured by the "
        "corrected schema-v1 daily MTM equity curve."
    ),
    "2_history_check": {
        "exp-20260614-020": (
            "Unchanged fixed source added +0.9921 legacy EV and +$21,322.65 "
            "with 3/3 windows positive, but failed only +5.22pp drawdown drift."
        ),
        "exp-20260614-021": "Low-deployment redesign regressed old_thin.",
        "exp-20260614-023": "Protective-stop redesign still failed drawdown/windows.",
        "exp-20260712-006": (
            "Accepted measurement repair: archived Sharpe/EV/drawdown are not "
            "comparable to schema-v1 daily MTM and final-cost measurements."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Same current schema-v1 baseline/challenger; positive aggregate EV/PnL, "
        "no window EV/PnL regression, >=20 trades across all windows, survival "
        ">=5%, drawdown drift <=0.5pp, concentration pass, and current-schema "
        "accepted comparators before any acceptance."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260712_011_accruals_cash_conversion_schema_v1.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()


def _install() -> None:
    """Point the frozen prior runner at this ID and the schema-v1 metric path."""

    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.OWNER = OWNER
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS

    original_load = prior._load_window_snapshot

    def load_and_bind_snapshot(*args: Any, **kwargs: Any) -> dict[str, list[dict[str, Any]]]:
        snapshot = original_load(*args, **kwargs)
        mtm_v1._CURRENT_WINDOW_SNAPSHOT = snapshot
        return snapshot

    prior._load_window_snapshot = load_and_bind_snapshot
    frozen_artifact = json.loads(PRIOR_ARTIFACT.read_text(encoding="utf-8"))
    frozen_trades = frozen_artifact["target_trades_by_window"]
    remaining_windows = list(prior.framework.WINDOWS)

    def select_frozen_prior_trades(
        *,
        snapshot: dict[str, list[dict[str, Any]]],
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        del snapshot, candidates
        if not remaining_windows:
            raise RuntimeError("fixed prior-trade selector called too many times")
        label = remaining_windows.pop(0)
        return list(frozen_trades[label]), []

    prior.framework._select_paper_trades = select_frozen_prior_trades
    mtm_v1.STEM = STEM
    prior.framework.sleeve._overlay_from_paper_trades = (
        mtm_v1._overlay_from_paper_trades_current_mtm
    )
    prior.framework.overlay_helper._metrics = mtm_v1._metrics_current
    prior.framework.overlay_helper._metrics_with_overlay = (
        mtm_v1._metrics_with_overlay_current
    )


def _policy_lock() -> dict[str, Any]:
    artifact = json.loads(PRIOR_ARTIFACT.read_text(encoding="utf-8"))
    prior_parameters = artifact["parameters"]
    current = {
        "fy_duration_min": prior.FY_DURATION_MIN,
        "fy_duration_max": prior.FY_DURATION_MAX,
        "max_annual_fact_age_days": prior.MAX_ANNUAL_FACT_AGE_DAYS,
        "min_cash_conversion": prior.MIN_CASH_CONVERSION,
        "max_accruals_to_assets": prior.MAX_ACCRUALS_TO_ASSETS,
        "min_price": prior.MIN_PRICE,
        "min_avg_dollar_volume_20d": prior.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": prior.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": prior.MIN_RET60_EXCESS_SPY,
        "min_signal_return": prior.MIN_SIGNAL_RETURN,
        "max_signal_return": prior.MAX_SIGNAL_RETURN,
        "min_close_location": prior.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": prior.MAX_REALIZED_VOL_20D,
        "paper_notional_usd": prior.BASE_NOTIONAL_USD,
        "hold_days": prior.HOLD_DAYS,
        "max_paper_trades_per_day": prior.MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": prior.SAME_TICKER_COOLDOWN_DAYS,
    }
    mismatches = {
        key: {"prior": prior_parameters.get(key), "current": value}
        for key, value in current.items()
        if prior_parameters.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"frozen policy drifted: {mismatches}")
    trade_keys = []
    for label in prior.framework.WINDOWS:
        for row in artifact["target_trades_by_window"][label]:
            trade_keys.append(
                "|".join(
                    [
                        label,
                        str(row.get("ticker") or ""),
                        str(row.get("signal_date") or ""),
                        str(row.get("entry_date") or ""),
                        str(row.get("exit_date") or ""),
                    ]
                )
            )
    identity_sha = hashlib.sha256(
        json.dumps(trade_keys, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "passed": True,
        "prior_experiment": "exp-20260614-020",
        "rule_version": RULE_VERSION,
        "parameters": current,
        "mismatches": {},
        "fixed_prior_trade_count": len(trade_keys),
        "fixed_prior_trade_identity_sha256": identity_sha,
        "trade_source": _repo_rel(PRIOR_ARTIFACT),
    }


def _baseline_identity(payload: dict[str, Any]) -> dict[str, Any]:
    expected = json.loads(CURRENT_BASELINE.read_text(encoding="utf-8"))
    expected_by_label = {row["label"]: row for row in expected["windows"]}
    rows: dict[str, Any] = {}
    passed = True
    for label, metrics in payload["before_metrics"].items():
        actual_inference = metrics.get("sharpe_inference") or {}
        expected_inference = expected_by_label[label]["sharpe_inference"]
        actual_hash = actual_inference.get("return_series_sha256")
        expected_hash = expected_inference.get("return_series_sha256")
        row_passed = (
            int(actual_inference.get("schema_version") or 0) >= 1
            and actual_hash == expected_hash
        )
        rows[label] = {
            "passed": row_passed,
            "actual_return_series_sha256": actual_hash,
            "expected_return_series_sha256": expected_hash,
            "schema_version": actual_inference.get("schema_version"),
        }
        passed = passed and row_passed
    return {
        "passed": passed,
        "artifact": _repo_rel(CURRENT_BASELINE),
        "measurement_contract": "trial_adjusted_sharpe_inference_v1",
        "windows": rows,
    }


def _postprocess(payload: dict[str, Any], policy_lock: dict[str, Any]) -> dict[str, Any]:
    payload["timestamp"] = _utc_now()
    baseline_identity = _baseline_identity(payload)
    legacy_ev_comparator_reasons = {
        "accepted_compression_ev_not_beaten",
        "accepted_distribution_ev_not_beaten",
    }
    failed = [
        reason
        for reason in payload["gate4"].get("failed_reasons") or []
        if reason not in legacy_ev_comparator_reasons
    ]
    if not baseline_identity["passed"]:
        failed.append("gate1_current_schema_baseline_failed")
    failed = list(dict.fromkeys(failed))
    numeric_passed = not failed

    aggregate = payload["delta_metrics"]["aggregate"]
    decision = (
        "positive_replay_lead_requires_current_schema_comparator_and_shared_helper"
        if numeric_passed
        else "rejected_accruals_cash_conversion_schema_v1_revalidation"
    )
    status = "positive_replay_lead_not_promoted" if numeric_passed else "rejected"
    interpretation = (
        "The unchanged accruals bundle cleared the corrected numeric screen, "
        "but remains only a replay lead until a current-schema accepted "
        "candidate-pool comparator and unchanged shared daily helper exist."
        if numeric_passed
        else (
            "The corrected schema-v1 daily MTM replay still rejected the "
            "unchanged accruals bundle (failed: " + ", ".join(failed) + ")."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "status": status,
            "decision": decision,
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": numeric_passed,
            "full_stack_verdict": "pending" if numeric_passed else "reject",
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "unchanged_policy_protocol_revalidation",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_quality_candidate_pool",
            "new_evidence_type": "corrected_gate_shape_schema_v1_daily_mtm",
            "new_evidence_axis": (
                "exp-20260712-006 replaced archived equity measurement with "
                "schema-v1 dated daily MTM, open-position marks, and final costs."
            ),
            "nearby_prior_experiments": [
                "exp-20260614-020",
                "exp-20260614-021",
                "exp-20260614-023",
                "exp-20260712-006",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "policy_lock": policy_lock,
            "fixed_trade_measurement_replay": {
                "enabled": True,
                "reason": (
                    "Current candidate regeneration changed dozens of trade identities "
                    "in late_strong/mid_weak during preflight. Freezing the exact "
                    "369 exp-20260614-020 trades isolates the schema-v1 equity "
                    "measurement change from later universe/data drift."
                ),
                "trade_count": policy_lock["fixed_prior_trade_count"],
                "trade_identity_sha256": policy_lock[
                    "fixed_prior_trade_identity_sha256"
                ],
                "candidate_policy_recomputed_for_diagnostics_only": True,
            },
            "fingerprint_caveat": (
                "Reservation over-matched portfolio_covariance_lane because "
                "daily/equity/curve terms dominated. The true surface is "
                "companyfacts_ratio with a new schema-v1 evaluation gate shape; "
                "saturation was self-audited on that real surface."
            ),
            "interpretation": interpretation,
            "rejection_reason": None if numeric_passed else ";".join(failed),
        }
    )
    payload["gate1"] = {
        **payload.get("gate1", {}),
        "baseline_artifact": _repo_rel(CURRENT_BASELINE),
        "schema_v1_identity": baseline_identity,
        "passed": baseline_identity["passed"],
    }
    payload["gate4"].update(
        {
            "failed_reasons": failed,
            "passed": numeric_passed,
            "decision": decision,
            "accepted_comparator_protocol": {
                "legacy_ev_comparators_excluded": sorted(legacy_ev_comparator_reasons),
                "pnl_comparators_retained": True,
                "current_schema_ev_comparator_required_before_acceptance": True,
            },
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": numeric_passed,
        "actual_success": numeric_passed,
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_mode_hit": any(
            mode.split("_")[0] in ";".join(failed)
            for mode in PREDICTION["main_failure_modes"]
        ),
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if numeric_passed else 0.0)) ** 2,
            6,
        ),
    }
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Schema-v1 aggregate EV delta {:+.4f}; PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades."
        ).format(
            aggregate["expected_value_score_delta_sum"],
            aggregate["total_pnl_delta_sum"],
            float(aggregate.get("max_drawdown_delta_max") or 0.0),
            payload["target_trade_summary"]["total_trade_count"],
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry accrual thresholds, cash-conversion ratios, annual "
            "freshness, price/RS/volume/volatility gates, top-N, hold, cooldown, "
            "notional, stops, or another measurement wrapper on these windows."
        ),
        "new_evidence_required": (
            "Reopen only with PIT TTM/quarterly same-period accrual change, "
            "materially settled forward replacement rows, or (if numeric pass) "
            "the unchanged shared helper plus a current-schema accepted comparator."
        ),
    }
    payload["next_evidence_needed"] = payload["post_run_reflection"]["new_evidence_required"]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(CURRENT_BASELINE),
        _repo_rel(PRIOR_ARTIFACT),
    ]
    return payload


def _card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Accruals schema-v1 revalidation",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Result",
        "",
        f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
        f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
        f"- Max drawdown drift: `{float(aggregate.get('max_drawdown_delta_max') or 0.0):+.4f}`",
        f"- Paper trades: `{payload['target_trade_summary']['total_trade_count']}`",
        f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
        "",
        "## Boundary",
        "",
        "No production, shared policy, live/default order, threshold, ranking, sizing, or exit behavior changed.",
    ]
    return "\n".join(lines) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    prior.framework._write_json(OUT_JSON, payload)
    prior.framework._write_json(LOG_JSON, payload)
    prior.framework._write_text(CARD_MD, _card(payload))
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["numeric_gate4_passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): prior.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): prior.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prior.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prior.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prior.framework._sha256(CARD_MD),
        },
    }
    prior.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _install()
    policy_lock = _policy_lock()
    payload = _postprocess(prior._build_payload(), policy_lock)
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "gate1": payload["gate1"]["schema_v1_identity"],
                "aggregate": payload["delta_metrics"]["aggregate"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
