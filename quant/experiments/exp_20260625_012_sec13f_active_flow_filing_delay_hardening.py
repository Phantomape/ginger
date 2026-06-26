"""exp-20260625-012: PIT filing-delay hardening for SEC13F active-flow scout.

This reuses the fixed exp-20260625-010 active-manager flow candidate bundle,
but changes exactly one attribution boundary: a 13F quarter is not available to
signals until 45 calendar days after quarter end. No production behavior is
changed and no live/default-off helper is promoted.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260625_010_sec13f_active_flow_historical_scout as base  # noqa: E402


EXPERIMENT_ID = "exp-20260625-012"
STEM = "sec13f_active_flow_filing_delay_hardening"
TRIAL_FAMILY = "sec13f_active_manager_flow_filing_delay_pit_hardening"
TRIAL_VARIANT_ID = "filing_delay_45d_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_active_manager_flow_filing_delay_pit_hardened_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
FILING_DELAY_DAYS = 45

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_012_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

NEW_EVIDENCE_AXIS = (
    "New machine-checkable gate shape: use only SEC13F active-flow windows whose "
    "quarter-end date is at least 45 calendar days before signal date, explicitly "
    "testing the filing-delay PIT weakness disclosed by exp-20260625-010; this "
    "does not retune active-holder/value thresholds, top-N, hold, cooldown, or "
    "notional."
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.05,
    "expected_pnl_delta": 1_000.0,
    "main_failure_modes": [
        "filing_delay_erases_candidate_coverage",
        "window_regression",
        "drawdown_drift",
        "not_incremental",
        "concentration_failed",
    ],
    "confidence_reason": (
        "The forward active-flow attribution was positive, but exp-20260625-010 "
        "already failed Gate 4 before filing-delay hardening and explicitly "
        "disclosed quarter-end availability as a PIT weakness. The only reason "
        "to run this is to decide whether the lead survives a realistic 13F "
        "availability boundary."
    ),
    "recorded_at": "2026-06-25T11:04:57+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "pit_filing_delay_days": FILING_DELAY_DAYS,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "This run tests whether the exp-20260625-010 active-flow lead survives "
        "a realistic SEC13F filing-delay boundary before any shared helper work."
    ),
    "parity_note": (
        "This experiment changes no production code. It only hardens the private "
        "historical replay by requiring each SEC13F active-flow window to be at "
        "least 45 calendar days past quarter end before a signal can use it. A "
        "positive result would still require a shared historical/daily default-off "
        "helper and parity tests."
    ),
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "pit_filing_delay_days": FILING_DELAY_DAYS,
        "kill_switch": "trade_enabled remains false; no production adapter changes",
    },
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC13F active-manager active-flow is only worth further "
        "shared-helper work if the fixed historical candidate bundle still passes "
        "Gate 4 when 13F windows become usable only after a 45-day filing delay."
    ),
    "2_history_check": {
        "exp-20260625-009": (
            "Positive observed-only Kova forward active-flow lead, not promoted "
            "because it lacked canonical fixed-window PIT coverage."
        ),
        "exp-20260625-010": (
            "Historical active-flow scout was rejected and disclosed quarter-end "
            "availability as a PIT weakness."
        ),
        "exp-20260624-018": "Aggregate SEC13F sponsorship forward lead; different field.",
        "exp-20260624-019": "Coownership network follow-up rejected; different relation field.",
        "novelty_gate": (
            "Initial reservation was blocked as a SEC13F near-neighbor. Override "
            "was recorded because the new axis is a machine-checkable 45-day "
            "filing-delay gate shape, not threshold retuning."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical windows and AGENTS Gate 4. Numeric "
        "evidence must improve aggregate EV/PnL with no window regression, "
        "survival >=5%, drawdown drift <=0.5pp, enough trades across all three "
        "windows, and clean concentration. Even a pass is only a private replay "
        "lead until shared historical/daily parity exists."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260625_012_sec13f_active_flow_filing_delay_hardening.py"
    ),
}


def _available_on(window_end: str) -> str:
    return (base._safe_date(window_end) + timedelta(days=FILING_DELAY_DAYS)).isoformat()


def _patch_base() -> None:
    base.__file__ = __file__
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
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.NEW_EVIDENCE_AXIS = NEW_EVIDENCE_AXIS
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS

    original_history = base._build_active_flow_history
    original_gate4 = base._gate4

    def build_active_flow_history_with_delay(universe: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows, summary = original_history(universe)
        for row in rows:
            if row.get("window_end"):
                row["active13f_window_available_on"] = _available_on(row["window_end"])
        summary["availability_rule"] = {
            "rule": "quarter_end_plus_calendar_days",
            "filing_delay_days": FILING_DELAY_DAYS,
            "reason": "approximate SEC 13F institutional manager filing deadline",
        }
        return rows, summary

    def latest_active_flow_window_with_delay(
        signal_date: str,
        ordered_windows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        signal = base._safe_date(signal_date)
        available = [
            row
            for row in ordered_windows
            if row.get("prior_window_label")
            and row.get("window_end")
            and base._safe_date(row["window_end"]) + timedelta(days=FILING_DELAY_DAYS) <= signal
        ]
        return available[-1] if available else None

    def gate4_with_delay_name(
        *,
        aggregate: dict[str, Any],
        target_summary: dict[str, Any],
        before_metrics: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        gate = original_gate4(
            aggregate=aggregate,
            target_summary=target_summary,
            before_metrics=before_metrics,
        )
        gate["decision"] = (
            "positive_replay_lead_not_promoted_sec13f_active_flow_filing_delay_hardened"
            if gate.get("passed")
            else "rejected_sec13f_active_flow_filing_delay_hardened_candidate_pool"
        )
        gate["pit_filing_delay_days"] = FILING_DELAY_DAYS
        return gate

    base._build_active_flow_history = build_active_flow_history_with_delay
    base._latest_active_flow_window = latest_active_flow_window_with_delay
    base._gate4 = gate4_with_delay_name


def _annotate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["single_causal_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["new_evidence_type"] = "pit_filing_delay_gate_shape"
    payload["new_evidence_axis"] = NEW_EVIDENCE_AXIS
    payload["prediction"] = {
        **payload.get("prediction", {}),
        **PREDICTION,
        "actual_success": payload.get("prediction", {}).get("actual_success"),
        "actual_ev_delta": payload.get("prediction", {}).get("actual_ev_delta"),
        "actual_pnl_delta": payload.get("prediction", {}).get("actual_pnl_delta"),
        "brier_score": payload.get("prediction", {}).get("brier_score"),
    }
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload.setdefault("parameters", {})["pit_filing_delay_days"] = FILING_DELAY_DAYS
    payload["backtest_protocol"]["sec13f_provenance"] = (
        "Cached SEC structured Form 13F filing-window ZIP files. A signal day "
        "uses the latest cached window whose quarter end is at least 45 calendar "
        "days before the signal date and compares it with the prior ended window."
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses active-flow SEC13F features only after the 45-day filing-delay "
        "availability boundary, plus signal-date OHLCV after the close. Paper entry "
        "is next available open; exit is the close 10 trading days after signal."
    )
    payload["causal_components"] = [
        "raw manager-level SEC13F active-manager classification",
        "quarter-over-quarter active-holder and active-value flow deltas",
        "45-day PIT filing-delay availability control",
        "fixed liquid leadership OHLCV confirmation",
        "same-ticker core-overlap exclusion",
        "next-open 10-session paper replay",
    ]
    payload["interpretation"] = (
        payload["interpretation"]
        .replace("active-manager active-flow source", "filing-delay-hardened active-manager active-flow source")
        .replace("active-manager active-flow candidate pool", "filing-delay-hardened active-manager active-flow candidate pool")
    )
    if not payload.get("gate4", {}).get("passed"):
        payload["rejection_reason"] = "; ".join(payload.get("gate4", {}).get("failed_reasons") or [])
    payload["next_evidence_needed"] = (
        "A valid retry needs enough closed 10d forward rows, non-quarterly active-manager "
        "flow provenance, populated borrow/loan availability cross-evidence, or a shared "
        "daily helper with true filing-date/as-of controls. Do not sweep active-flow, "
        "OHLCV, top-N, hold, cooldown, or notional thresholds on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": payload["interpretation"],
        "outcome_summary": payload["post_run_reflection"].get("outcome_summary"),
        "forbidden_near_neighbor_retry": (
            "Do not retry SEC13F active-holder share, active-value share, active-flow "
            "deltas, aggregate sponsorship, coownership network, filing-delay offsets, "
            "top-N, hold, cooldown, notional, or allocator thresholds on the same "
            "frozen windows or the same exp017 partial forward rows."
        ),
        "new_evidence_required": (
            "Need materially more closed 10d forward rows, non-quarterly active-manager "
            "flow provenance, populated borrow/loan availability cross-evidence, or "
            "shared helper/daily snapshot evidence with exact filing-date/as-of controls."
        ),
    }
    payload["related_files"] = base._related_files()
    payload["changed_files"] = base._related_files()
    return payload


def main() -> None:
    _patch_base()
    payload = _annotate_payload(base._build_payload())
    base.persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
