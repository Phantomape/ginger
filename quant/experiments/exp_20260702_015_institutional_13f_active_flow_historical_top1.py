"""exp-20260702-015: actual filing-date PIT 13F active-flow top-1 replay.

This is a private replay scout. It reuses the fixed SEC 13F active-manager
flow candidate bundle from exp-20260625-010, but changes the attribution
boundary to require each structured 13F filing-window ZIP to be available only
after the maximum actual FILING_DATE present in that ZIP. No production/default
behavior is changed.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260625_010_sec13f_active_flow_historical_scout as base  # noqa: E402


EXPERIMENT_ID = "exp-20260702-015"
STEM = "institutional_13f_active_flow_historical_top1"
TRIAL_FAMILY = "institutional_13f_active_flow_historical_candidate_source"
TRIAL_VARIANT_ID = "filing_date_pit_top1_day_v1"
CHANGED_VARIABLE = "institutional_13f_active_flow_historical_top1_day_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260702_015_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

NEW_EVIDENCE_AXIS = (
    "New machine-checkable gate shape: raw institutional Form 13F quarterly "
    "filing-window ZIP ownership-flow features are joined to canonical fixed "
    "windows only after the maximum actual FILING_DATE present in each "
    "structured ZIP. This is not the SEC FTD plus FINRA parked observer and "
    "not another 2026 forward-row reslice, sponsorship threshold, coownership "
    "graph, hold-day, notional, or response-curve retry."
)

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 5_000.0,
    "main_failure_modes": [
        "window_instability",
        "accepted_comparator_not_beaten",
        "coverage_too_sparse",
        "old_thin_13f_lag",
    ],
    "confidence_reason": (
        "The 10d forward active-flow lead survived in exp-20260701-009 and "
        "uses manager-level ownership-change direction rather than sponsorship "
        "level, but previous historical 13F promotion attempts were fragile "
        "and quarterly filing lag can dilute canonical windows."
    ),
    "recorded_at": "2026-07-02T14:05:40+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "implementation_mode": "private_replay_scout",
    "actual_filing_date_pit": True,
    "private_replay_scout_escape_reason": (
        "This run checks whether the Kova active-flow forward lead has enough "
        "historical canonical-window support under actual structured 13F filing "
        "dates before any shared helper or daily default-off work."
    ),
    "parity_note": (
        "This experiment changes no production code. It only hardens the "
        "private historical replay by requiring each structured 13F window to "
        "be available after the maximum FILING_DATE present in its ZIP. A "
        "positive result would still need a shared historical/daily default-off "
        "helper and parity tests."
    ),
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "pit_availability_rule": "max_actual_submission_filing_date_per_structured_13f_zip",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
    },
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/ranking: a fixed historical institutional Form 13F "
        "active-manager ownership-flow top-1/day default-off candidate source "
        "may preserve the Kova forward lead across canonical windows when using "
        "actual structured-ZIP FILING_DATE availability and next-open 10d "
        "execution."
    ),
    "2_history_check": {
        "exp-20260625-009": (
            "Observed-only Kova forward active-flow lead was positive, but it "
            "was not canonical historical Gate 4 evidence."
        ),
        "exp-20260625-010": (
            "Historical active-flow scout was rejected despite positive "
            "aggregate EV/PnL because it regressed one window and had drawdown "
            "drift; it used filing-window end dates, not explicit max "
            "FILING_DATE rows."
        ),
        "exp-20260625-012": (
            "45-day delay hardening was rejected; this run uses the actual "
            "structured ZIP FILING_DATE maximum instead of a calendar-delay "
            "proxy."
        ),
        "exp-20260701-009": (
            "Fresh Kova 10d active-flow forward value remained a positive lead, "
            "but historical canonical-window coverage was still the blocker."
        ),
        "novelty_gate": (
            "Reservation required novelty override because 13F ownership "
            "candidate-pool neighbors exist. The declared new axis is the "
            "actual FILING_DATE availability gate shape, not a threshold or "
            "response-curve retune."
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
        "exp_20260702_015_institutional_13f_active_flow_historical_top1.py"
    ),
}

_AVAILABILITY_CACHE: dict[str, dict[str, Any]] = {}


def _parse_filing_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.upper(), fmt).date()
        except ValueError:
            pass
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    return None


def _window_filing_availability(label: str) -> dict[str, Any]:
    if label in _AVAILABILITY_CACHE:
        return _AVAILABILITY_CACHE[label]

    zip_path = base.SEC13F_CACHE / f"{label}_form13f.zip"
    fallback_date = base.window_end_date(label) + timedelta(days=45)
    result = {
        "window_label": label,
        "available_on": fallback_date.isoformat(),
        "availability_source": "fallback_window_end_plus_45d_unparsed_submission_dates",
        "submission_rows_with_filing_date": 0,
        "zip_path": base._repo_rel(zip_path),
    }
    if not zip_path.exists():
        result["availability_source"] = "fallback_window_end_plus_45d_missing_zip"
        _AVAILABILITY_CACHE[label] = result
        return result

    with base.zipfile.ZipFile(zip_path) as archive:
        sub_name = next(
            (
                name
                for name in archive.namelist()
                if name.upper().endswith("SUBMISSION.TSV")
                or name.upper().endswith("SUBMISSION.CSV")
            ),
            None,
        )
        if not sub_name:
            _AVAILABILITY_CACHE[label] = result
            return result
        max_filing_date: date | None = None
        count = 0
        for row in base._iter_zip_table(archive, sub_name):
            filing_date = _parse_filing_date(
                base._safe_key(row, "FILING_DATE", "filing_date")
            )
            if filing_date is None:
                continue
            count += 1
            if max_filing_date is None or filing_date > max_filing_date:
                max_filing_date = filing_date
        if max_filing_date is not None:
            result = {
                **result,
                "available_on": max_filing_date.isoformat(),
                "availability_source": "max_submission_filing_date_in_structured_zip",
                "submission_rows_with_filing_date": count,
            }
    _AVAILABILITY_CACHE[label] = result
    return result


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

    def build_active_flow_history_with_actual_filing_date(
        universe: set[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows, summary = original_history(universe)
        availability_by_label = {
            row["window_label"]: _window_filing_availability(row["window_label"])
            for row in rows
            if row.get("window_label")
        }
        for row in rows:
            info = availability_by_label.get(row.get("window_label"))
            if not info:
                continue
            row["active13f_window_available_on"] = info["available_on"]
            row["active13f_window_availability_source"] = info["availability_source"]
            row.setdefault("source_summary", {}).update(
                {
                    "active13f_window_available_on": info["available_on"],
                    "active13f_window_availability_source": info["availability_source"],
                    "submission_rows_with_filing_date": info[
                        "submission_rows_with_filing_date"
                    ],
                }
            )
            for feature in row.get("ticker_features", {}).values():
                feature["active13f_window_available_on"] = info["available_on"]
                feature["active13f_window_availability_source"] = info[
                    "availability_source"
                ]
        summary["availability_rule"] = {
            "rule": "max_actual_submission_filing_date_per_structured_13f_zip",
            "fallback": "window_end_plus_45d_only_if_submission_table_or_zip_missing",
            "reason": "point-in-time filing availability for private historical replay",
        }
        summary["window_availability_by_label"] = availability_by_label
        for window in summary.get("windows_loaded", []):
            info = availability_by_label.get(window.get("window_label"))
            if info:
                window["active13f_window_available_on"] = info["available_on"]
                window["active13f_window_availability_source"] = info[
                    "availability_source"
                ]
                window["submission_rows_with_filing_date"] = info[
                    "submission_rows_with_filing_date"
                ]
        return rows, summary

    def latest_active_flow_window_with_actual_filing_date(
        signal_date: str,
        ordered_windows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        signal = base._safe_date(signal_date)
        available = []
        for row in ordered_windows:
            if not row.get("prior_window_label"):
                continue
            available_on = row.get("active13f_window_available_on") or row.get("window_end")
            if base._safe_date(available_on) <= signal:
                available.append(row)
        return available[-1] if available else None

    def gate4_with_actual_filing_date_name(
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
            "positive_replay_lead_not_promoted_institutional_13f_actual_filing_date"
            if gate.get("passed")
            else "rejected_institutional_13f_actual_filing_date_candidate_source"
        )
        gate["actual_filing_date_pit"] = True
        return gate

    base._build_active_flow_history = build_active_flow_history_with_actual_filing_date
    base._latest_active_flow_window = latest_active_flow_window_with_actual_filing_date
    base._gate4 = gate4_with_actual_filing_date_name


def _annotate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["hypothesis"] = PRE_RUN_QUESTIONS["1_alpha_hypothesis"]
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["single_causal_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["mechanism_family"] = "production_visible_institutional_13f_active_flow_candidate_pool"
    payload["new_evidence_type"] = "actual_filing_date_pit_gate_shape"
    payload["new_evidence_axis"] = NEW_EVIDENCE_AXIS
    payload["nearby_prior_experiments"] = [
        "exp-20260625-009",
        "exp-20260625-010",
        "exp-20260625-012",
        "exp-20260701-009",
    ]
    payload["prior_trial_count"] = 4
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
    payload.setdefault("parameters", {})[
        "pit_availability_rule"
    ] = "max_actual_submission_filing_date_per_structured_13f_zip"
    payload["backtest_protocol"]["sec13f_provenance"] = (
        "Cached SEC structured Form 13F filing-window ZIP files. A signal day "
        "uses the latest cached window whose maximum actual SUBMISSION.FILING_DATE "
        "is <= signal date and compares it with the prior available window."
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses active-flow 13F features only after the actual max filing-date "
        "availability boundary, plus signal-date OHLCV after the close. Paper entry "
        "is next available open; exit is the close 10 trading days after signal."
    )
    payload["causal_components"] = [
        "raw institutional Form 13F active-manager classification",
        "quarter-over-quarter active-holder and active-value flow deltas",
        "actual max SUBMISSION.FILING_DATE availability control",
        "fixed liquid leadership OHLCV confirmation",
        "same-ticker core-overlap exclusion",
        "next-open 10-session paper replay",
    ]
    payload["interpretation"] = (
        payload["interpretation"]
        .replace("SEC13F active-manager active-flow source", "institutional 13F actual-filing-date active-flow source")
        .replace("SEC13F active-manager active-flow candidate pool", "institutional 13F actual-filing-date active-flow candidate pool")
    )
    if not payload.get("gate4", {}).get("passed"):
        payload["rejection_reason"] = "; ".join(
            payload.get("gate4", {}).get("failed_reasons") or []
        )
    payload["next_evidence_needed"] = (
        "A valid retry needs materially more closed 10d forward rows, "
        "non-quarterly active-manager flow provenance, populated borrow/loan "
        "availability cross-evidence, or a shared daily helper with exact "
        "filing-date/as-of controls. Do not sweep active-flow, OHLCV, top-N, "
        "hold, cooldown, notional, or allocator thresholds on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": payload["interpretation"],
        "outcome_summary": payload["post_run_reflection"].get("outcome_summary"),
        "forbidden_near_neighbor_retry": (
            "Do not retry 13F active-holder share, active-value share, active-flow "
            "deltas, aggregate sponsorship, coownership network, filing-date "
            "offsets, top-N, hold, cooldown, notional, or allocator thresholds on "
            "the same frozen windows or same partial forward rows."
        ),
        "new_evidence_required": (
            "Need materially more closed 10d forward rows, non-quarterly "
            "active-manager flow provenance, populated borrow/loan availability "
            "cross-evidence, or shared helper/daily snapshot evidence with exact "
            "filing-date/as-of controls."
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
