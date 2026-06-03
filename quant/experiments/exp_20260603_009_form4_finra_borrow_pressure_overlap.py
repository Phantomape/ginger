"""Replay Form 4 purchase candidates confirmed by accepted FINRA borrow pressure.

This alpha search keeps the raw PIT-safe Form 4 meaningful-purchase queue and
the event-sleeve replay mechanics fixed. The single tested variable is source
overlap: a Form 4 candidate is retained only when the same ticker's latest
published FINRA row has days-to-cover >= 3.0 and a positive short-interest
change, matching the accepted FINRA borrow-pressure admission rule.

No production orders, shared policy modules, ranking, sizing, exits, LLM/news,
or watchlists are changed. This is a default-off replay scout only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260602_016_form4_finra_short_pressure_consensus as prior


EXP_ID = "exp-20260603-009"
STEM = "form4_finra_borrow_pressure_overlap"
TRIAL_FAMILY = "form4_finra_borrow_pressure_cross_source_overlap"
CHANGED_VARIABLE = "form4_finra_borrow_pressure_source_overlap_candidate_v1"
RULE_VERSION = "form4_finra_borrow_pressure_source_overlap_candidate_v1"

MIN_FINRA_DAYS_TO_COVER = 3.0
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
RAW_FORM4_AGG_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

_BASE_BUILD_PAYLOAD = prior.build_payload
_BASE_TICKET = prior._ticket


def _accepted_borrow_pressure_row(
    row: dict[str, Any] | None,
) -> tuple[bool, dict[str, Any]]:
    if row is None:
        return False, {
            "reason": "missing_published_finra_row",
            "finra_days_to_cover": None,
            "finra_short_interest_change_pct": None,
        }
    days_to_cover = prior._float_or_none(row.get("days_to_cover"))
    short_change_pct = prior._float_or_none(row.get("short_interest_change_pct"))
    if days_to_cover is None:
        return False, {
            "reason": "missing_finra_days_to_cover",
            "finra_days_to_cover": None,
            "finra_short_interest_change_pct": short_change_pct,
        }
    if short_change_pct is None:
        return False, {
            "reason": "missing_finra_short_interest_change_pct",
            "finra_days_to_cover": days_to_cover,
            "finra_short_interest_change_pct": None,
        }
    if days_to_cover < MIN_FINRA_DAYS_TO_COVER:
        return False, {
            "reason": "days_to_cover_below_accepted_threshold",
            "finra_days_to_cover": days_to_cover,
            "finra_short_interest_change_pct": short_change_pct,
        }
    if short_change_pct <= MIN_FINRA_SHORT_INTEREST_CHANGE_PCT:
        return False, {
            "reason": "short_interest_change_not_positive",
            "finra_days_to_cover": days_to_cover,
            "finra_short_interest_change_pct": short_change_pct,
        }
    return True, {
        "reason": "accepted_finra_borrow_pressure_overlap",
        "finra_days_to_cover": days_to_cover,
        "finra_short_interest_change_pct": short_change_pct,
    }


def _load_forward_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not prior.FORM4_TRANSACTIONS_PATH.exists():
        return [], {"source_status": "missing_form4_transactions"}
    rows = prior.load_form4_transaction_rows(prior.FORM4_TRANSACTIONS_PATH)
    rows_by_ticker, finra_diagnostics = prior._load_finra_rows()
    start = min(window["start"] for window in prior.WINDOWS.values())
    end = max(window["end"] for window in prior.WINDOWS.values())
    raw_events = [
        event
        for event in prior.aggregate_purchase_events(rows, start=start, end=end)
        if prior.qualifies_forward_queue_event(event)
    ]

    events: list[dict[str, Any]] = []
    reject_counts: dict[str, int] = {}
    qualifying = 0
    examples: list[dict[str, Any]] = []
    for event in raw_events:
        ticker = str(event.get("ticker") or "").upper()
        usable = prior._date10(event.get("usable_trade_date"))
        window = prior._window_name(usable)
        if not ticker or not usable or not window:
            continue
        finra_row = prior._latest_finra_row(rows_by_ticker, ticker, usable)
        passed, reason = _accepted_borrow_pressure_row(finra_row)
        qualifying += int(passed)
        reject_counts[reason["reason"]] = reject_counts.get(reason["reason"], 0) + 1
        if len(examples) < 25:
            examples.append(
                {
                    "ticker": ticker,
                    "usable_trade_date": usable,
                    "window": window,
                    "passed": passed,
                    "reason": reason["reason"],
                    "finra_days_to_cover": reason["finra_days_to_cover"],
                    "finra_short_interest_change_pct": reason[
                        "finra_short_interest_change_pct"
                    ],
                }
            )
        events.append(
            {
                **event,
                "ticker": ticker,
                "usable_trade_date": usable,
                "window": window,
                "finra_consensus_ge_070": passed,
                "form4_finra_borrow_pressure_overlap": passed,
                "finra_qualification_reason": reason["reason"],
                "finra_short_pressure_score": None,
                "finra_short_crowding_score": None,
                "finra_short_change_score": None,
                "same_day_finra_covered_count": None,
                "finra_settlement_date": None if finra_row is None else finra_row.get("settlement_date"),
                "finra_publication_date": None if finra_row is None else finra_row.get("publication_date"),
                "finra_publication_date_method": None
                if finra_row is None
                else finra_row.get("publication_date_method"),
                "finra_days_to_cover": reason["finra_days_to_cover"],
                "finra_short_interest": None if finra_row is None else finra_row.get("short_interest"),
                "finra_previous_short_interest": None
                if finra_row is None
                else finra_row.get("previous_short_interest"),
                "finra_short_interest_change_pct": reason[
                    "finra_short_interest_change_pct"
                ],
                "finra_source_url": None if finra_row is None else finra_row.get("source_url"),
                "known_at": (
                    "after_form4_usable_trade_date_with_latest_published_finra_"
                    "row_on_or_before_event_date"
                ),
                "trade_enabled": False,
                "alters_orders": False,
                "rule_version": RULE_VERSION,
            }
        )

    diagnostics = {
        "form4_source_status": "loaded",
        "form4_transactions_path": prior._repo_rel(prior.FORM4_TRANSACTIONS_PATH),
        "transaction_rows": len(rows),
        "raw_forward_event_count": len(events),
        "accepted_finra_borrow_pressure_event_count": qualifying,
        "borrow_pressure_reject_counts": dict(sorted(reject_counts.items())),
        "borrow_pressure_examples": examples,
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "finra": finra_diagnostics,
    }
    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"])), diagnostics


def _retitle_decision(payload: dict[str, Any]) -> None:
    gate = payload["gate4"]
    aggregate_vs_core = payload["aggregate_delta_vs_core"]
    if gate["passed"]:
        payload["decision"] = (
            "accepted_research_form4_finra_borrow_pressure_overlap_requires_shared_adapter"
        )
        payload["status"] = "accepted_default_off"
        payload["decision_rationale"] = (
            "The accepted FINRA borrow-pressure overlap improved both core and raw "
            "Form 4 metrics while passing sample, window, drawdown, materiality, "
            "and concentration gates. It remains replay-only until implemented in "
            "a shared default-off adapter with parity tests."
        )
    elif (
        aggregate_vs_core["aggregate_ev_delta"] > 0
        and aggregate_vs_core["aggregate_pnl_delta"] > 0
    ):
        payload["decision"] = "rejected_positive_not_promotable"
        payload["status"] = "rejected"
        payload["decision_rationale"] = (
            "The accepted FINRA borrow-pressure overlap was positive versus the "
            "core baseline, but it failed replacement value against raw Form 4 or "
            "failed one of the materiality, window, sample, drawdown, or "
            "concentration guards."
        )
    else:
        payload["decision"] = "rejected_form4_finra_borrow_pressure_overlap"
        payload["status"] = "rejected"
        payload["decision_rationale"] = (
            "The accepted FINRA borrow-pressure overlap did not produce positive, "
            "stable three-window EV/PnL evidence versus the core baseline."
        )


def build_payload() -> dict[str, Any]:
    payload = _BASE_BUILD_PAYLOAD()
    _retitle_decision(payload)
    actual_success = 1 if payload["gate4"]["passed"] else 0
    payload.update(
        {
            "experiment_id": EXP_ID,
            "hypothesis": (
                "Raw PIT-safe Form 4 meaningful-purchase events may have cleaner "
                "candidate-pool replacement value when confirmed by the accepted "
                "official FINRA borrow-pressure admission rule."
            ),
            "change_type": "event_qualification_replay",
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": RULE_VERSION,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": (
                "raw PIT-safe Form 4 forward events require latest published FINRA "
                "days-to-cover >= 3.0 and short-interest change pct > 0.0 on or "
                "before usable trade date"
            ),
            "prediction": {
                "success_probability": 0.22,
                "expected_ev_delta": 0.15,
                "expected_pnl_delta": 2500.0,
                "main_failure_modes": [
                    "sample_too_thin",
                    "does_not_improve_raw_form4_queue",
                    "window_regression",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "Raw Form 4 and the accepted FINRA borrow-pressure condition "
                    "each have some evidence, but prior Form 4 qualifiers and the "
                    "older percentile FINRA consensus failed replacement/sample "
                    "gates."
                ),
                "recorded_at": "2026-06-03T08:08:40+00:00",
                "actual_success": actual_success,
                "brier_score": round((0.22 - actual_success) ** 2, 6),
            },
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: meaningful insider buys may retain cleaner "
            "replacement value when the same ticker also has official FINRA "
            "borrow-pressure evidence. This follows the playbook preference for "
            "free, PIT-safe, production-visible candidate-pool data edges."
        ),
        "2_history_check": {
            "exp-20260602-016": (
                "Older Form4+FINRA percentile-score consensus failed; this run "
                "uses the later accepted FINRA days-to-cover plus positive short "
                "interest change rule instead of retuning a score floor."
            ),
            "exp-20260603-006": (
                "FINRA borrow-pressure candidate admission improved all three "
                "windows and was accepted as a default-off paper source."
            ),
            "exp-20260603-007": (
                "Shared FINRA borrow-pressure adapter promotion changed no live "
                "orders and established the accepted borrow-pressure condition."
            ),
            "exp-20260603-008": (
                "Form 4 post-drawdown qualifier was positive vs core but failed "
                "raw Form 4 replacement and sample/window/concentration gates."
            ),
            "exp-20260530-011": (
                "Multi-filer Form 4 queue was not promotable; this run avoids "
                "another Form 4-only threshold by requiring independent FINRA "
                "confirmation."
            ),
        },
        "3_single_causal_variable": payload["single_causal_variable"],
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; must improve aggregate "
            "EV/PnL versus core and raw Form 4, avoid window EV/PnL regressions, "
            "pass drawdown, survival, target sample, materiality, and "
            "concentration guards."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260603_009_form4_finra_borrow_pressure_overlap.py"
        ),
    }
    payload["parameters"].update(
        {
            "finra_admission_rule": {
                "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
                "min_finra_short_interest_change_pct": (
                    MIN_FINRA_SHORT_INTEREST_CHANGE_PCT
                ),
                "short_interest_change_condition": "> 0.0",
            },
            "rule_version": RULE_VERSION,
        }
    )
    payload["why_not_other_alpha"] = (
        "Skipped LLM soft-ranking and estimate-revision PEAD because the current "
        "historical replay coverage is too sparse for all three canonical windows. "
        "Skipped Companyfacts, post-earnings, raw OHLCV/state-surface, and FINRA "
        "threshold/support retunes per playbook freeze guidance. This run tests a "
        "new cross-source overlap without changing either source threshold."
    )
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "promotion_blocker_if_positive": (
                "A shared default-off Form 4 + accepted FINRA borrow-pressure "
                "adapter must be wired through production and replay with parity "
                "tests before any production report, watchlist, or order behavior "
                "can change."
            ),
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "This runner changes no production path, so it cannot introduce a new "
            "production/backtest inconsistency. A retained lead would need a "
            "shared default-off adapter and parity test before promotion."
        ),
    }
    payload["data_sources"]["pit_status"] = (
        "uses Form 4 usable_trade_date plus latest FINRA publication_date on or "
        "before the same event date; no LLM or inferred hidden data"
    )
    payload["rejection_reason"] = (
        None
        if payload["gate4"]["passed"]
        else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["next_evidence_needed"] = (
        "If rejected, do not retry nearby Form4/FINRA overlap unless forward "
        "replacement rows or a materially richer borrow-cost or loan-availability "
        "field appears. If accepted, implement only through shared default-off "
        "parity-covered adapters."
    )
    payload["related_files"] = [
        prior._repo_rel(Path(__file__)),
        prior._repo_rel(OUT_JSON),
        prior._repo_rel(BEFORE_AGG_JSON),
        prior._repo_rel(RAW_FORM4_AGG_JSON),
        prior._repo_rel(AFTER_AGG_JSON),
        prior._repo_rel(LOG_JSON),
        prior._repo_rel(TICKET_JSON),
        prior._repo_rel(DOC_TICKET_JSON),
        prior._repo_rel(ARTIFACT_MD),
    ]
    return payload


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    ticket = _BASE_TICKET(payload)
    ticket["title"] = "Form 4 FINRA borrow-pressure overlap"
    return ticket


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 FINRA Borrow-Pressure Overlap",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate Questions",
        "",
        "```json",
        json.dumps(payload["gate_questions"], indent=2, sort_keys=True),
        "```",
        "",
        "## Three-Window Results",
        "",
        "| Window | Core EV | Raw Form4 EV | Overlap EV | Delta vs raw | Delta vs core | Core PnL | Overlap PnL | Event PnL | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.WINDOWS:
        core = payload["core_baseline_metrics"][label]
        raw = payload["raw_form4_metrics"][label]
        after = payload["after_metrics"][label]
        raw_delta = payload["deltas_vs_raw_form4"][label]
        core_delta = payload["deltas_vs_core"][label]
        lines.append(
            f"| {label} | {core['expected_value_score']} | "
            f"{raw['expected_value_score']} | {after['expected_value_score']} | "
            f"{raw_delta['expected_value_score']} | "
            f"{core_delta['expected_value_score']} | ${core['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | "
            f"${float(after.get('event_pnl') or 0.0):,.2f} | "
            f"{core['trade_count']} -> {after['trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate vs Raw Form4",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_raw_form4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Aggregate vs Core",
            "",
            "```json",
            json.dumps(payload["aggregate_delta_vs_core"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines[:49]) + "\n", encoding="utf-8")


def _install() -> None:
    prior.EXP_ID = EXP_ID
    prior.STEM = STEM
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    prior.RAW_FORM4_AGG_JSON = RAW_FORM4_AGG_JSON
    prior.AFTER_AGG_JSON = AFTER_AGG_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.DOC_TICKET_JSON = DOC_TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior._load_forward_events = _load_forward_events
    prior.build_payload = build_payload
    prior._ticket = _ticket
    prior._write_report = _write_report


def main() -> None:
    _install()
    prior.main()


if __name__ == "__main__":
    main()
