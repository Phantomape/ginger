"""exp-20260606-020: macro relief top-2 shared adapter.

Promotes the accepted exp-20260606-019 replay-only lead into a shared
default-off production-visible paper adapter and verifies the same
three-window evidence through the shared adapter code paths.

No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260606_019_macro_relief_top2_leadership_candidate_pool as base
from macro_relief_leadership_paper_sleeve import (
    candidate_rows_for_window as _shared_candidate_rows,
    select_paper_trades as _shared_select_trades,
)

EXPERIMENT_ID = "exp-20260606-020"
STEM = "macro_relief_top2_shared_adapter"
TRIAL_FAMILY = "macro_relief_leadership_candidate_pool"
TRIAL_VARIANT_ID = "macro_relief_top2_shared_adapter_v1"
CHANGED_VARIABLE = "shared_macro_relief_top2_leadership_paper_adapter_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = base.EXPERIMENT_LOG
REGISTRY_JSON = base.REGISTRY_JSON

MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS

PREDICTION = {
    "success_probability": 0.42,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "shared_adapter_replay_mismatch",
        "production_parity_gap",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260606-019 passed all three canonical windows but was replay-only; "
        "the next alpha value is validating the same source through shared "
        "default-off adapter semantics, not retuning thresholds."
    ),
    "recorded_at": "2026-06-06T17:04:37+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_paper_adapter_no_live_orders",
    "shared_policy_changed": True,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "The shared macro_relief_leadership_paper_sleeve helper now owns the "
        "official CPI/FOMC/NFP calendar, SPY+QQQ relief-day test, liquid stock "
        "universe candidate scoring, top-2 selection, 10-trading-day hold, "
        "next-open paper entry, slippage/cost model, and no-live-order boundary. "
        "The historical runner calls the same helper used by daily production snapshots."
    ),
}

HYPOTHESIS = (
    "The accepted macro relief top-2 leadership replay lead (exp-20260606-019) "
    "can be promoted into a shared default-off production-visible paper adapter "
    "with the same three-window evidence replicated through shared adapter code paths."
)


def _candidate_rows_for_window_shared(
    *,
    snapshot: dict[str, Any],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    return _shared_candidate_rows(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )


def _select_paper_trades_shared(
    *,
    snapshot: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _shared_select_trades(snapshot=snapshot, candidates=candidates)


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, Any],
) -> dict[str, Any]:
    gate = base.BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = [r for r in gate["failed_reasons"] if r != "target_sample_too_small"]
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["decision"] = (
        "accepted_shared_default_off_macro_relief_top2_leadership_paper_adapter"
        if not failed
        else "rejected_shared_macro_relief_top2_leadership_paper_adapter"
    )
    gate["target_trade_count_min"] = MIN_TARGET_TRADES
    gate["target_window_count_min"] = MIN_TARGET_WINDOWS
    return gate


def _configure_experiment() -> None:
    """Patch exp-033 (base.framework) globals so BASE_BUILD_PAYLOAD uses shared adapter."""
    fw = base.framework
    fw._candidate_rows_for_window = _candidate_rows_for_window_shared
    fw._select_paper_trades = _select_paper_trades_shared
    fw._gate4 = _gate4
    fw.EXPERIMENT_ID = EXPERIMENT_ID
    fw.STEM = STEM
    fw.TRIAL_FAMILY = TRIAL_FAMILY
    fw.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    fw.CHANGED_VARIABLE = CHANGED_VARIABLE
    fw.RULE_VERSION = CHANGED_VARIABLE
    fw.OUT_DIR = OUT_DIR
    fw.OUT_JSON = OUT_JSON
    fw.LOG_JSON = LOG_JSON
    fw.TICKET_JSON = TICKET_JSON
    fw.CARD_MD = CARD_MD
    fw.MANIFEST_JSON = MANIFEST_JSON
    fw.EXPERIMENT_LOG = EXPERIMENT_LOG
    fw.REGISTRY_JSON = REGISTRY_JSON
    fw.PREDICTION = PREDICTION
    fw.PRODUCTION_IMPACT = PRODUCTION_IMPACT


def _build_payload() -> dict[str, Any]:
    _configure_experiment()
    # Call exp-033's original _build_payload, now wired to shared adapter functions.
    payload = base.BASE_BUILD_PAYLOAD()
    gate4_passed = payload["gate4"]["passed"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": HYPOTHESIS,
            "change_type": "default_off_paper_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "free_official_macro_calendar_plus_ohlcv_candidate_pool",
            "new_evidence_type": "production_visible_shared_adapter_validation",
            "status": "accepted" if gate4_passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "nearby_prior_experiments": [
                "exp-20260606-019",
                "exp-20260606-017",
                "exp-20260525-901",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": (
                "The shared adapter reproduced the accepted macro relief top-2 "
                "leadership three-window edge while remaining default-off and "
                "order-disabled."
                if gate4_passed
                else (
                    "The shared adapter failed to reproduce exp-019 evidence cleanly. "
                    "Do not retain; revert to replay-only."
                )
            ),
            "rejection_reason": (
                None if gate4_passed else "; ".join(payload["gate4"]["failed_reasons"])
            ),
            "next_evidence_needed": (
                "Collect at least 30 closed forward 10-day macro relief paper "
                "trades before any live cash-deployment adapter."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    fw = base.framework
    payload.update(
        {
            "related_files": [
                fw._repo_rel(Path(__file__)),
                fw._repo_rel("quant/macro_relief_leadership_paper_sleeve.py"),
                fw._repo_rel("quant/test_macro_relief_leadership_paper_sleeve.py"),
                fw._repo_rel(OUT_JSON),
                fw._repo_rel(LOG_JSON),
                fw._repo_rel(TICKET_JSON),
                fw._repo_rel(CARD_MD),
                fw._repo_rel(MANIFEST_JSON),
                fw._repo_rel(EXPERIMENT_LOG),
                fw._repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "shared_adapter_promotion: can the macro relief top-2 leadership "
            "replay lead be promoted into a shared default-off production adapter "
            "with the same three-window evidence and parity test coverage?"
        ),
        "2_history_check": {
            "exp-20260606-019": (
                "Accepted replay lead: aggregate EV improved in all 3 windows, "
                "19+ trades, no regressions, but replay-only."
            ),
            "exp-20260606-017": (
                "Top-1 variant improved all windows but only 10 trades; "
                "top-2 fixed the sample size."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three canonical windows. Aggregate EV/PnL must improve vs "
            "baseline; no EV/PnL regression window; target trades >= 20 across "
            "all 3 windows; survival >= 5%; drawdown drift <= 0.5pp; "
            "concentration guard must pass."
        ),
        "5_reproducibility": (
            "python -B quant/experiments/"
            "exp_20260606_020_macro_relief_top2_shared_adapter.py"
        ),
    }
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4_passed,
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4_passed else 0.0)) ** 2,
            6,
        ),
    }
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    fw = base.framework
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "free_official_macro_calendar_plus_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": HYPOTHESIS,
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": fw._repo_rel(OUT_JSON),
        "log": fw._repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "macro_relief_day_count": payload["context_scan_by_window"][label].get(
                    "macro_relief_days"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in fw.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    fw = base.framework
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Macro relief days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in fw.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("macro_relief_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return (
        "\n".join(
            [
                f"# {EXPERIMENT_ID} Macro Relief Top-2 Shared Adapter",
                "",
                f"Status: `{payload['status']}`",
                f"Decision: `{payload['decision']}`",
                "",
                "## Hypothesis",
                "",
                HYPOTHESIS,
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
                "Shared default-off paper adapter (`quant/macro_relief_leadership_paper_sleeve.py`). "
                "No live orders. No core entry, ranking, sizing, exit, LLM, news, or watchlist behavior changed.",
                "",
                "No JavaScript was used.",
            ]
        )
        + "\n"
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    fw = base.framework
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            fw._repo_rel(Path(__file__)),
            fw._repo_rel("quant/macro_relief_leadership_paper_sleeve.py"),
            fw._repo_rel("quant/test_macro_relief_leadership_paper_sleeve.py"),
            fw._repo_rel(OUT_JSON),
            fw._repo_rel(LOG_JSON),
            fw._repo_rel(TICKET_JSON),
            fw._repo_rel(CARD_MD),
            fw._repo_rel(MANIFEST_JSON),
            fw._repo_rel(EXPERIMENT_LOG),
            fw._repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            fw._repo_rel(Path(__file__)): fw._sha256(Path(__file__)),
            fw._repo_rel(OUT_JSON): fw._sha256(OUT_JSON),
            fw._repo_rel(LOG_JSON): fw._sha256(LOG_JSON),
            fw._repo_rel(TICKET_JSON): fw._sha256(TICKET_JSON),
            fw._repo_rel(CARD_MD): fw._sha256(CARD_MD),
        },
    }
    fw._write_json(MANIFEST_JSON, manifest)


def _update_ticket_and_registry(
    payload: dict[str, Any], log_record: dict[str, Any]
) -> None:
    fw = base.framework
    ticket = (
        json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    )
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": fw._repo_rel(OUT_JSON),
                "log": fw._repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    fw._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    for row in registry.setdefault("experiments", []):
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": fw._repo_rel(OUT_JSON),
                "log": fw._repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(fw._safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def persist(payload: dict[str, Any]) -> None:
    fw = base.framework
    log_record = _build_log_record(payload)
    fw._write_json(OUT_JSON, payload)
    fw._write_json(LOG_JSON, payload)
    fw._write_text(CARD_MD, _build_card(payload))
    fw._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    fw = base.framework
    print(json.dumps(fw._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
