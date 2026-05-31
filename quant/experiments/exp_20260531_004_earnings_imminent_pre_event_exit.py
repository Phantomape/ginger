"""exp-20260531-004: earnings-imminent pre-event exit lifecycle.

This alpha search keeps the rejected exp-20260531-003 earnings-imminent
surprise/RS candidate source fixed and changes only the default-off paper
exit lifecycle: exit before the earnings event instead of holding a fixed
ten trading days through the event.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_003_earnings_imminent_surprise_rs_candidate_pool as source


framework = source.framework

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260531-004"
STEM = "earnings_imminent_pre_event_exit"
TRIAL_FAMILY = "earnings_imminent_surprise_rs_event_lifecycle"
CHANGED_VARIABLE = "earnings_imminent_pre_event_exit_policy_v1"
RULE_VERSION = "earnings_imminent_1_7_surprise_rs_pre_event_exit_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260531_004_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_EXPERIMENT_ID = "exp-20260531-003"
BASELINE_STEM = "earnings_imminent_surprise_rs_candidate_pool"
MIN_PRE_EVENT_HOLD_DAYS = 1


def _event_pre_exit_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    rows = framework.ohlcv_helper._series(snapshot, str(candidate.get("ticker") or ""))
    idx = framework.ohlcv_helper._row_index(rows).get(str(candidate.get("date") or ""))
    if idx is None:
        return None

    days_to_earnings = candidate.get("days_to_earnings")
    try:
        dte = int(days_to_earnings)
    except (TypeError, ValueError):
        return None

    entry_idx = idx + 1
    exit_idx = idx + min(framework.base.HOLD_DAYS, dte - 1)
    if dte <= MIN_PRE_EVENT_HOLD_DAYS or entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    if exit_idx < entry_idx:
        return None

    entry_raw = framework.ohlcv_helper._value(rows[entry_idx], "Open")
    exit_raw = framework.ohlcv_helper._value(rows[exit_idx], "Close")
    if not entry_raw or not exit_raw:
        return None

    entry_price = framework.base.apply_entry_fill(entry_raw)
    exit_price = framework.base.apply_slippage(
        exit_raw,
        framework.base.SLIPPAGE_BPS_TARGET,
        "sell",
    )
    pnl_pct_net = (exit_price / entry_price) - 1.0 - framework.base.ROUND_TRIP_COST_PCT
    pnl = framework.base.BASE_NOTIONAL_USD * pnl_pct_net
    realized_hold_days = exit_idx - idx
    return {
        **candidate,
        "signal_date": candidate.get("date"),
        "entry_date": framework.ohlcv_helper._date(rows[entry_idx]),
        "exit_date": framework.ohlcv_helper._date(rows[exit_idx]),
        "entry_raw_open": framework.base._round(entry_raw, 4),
        "exit_raw_close": framework.base._round(exit_raw, 4),
        "entry_price": framework.base._round(entry_price, 4),
        "exit_price": framework.base._round(exit_price, 4),
        "hold_days": realized_hold_days,
        "baseline_hold_days": framework.base.HOLD_DAYS,
        "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
        "pnl_pct_net": framework.base._round(pnl_pct_net, 6),
        "pnl": framework.base._round(pnl, 2),
        "event_lifecycle_exit_policy": RULE_VERSION,
        "exit_before_earnings_event": True,
        "days_to_earnings_at_signal": dte,
    }


def _patch_framework() -> None:
    source._patch_framework()
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = DOC_TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.base._paper_trade_from_candidate = _event_pre_exit_trade_from_candidate
    framework._build_report = _build_report


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate4["passed"]
        else "rejected_earnings_imminent_pre_event_exit"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Earnings-imminent surprise/RS candidates may work as a pre-earnings "
                "run-up sleeve if the paper lifecycle exits before the earnings event "
                "instead of crossing the event."
            ),
            "change_type": "default_off_paper_exit_lifecycle",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260531-003",
                "exp-20260531-001",
                "exp-20260508-013",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "production_visible_earnings_snapshot_event_lifecycle",
            "prediction": {
                "success_probability": 0.26,
                "expected_ev_delta": 0.25,
                "expected_pnl_delta": 5000.0,
                "main_failure_modes": [
                    "late_strong_regression",
                    "mid_old_upside_lost",
                    "drawdown_drift",
                    "nearby_pre_earnings_repeat",
                ],
                "confidence_reason": (
                    "The latest imminent-earnings pool had strong aggregate EV but "
                    "failed by crossing the event; event-before exit is a different "
                    "lifecycle variable using the same production-visible snapshot field."
                ),
                "recorded_at": "2026-05-31T03:05:48+00:00",
                "brier_score": round((0.26 - actual_success) ** 2, 6),
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / exit lifecycle: the 1-7 day earnings-imminent "
                    "surprise/RS pool may be a run-up capture, not a post-earnings "
                    "drift sleeve."
                ),
                "2_history_check": {
                    "exp-20260531-003": (
                        "Same candidate source improved aggregate EV by +3.3705 but "
                        "failed Gate 4 due late_strong regression and drawdown drift "
                        "when held ten trading days through the event."
                    ),
                    "exp-20260531-001": (
                        "The 22-45 day pre-earnings surprise/revision source regressed "
                        "aggregate EV; this keeps the better 1-7 day source fixed."
                    ),
                    "exp-20260508-013": (
                        "Prior pre-earnings timing variants were unstable; this run "
                        "tests a lifecycle boundary, not another selection threshold."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                    "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                    ">=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260531_004_earnings_imminent_pre_event_exit.py"
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "shared_adapter_added": False,
                "parity_note": (
                    "No production code path is changed. A retained result would "
                    "require a shared default-off adapter that reads the same daily "
                    "earnings snapshot days_to_earnings field and exposes the "
                    "pre-event exit policy in production reports before activation."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A positive replay lead is not promoted without a shared "
                    "default-off paper adapter, production report wiring, and parity tests."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because candidate-level attribution remains sparse. "
                "Skipped Companyfacts/VBB/VCP/FINRA/state-surface scalar retunes because "
                "the playbook asks for forward rows or materially new fields. This run "
                "keeps the exp-20260531-003 candidate source fixed and changes only "
                "the earnings-aware paper exit lifecycle."
            ),
            "interpretation": (
                "The pre-event exit lifecycle cleared Gate 4 as a replay-only lead, "
                "but no production/shared adapter was promoted."
                if gate4["passed"]
                else (
                    "The pre-event exit lifecycle did not clear Gate 4. Do not promote "
                    "it or retry nearby pre-earnings lifecycle thresholds on the frozen "
                    "windows without forward replacement-value rows or a richer "
                    "expectation-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use closed forward replacement-value rows or a richer "
                "expectation-quality field; do not simply retune the 1-7 day candidate "
                "or pre-event hold thresholds on the frozen windows."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"].update(
        {
            "candidate_source_fixed_from": BASELINE_EXPERIMENT_ID,
            "candidate_source_rule_version": source.RULE_VERSION,
            "baseline_hold_days": framework.base.HOLD_DAYS,
            "event_exit_policy": RULE_VERSION,
            "min_pre_event_hold_days": MIN_PRE_EVENT_HOLD_DAYS,
            "changed_only": [
                "paper exit index = signal index + min(10, days_to_earnings - 1)",
                "skip candidate when no post-entry pre-event close exists",
            ],
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Candidate fields are identical to exp-20260531-003 and are known after "
        "the signal-date close. Paper entry is the next available open with "
        "production entry slippage. The only changed variable is the paper exit: "
        "the latest feasible close before the earnings event, approximated from "
        "the PIT daily earnings snapshot days_to_earnings field."
    )
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "days_to_earnings",
            "days_to_earnings_at_signal",
            "event_lifecycle_exit_policy",
            "exit_before_earnings_event",
            "avg_historical_surprise_pct",
            "positive_historical_surprise_count",
            "eps_estimate",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(DOC_TICKET_JSON),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260531-004 Earnings-Imminent Pre-Event Exit",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: keep the exp-20260531-003 1-7 day surprise/RS candidate source fixed, but exit before the earnings event instead of holding ten trading days through the event.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity test.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Earnings-imminent pre-event exit",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
            "before_result_file": framework.base._repo_rel(BEFORE_AGG_JSON),
            "after_result_file": framework.base._repo_rel(AFTER_AGG_JSON),
            "result_file": framework.base._repo_rel(OUT_JSON),
            "artifact": framework.base._repo_rel(ARTIFACT_MD),
            "gate4_passed": payload["gate4"]["passed"],
            "delta_metrics": {
                "expected_value_score": payload["expected_value_score_delta"],
                "total_pnl": payload["total_pnl_delta"],
                "max_drawdown_pct": payload["delta_metrics"]["aggregate"][
                    "max_drawdown_delta_max"
                ],
            },
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_json(DOC_TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_report(payload))
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
