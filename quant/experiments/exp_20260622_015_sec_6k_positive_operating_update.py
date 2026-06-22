"""exp-20260622-015: SEC 6-K positive operating-update helper replay.

Alpha-search experiment for a newly repaired production-visible 6-K text
surface. The single decision hypothesis is that foreign issuer 6-K text with
explicit positive operating updates or raised outlook, combined with same-day
liquid SPY-relative absorption, can form a default-off paper candidate source.

The helper is shared and daily-capable, but this experiment does not wire it
into run.py, backtester.py, live orders, or paper-sleeve state. If Gate 4 fails,
the helper is not promoted as a retained strategy surface.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import sec_6k_positive_operating_update_paper_sleeve as helper


EXPERIMENT_ID = "exp-20260622-015"
STEM = "sec_6k_positive_operating_update"
TRIAL_FAMILY = "sec_6k_foreign_issuer_text_positive_operating_update_candidate_pool"
TRIAL_VARIANT_ID = "sec_6k_positive_operating_update_v1"
CHANGED_VARIABLE = "sec_6k_positive_operating_update_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
HELPER_PY = REPO_ROOT / "quant" / "sec_6k_positive_operating_update_paper_sleeve.py"
TEST_PY = REPO_ROOT / "quant" / "test_sec_6k_positive_operating_update_paper_sleeve.py"

BASE_NOTIONAL_USD = helper.BASE_NOTIONAL_USD
HOLD_DAYS = helper.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = helper.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = helper.SAME_TICKER_COOLDOWN_DAYS

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "sparse_semantic_hits",
        "sec_text_false_positives",
        "accepted_comparator_not_beaten",
        "old_thin_window_fragility",
    ],
    "confidence_reason": (
        "exp-20260622-014 repaired production-visible 6-K event/text rows "
        "across all windows, and 6-K is a new foreign-issuer channel; however "
        "SEC text candidate pools are saturated and semantic false positives "
        "plus accepted-comparator weakness are likely."
    ),
    "recorded_at": "2026-06-22T15:03:59+00:00",
}

PRODUCTION_IMPACT = {
    **helper.production_impact(),
    "shared_policy_changed": True,
    "shared_helper_added": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": False,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "trade_enabled": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "parity_test_added": True,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "cash/default-off overlay only unless a future run adapter and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing 6-K/6-KA text, missing positive operating-update evidence, "
            "excluded financing/legal text, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "The helper exposes the same classifier and candidate builder for "
        "historical replay and daily snapshot construction, but this experiment "
        "does not wire it into run.py or write paper-sleeve state. A failing "
        "Gate 4 means no strategy promotion."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 6-K foreign issuer text with explicit positive "
        "operating updates or raised outlook, plus same-day liquid SPY-relative "
        "absorption, may identify ADR information shocks missed by domestic SEC "
        "event sleeves."
    ),
    "2_history_check": {
        "novelty_gate": "experiment.py new reported no strong near-neighbor.",
        "exp-20260621-018": (
            "Blocked raw 6-K metadata because the production-visible event/text "
            "surface was missing."
        ),
        "exp-20260622-014": (
            "Accepted measurement repair: shared daily event/text defaults now "
            "include 6-K with enough rows across all three windows."
        ),
        "exp-20260622-004": (
            "Supplier payment terms used multiple SEC forms including 6-K; this "
            "run tests a 6-K-specific operating-update semantic source, not "
            "supplier financing or generic SEC phrase scanning."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, at least two windows improve, no unacceptable drawdown or "
        "concentration drift, and accepted compression/distribution comparators "
        "must be beaten. If Gate 4 fails, do not promote the helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260622_015_sec_6k_positive_operating_update.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_shared_helper_lead_needs_daily_wiring_sec_6k_positive_operating_update"
        if gate["passed"]
        else "rejected_sec_6k_positive_operating_update_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | 6-K Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("event_rows_in_window", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 6-K Positive Operating Update",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Shared helper and parity test only. No run.py wiring, "
                "backtester.py change, paper-sleeve state write, live/default "
                "order, ranking, sizing, exit, LLM, or news behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = helper.load_sec_6k_positive_operating_update_rows
    base._build_quality_index = helper.build_sec_6k_positive_operating_update_quality_index
    base._candidate_rows_for_window = helper.candidate_rows_for_window
    base._gate4 = _gate4
    base._build_card = _build_card


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        status = "positive_shared_helper_lead_needs_daily_wiring"
        interpretation = (
            "The SEC 6-K positive operating-update helper cleared the numeric "
            "replay screen, but it is not promoted as accepted alpha here "
            "because run.py/default-off daily wiring was intentionally not "
            "changed in this experiment."
        )
    else:
        status = "rejected"
        interpretation = (
            "The SEC 6-K positive operating-update helper did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not promoted as a retained default-off strategy surface."
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "shared_helper_replay_no_run_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_6k_foreign_issuer_candidate_pool",
            "new_evidence_type": "sec_6k_daily_text_surface_repaired",
            "nearby_prior_experiments": [
                "exp-20260621-018",
                "exp-20260622-014",
                "exp-20260622-004",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "causal_components": [
                "6-K text semantic classifier",
                "historical replay through shared helper",
                "daily-capable snapshot helper",
                "focused helper parity test",
                "execution envelope",
                "Gate 1-4 verdict",
            ],
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "ev_prediction_error": (
            None
            if PREDICTION["expected_ev_delta"] is None
            else round(float(aggregate["expected_value_score_delta_sum"]) - PREDICTION["expected_ev_delta"], 6)
        ),
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "pnl_prediction_error": round(
            float(aggregate["total_pnl_delta_sum"]) - PREDICTION["expected_pnl_delta"],
            2,
        ),
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]).intersection(set(gate4["failed_reasons"]))
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "allowed_form_bases": sorted(helper.ALLOWED_FORM_BASES),
        "min_text_words": helper.MIN_TEXT_WORDS,
        "max_text_chars_scanned": helper.MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": helper.EVIDENCE_SPAN_CHARS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "positive_terms": helper.POSITIVE_RE.pattern,
        "operating_context_terms": helper.OPERATING_CONTEXT_RE.pattern,
        "outlook_raise_terms": helper.OUTLOOK_RAISE_RE.pattern,
        "exclude_terms": helper.EXCLUDE_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = None
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(helper.TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "SEC 6-K/6-KA filing text is keyed by accepted_at and usable_trade_date. "
        "The helper admits rows only when a local evidence span contains positive "
        "operating-update language plus operating metric context, while financing, "
        "offering, tender, M&A, litigation, meeting, and incentive-plan false "
        "positive buckets are excluded. Price confirmation uses only signal-date "
        "OHLCV. Paper entry is the next available open; exit is the close 10 "
        "trading days after signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing form_base/form_type 6-K or 6-K/A",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span positive operating-update terms",
        "local evidence-span operating metric context",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer 6-K semantics such as normalized "
        "issuer country/ADR liquidity, structured earnings table extraction, "
        "guidance revision magnitude, English-translation provenance, or closed "
        "forward replacement-value rows from a wired daily default-off helper. "
        "Do not sweep positive phrase lists, percentage thresholds, RS/close/"
        "volume guards, top-N, hold, cooldown, or notional on these frozen "
        "windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping 6-K positive phrase lists, operating-term "
            "lists, percentage thresholds, same-day absorption/RS/volume guards, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(HELPER_PY),
        _repo_rel(TEST_PY),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
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
        "implementation_mode": payload["implementation_mode"],
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
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
        "gate4": payload["gate4"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "lean_quality_passed": True,
    }
    base.persist_self_registered_result(
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
    files = [
        Path(__file__),
        HELPER_PY,
        TEST_PY,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(HELPER_PY),
            _repo_rel(TEST_PY),
            _repo_rel(OUT_JSON.parent),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(path): base.framework._sha256(path)
            for path in files
            if path.exists()
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
