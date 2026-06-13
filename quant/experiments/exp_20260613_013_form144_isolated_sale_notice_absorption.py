"""exp-20260613-013: isolated Form 144 sale-notice absorption scout.

Replay-only alpha search. This tests one event-quality candidate-pool policy:
start from the prior Form 144 absorbed-sale-notice scout, but admit only
isolated notices, not same-ticker Form 144 clusters. The fixed cluster rule is
same-day accessions <= 1 and trailing seven-calendar-day accessions <= 2.

No production path, shared policy, order, ranking, sizing, exit, watchlist,
LLM, or news behavior changes. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict, deque
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import exp_20260612_023_form144_sale_notice_absorption as base


EXPERIMENT_ID = "exp-20260613-013"
STEM = "form144_isolated_sale_notice_absorption"
TRIAL_FAMILY = "form144_sale_notice_absorption_candidate_pool"
TRIAL_VARIANT_ID = "form144_isolated_absorbed_top1_next_open_10d_v1"
CHANGED_VARIABLE = "form144_isolated_sale_notice_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

MAX_SAME_DAY_FORM144_ACCESSIONS = 1
MAX_TRAILING_7D_FORM144_ACCESSIONS = 2
TRAILING_CLUSTER_DAYS = 7

CLUSTER_EVENT_SUMMARY: dict[str, Any] = {}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "drawdown_drift_persists",
        "sample_thinned",
        "cluster_count_not_independent",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Base Form 144 scout improved EV/PnL in all windows but failed "
        "old_thin drawdown. A PIT Form144-specific cluster field from the same "
        "SEC form index may separate routine supply programs from absorbable "
        "isolated notices, but nearby Form4/Form144 sale lanes failed risk "
        "gates."
    ),
    "recorded_at": "2026-06-13T09:08:00+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "private_replay_scout_escape_reason": (
        "The isolated Form 144 cluster field is built from local EDGAR form "
        "index files inside this experiment. No shared daily helper or "
        "production daily Form 144 cluster snapshot exists yet, so a positive "
        "result is lead-only until the event build, cluster rule, absorption "
        "gates, overlap exclusion, next-open paper entry, costs, hold, and "
        "cooldown are implemented in shared historical replay and daily "
        "default-off snapshots."
    ),
    "parity_note": (
        "No production code changes. Positive replay would require a shared "
        "default-off helper plus daily EDGAR Form 144 cluster snapshot parity "
        "before any accepted-alpha claim."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: Form 144 planned-sale notices may work better when "
        "the filing is isolated rather than clustered. Clustered same-ticker "
        "notices imply persistent planned-sale supply; isolated notices with "
        "same-day price/liquidity absorption are more likely to reflect real "
        "demand overcoming known supply."
    ),
    "2_history_check": {
        "exp-20260612-023": (
            "Base Form 144 sale-notice absorption improved aggregate EV/PnL "
            "and all three windows, but was rejected because max drawdown "
            "worsened beyond the guardrail, especially old_thin."
        ),
        "exp-20260611-026": (
            "Nearby Form 4 sale absorption was rejected at -0.1340 EV and "
            "-$1,537.49."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption is the closest positive "
            "supply/absorption comparator at +0.5286 EV and +$10,432.91."
        ),
        "difference": (
            "This run does not sweep price, liquidity, volume, top-N, hold, "
            "cooldown, or notional. It tests one new PIT Form 144 event-quality "
            "field: whether the notice is isolated in the issuer's recent "
            "Form 144 stream."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no EV/PnL window regression, target trades "
        "cover all three windows, survival/drawdown/concentration pass, and "
        "the accepted distribution-day absorption comparator is beaten. Even "
        "if positive, replay-only status is not accepted production alpha."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_013_form144_isolated_sale_notice_absorption.py"
    ),
}

_original_load_sec_events = base._load_sec_events
_original_candidate_for_ticker = base._candidate_for_ticker
_original_build_payload = base._build_payload
_original_build_log_record = base._build_log_record
_original_build_card = base._build_card


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _event_is_isolated(event: dict[str, Any]) -> bool:
    return (
        int(event.get("same_day_form144_accession_count") or 0)
        <= MAX_SAME_DAY_FORM144_ACCESSIONS
        and int(event.get("trailing_7d_form144_accession_count") or 0)
        <= MAX_TRAILING_7D_FORM144_ACCESSIONS
    )


def _enrich_cluster_counts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in events:
        by_ticker[str(row.get("ticker") or "").upper()].append(row)

    enriched: list[dict[str, Any]] = []
    total_events = 0
    isolated_events = 0
    same_day_cluster_events = 0
    trailing_cluster_events = 0
    max_same_day = 0
    max_trailing = 0

    for ticker, rows in by_ticker.items():
        parsed_rows = [
            (parsed, row)
            for row in rows
            if (parsed := _parse_date(row.get("filing_date"))) is not None
        ]
        day_counts = Counter(parsed for parsed, _row in parsed_rows)
        trailing_by_day: dict[date, int] = {}
        active_days: deque[date] = deque()
        active_total = 0
        for current_day in sorted(day_counts):
            active_days.append(current_day)
            active_total += day_counts[current_day]
            cutoff = current_day - timedelta(days=TRAILING_CLUSTER_DAYS)
            while active_days and active_days[0] < cutoff:
                expired = active_days.popleft()
                active_total -= day_counts[expired]
            trailing_by_day[current_day] = active_total

        for parsed, row in parsed_rows:
            same_day = day_counts[parsed]
            trailing = trailing_by_day[parsed]
            prior_trailing = max(0, trailing - same_day)
            output = {
                **row,
                "same_day_form144_accession_count": same_day,
                "trailing_7d_form144_accession_count": trailing,
                "prior_7d_form144_accession_count": prior_trailing,
                "form144_cluster_policy_version": RULE_VERSION,
            }
            output["form144_isolated_notice"] = _event_is_isolated(output)
            total_events += 1
            isolated_events += 1 if output["form144_isolated_notice"] else 0
            same_day_cluster_events += 1 if same_day > MAX_SAME_DAY_FORM144_ACCESSIONS else 0
            trailing_cluster_events += 1 if trailing > MAX_TRAILING_7D_FORM144_ACCESSIONS else 0
            max_same_day = max(max_same_day, same_day)
            max_trailing = max(max_trailing, trailing)
            enriched.append(output)

    CLUSTER_EVENT_SUMMARY.clear()
    CLUSTER_EVENT_SUMMARY.update(
        {
            "cluster_policy": "same_day_accessions_le_1_and_trailing_7d_accessions_le_2",
            "trailing_cluster_days": TRAILING_CLUSTER_DAYS,
            "max_same_day_form144_accessions_allowed": MAX_SAME_DAY_FORM144_ACCESSIONS,
            "max_trailing_7d_form144_accessions_allowed": MAX_TRAILING_7D_FORM144_ACCESSIONS,
            "total_form144_events_with_cluster_fields": total_events,
            "isolated_form144_event_count": isolated_events,
            "clustered_form144_event_count": total_events - isolated_events,
            "same_day_cluster_event_count": same_day_cluster_events,
            "trailing_cluster_event_count": trailing_cluster_events,
            "max_same_day_form144_accessions_observed": max_same_day,
            "max_trailing_7d_form144_accessions_observed": max_trailing,
            "event_ticker_count": len(by_ticker),
        }
    )
    enriched.sort(key=lambda row: (row["filing_date"], row["ticker"], row["accession_number"]))
    return enriched


def _load_sec_events() -> list[dict[str, Any]]:
    return _enrich_cluster_counts(_original_load_sec_events())


def _candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    event = kwargs.get("event") or {}
    if not _event_is_isolated(event):
        return None
    row = _original_candidate_for_ticker(**kwargs)
    if row is None:
        return None
    row.update(
        {
            "source": "FORM144_ISOLATED_SALE_NOTICE_ABSORPTION_PAPER",
            "strategy": TRIAL_FAMILY,
            "candidate_same_day_form144_accession_count": int(
                event.get("same_day_form144_accession_count") or 0
            ),
            "candidate_trailing_7d_form144_accession_count": int(
                event.get("trailing_7d_form144_accession_count") or 0
            ),
            "candidate_prior_7d_form144_accession_count": int(
                event.get("prior_7d_form144_accession_count") or 0
            ),
            "candidate_form144_isolated_notice": True,
            "rule_version": RULE_VERSION,
            "decision_id": (
                f"FORM144_ISOLATED:{RULE_VERSION}:{row['date']}:{row['ticker']}"
            ),
        }
    )
    return row


def _build_payload() -> dict[str, Any]:
    payload = _original_build_payload()
    passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_lead_not_promoted_form144_isolated_sale_notice_absorption"
        if passed
        else "rejected_form144_isolated_sale_notice_absorption_candidate_pool"
    )
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    aggregate = payload["delta_metrics"]["aggregate"]
    why = (
        "The isolated Form 144 cluster rule cleared numeric replay gates, but "
        "is not accepted alpha because shared replay/daily parity and forward "
        "replacement-value rows are required before production-visible "
        "promotion."
        if passed
        else (
            "The isolated Form 144 cluster rule did not clear Gate 4. The "
            "fixed cluster field either removed too much sample or did not "
            "separate genuine absorbed supply from routine planned-sale "
            "notices enough to beat drawdown and accepted-comparator gates."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": decision,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_sale_notice_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260612-023",
                "exp-20260611-026",
                "exp-20260611-007",
            ],
            "prior_trial_count": 1,
            "new_evidence_type": "pit_sec_form144_cluster_event_quality_field",
            "gate_questions": PRE_RUN_QUESTIONS,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_distribution_comparator": base.ACCEPTED_DISTRIBUTION_COMPARATOR,
            "interpretation": (
                "The isolated Form 144 candidate source cleared numeric replay "
                "gates, but remains lead-only because no shared daily helper "
                "or production EDGAR daily-index cluster fetcher was promoted."
                if passed
                else (
                    "The isolated Form 144 candidate source was rejected under "
                    "the standard three-window protocol and accepted "
                    "distribution-day absorption comparator."
                )
            ),
            "rejection_reason": None
            if passed
            else "; ".join(payload["gate4"]["failed_reasons"]),
            "next_evidence_needed": (
                "A retry needs materially richer Form 144 semantics, such as "
                "parsed planned-sale size, insider role, sale percentage, "
                "holder identity, or closed forward replacement-value rows "
                "from a shared daily helper. Do not sweep same-day/trailing "
                "cluster thresholds or the existing liquidity, price, "
                "absorption, top-N, hold-day, cooldown, or notional thresholds "
                "on the same frozen windows."
            ),
        }
    )
    payload["gate4"]["decision"] = decision
    payload["prediction"] = {
        **PREDICTION,
        "actual_success": 1 if passed else 0,
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "brier_score": payload["calibration"]["brier_score"],
    }
    payload["calibration"]["predicted_success_probability"] = PREDICTION[
        "success_probability"
    ]
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus "
        "experiment-local SEC Form 144 isolated-cluster absorption paper overlay"
    )
    payload["backtest_protocol"]["execution_model"] = (
        payload["backtest_protocol"]["execution_model"]
        + " Candidate is additionally excluded when same-day Form 144 "
        "accessions exceed 1 or trailing seven-calendar-day same-ticker "
        "accessions exceed 2."
    )
    payload["parameters"].update(
        {
            "max_same_day_form144_accessions": MAX_SAME_DAY_FORM144_ACCESSIONS,
            "trailing_cluster_days": TRAILING_CLUSTER_DAYS,
            "max_trailing_7d_form144_accessions": MAX_TRAILING_7D_FORM144_ACCESSIONS,
            "form144_cluster_policy": (
                "same_day_accessions_le_1_and_trailing_7d_accessions_le_2"
            ),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["event_archive_summary"]["cluster_filter_summary"] = dict(CLUSTER_EVENT_SUMMARY)
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core entry filter is added. The isolated Form 144 source is an "
        "additive default-off paper candidate source; core signals and "
        "survival are unchanged."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why,
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping same-day/trailing cluster thresholds, "
            "liquidity, price, signal-return, relative-strength, "
            "close-location, volume-ratio, top-N, hold-day, cooldown, or "
            "notional thresholds, and do not simply merge this with rejected "
            "Form 4 sale absorption."
        ),
        "new_evidence_required": (
            "Parsed Form 144 document fields, holder role, planned-sale size "
            "as percent of float, holder identity, a broader PIT universe, or "
            "forward replacement-value rows from a shared helper."
        ),
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(base.OUT_JSON),
        _repo_rel(base.SEC_EVENTS_PATH),
        _repo_rel(base.LOG_JSON),
        _repo_rel(base.TICKET_JSON),
        _repo_rel(base.CARD_MD),
        _repo_rel(base.MANIFEST_JSON),
        _repo_rel(base.EXPERIMENT_LOG),
        _repo_rel(base.REGISTRY_JSON),
    ]
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _original_build_log_record(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": [
                "SEC form-index Form 144 event archive",
                "issuer ticker mapping",
                "same-day and trailing Form 144 cluster rule",
                "same-day absorption gates",
                "same-ticker core overlap exclusion",
                "next-open paper entry",
                "10d exit",
                "costs",
                "three-window Gate 1-4",
            ],
            "new_evidence_type": payload["new_evidence_type"],
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "negative_reflection": None
            if payload["gate4"]["passed"]
            else payload["post_run_reflection"]["why_result_happened"],
        }
    )
    return record


def _build_card(payload: dict[str, Any]) -> str:
    text = _original_build_card(payload)
    text = text.replace(
        f"# {EXPERIMENT_ID} Form 144 Sale-Notice Absorption",
        f"# {EXPERIMENT_ID} Isolated Form 144 Sale-Notice Absorption",
    )
    marker = "## Gate 1-4\n"
    cluster_summary = payload["event_archive_summary"].get("cluster_filter_summary", {})
    insertion = (
        "\n- Cluster policy: `{}`\n"
        "- Isolated Form 144 events: `{}` / `{}`\n"
    ).format(
        cluster_summary.get("cluster_policy"),
        cluster_summary.get("isolated_form144_event_count"),
        cluster_summary.get("total_form144_events_with_cluster_fields"),
    )
    return text.replace(marker, insertion + "\n" + marker)


def _configure_base() -> None:
    base.__file__ = __file__
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    base.OUT_JSON = base.OUT_DIR / f"exp_20260613_013_{STEM}.json"
    base.LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    base.TICKET_JSON = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    base.CARD_MD = base.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
    base.MANIFEST_JSON = (
        base.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
    )
    base.SEC_EVENTS_PATH = base.OUT_DIR / "form144_isolated_sale_notice_events.jsonl"
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._load_sec_events = _load_sec_events
    base._candidate_for_ticker = _candidate_for_ticker
    base._build_payload = _build_payload
    base._build_log_record = _build_log_record
    base._build_card = _build_card


def main() -> None:
    _configure_base()
    base.main()


if __name__ == "__main__":
    main()
