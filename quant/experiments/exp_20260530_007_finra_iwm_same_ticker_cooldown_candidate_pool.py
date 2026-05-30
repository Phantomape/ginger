"""exp-20260530-007: FINRA IWM-confirmed candidates with ticker cooldown.

This alpha search keeps the rejected exp-20260530-005 FINRA short-pressure
IWM-confirmed source and changes one production-visible variable: after a
ticker is admitted as an eligible paper candidate, do not admit the same ticker
again for the next seven calendar days. The goal is to preserve the three-window
EV/PnL lift while removing APP-like repeated-ticker positive PnL concentration.
No production order path is changed and no JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260530_005_finra_short_pressure_iwm_confirmed_candidate_pool as prior


EXPERIMENT_ID = "exp-20260530-007"
STEM = "finra_iwm_same_ticker_cooldown_candidate_pool"
TRIAL_FAMILY = "finra_iwm_same_ticker_cooldown_candidate_pool"
CHANGED_VARIABLE = "finra_iwm_same_ticker_signal_cooldown_v1"
RULE_VERSION = "finra_iwm_same_ticker_signal_cooldown_v1"

SAME_TICKER_COOLDOWN_CALENDAR_DAYS = 7

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_007_{STEM}.json"
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

FRAMEWORK = prior.prior.framework
_BASE_IWM_CANDIDATE_ROWS_FOR_WINDOW = prior._candidate_rows_for_window
_BASE_IWM_POSTPROCESS_PAYLOAD = prior._postprocess_payload


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _apply_same_ticker_cooldown(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    last_admitted_by_ticker: dict[str, datetime] = {}
    filtered: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    rejected_examples: list[dict[str, Any]] = []

    for candidate in candidates:
        ticker = str(candidate.get("ticker") or "")
        signal_dt = _parse_date(candidate.get("date"))
        if not ticker or signal_dt is None:
            reject_counts["missing_ticker_or_date"] += 1
            continue

        last_signal_dt = last_admitted_by_ticker.get(ticker)
        if last_signal_dt is not None:
            days_since_last = (signal_dt - last_signal_dt).days
            if 0 <= days_since_last <= SAME_TICKER_COOLDOWN_CALENDAR_DAYS:
                reject_counts["same_ticker_cooldown_active"] += 1
                if len(rejected_examples) < 20:
                    rejected_examples.append(
                        {
                            "ticker": ticker,
                            "date": candidate.get("date"),
                            "prior_admitted_date": last_signal_dt.date().isoformat(),
                            "days_since_prior_admitted": days_since_last,
                            "candidate_selection_score": candidate.get(
                                "candidate_selection_score"
                            ),
                        }
                    )
                continue

        enriched = dict(candidate)
        enriched.update(
            {
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "same_ticker_cooldown_rule_version": RULE_VERSION,
                "same_ticker_cooldown_calendar_days": SAME_TICKER_COOLDOWN_CALENDAR_DAYS,
                "same_ticker_cooldown_known_at": (
                    "after_signal_date_close_using_prior_admitted_default_off_candidates"
                ),
                "same_ticker_cooldown_trade_enabled": False,
                "same_ticker_cooldown_alters_orders": False,
                "prior_same_ticker_admitted_date": last_signal_dt.date().isoformat()
                if last_signal_dt
                else None,
                "days_since_prior_same_ticker_admitted": (
                    (signal_dt - last_signal_dt).days if last_signal_dt else None
                ),
            }
        )
        filtered.append(enriched)
        last_admitted_by_ticker[ticker] = signal_dt

    return filtered, {
        "candidate_count_before_same_ticker_cooldown": len(candidates),
        "candidate_count": len(filtered),
        "candidate_days": len({row["date"] for row in filtered}),
        "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
        "same_ticker_cooldown_calendar_days": SAME_TICKER_COOLDOWN_CALENDAR_DAYS,
        "same_ticker_cooldown_reject_counts": dict(sorted(reject_counts.items())),
        "same_ticker_cooldown_rejected_examples": rejected_examples,
        "rule_version": RULE_VERSION,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = _BASE_IWM_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    filtered, cooldown_audit = _apply_same_ticker_cooldown(candidates)
    enriched_audit = dict(audit)
    enriched_audit.update(cooldown_audit)
    return filtered, enriched_audit


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _BASE_IWM_POSTPROCESS_PAYLOAD(payload)
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_finra_iwm_same_ticker_cooldown"
        if gate4["passed"]
        else "rejected_finra_iwm_same_ticker_cooldown"
    )
    actual_success = 1 if gate4["passed"] else 0

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "FINRA short-pressure IWM-confirmed candidates failed the prior "
                "promotion screen only by repeated same-ticker positive PnL "
                "concentration. A seven-calendar-day same-ticker signal cooldown "
                "should reduce clustered APP-like contribution without changing "
                "the FINRA, IWM, ranking, sizing, or exit logic."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": RULE_VERSION,
            "new_evidence_type": "production_visible_finra_iwm_candidate_freshness_state",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260530-005",
                "exp-20260529-017",
                "exp-20260529-018",
                "exp-20260528-001",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "prediction": {
                "success_probability": 0.26,
                "expected_ev_delta": 0.35,
                "expected_pnl_delta": 7000.0,
                "main_failure_modes": [
                    "pnl_lost_from_removed_winners",
                    "still_concentrated",
                    "old_thin_sample_loss",
                    "nearby_finra_source_rejected",
                ],
                "confidence_reason": (
                    "exp-20260530-005 improved all three windows but breached "
                    "positive PnL concentration by only 1.5pp. The observed APP "
                    "profit cluster came from same-ticker signals within seven "
                    "calendar days, so a freshness rule targets the failure "
                    "mechanism without relaxing the guard."
                ),
                "recorded_at": "2026-05-30T02:30:05+00:00",
                "brier_score": round((0.26 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "same_ticker_cooldown_calendar_days": SAME_TICKER_COOLDOWN_CALENDAR_DAYS,
            "source_definition": [
                *payload["parameters"].get("source_definition", []),
                (
                    "After an admitted default-off FINRA+IWM candidate, the same "
                    "ticker is ineligible for another FINRA+IWM candidate for the "
                    "next seven calendar days."
                ),
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: FINRA short-pressure IWM-confirmed signals "
            "retain edge, but repeated same-ticker bursts should be treated as "
            "stale crowding rather than independent new alpha."
        ),
        "2_history_check": {
            "exp-20260530-005": (
                "IWM-confirmed FINRA source improved all three windows "
                "(+0.6579 EV / +$14,019.35) but failed promotion because APP "
                "was 41.5003% of positive PnL versus a 40% guard."
            ),
            "exp-20260529-017": (
                "Raw FINRA short-pressure breakout was aggregate positive but "
                "failed one-window stability."
            ),
            "exp-20260529-018": (
                "FINRA score monotonicity failed, so this run does not retune "
                "the FINRA score or threshold."
            ),
            "exp-20260528-001": (
                "Broad-market first-hit decay failed; this run narrows the idea "
                "to same-ticker freshness inside a distinct FINRA+IWM source."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "no EV/PnL-regressed window; at least 20 target trades across all "
            "3 windows; max drawdown drift <=0.5pp; survival >=5%; concentration "
            "inside guardrails without production/backtest divergence."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.py"
        ),
    }
    payload["why_not_other_changes"] = (
        "Did not raise the concentration guard, exclude APP by ticker, retune the "
        "FINRA score, retune IWM/SPY thresholds, or change rank/sizing/exits. "
        "The single variable is a production-replayable same-ticker freshness "
        "state over admitted candidates."
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
            "Before live/default use, implement a shared default-off FINRA paper "
            "adapter that exposes publication-date FINRA rows, IWM/SPY "
            "confirmation, and the same seven-day ticker cooldown to both "
            "run-time and backtest code."
        ),
    }
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "The experiment changes no production path, so it cannot introduce "
            "a new production/backtest inconsistency. A positive result is only "
            "promotion-ready after the same source and cooldown are moved into a "
            "shared default-off adapter with parity tests."
        ),
    }
    payload["interpretation"] = (
        "The seven-day same-ticker cooldown keeps the FINRA+IWM alpha lead inside "
        "the three-window EV/PnL, drawdown, sample, survival, and concentration "
        "promotion screen as a default-off paper candidate."
        if gate4["passed"]
        else (
            "The seven-day same-ticker cooldown did not move the FINRA+IWM source "
            "inside the full promotion screen. Do not relax concentration or "
            "ticker-exclude; require forward rows or stronger borrow/availability "
            "data before retrying this family."
        )
    )
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "If accepted, the next step is a shared default-off FINRA paper adapter "
        "with run/backtest parity. If rejected, the next evidence must be "
        "forward replacement rows or borrow-cost/availability/float-normalized "
        "short-interest data."
    )
    payload["related_files"] = [
        FRAMEWORK.base._repo_rel(Path(__file__)),
        FRAMEWORK.base._repo_rel(OUT_JSON),
        FRAMEWORK.base._repo_rel(BEFORE_AGG_JSON),
        FRAMEWORK.base._repo_rel(AFTER_AGG_JSON),
        FRAMEWORK.base._repo_rel(FINRA_ROWS_JSON),
        FRAMEWORK.base._repo_rel(FINRA_FILES_JSON),
        FRAMEWORK.base._repo_rel(LOG_JSON),
        FRAMEWORK.base._repo_rel(TICKET_JSON),
        FRAMEWORK.base._repo_rel(DOC_TICKET_JSON),
        FRAMEWORK.base._repo_rel(CARD_MD),
        FRAMEWORK.base._repo_rel(ARTIFACT_MD),
        FRAMEWORK.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates | Cooldown rejects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in FRAMEWORK.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rejects = audit.get("same_ticker_cooldown_reject_counts", {}).get(
            "same_ticker_cooldown_active",
            0,
        )
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} | {rejects} |".format(
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
                rejects=rejects,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            "# exp-20260530-007 FINRA IWM Same-Ticker Cooldown Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: add a seven-calendar-day same-ticker cooldown "
                "after an admitted FINRA short-pressure IWM-confirmed default-off "
                "paper candidate."
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
                "core entry, ranking, sizing, exits, LLM, or news behavior changed. "
                "Promotion requires moving the same source and cooldown into a "
                "shared run/backtest adapter with parity tests."
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
