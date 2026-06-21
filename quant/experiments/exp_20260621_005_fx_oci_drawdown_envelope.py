"""exp-20260621-005: FX OCI drawdown-aware notional envelope.

Replay-only alpha search. The fixed decision hypothesis is a risk-allocation
policy bundle on top of the already tested raw SEC FX-translation OCI component
tailwind source from exp-20260620-026. The source, ranking, hold, cooldown,
entry/exit semantics, FX tags, and revenue gates stay fixed. Only selected
paper trades are resized by a pre-entry OHLCV volatility/drawdown envelope.

No production code, shared adapter, live/default orders, core ranking, exits,
LLM/news path, or watchlist behavior is changed. A positive replay is only a
lead until a shared default-off helper reproduces the same policy in both
historical replay and daily observation. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260620_026_foreign_currency_oci_component_tailwind as prior
from experiment_registry import persist_self_registered_result


EXPERIMENT_ID = "exp-20260621-005"
STEM = "fx_oci_drawdown_envelope"
TRIAL_FAMILY = "fx_oci_drawdown_aware_risk_allocation"
TRIAL_VARIANT_ID = "fx_oci_prior_vol_drawdown_notional_envelope_top1_next_open_10d_v1"
CHANGED_VARIABLE = "fx_oci_drawdown_aware_volatility_notional_envelope_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
TARGET_REALIZED_VOL_20D = 0.045
TARGET_PRIOR_DRAWDOWN_20D = 0.080
MIN_NOTIONAL_SCALAR = 0.35
MAX_NOTIONAL_SCALAR = 1.00

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "pnl_comparator_not_beaten",
        "drawdown_still_high",
        "window_regression",
        "source_risk_not_ex_ante_separable",
    ],
    "confidence_reason": (
        "The source already showed positive EV/PnL in all three fixed windows "
        "and failed only the drawdown guard; the allowed new axis is a "
        "predeclared OHLCV risk envelope, not FX tag/notional/hold threshold "
        "mining. Main risk is that the drawdown came from needed winners, so "
        "risk scaling loses the accepted distribution comparator."
    ),
    "recorded_at": "2026-06-21T04:08:56+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "trade_enabled": False,
    "live_ready": False,
    "live_realism_evaluated": True,
    "execution_envelope": {
        **prior.PRODUCTION_IMPACT["execution_envelope"],
        "target_notional_per_paper_trade": (
            f"{BASE_NOTIONAL_USD:.0f} * scalar, scalar clipped to "
            f"{MIN_NOTIONAL_SCALAR:.2f}-{MAX_NOTIONAL_SCALAR:.2f}"
        ),
        "notional_scalar_rule": (
            "min(1.0, target_vol20 / realized_vol20, "
            "target_drawdown20 / prior_drawdown20), floored at 0.35"
        ),
        "failure_handling": (
            "missing FX OCI source fields, missing OHLCV risk fields, missing "
            "next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC FX OCI source plus the same PIT OHLCV realized-volatility and "
        "prior-drawdown notional envelope in both historical replay and daily "
        "production observation."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "risk_allocation: the raw SEC FX-translation OCI component tailwind "
        "source was positive in all three canonical windows but failed only "
        "drawdown; applying one fixed PIT OHLCV volatility/drawdown notional "
        "envelope may preserve replacement value while bringing max drawdown "
        "drift inside Gate 4."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new warned on companyfacts/risk-allocation "
            "near-neighbors. Override records the new evidence axis explicitly "
            "allowed by exp-20260620-026: a predeclared drawdown-aware policy "
            "bundle using PIT OHLCV volatility/drawdown while FX source tags, "
            "ranking, hold, cooldown, and daily top-1 selection stay fixed."
        ),
        "exp-20260620-026": (
            "Raw FX OCI tailwind improved all three windows and beat accepted "
            "compression/distribution aggregate comparators, but failed only "
            "drawdown drift."
        ),
        "exp-20260620-028": (
            "FX OCI plus hedge confirmation became too weak/thin and did not "
            "solve the deployable edge."
        ),
        "exp-20260620-030": (
            "FX OCI plus cash-effect confirmation remained drawdown/comparator "
            "fragile. This run does not add another FX field; it tests an "
            "ex-ante OHLCV risk envelope."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. The after policy must "
        "have positive aggregate EV/PnL, no window EV/PnL regression, target "
        "sample across all three windows, survival >=5%, max drawdown drift "
        "<=0.5pp, concentration pass, and accepted compression/distribution "
        "candidate-pool comparators beaten. Because this is a replay-only "
        "risk-allocation scout, a positive result remains a lead until a shared "
        "daily/backtest helper exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260621_005_fx_oci_drawdown_envelope.py"
    ),
}

_ORIGINAL_SELECT = prior.base.framework._select_paper_trades


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior.base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior.base._round(value, digits)


def _prior_drawdown_20d(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> float | None:
    rows = prior.base.framework.shadow._series(snapshot, ticker)
    idx = prior.base.framework.shadow._row_index(rows).get(signal_date)
    if idx is None or idx < 19:
        return None
    closes: list[float] = []
    for row in rows[idx - 19 : idx + 1]:
        close = prior.base.framework.shadow._value(row, "Close")
        if close is None or close <= 0.0:
            return None
        closes.append(float(close))
    peak = max(closes)
    current = closes[-1]
    if peak <= 0.0:
        return None
    return max(0.0, 1.0 - current / peak)


def _notional_scalar(trade: dict[str, Any], prior_drawdown_20d: float | None) -> tuple[float, dict[str, Any]]:
    realized_vol = float(trade.get("candidate_realized_vol_20d") or 0.0)
    vol_scalar = 1.0
    if realized_vol > 0.0:
        vol_scalar = min(1.0, TARGET_REALIZED_VOL_20D / realized_vol)

    drawdown_scalar = 1.0
    if prior_drawdown_20d is not None and prior_drawdown_20d > 0.0:
        drawdown_scalar = min(1.0, TARGET_PRIOR_DRAWDOWN_20D / prior_drawdown_20d)

    raw_scalar = min(MAX_NOTIONAL_SCALAR, vol_scalar, drawdown_scalar)
    scalar = max(MIN_NOTIONAL_SCALAR, raw_scalar)
    return scalar, {
        "fx_oci_risk_realized_vol_20d": _round(realized_vol, 6),
        "fx_oci_risk_prior_drawdown_20d": _round(prior_drawdown_20d, 6),
        "fx_oci_risk_vol_scalar": _round(vol_scalar, 6),
        "fx_oci_risk_drawdown_scalar": _round(drawdown_scalar, 6),
        "fx_oci_risk_raw_notional_scalar": _round(raw_scalar, 6),
        "fx_oci_risk_notional_scalar": _round(scalar, 6),
        "fx_oci_risk_rule_version": RULE_VERSION,
    }


def _apply_drawdown_envelope(
    snapshot: dict[str, list[dict[str, Any]]],
    selected: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    scan: Counter[str] = Counter()
    scalars: list[float] = []
    for trade in selected:
        ticker = str(trade.get("ticker") or "").upper()
        signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
        prior_dd = _prior_drawdown_20d(snapshot, ticker, signal_date)
        scalar, fields = _notional_scalar(trade, prior_dd)
        pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
        adjusted_notional = BASE_NOTIONAL_USD * scalar
        adjusted_trade = {
            **trade,
            **fields,
            "paper_notional_usd_before_risk": BASE_NOTIONAL_USD,
            "paper_notional_usd": _round(adjusted_notional, 2),
            "pnl_before_risk": trade.get("pnl"),
            "pnl": _round(adjusted_notional * pnl_pct, 2),
        }
        adjusted.append(adjusted_trade)
        scalars.append(scalar)
        if scalar < 0.999:
            scan["scaled_down_trades"] += 1
        if prior_dd is None:
            scan["missing_prior_drawdown"] += 1
    scan["selected_trade_count"] = len(selected)
    scan["mean_notional_scalar"] = _round(sum(scalars) / len(scalars), 6) if scalars else None
    scan["min_notional_scalar"] = _round(min(scalars), 6) if scalars else None
    scan["max_notional_scalar"] = _round(max(scalars), 6) if scalars else None
    return adjusted, dict(scan)


def _select_paper_trades_with_drawdown_envelope(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected, filtered = _ORIGINAL_SELECT(snapshot=snapshot, candidates=candidates)
    adjusted, risk_scan = _apply_drawdown_envelope(snapshot, selected)
    for trade in adjusted:
        trade["risk_envelope_scan"] = risk_scan
    return adjusted, filtered


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fx_oci_drawdown_envelope"
        if gate["passed"]
        else "rejected_fx_oci_drawdown_envelope"
    )
    return gate


def _configure() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OWNER = OWNER
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior._configure_base()
    prior.base.framework._select_paper_trades = _select_paper_trades_with_drawdown_envelope
    prior.base._gate4 = _gate4


def _postprocess(payload: dict[str, Any]) -> dict[str, Any]:
    payload = prior._postprocess_payload(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    raw_baseline = json.loads(
        (REPO_ROOT / "data" / "experiments" / "exp-20260620-026" / "exp_20260620_026_foreign_currency_oci_component_tailwind.json").read_text(
            encoding="utf-8"
        )
    )
    raw_aggregate = raw_baseline["delta_metrics"]["aggregate"]
    risk_scans: dict[str, Any] = {}
    for label, trades in payload["target_trades_by_window"].items():
        if trades:
            risk_scans[label] = trades[0].get("risk_envelope_scan", {})
        else:
            risk_scans[label] = {}

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected",
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "risk_allocation_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_free_sec_companyfacts_oci_component_candidate_pool"
            ),
            "new_evidence_type": "pit_ohlcv_drawdown_aware_policy_bundle",
            "nearby_prior_experiments": [
                "exp-20260620-026",
                "exp-20260620-028",
                "exp-20260620-030",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "risk_envelope_by_window": risk_scans,
            "raw_fx_oci_comparator": {
                "experiment_id": "exp-20260620-026",
                "aggregate_expected_value_delta": raw_aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": raw_aggregate["total_pnl_delta_sum"],
                "max_drawdown_delta": raw_aggregate["max_drawdown_delta_max"],
                "decision": raw_baseline["decision"],
            },
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "single_causal_variable": CHANGED_VARIABLE,
        "base_notional_usd": BASE_NOTIONAL_USD,
        "target_realized_vol_20d": TARGET_REALIZED_VOL_20D,
        "target_prior_drawdown_20d": TARGET_PRIOR_DRAWDOWN_20D,
        "min_notional_scalar": MIN_NOTIONAL_SCALAR,
        "max_notional_scalar": MAX_NOTIONAL_SCALAR,
        "unchanged_fx_oci_source_experiment": "exp-20260620-026",
    }
    payload["backtest_protocol"]["execution_model"] = (
        payload["backtest_protocol"]["execution_model"]
        + " After selected trades are formed under the unchanged exp-20260620-026 "
        "source, paper notional is scaled before overlay PnL by a PIT OHLCV "
        "risk envelope using signal-date realized_vol20 and prior 20-session "
        "drawdown from high. Entry/exit prices, hold, cooldown, daily top-1 "
        "selection, source tags, source thresholds, and candidate ranking remain fixed."
    )
    payload["gate2"]["runtime_fields"].extend(
        [
            "candidate_realized_vol_20d from signal-date OHLCV",
            "prior 20-session drawdown from signal-date OHLCV",
        ]
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
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    if gate4["passed"]:
        interpretation = (
            "The drawdown-aware OHLCV notional envelope cleared the canonical "
            "three-window replay screen, but remains only a replay lead because "
            "the shared daily/backtest helper was not promoted in this scout."
        )
    else:
        interpretation = (
            "The drawdown-aware OHLCV notional envelope did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "The fixed source and entry logic were unchanged; the result shows "
            "whether ex-ante vol/drawdown can separate the raw FX OCI source's "
            "tail risk without losing too much accepted-comparator replacement value."
        )
    payload["interpretation"] = interpretation
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping FX OCI tags, FX OCI ratio/improvement, "
            "revenue, fact freshness, price/RS/volume guards, top-N, hold, "
            "cooldown, or the vol/drawdown scalar constants on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially richer PIT global-exposure evidence "
            "such as segment/currency revenue mix, FX sensitivity disclosure, "
            "cash-flow hedge OCI reclassification detail, or closed forward "
            "replacement-value rows under a shared default-off helper."
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
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Mean scalar |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        risk = payload["risk_envelope_by_window"].get(label) or {}
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {scalar} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                scalar=risk.get("mean_notional_scalar"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FX OCI Drawdown-Aware Envelope",
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
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Max drawdown drift: `{:+.4f}`".format(aggregate["max_drawdown_delta_max"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    log_record = prior.base._build_log_record(payload)
    prior.base.framework._write_json(OUT_JSON, payload)
    prior.base.framework._write_json(LOG_JSON, payload)
    prior.base.framework._write_text(CARD_MD, _card(payload))
    prior.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
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
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): prior.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): prior.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prior.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prior.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prior.base.framework._sha256(CARD_MD),
        },
    }
    prior.base.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure()
    payload = _postprocess(prior.base._build_payload())
    _persist(payload)
    print(json.dumps(prior.base.framework._safe(prior.base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
