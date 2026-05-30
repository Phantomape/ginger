"""exp-20260530-005: FINRA short-pressure with IWM confirmation.

This alpha search tests one refinement on the rejected exp-20260529-017 FINRA
short-pressure breakout source: admit the default-off paper candidate only when
IWM 20-day momentum leads SPY by at least 30bp. The mechanism is that crowded
short breakouts need small-cap/risk-appetite confirmation to avoid mixed-window
false positives. Core trading behavior and live/default orders are unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_017_finra_short_pressure_breakout_candidate_pool as prior


EXPERIMENT_ID = "exp-20260530-005"
STEM = "finra_short_pressure_iwm_confirmed_candidate_pool"
TRIAL_FAMILY = "finra_short_pressure_iwm_confirmed_candidate_pool"
CHANGED_VARIABLE = "finra_short_pressure_iwm_confirmed_candidate_source_v1"
RULE_VERSION = "finra_short_pressure_iwm_confirmed_candidate_source_v1"

MARKET_CONFIRM_DAYS = 20
MIN_IWM_RET20_MINUS_SPY = 0.003

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_005_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FINRA_ROWS_JSON = OUT_DIR / "finra_short_interest_rows.json"
FINRA_FILES_JSON = OUT_DIR / "finra_source_files.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

_BASE_CANDIDATE_ROWS_FOR_WINDOW = prior._candidate_rows_for_window
_BASE_POSTPROCESS_PAYLOAD = prior._postprocess_payload


def _market_confirmation(
    snapshot: dict[str, list[dict[str, Any]]],
    signal_date: str,
) -> dict[str, Any]:
    iwm_rows = prior.framework.ohlcv_helper._series(snapshot, "IWM")
    spy_rows = prior.framework.ohlcv_helper._series(snapshot, "SPY")
    iwm_idx = prior.framework.ohlcv_helper._row_index(iwm_rows).get(signal_date)
    spy_idx = prior.framework.ohlcv_helper._row_index(spy_rows).get(signal_date)
    if (
        iwm_idx is None
        or spy_idx is None
        or iwm_idx < MARKET_CONFIRM_DAYS
        or spy_idx < MARKET_CONFIRM_DAYS
    ):
        return {"passed": False, "reason": "missing_iwm_or_spy_market_context"}

    iwm_ret20 = prior.framework._close_return(
        iwm_rows,
        iwm_idx - MARKET_CONFIRM_DAYS,
        iwm_idx,
    )
    spy_ret20 = prior.framework._close_return(
        spy_rows,
        spy_idx - MARKET_CONFIRM_DAYS,
        spy_idx,
    )
    if iwm_ret20 is None or spy_ret20 is None:
        return {"passed": False, "reason": "missing_iwm_or_spy_ret20"}
    spread = iwm_ret20 - spy_ret20
    return {
        "passed": spread >= MIN_IWM_RET20_MINUS_SPY,
        "reason": "iwm_spy_confirmation_passed"
        if spread >= MIN_IWM_RET20_MINUS_SPY
        else "iwm_not_leading_spy_enough",
        "iwm_ret20": prior.framework.base._round(iwm_ret20, 6),
        "market_spy_ret20": prior.framework.base._round(spy_ret20, 6),
        "iwm_minus_spy_ret20": prior.framework.base._round(spread, 6),
        "min_iwm_minus_spy_ret20": MIN_IWM_RET20_MINUS_SPY,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = _BASE_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    filtered: list[dict[str, Any]] = []
    reason_counts: dict[str, int] = {}
    for candidate in candidates:
        context = _market_confirmation(snapshot, str(candidate.get("date") or ""))
        reason = str(context.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if not context["passed"]:
            continue
        enriched = dict(candidate)
        enriched.update(
            {
                "rule_version": RULE_VERSION,
                "market_confirmation_rule_version": "iwm_spy_20d_risk_appetite_v1",
                "market_confirmation_days": MARKET_CONFIRM_DAYS,
                "market_confirmation_known_at": (
                    "after_signal_date_close_before_next_open_paper_entry"
                ),
                "market_confirmation_trade_enabled": False,
                "market_confirmation_alters_orders": False,
                **context,
            }
        )
        filtered.append(enriched)

    enriched_audit = dict(audit)
    enriched_audit.update(
        {
            "base_candidate_count_before_iwm_gate": len(candidates),
            "candidate_count": len(filtered),
            "candidate_days": len({row["date"] for row in filtered}),
            "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
            "iwm_confirmation_reject_counts": dict(sorted(reason_counts.items())),
            "market_confirmation_days": MARKET_CONFIRM_DAYS,
            "min_iwm_minus_spy_ret20": MIN_IWM_RET20_MINUS_SPY,
            "rule_version": RULE_VERSION,
        }
    )
    return filtered, enriched_audit


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _BASE_POSTPROCESS_PAYLOAD(payload)
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_finra_short_pressure_iwm_confirmed"
        if gate4["passed"]
        else "rejected_finra_short_pressure_iwm_confirmed"
    )
    actual_success = 1 if gate4["passed"] else 0

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "FINRA short-pressure breakout candidates should require small-cap "
                "risk-appetite confirmation; IWM leading SPY may remove the "
                "mixed-window false positives from exp-20260529-017 without adding "
                "ticker noise."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": RULE_VERSION,
            "new_evidence_type": (
                "production_visible_finra_short_interest_plus_iwm_spy_risk_appetite_field"
            ),
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260529-017",
                "exp-20260529-018",
                "exp-20260516-037",
            ],
            "multiple_testing_risk_bucket": "moderate_high",
            "prediction": {
                "success_probability": 0.22,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "finra_score_not_monotonic",
                    "mid_weak_regression",
                    "old_thin_sample_loss",
                    "nearby_source_rejected",
                ],
                "confidence_reason": (
                    "The prior FINRA source had positive aggregate EV/PnL with "
                    "adequate sample but failed one window; IWM/SPY confirmation "
                    "is a mechanism-level risk-appetite gate rather than a FINRA "
                    "score retune."
                ),
                "recorded_at": "2026-05-30T02:12:39+00:00",
                "brier_score": round((0.22 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "market_confirmation_days": MARKET_CONFIRM_DAYS,
            "min_iwm_minus_spy_ret20": MIN_IWM_RET20_MINUS_SPY,
            "source_definition": [
                *payload["parameters"].get("source_definition", []),
                "IWM prior-20-day return must lead SPY by at least 30bp on the signal date",
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: published FINRA short-pressure breakouts "
            "should only be admitted when small-cap risk appetite confirms, "
            "because squeeze continuation needs broad speculative participation."
        ),
        "2_history_check": {
            "exp-20260529-017": (
                "raw FINRA short-pressure breakout was aggregate positive "
                "(+0.3125 EV / +$7,634.63) but failed Gate 4 due to mid_weak "
                "EV/PnL regression."
            ),
            "exp-20260529-018": (
                "FINRA score monotonicity failed, so this run does not retune "
                "the FINRA score; it adds one orthogonal market-state gate."
            ),
            "exp-20260516-037": (
                "short-squeeze demand as a core top-up required shared FINRA "
                "adapter parity before promotion; this replay remains default-off."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "no EV/PnL-regressed window; at least 20 target trades across all 3 "
            "windows; max drawdown drift <=0.5pp; survival >=5%; concentration "
            "inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260530_005_finra_short_pressure_iwm_confirmed_candidate_pool.py"
        ),
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and Companyfacts/VBB/VCP/state-surface retunes "
        "per playbook freeze guidance. Chose this only because exp-20260529-017 "
        "had adequate sample and positive aggregate EV/PnL, while the new field "
        "directly targets its mixed-window failure mode."
    )
    payload["production_impact"] = {
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
            "A retained result would require a shared default-off FINRA paper "
            "adapter exposing the same publication-date rows, OHLCV market "
            "confirmation, and parity tests before any production surface changes."
        ),
    }
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "No production code path is changed in this experiment. Positive "
            "replay evidence is not retained as a strategy change until shared "
            "run/backtest parity is implemented."
        ),
    }
    payload["interpretation"] = (
        "The FINRA short-pressure IWM-confirmed candidate pool cleared Gate 4 as "
        "a replay lead only; no production/shared policy was promoted."
        if gate4["passed"]
        else (
            "The FINRA short-pressure IWM-confirmed candidate pool did not clear "
            "Gate 4. Do not promote it or retry nearby FINRA short-pressure "
            "candidate gates on the same frozen windows without forward rows or "
            "a stronger borrow-cost/availability field."
        )
    )
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "Forward replacement-value rows or a materially stronger short-pressure "
        "field such as borrow fee, borrow availability, or float-normalized short interest."
    )
    payload["related_files"] = [
        prior.framework.base._repo_rel(Path(__file__)),
        prior.framework.base._repo_rel(OUT_JSON),
        prior.framework.base._repo_rel(BEFORE_AGG_JSON),
        prior.framework.base._repo_rel(AFTER_AGG_JSON),
        prior.framework.base._repo_rel(FINRA_ROWS_JSON),
        prior.framework.base._repo_rel(FINRA_FILES_JSON),
        prior.framework.base._repo_rel(LOG_JSON),
        prior.framework.base._repo_rel(TICKET_JSON),
        prior.framework.base._repo_rel(DOC_TICKET_JSON),
        prior.framework.base._repo_rel(CARD_MD),
        prior.framework.base._repo_rel(ARTIFACT_MD),
        prior.framework.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.framework.base.WINDOWS:
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
    return "\n".join(
        [
            "# exp-20260530-005 FINRA Short-Pressure IWM-Confirmed Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: require IWM 20-day return to lead SPY by at "
                "least 30bp before admitting the FINRA short-pressure breakout "
                "default-off paper candidate."
            ),
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
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, exits, LLM, or news behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _install() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    prior.AFTER_AGG_JSON = AFTER_AGG_JSON
    prior.FINRA_ROWS_JSON = FINRA_ROWS_JSON
    prior.FINRA_FILES_JSON = FINRA_FILES_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.DOC_TICKET_JSON = DOC_TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior._FINRA_CACHE = None
    prior._candidate_rows_for_window = _candidate_rows_for_window
    prior._postprocess_payload = _postprocess_payload
    prior._build_report = _build_report


def main() -> int:
    _install()
    return prior.main()


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
