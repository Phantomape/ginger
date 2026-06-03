"""exp-20260603-006: FINRA borrow-pressure candidate admission.

This alpha search keeps the accepted FINRA/IWM same-ticker cooldown candidate
source and changes one production-visible admission field: require the latest
published FINRA short-interest row to show both meaningful days-to-cover and a
positive short-interest change. The experiment is default-off paper replay only;
core signals, sizing, exits, LLM/news, watchlists, and orders are unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool as prior


EXPERIMENT_ID = "exp-20260603-006"
STEM = "finra_borrow_pressure_candidate_pool"
TRIAL_FAMILY = "finra_borrow_pressure_candidate_pool"
CHANGED_VARIABLE = "finra_days_to_cover_positive_short_change_borrow_pressure_source_v1"
RULE_VERSION = "finra_days_to_cover_positive_short_change_borrow_pressure_source_v1"

MIN_FINRA_DAYS_TO_COVER = 3.0
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_006_{STEM}.json"
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

FRAMEWORK = prior.FRAMEWORK
_BASE_CANDIDATE_ROWS_FOR_WINDOW = prior._candidate_rows_for_window
_BASE_POSTPROCESS_PAYLOAD = prior._postprocess_payload


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _apply_borrow_pressure_gate(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    rejected_examples: list[dict[str, Any]] = []
    field_examples: list[dict[str, Any]] = []

    for candidate in candidates:
        days_to_cover = _as_float(candidate.get("finra_days_to_cover"))
        short_change_pct = _as_float(candidate.get("finra_short_interest_change_pct"))
        ticker = str(candidate.get("ticker") or "")
        signal_date = str(candidate.get("date") or "")

        if days_to_cover is None:
            reject_counts["missing_finra_days_to_cover"] += 1
            continue
        if short_change_pct is None:
            reject_counts["missing_finra_short_interest_change_pct"] += 1
            continue
        if days_to_cover < MIN_FINRA_DAYS_TO_COVER:
            reject_counts["days_to_cover_below_threshold"] += 1
            if len(rejected_examples) < 20:
                rejected_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "finra_days_to_cover": days_to_cover,
                        "finra_short_interest_change_pct": short_change_pct,
                        "reason": "days_to_cover_below_threshold",
                    }
                )
            continue
        if short_change_pct <= MIN_FINRA_SHORT_INTEREST_CHANGE_PCT:
            reject_counts["short_interest_change_not_positive"] += 1
            if len(rejected_examples) < 20:
                rejected_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "finra_days_to_cover": days_to_cover,
                        "finra_short_interest_change_pct": short_change_pct,
                        "reason": "short_interest_change_not_positive",
                    }
                )
            continue

        enriched = dict(candidate)
        enriched.update(
            {
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "finra_borrow_pressure_rule_version": RULE_VERSION,
                "finra_borrow_pressure_known_at": (
                    "after_signal_date_close_with_latest_published_finra_before_next_open_paper_entry"
                ),
                "finra_borrow_pressure_trade_enabled": False,
                "finra_borrow_pressure_alters_orders": False,
                "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
                "min_finra_short_interest_change_pct": (
                    MIN_FINRA_SHORT_INTEREST_CHANGE_PCT
                ),
            }
        )
        filtered.append(enriched)
        if len(field_examples) < 20:
            field_examples.append(
                {
                    "ticker": ticker,
                    "date": signal_date,
                    "finra_days_to_cover": days_to_cover,
                    "finra_short_interest_change_pct": short_change_pct,
                    "candidate_selection_score": candidate.get(
                        "candidate_selection_score"
                    ),
                }
            )

    return filtered, {
        "candidate_count_before_borrow_pressure_gate": len(candidates),
        "candidate_count": len(filtered),
        "candidate_days": len({row["date"] for row in filtered}),
        "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "borrow_pressure_reject_counts": dict(sorted(reject_counts.items())),
        "borrow_pressure_rejected_examples": rejected_examples,
        "borrow_pressure_field_examples": field_examples,
        "rule_version": RULE_VERSION,
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
    filtered, borrow_audit = _apply_borrow_pressure_gate(candidates)
    enriched_audit = dict(audit)
    enriched_audit.update(borrow_audit)
    return filtered, enriched_audit


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _BASE_POSTPROCESS_PAYLOAD(payload)
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_finra_borrow_pressure"
        if gate4["passed"]
        else "rejected_finra_borrow_pressure"
    )
    actual_success = 1 if gate4["passed"] else 0

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Official FINRA borrow-pressure rows with high days-to-cover and "
                "positive short-interest change may improve the accepted FINRA/IWM "
                "default-off candidate pool by requiring both crowding and active "
                "borrow-demand pressure."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": "dtc_ge_3_short_change_positive",
            "new_evidence_type": (
                "production_visible_official_finra_borrow_availability_pressure_field"
            ),
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260529-017",
                "exp-20260529-018",
                "exp-20260530-007",
                "exp-20260601-029",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "prediction": {
                "success_probability": 0.24,
                "expected_ev_delta": 0.08,
                "expected_pnl_delta": 1500.0,
                "main_failure_modes": [
                    "thin_adjusted_sample",
                    "window_regression",
                    "concentration_failed",
                    "nearby_finra_family_frozen",
                ],
                "confidence_reason": (
                    "Accepted FINRA/IWM source has full-window evidence and the "
                    "playbook allows materially stronger borrow/availability "
                    "fields. Prior FINRA score monotonicity and simple support "
                    "retunes failed, so this run changes only raw official "
                    "borrow-pressure admission."
                ),
                "recorded_at": "2026-06-03T04:11:15+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": payload["delta_metrics"]["aggregate"][
                    "expected_value_score_delta_sum"
                ],
                "actual_pnl_delta": payload["delta_metrics"]["aggregate"][
                    "total_pnl_delta_sum"
                ],
                "brier_score": round((0.24 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
            "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
            "source_definition": [
                *payload["parameters"].get("source_definition", []),
                (
                    "Latest PIT-safe published FINRA row must have days-to-cover "
                    ">= 3.0 and short-interest change pct > 0.0 before admission."
                ),
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: crowded short breakouts should have a "
            "cleaner edge when official FINRA data shows both high days-to-cover "
            "and active positive short-interest change. This follows the playbook "
            "preference for free, production-visible candidate-pool sources."
        ),
        "2_history_check": {
            "exp-20260529-017": (
                "Raw FINRA short-pressure breakout was aggregate positive but "
                "failed one-window stability."
            ),
            "exp-20260529-018": (
                "FINRA score monotonicity failed, so this run does not retune "
                "the existing composite score or score threshold."
            ),
            "exp-20260530-007": (
                "FINRA+IWM with seven-day same-ticker cooldown passed the prior "
                "candidate-pool screen; this run tests only an additional raw "
                "official borrow-pressure admission field."
            ),
            "exp-20260601-029": (
                "FINRA/IWM support tuning is frozen without stronger evidence; "
                "this run uses a stronger borrow/availability field instead of "
                "another notional scalar."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "no EV/PnL-regressed window; at least 20 target trades across all 3 "
            "windows; max drawdown drift <=0.5pp; survival >=5%; concentration "
            "inside guardrails; no production/backtest divergence."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260603_006_finra_borrow_pressure_candidate_pool.py"
        ),
    }
    payload["gate1"] = {
        **payload.get("gate1", {}),
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "baseline_min_survival_rate": payload["delta_metrics"]["aggregate"].get(
            "min_survival_rate"
        ),
        "protocol_source": "docs/backtesting.md canonical three-window replay",
    }
    payload["gate2"] = {
        **payload.get("gate2", {}),
        "minimum_open_position_fields_checked": ["entry_date", "target_price"],
        "operator_inputs_open_positions_missing_required_fields": 0,
        "borrow_pressure_required_fields": [
            "finra_days_to_cover",
            "finra_short_interest_change_pct",
            "finra_publication_date",
            "finra_source_url",
        ],
        "llm_dependency": False,
    }
    payload["gate3"] = {
        **payload.get("gate3", {}),
        "core_survival_guard": "baseline min survival remains far above 5%",
        "new_core_filter_added": False,
        "candidate_pool_gate_only": True,
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because the data remains too sparse, skipped "
        "Companyfacts/post-earnings nearby retunes per playbook freeze guidance, "
        "and did not retune FINRA score, IWM threshold, cooldown, ranking, sizing, "
        "exits, or concentration guards."
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
            "A retained positive result would require moving the same FINRA "
            "borrow-pressure admission into a shared default-off run/backtest "
            "adapter with parity tests before any production surface change."
        ),
    }
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "This runner changes no production path, so it cannot introduce a new "
            "production/backtest inconsistency. If accepted, it is only a replay "
            "lead until implemented in a shared default-off adapter and parity "
            "covered."
        ),
    }
    payload["interpretation"] = (
        "The official FINRA borrow-pressure admission improved the FINRA/IWM "
        "candidate source inside the three-window promotion screen."
        if gate4["passed"]
        else (
            "The official FINRA borrow-pressure admission did not pass the full "
            "three-window promotion screen. Do not retain or promote it; require "
            "forward replacement rows or a materially richer borrow-cost/loan "
            "availability field before retrying this FINRA family."
        )
    )
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["next_evidence_needed"] = (
        "If accepted, build a shared default-off adapter plus parity tests. If "
        "rejected, move away from FINRA threshold/support variants unless new "
        "borrow-cost, loan-availability, or forward replacement evidence arrives."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates before | Borrow rejects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in FRAMEWORK.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rejects = sum(audit.get("borrow_pressure_reject_counts", {}).values())
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
                raw=audit.get("candidate_count_before_borrow_pressure_gate", 0),
                rejects=rejects,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            "# exp-20260603-006 FINRA Borrow-Pressure Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: require latest published FINRA days-to-cover "
                ">= 3.0 and short-interest change pct > 0.0 before admitting the "
                "accepted FINRA/IWM/cooldown default-off paper candidate."
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
                "Promotion requires a shared run/backtest adapter with parity tests."
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
    raise SystemExit(main())
