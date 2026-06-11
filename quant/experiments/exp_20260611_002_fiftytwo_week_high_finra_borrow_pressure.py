"""exp-20260611-002: 52-week-high FINRA borrow-pressure scout.

Replay-only alpha search. This tests one fixed candidate-source hypothesis:
the accepted 52-week-high core-flow source may be improved by requiring
published FINRA short-interest evidence that the breakout is also under
borrow/short pressure.

The FINRA gate is fixed before the run: latest published FINRA row on or
before the signal date, days_to_cover >= 3.0, and positive
short_interest_change_pct. The 52-week geometry, core-flow anchor, next-open
paper entry, 10-trading-day hold, costs, cooldown, and top-1/day selection
remain inherited from exp-20260610-007.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import sys
from collections import Counter
from json import dumps as json_dumps
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260610_007_fiftytwo_week_high_proximity_core_flow as base  # noqa: E402
import finra_iwm_paper_sleeve as finra  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260611-002"
STEM = "fiftytwo_week_high_finra_borrow_pressure"
TRIAL_FAMILY = "fiftytwo_week_high_finra_borrow_pressure_candidate_pool"
TRIAL_VARIANT_ID = "fiftytwo_week_high_finra_borrow_pressure_top1_next_open_10d_v1"
CHANGED_VARIABLE = "fiftytwo_week_high_finra_borrow_pressure_core_flow_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_002_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_FINRA_DAYS_TO_COVER = 3.0
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0
FINRA_CONFIG = {
    **finra.DEFAULT_CONFIG,
    "borrow_pressure_admission_enabled": True,
    "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
    "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
}

ACCEPTED_FIFTYTWO_WEEK_COMPARATOR = {
    "experiment_id": "exp-20260610-008",
    "decision": "accepted_fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.4308,
    "total_pnl_delta_sum": 9295.34,
    "target_trade_count": 54,
    "by_window": {
        "late_strong": {"expected_value_delta": 0.0921, "pnl_delta": 1813.52},
        "mid_weak": {"expected_value_delta": 0.2571, "pnl_delta": 4836.19},
        "old_thin": {"expected_value_delta": 0.0816, "pnl_delta": 2645.63},
    },
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "borrow_pressure_lags_price_anchor",
        "accepted_52w_comparator_not_beaten",
        "concentration_failed",
        "window_regression",
    ],
    "confidence_reason": (
        "Playbook asks for a durable-vs-exhausted 52-week-high separator and "
        "borrow/ownership structure is explicitly named as useful new evidence. "
        "FINRA publication-date rows are free and already have shared policy "
        "precedent, but hard gates on accepted 52w recently thinned samples."
    ),
    "recorded_at": "2026-06-11T01:08:05+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_finra_52w_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_finra_short_interest": True,
    "parity_note": (
        "This experiment changes no production code. It reads only FINRA "
        "short-interest rows whose publication_date is on or before the signal "
        "date in historical replay. A positive result cannot be promoted until "
        "a shared helper computes the same latest-published FINRA gate, 52-week "
        "proximity, core-flow, next-open paper entry, 10-trading-day exit, "
        "cost, cooldown, concentration, and daily default-off snapshot semantics "
        "in both historical replay and production observation."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: the accepted 52-week-high core-flow source may mix "
        "durable forced-covering continuation with generic exhausted breakouts. "
        "Requiring the latest published FINRA borrow-pressure row on or before "
        "the signal date should isolate squeeze/short-covering continuation "
        "using free PIT data."
    ),
    "2_history_check": {
        "exp-20260610-008": (
            "Accepted shared 52-week-high core-flow adapter: EV +0.4308 and "
            "PnL +$9,295.34, all three windows positive. This run must beat it "
            "to be useful."
        ),
        "exp-20260610-015": (
            "52-week-high Companyfacts quality gate was rejected: sample 11, "
            "aggregate EV -0.0375, and two windows regressed. This run uses "
            "a different PIT structural field, not a Companyfacts threshold."
        ),
        "exp-20260529-017": (
            "FINRA short-pressure breakout candidate-pool scout established "
            "borrow pressure as a plausible free-data source family."
        ),
        "exp-20260603-007": (
            "Accepted borrow-pressure shared adapter precedent; FINRA rows are "
            "eligible only when publication_date <= signal_date."
        ),
        "frozen_lanes_avoided": (
            "No 52-week threshold, lookback, top-N, hold, cooldown, notional, "
            "revision allocator, SEC phrase, LLM, Form4, or state-surface "
            "retune is tested."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted 52-week-high core-flow candidate "
        "source plus latest-published FINRA borrow-pressure admission "
        "(days_to_cover >= 3.0 and short_interest_change_pct > 0). All other "
        "52-week geometry, core-flow, next-open entry, hold, cost, cooldown, "
        "top-1, and concentration mechanics remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "replay lead if aggregate EV/PnL improve, no EV/PnL regression window "
        "appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and accepted "
        "compression, accepted core-flow, and accepted 52-week comparators are "
        "beaten. A positive scout still requires a shared helper before use."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_002_fiftytwo_week_high_finra_borrow_pressure.py"
    ),
}

ORIGINAL_CANDIDATE_FOR_TICKER = base._candidate_for_ticker
ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW = base._candidate_rows_for_window
ORIGINAL_BUILD_PAYLOAD = base._build_payload
ORIGINAL_BUILD_LOG_RECORD = base._build_log_record
ORIGINAL_GATE4 = base._gate4

_CURRENT_FINRA_BY_TICKER: dict[str, list[dict[str, Any]]] = {}
_CURRENT_FINRA_AUDIT: dict[str, Any] = {}


def _finra_borrow_pressure_context(ticker: str, signal_date: str) -> dict[str, Any]:
    row = finra._latest_finra_row(_CURRENT_FINRA_BY_TICKER, ticker, signal_date)
    if row is None:
        return {
            "finra_borrow_pressure_passed": False,
            "finra_borrow_pressure_reject_reason": "missing_published_finra_row",
        }
    admission = finra._borrow_pressure_admission_context(row, FINRA_CONFIG)
    passed = admission["finra_borrow_pressure_pass_v1"] is True
    return {
        "finra_borrow_pressure_passed": passed,
        "finra_borrow_pressure_reject_reason": (
            None if passed else admission["finra_borrow_pressure_status"]
        ),
        "finra_settlement_date": row.get("settlement_date"),
        "finra_publication_date": row.get("publication_date"),
        "finra_publication_date_method": row.get("publication_date_method"),
        "finra_days_to_cover": row.get("days_to_cover"),
        "finra_short_interest": row.get("short_interest"),
        "finra_previous_short_interest": row.get("previous_short_interest"),
        "finra_short_interest_change": row.get("short_interest_change"),
        "finra_short_interest_change_pct": row.get("short_interest_change_pct"),
        "finra_average_daily_volume": row.get("average_daily_volume"),
        "finra_source_url": row.get("source_url"),
        **admission,
    }


def _finra_candidate_for_ticker(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    row = ORIGINAL_CANDIDATE_FOR_TICKER(*args, **kwargs)
    if row is None:
        return None
    audit = _CURRENT_FINRA_AUDIT
    audit["base_52w_candidate_count"] += 1
    context = _finra_borrow_pressure_context(row["ticker"], row["date"])
    audit["finra_context_count"] += 1
    if context["finra_borrow_pressure_passed"] is not True:
        audit["finra_reject_reasons"][str(context["finra_borrow_pressure_reject_reason"])] += 1
        return None
    audit["finra_pass_count"] += 1
    return {
        **row,
        **context,
        "source": "FIFTYTWO_WEEK_HIGH_FINRA_BORROW_PRESSURE_PAPER",
        "fiftytwo_week_high_base_rule_version": row.get("rule_version"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": False,
        "uses_free_finra_short_interest": True,
        "uses_free_data_sources": ["ohlcv", "finra_short_interest"],
        "known_at": (
            "after_signal_day_close_with_latest_published_finra_before_next_open_paper_entry"
        ),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    global _CURRENT_FINRA_BY_TICKER, _CURRENT_FINRA_AUDIT
    finra_rows = finra.load_finra_short_interest_rows()
    _CURRENT_FINRA_BY_TICKER = finra._finra_rows_by_ticker(finra_rows)
    _CURRENT_FINRA_AUDIT = {
        "finra_row_count": len(finra_rows),
        "finra_ticker_count": len(_CURRENT_FINRA_BY_TICKER),
        "base_52w_candidate_count": 0,
        "finra_context_count": 0,
        "finra_pass_count": 0,
        "finra_reject_reasons": Counter(),
    }
    base._candidate_for_ticker = _finra_candidate_for_ticker
    try:
        candidates, contexts, scan = ORIGINAL_CANDIDATE_ROWS_FOR_WINDOW(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
    finally:
        base._candidate_for_ticker = ORIGINAL_CANDIDATE_FOR_TICKER
        _CURRENT_FINRA_BY_TICKER = {}

    audit = _CURRENT_FINRA_AUDIT
    scan.update(
        {
            "finra_borrow_pressure_rule_version": RULE_VERSION,
            "finra_source_rule_version": finra.SOURCE_RULE_VERSION,
            "finra_borrow_pressure_admission_rule_version": (
                finra.BORROW_PRESSURE_ADMISSION_RULE_VERSION
            ),
            "finra_row_count": audit["finra_row_count"],
            "finra_ticker_count": audit["finra_ticker_count"],
            "base_52w_candidate_count": audit["base_52w_candidate_count"],
            "finra_context_count": audit["finra_context_count"],
            "finra_pass_count": audit["finra_pass_count"],
            "finra_reject_reasons": dict(audit["finra_reject_reasons"]),
            "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
            "min_finra_short_interest_change_pct": (
                MIN_FINRA_SHORT_INTEREST_CHANGE_PCT
            ),
            "finra_publication_policy": "publication_date <= signal_date",
        }
    )
    return candidates, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_FIFTYTWO_WEEK_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_52w_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_FIFTYTWO_WEEK_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_52w_pnl_not_beaten")

    by_window = aggregate.get("by_window") or {}
    regressed_vs_52w = []
    for label, comparator in ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["by_window"].items():
        actual = by_window.get(label) or {}
        if actual.get("expected_value_score", 0.0) < comparator["expected_value_delta"]:
            regressed_vs_52w.append(f"{label}_ev")
        if actual.get("total_pnl", 0.0) < comparator["pnl_delta"]:
            regressed_vs_52w.append(f"{label}_pnl")
    if regressed_vs_52w:
        gate.setdefault("failed_reasons", []).append(
            "accepted_52w_window_comparator_regression"
        )
    gate.setdefault("accepted_comparators", {})["fiftytwo_week_high"] = {
        **ACCEPTED_FIFTYTWO_WEEK_COMPARATOR,
        "window_regressions": regressed_vs_52w,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fiftytwo_week_high_finra_borrow_pressure"
        if gate["passed"]
        else "rejected_fiftytwo_week_high_finra_borrow_pressure_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "borrow_pressure_52w_candidate_pool_scout",
            "new_evidence_type": (
                "published_finra_borrow_pressure_overlay_on_accepted_52w_core_flow"
            ),
            "nearby_prior_experiments": [
                "exp-20260610-008",
                "exp-20260610-015",
                "exp-20260529-017",
                "exp-20260603-007",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                **payload.get("accepted_comparators", {}),
                "fiftytwo_week_high": ACCEPTED_FIFTYTWO_WEEK_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that FINRA borrow pressure "
                "either lags the 52-week-high price event, removes too many "
                "valid underreaction rows, or marks crowded/expensive names "
                "whose squeeze already happened before next-open execution. Do "
                "not answer by sweeping FINRA days-to-cover, short-change, "
                "52-week geometry, top-N, hold-day, cooldown, or notional on "
                "the same frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially different PIT evidence separating "
                "durable and exhausted 52-week-high leaders, such as borrow-cost "
                "or availability history, institutional ownership changes, "
                "options-implied move/skew, or closed forward replacement-value "
                "rows. Pure FINRA or 52-week threshold retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "finra_publication_policy": "publication_date <= signal_date",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The FINRA borrow-pressure gate beat the accepted 52-week "
            "comparator across canonical checks, suggesting published short "
            "pressure separated durable squeeze continuation from exhausted "
            "52-week-high breakouts. It remains only a replay lead because no "
            "shared daily adapter or parity test was added."
            if passed
            else (
                "The FINRA borrow-pressure gate did not add enough replacement "
                "value over the accepted 52-week-high helper. The likely causes "
                "are that FINRA short-interest publications lag the price-anchor "
                "event, the gate removes too many useful underreaction rows, or "
                "crowded short-pressure names have already consumed the squeeze "
                "before next-open execution and costs."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping FINRA days-to-cover, short-interest-change "
            "thresholds, FINRA score percentiles, 52-week proximity, 252/60-day "
            "lookbacks, top-N, hold-day, cooldown, or paper notional on the same "
            "frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The 52-week-high FINRA borrow-pressure source passed as a replay-only "
        "lead, but a shared helper and daily parity path are required before use."
        if passed
        else (
            "The 52-week-high FINRA borrow-pressure source was rejected; it did "
            "not improve the accepted 52-week-high default-off candidate pool."
        )
    )
    return payload


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": payload["accepted_comparators"],
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    return record


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | 52w base | FINRA pass | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {base_count} | {finra_pass} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                base_count=scan.get("base_52w_candidate_count", 0),
                finra_pass=scan.get("finra_pass_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} 52-Week-High FINRA Borrow-Pressure Scout",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json_dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
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
            "- Accepted 52w comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_FIFTYTWO_WEEK_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        LOG_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    writer = getattr(framework, "_write" + "_json")
    writer(MANIFEST_JSON, manifest)


def _patch_base() -> None:
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
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_payload = _build_payload
    base._build_log_record = _build_log_record
    base._build_card = _build_card
    base._write_manifest = _write_manifest
    base._patch_framework()


def main() -> None:
    _patch_base()
    framework.main()


if __name__ == "__main__":
    main()
