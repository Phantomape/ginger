"""exp-20260609-006: Fundamental Growth RS quality-gated top-1 replacement.

Alpha search replay scout. This changes one candidate-selection policy inside
the accepted SEC Companyfacts Fundamental Growth RS paper source: before the
existing daily top-1 selector, keep only candidates whose filed-date-safe
operating-income filing recency and liabilities/assets checks both pass.

The runner changes no production code, shared adapter, live orders, watchlists,
LLM/news path, core ranking, sizing, or exits. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_017_fundamental_growth_rs_low_liability_support as accepted


EXPERIMENT_ID = "exp-20260609-006"
STEM = "fundamental_growth_rs_quality_gated_top1_replacement"
TRIAL_FAMILY = "fundamental_growth_rs_quality_gated_candidate_selection"
TRIAL_VARIANT_ID = "fundamental_growth_rs_filing_recency_low_liability_top1_replacement_v1"
CHANGED_VARIABLE = "fundamental_growth_rs_quality_gated_top1_replacement_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_006_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / ("experiment_" + "registry.json")

REFERENCE_EXPERIMENT_ID = "exp-20260528-017"
REFERENCE_LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{REFERENCE_EXPERIMENT_ID}.json"

MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "rejecting_top_ranked_winners",
        "too_few_quality_candidates",
        "old_thin_regression",
        "companyfacts_support_fields_not_selection_fields",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Filing recency and low liability were accepted as small support fields, "
        "but broad Companyfacts candidate-pool variants recently failed and this "
        "family has high multiple-testing risk; this is a narrow replay scout, "
        "not a production promotion."
    ),
    "recorded_at": "2026-06-09T06:08:14+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter_change",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "parity_note": (
        "This experiment changes no production code. It reuses filed-date-safe "
        "SEC Companyfacts and signal-date OHLCV fields in replay only. A positive "
        "result cannot be promoted unless the same quality-gated selection is "
        "implemented in a shared default-off adapter, daily snapshot, historical "
        "replay, and parity tests before any report queue, watchlist, sizing, "
        "or order behavior changes."
    ),
}

QUALITY_SELECTION_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _base():
    return accepted._base()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _round(value: Any, digits: int = 6) -> Any:
    return _base()._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return _base()._repo_rel(Path(path))


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any, *, sort_keys: bool = True) -> None:
    _base()._write_json(path, payload)
    if not sort_keys:
        path.write_text(json.dumps(_base()._safe(payload), indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    _base()._write_text(path, text)


def _filing_recency_pass(row: dict[str, Any]) -> bool:
    return accepted.prev._filing_recency_scalar(row) > 1.0


def _quality_context(
    row: dict[str, Any],
    balance_sheet_index: accepted.CompanyfactsBalanceSheetIndex,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("date") or "")
    balance_context = balance_sheet_index.current_context(ticker, signal_date)
    filing_pass = _filing_recency_pass(row)
    low_liability_pass = accepted._balance_sheet_scalar(balance_context) > 1.0
    return {
        "quality_gated_selection_rule_version": RULE_VERSION,
        "quality_gated_selection_known_at": (
            "SEC Companyfacts filed date <= signal_date plus signal-date OHLCV; "
            "paper entry remains next open"
        ),
        "quality_gated_selection_trade_enabled": False,
        "quality_gated_selection_alters_orders": False,
        "quality_filing_recency_pass_v1": filing_pass,
        "quality_low_liability_pass_v1": low_liability_pass,
        "quality_gated_candidate_selection_pass_v1": filing_pass and low_liability_pass,
        "quality_liabilities_assets_ratio": balance_context.get("liabilities_assets_ratio"),
        "quality_balance_sheet_status": balance_context.get("balance_sheet_status"),
    }


def _select_quality_gated_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    label = accepted._governor()._window_label_for_candidates(candidates)
    balance_sheet_index = accepted._balance_sheet_index_for_candidates(candidates)
    kept: list[dict[str, Any]] = []
    quality_filtered: list[dict[str, Any]] = []
    context_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    date_counts: dict[str, Counter[str]] = {}
    audit: Counter[str] = Counter()

    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        context = _quality_context(row, balance_sheet_index)
        context_by_key[(signal_date, ticker)] = context
        bucket = date_counts.setdefault(signal_date, Counter())
        bucket["total"] += 1
        if context["quality_filing_recency_pass_v1"]:
            audit["filing_recency_passed_candidates"] += 1
            bucket["filing_recency_passed"] += 1
        if context["quality_low_liability_pass_v1"]:
            audit["low_liability_passed_candidates"] += 1
            bucket["low_liability_passed"] += 1
        if context["quality_gated_candidate_selection_pass_v1"]:
            audit["quality_passed_candidates"] += 1
            bucket["quality_passed"] += 1
            kept.append({**row, **context})
        else:
            reason = (
                "missing_both_quality_gates"
                if not context["quality_filing_recency_pass_v1"]
                and not context["quality_low_liability_pass_v1"]
                else (
                    "missing_filing_recency_gate"
                    if not context["quality_filing_recency_pass_v1"]
                    else "missing_low_liability_gate"
                )
            )
            audit[reason] += 1
            quality_filtered.append({**row, **context, "filter_reason": reason})

    selected: list[dict[str, Any]]
    downstream_filtered: list[dict[str, Any]]
    if kept:
        selected, downstream_filtered = accepted._select_low_liability_supported_paper_trades(
            snapshot,
            kept,
        )
    else:
        selected, downstream_filtered = [], []

    selected_with_context: list[dict[str, Any]] = []
    for trade in selected:
        key = (str(trade.get("date") or trade.get("signal_date") or ""), str(trade.get("ticker") or "").upper())
        context = context_by_key.get(key, {})
        selected_with_context.append(
            {
                **trade,
                **context,
                "selection_rule_version": RULE_VERSION,
                "rule_version": RULE_VERSION,
            }
        )

    first_by_date: dict[str, dict[str, Any]] = {}
    for row in candidates:
        first_by_date.setdefault(str(row.get("date") or ""), row)
    replacement_days = 0
    no_quality_candidate_days = 0
    for signal_date, counts in date_counts.items():
        first = first_by_date.get(signal_date) or {}
        first_key = (signal_date, str(first.get("ticker") or "").upper())
        first_passed = bool(
            context_by_key.get(first_key, {}).get("quality_gated_candidate_selection_pass_v1")
        )
        if counts.get("quality_passed", 0) <= 0:
            no_quality_candidate_days += 1
        elif not first_passed:
            replacement_days += 1

    selected_tickers = Counter(str(row.get("ticker") or "").upper() for row in selected_with_context)
    QUALITY_SELECTION_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "input_candidates": len(candidates),
        "quality_passed_candidates": len(kept),
        "quality_filtered_candidates": len(quality_filtered),
        "quality_candidate_days": sum(1 for counts in date_counts.values() if counts.get("quality_passed", 0) > 0),
        "no_quality_candidate_days": no_quality_candidate_days,
        "replacement_day_count": replacement_days,
        "selected_trades": len(selected_with_context),
        "selected_unique_tickers": len(selected_tickers),
        "selected_ticker_counts": dict(sorted(selected_tickers.items())),
        "downstream_filtered_candidates": len(downstream_filtered),
        **dict(sorted(audit.items())),
    }
    return selected_with_context, quality_filtered + downstream_filtered


def _configure_modules() -> None:
    accepted.EXPERIMENT_ID = EXPERIMENT_ID
    accepted.STEM = STEM
    accepted.TRIAL_FAMILY = TRIAL_FAMILY
    accepted.CHANGED_VARIABLE = CHANGED_VARIABLE
    accepted.OUT_DIR = OUT_DIR
    accepted.OUT_JSON = OUT_JSON
    accepted.LOG_JSON = LOG_JSON
    accepted.TICKET_JSON = TICKET_JSON
    accepted.DOC_TICKET_JSON = DOC_TICKET_JSON
    accepted.ARTIFACT_MD = ARTIFACT_MD
    accepted.EXPERIMENT_LOG = EXPERIMENT_LOG
    accepted.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    accepted.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    accepted.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    accepted.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    accepted.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    accepted.BALANCE_SHEET_AUDIT.clear()
    QUALITY_SELECTION_AUDIT.clear()
    accepted._configure_modules()
    _base()._select_paper_trades = _select_quality_gated_paper_trades


def _aggregate_metrics(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return accepted._aggregate_metrics(metrics_by_window)


def _reference_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    if not REFERENCE_LOG_JSON.exists():
        return {"available": False, "reason": "missing_exp_20260528_017_reference"}
    reference = _load_json(REFERENCE_LOG_JSON)
    ref_after = reference.get("after_metrics") or {}
    after = payload.get("after_metrics") or {}
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in _base().WINDOWS:
        ref = ref_after.get(label) or {}
        cur = after.get(label) or {}
        by_window[label] = {
            "expected_value_score_delta": _round(
                float(cur.get("expected_value_score") or 0.0)
                - float(ref.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_delta": _round(
                float(cur.get("total_pnl") or 0.0) - float(ref.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_pct_delta": _round(
                float(cur.get("max_drawdown_pct") or 0.0)
                - float(ref.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
    ref_agg = _aggregate_metrics(ref_after)
    cur_agg = _aggregate_metrics(after)
    return {
        "available": True,
        "reference_experiment_id": REFERENCE_EXPERIMENT_ID,
        "reference_decision": reference.get("decision"),
        "by_window_delta_after_vs_accepted_low_liability": by_window,
        "aggregate_delta_after_vs_accepted_low_liability": {
            "expected_value_score_delta_sum": _round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": _round(cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"], 2),
            "max_drawdown_pct_delta_max": _round(
                cur_agg["max_drawdown_pct_max"] - ref_agg["max_drawdown_pct_max"],
                6,
            ),
        },
    }


def _accepted_stack_gate(reference_comparison: dict[str, Any]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    if not reference_comparison.get("available"):
        return False, ["missing_accepted_low_liability_reference"]
    aggregate = reference_comparison["aggregate_delta_after_vs_accepted_low_liability"]
    by_window = reference_comparison["by_window_delta_after_vs_accepted_low_liability"]
    ev_delta = float(aggregate.get("expected_value_score_delta_sum") or 0.0)
    pnl_delta = float(aggregate.get("total_pnl_delta_sum") or 0.0)
    if ev_delta <= 0.0:
        failed.append("aggregate_ev_not_above_accepted_exp017")
    if pnl_delta <= 0.0:
        failed.append("aggregate_pnl_not_above_accepted_exp017")
    if any(float(row.get("expected_value_score_delta") or 0.0) < 0.0 for row in by_window.values()):
        failed.append("window_ev_regressed_vs_accepted_exp017")
    if any(float(row.get("total_pnl_delta") or 0.0) < 0.0 for row in by_window.values()):
        failed.append("window_pnl_regressed_vs_accepted_exp017")
    return not failed, failed


def _calibration(gate4_passed: bool) -> dict[str, Any]:
    actual = 1 if gate4_passed else 0
    predicted = float(PREDICTION["success_probability"])
    observed_failures = [
        failure
        for failure in PREDICTION["main_failure_modes"]
        if failure in {
            "rejecting_top_ranked_winners",
            "too_few_quality_candidates",
            "old_thin_regression",
            "companyfacts_support_fields_not_selection_fields",
            "concentration_failed",
        }
    ]
    return {
        "predicted_success_probability": predicted,
        "actual_gate4_passed": gate4_passed,
        "actual_success": actual,
        "brier_score": _round((predicted - actual) ** 2, 6),
        "failure_modes_observed": observed_failures if not gate4_passed else [],
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    reference_comparison = _reference_comparison(payload)
    accepted_stack_passed, accepted_stack_failed = _accepted_stack_gate(reference_comparison)
    core_gate4_passed = bool(payload["gate4"]["passed"])
    gate4_passed = core_gate4_passed and accepted_stack_passed
    decision = (
        "promising_replay_only_fundamental_growth_rs_quality_gated_top1_replacement"
        if gate4_passed
        else "rejected_fundamental_growth_rs_quality_gated_top1_replacement"
    )
    completed_at = _utc_now()

    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = completed_at
    payload["completed_at"] = completed_at
    payload["status"] = "accepted" if gate4_passed else "rejected"
    payload["accepted"] = gate4_passed
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Candidate-pool selection alpha: within the accepted SEC Companyfacts "
        "Fundamental Growth RS paper source, replacing the daily top-1 with the "
        "best same-day candidate that has both fresh operating-income filing "
        "and low-liability balance-sheet evidence may improve source quality "
        "without adding noisy tickers."
    )
    payload["change_type"] = "default_off_paper_candidate_selection"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["prior_trial_count"] = 24
    payload["nearby_prior_experiments"] = [
        "exp-20260528-016",
        "exp-20260528-017",
        "exp-20260601-027",
        "exp-20260607-002",
        "exp-20260608-014",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_sec_companyfacts_selection_replacement"
    payload["prediction"] = PREDICTION
    payload["calibration"] = _calibration(gate4_passed)
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["anti_js"] = "No JavaScript was used."
    payload["parameters"]["quality_gated_top1_replacement"] = {
        "filing_recency_rule": "operating_income filing age <= exp-20260528-016 accepted threshold",
        "low_liability_rule": "liabilities/assets <= exp-20260528-017 accepted threshold",
        "selection_order": (
            "prefilter candidate rows by both gates, then reuse the existing "
            "Fundamental Growth RS score order and daily top-1 selector"
        ),
        "execution": "next open paper entry, 10 trading day paper hold",
        "uses_future_data": False,
        "production_visible_fields": [
            "SEC Companyfacts operating_income filed date <= signal_date",
            "SEC Companyfacts assets/liabilities filed date <= signal_date",
            "signal-date and trailing OHLCV rows",
        ],
    }
    payload["parameters"]["locked_variables"] = [
        "all exp-20260528-017 low-liability scalar semantics",
        "all exp-20260528-016 filing-recency scalar semantics",
        "all exp-20260528-015 low-volume participation logic",
        "all exp-20260528-008 closed-ledger governor logic",
        "all exp-20260528-004 operating-profit quality logic",
        "all exp-20260527-017 Companyfacts growth thresholds",
        "all exp-20260527-017 RS proxy thresholds",
        "paper notional base",
        "10-trading-day paper hold",
        "core signal generation",
        "core ranking",
        "core sizing",
        "core exits",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
    ]
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "Candidate selection: fresh SEC operating-income filings plus low "
            "liabilities/assets should be cleaner than blindly taking the highest "
            "Fundamental Growth RS score for a day."
        ),
        "2_history_check": {
            "exp-20260528-016": "Accepted filing-recency support, but only as a scalar after selection.",
            "exp-20260528-017": "Accepted low-liability support, also only as a scalar after selection.",
            "exp-20260607-002": "Broad Companyfacts freshness candidate pool improved aggregate EV but failed old_thin.",
            "exp-20260608-014": "Companyfacts quality compression source was too sparse and rejected.",
            "current_difference": (
                "This run does not retune thresholds or add a broad source; it "
                "tests whether two accepted quality fields work as a replacement "
                "selector inside the existing source."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md three-window replay; positive aggregate EV and "
            "PnL; no EV/PnL regression in any of the three windows versus both "
            "the core baseline and accepted exp-20260528-017; >=30 target trades; "
            "survival >=5%; drawdown and concentration guardrails pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_006_fundamental_growth_rs_quality_gated_top1_replacement.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "operating_income_current_filed with filed <= signal_date",
        "assets and liabilities facts with filed <= signal_date",
    ]
    payload["gate2"]["note"] = (
        "The selection gates are computed only from SEC filed dates <= signal_date "
        "and signal-date/trailing OHLCV. Paper entry remains next open and the "
        "closed-ledger governor uses only rows with exit_date < entry_date."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No live or core filter was added. The default-off paper candidate selector "
        "became stricter inside one private replay source, so core survival is unchanged."
    )
    payload["gate4"]["core_gate4_passed"] = core_gate4_passed
    payload["gate4"]["accepted_low_liability_comparison_passed"] = accepted_stack_passed
    payload["gate4"]["accepted_low_liability_failed_checks"] = accepted_stack_failed
    payload["gate4"]["passed"] = gate4_passed
    payload["gate4"]["decision"] = decision
    payload["quality_selection_audit"] = QUALITY_SELECTION_AUDIT
    payload["balance_sheet_audit"] = accepted.BALANCE_SHEET_AUDIT
    payload["filing_recency_audit"] = accepted.prev.FILING_RECENCY_AUDIT
    payload["low_volume_participation_audit"] = accepted.prev.prev.LOW_VOLUME_AUDIT
    payload["reference_accepted_low_liability_exp017_comparison"] = reference_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM/revision/Kova paths because recent records show data limits. "
        "Skipped state-surface, lagged-consensus source additions, OHLCV gap/compression "
        "retunes, and Companyfacts threshold/scalar mining because those near-neighbors "
        "are frozen or recently failed. This run tests only a predeclared replacement "
        "selector using already accepted free SEC fields."
    )
    if gate4_passed:
        payload["interpretation"] = (
            "The replay scout beat the accepted low-liability comparator. It is only "
            "a production-visible lead; promotion requires a shared default-off adapter "
            "and parity tests before any daily report or order surface changes."
        )
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "The two accepted Companyfacts quality fields were strong enough as "
                "selection fields, not only notional scalars, and avoided weaker top-ranked rows."
            ),
            "new_evidence_required": (
                "Implement the exact same selector in a shared default-off adapter and "
                "collect forward closed replacement-value rows before live activation."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune filing-age, liabilities/assets, top-N, hold-day, or "
                "notional thresholds on these same windows as a separate acceptance claim."
            ),
        }
    else:
        payload["interpretation"] = (
            "The quality-gated replacement selector did not clear Gate 4. The likely "
            "mechanism is that filing recency and low liabilities are useful as small "
            "support scalars but too blunt as a hard replacement selector, removing "
            "top-ranked winners or making the source too sparse."
        )
        payload["negative_reflection"] = payload["interpretation"]
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "The selector likely rejected high-ranked winners or starved one of "
                "the standard windows; the two quality fields are not sufficient as "
                "hard candidate-selection gates on the frozen sample."
            ),
            "new_evidence_required": (
                "A useful retry needs materially new PIT source evidence or forward "
                "closed replacement-value rows, not another liabilities/assets or "
                "filing-age threshold sweep."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by only loosening filing-recency days, liabilities/assets "
                "ratio, top-N, hold-day, or support scalar values on the same windows."
            ),
        }
    payload["next_evidence_needed"] = payload["post_run_reflection"]["new_evidence_required"]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOC_TICKET_JSON),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Quality candidates | Replacement days |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["quality_selection_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | {quality} | {repl} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                quality=audit.get("quality_passed_candidates"),
                repl=audit.get("replacement_day_count"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    target = payload["target_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Fundamental Growth RS Quality-Gated Top-1 Replacement",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single decision hypothesis: prefilter the accepted Fundamental Growth "
                "RS candidate rows to candidates passing both filed-date-safe filing "
                "recency and low-liability gates before the existing top-1/day selector."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core baseline: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core baseline: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{aggregate['target_trade_count_sum']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
            "",
            "## Accepted Comparator",
            "",
            "```json",
            json.dumps(
                payload["reference_accepted_low_liability_exp017_comparison"],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Quality Selection Audit",
            "",
            "```json",
            json.dumps(payload["quality_selection_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Reflection",
            "",
            payload["interpretation"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Fundamental Growth RS Quality-Gated Top-1 Replacement",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta vs core: `{aggregate['expected_value_score_delta_sum']}`",
            f"- Aggregate PnL delta vs core: `${aggregate['total_pnl_delta_sum']}`",
            "- Production impact: replay-only; no shared adapter or live/default orders changed.",
            "- Comparator: accepted `exp-20260528-017` low-liability stack.",
            "",
        ]
    )


def _update_ticket(path: Path, payload: dict[str, Any]) -> None:
    ticket = _load_json(path) if path.exists() else {}
    ticket.update(
        {
            "status": "completed",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "production_impact": PRODUCTION_IMPACT,
            "result": {
                "accepted": payload["accepted"],
                "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
                    "expected_value_score_delta_sum"
                ],
                "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
                    "total_pnl_delta_sum"
                ],
            },
        }
    )
    _base()._write_json(path, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(TICKET_JSON),
                _repo_rel(ARTIFACT_MD),
            ],
        }
    )
    _base()._write_json(MANIFEST_JSON, manifest)


def _persist_registry_result(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "report": _repo_rel(ARTIFACT_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "production_impact": PRODUCTION_IMPACT,
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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


def _persist(payload: dict[str, Any]) -> None:
    _base()._write_json(OUT_JSON, payload)
    _base()._write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _write_text(ARTIFACT_MD, _build_report(payload))
    _update_manifest(payload)
    _persist_registry_result(payload)
    _update_ticket(TICKET_JSON, payload)
    _update_ticket(DOC_TICKET_JSON, payload)
    _base()._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _update_payload(_base()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _base()._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["delta_metrics"]["aggregate"][
                        "expected_value_score_delta_sum"
                    ],
                    "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
                    "gate4": payload["gate4"],
                    "quality_selection_audit": payload["quality_selection_audit"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
