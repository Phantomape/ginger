"""exp-20260613-031: Fundamental Growth RS operating-efficiency selector.

Replay-only alpha search. This tests one fixed candidate-selection hypothesis
inside the accepted SEC Companyfacts Fundamental Growth RS paper source: before
the existing daily top-1 selector, keep only candidates whose latest filed-date
safe quarterly operating income is high relative to latest filed assets.

No production code, shared helper, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive result is only a
replay lead until a shared default-off adapter and daily parity reproduce it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import hashlib
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_017_fundamental_growth_rs_low_liability_support as accepted
import exp_20260609_006_fundamental_growth_rs_quality_gated_top1_replacement as base_exp


EXPERIMENT_ID = "exp-20260613-031"
STEM = "fundamental_growth_rs_operating_efficiency"
TRIAL_FAMILY = "fundamental_growth_rs_operating_efficiency_candidate_selection"
TRIAL_VARIANT_ID = "operating_income_assets_top1_replacement_v1"
CHANGED_VARIABLE = "operating_efficiency_assets_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_031_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

OPERATING_INCOME_ASSETS_MIN = 0.015
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1200.0,
    "main_failure_modes": [
        "sample_too_thin",
        "rejecting_top_ranked_winners",
        "accepted_low_liability_comparator_not_beaten",
        "old_thin_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Companyfacts+RS has strong accepted history, but prior hard "
        "quality-gated top1 replacement failed. Operating income/assets is a "
        "distinct free PIT capital-efficiency field; multiple-testing and "
        "accepted-comparator risk remain high."
    ),
    "recorded_at": "2026-06-13T23:05:15+00:00",
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
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_non_ohlcv": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This experiment changes no production code. It reuses filed-date-safe "
        "SEC Companyfacts and signal-date OHLCV fields in replay only. A positive "
        "result cannot be promoted unless the exact operating-income/assets "
        "selector is implemented in a shared default-off helper, historical "
        "replay, daily snapshot, and focused parity tests before any report "
        "queue, watchlist, sizing, or order behavior changes."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC Companyfacts Fundamental Growth RS candidates with "
        "high filed-date-safe operating income over assets may represent "
        "capital-efficient growth leaders whose next-open 10d paper replacement "
        "value beats the accepted low-liability Companyfacts stack."
    ),
    "2_history_check": {
        "exp-20260528-004": (
            "Positive operating income quality was accepted earlier as a broad "
            "source-quality field; this run asks for a stricter efficiency ratio, "
            "not just profitability > 0."
        ),
        "exp-20260528-006": (
            "Cash conversion quality failed drawdown/concentration, so this run "
            "does not use cash-flow conversion or capex variants."
        ),
        "exp-20260528-012": (
            "Gross-margin expansion failed concentration; this run does not "
            "reuse gross-margin thresholds."
        ),
        "exp-20260528-017": (
            "Accepted low-liability support is the binding Companyfacts stack "
            "comparator this candidate selector must beat."
        ),
        "exp-20260609-006": (
            "Rejected filing-recency + low-liability hard top1 selector; the "
            "main risk here is the same rejection of top-ranked winners."
        ),
        "exp-20260610-019": (
            "Fundamental Growth RS did not add enough as an allocator source "
            "after higher-priority accepted rows; this run stays inside the "
            "standalone Companyfacts source instead."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=30 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and the accepted "
        "exp-20260528-017 low-liability comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_031_fundamental_growth_rs_operating_efficiency.py"
    ),
}

OPERATING_EFFICIENCY_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _base():
    return base_exp._base()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _round(value: Any, digits: int = 6) -> float | None:
    return _base()._round(value, digits)


def _float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _repo_rel(path: Path | str) -> str:
    return _base()._repo_rel(Path(path))


def _write_json(path: Path, payload: Any) -> None:
    _base()._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    _base()._write_text(path, text)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    with TICKET_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _operating_efficiency_context(
    row: dict[str, Any],
    balance_sheet_index: accepted.CompanyfactsBalanceSheetIndex,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
    balance = balance_sheet_index.current_context(ticker, signal_date)
    operating_income = _float(row.get("operating_income_current_value"))
    assets = _float(balance.get("assets_current_value"))
    ratio = None
    if operating_income is not None and assets is not None and assets > 0.0:
        ratio = operating_income / assets
    passed = ratio is not None and ratio >= OPERATING_INCOME_ASSETS_MIN
    return {
        **balance,
        "operating_efficiency_assets_rule_version": RULE_VERSION,
        "operating_efficiency_assets_known_at": (
            "SEC Companyfacts operating_income and assets filed date <= signal_date"
        ),
        "operating_efficiency_assets_trade_enabled": False,
        "operating_efficiency_assets_alters_orders": False,
        "operating_efficiency_assets_min": OPERATING_INCOME_ASSETS_MIN,
        "operating_efficiency_operating_income": _round(operating_income, 6),
        "operating_efficiency_assets_value": _round(assets, 6),
        "operating_income_assets_ratio": _round(ratio, 6),
        "operating_efficiency_assets_pass_v1": passed,
    }


def _select_operating_efficiency_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    label = accepted._governor()._window_label_for_candidates(candidates)
    balance_sheet_index = accepted._balance_sheet_index_for_candidates(candidates)
    kept: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    context_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    date_counts: dict[str, Counter[str]] = {}
    audit: Counter[str] = Counter()
    ratio_buckets: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for row in candidates:
        signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        context = _operating_efficiency_context(row, balance_sheet_index)
        context_by_key[(signal_date, ticker)] = context
        bucket = date_counts.setdefault(signal_date, Counter())
        bucket["total"] += 1
        status_counts[str(context.get("balance_sheet_status") or "unknown")] += 1
        ratio_buckets[_ratio_bucket(context.get("operating_income_assets_ratio"))] += 1
        if context["operating_efficiency_assets_pass_v1"]:
            audit["operating_efficiency_passed_candidates"] += 1
            bucket["operating_efficiency_passed"] += 1
            kept.append({**row, **context})
        else:
            reason = (
                "missing_operating_income_assets_ratio"
                if context.get("operating_income_assets_ratio") is None
                else "operating_income_assets_below_min"
            )
            audit[reason] += 1
            filtered.append({**row, **context, "filter_reason": reason})

    if kept:
        selected, downstream_filtered = accepted._select_low_liability_supported_paper_trades(
            snapshot,
            kept,
        )
    else:
        selected, downstream_filtered = [], []

    selected_with_context: list[dict[str, Any]] = []
    for trade in selected:
        key = (
            str(trade.get("date") or trade.get("signal_date") or "")[:10],
            str(trade.get("ticker") or "").upper(),
        )
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
        first_by_date.setdefault(str(row.get("date") or "")[:10], row)
    replacement_days = 0
    no_efficiency_candidate_days = 0
    for signal_date, counts in date_counts.items():
        first = first_by_date.get(signal_date) or {}
        first_key = (signal_date, str(first.get("ticker") or "").upper())
        first_passed = bool(
            context_by_key.get(first_key, {}).get("operating_efficiency_assets_pass_v1")
        )
        if counts.get("operating_efficiency_passed", 0) <= 0:
            no_efficiency_candidate_days += 1
        elif not first_passed:
            replacement_days += 1

    selected_tickers = Counter(str(row.get("ticker") or "").upper() for row in selected_with_context)
    OPERATING_EFFICIENCY_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "operating_income_assets_min": OPERATING_INCOME_ASSETS_MIN,
        "input_candidates": len(candidates),
        "operating_efficiency_passed_candidates": len(kept),
        "operating_efficiency_filtered_candidates": len(filtered),
        "operating_efficiency_candidate_days": sum(
            1 for counts in date_counts.values() if counts.get("operating_efficiency_passed", 0) > 0
        ),
        "no_operating_efficiency_candidate_days": no_efficiency_candidate_days,
        "replacement_day_count": replacement_days,
        "selected_trades": len(selected_with_context),
        "downstream_filtered_candidates": len(downstream_filtered),
        "selected_unique_tickers": len(selected_tickers),
        "selected_ticker_counts": dict(sorted(selected_tickers.items())),
        "ratio_bucket_counts": dict(sorted(ratio_buckets.items())),
        "balance_sheet_status_counts": dict(sorted(status_counts.items())),
        **dict(sorted(audit.items())),
    }
    return selected_with_context, filtered + downstream_filtered


def _ratio_bucket(value: Any) -> str:
    ratio = _float(value)
    if ratio is None:
        return "missing"
    if ratio < 0.0:
        return "negative"
    if ratio < 0.005:
        return "low_0_0p005"
    if ratio < OPERATING_INCOME_ASSETS_MIN:
        return "mid_below_min"
    if ratio < 0.035:
        return "pass_0p015_0p035"
    if ratio < 0.065:
        return "strong_0p035_0p065"
    return "elite_gte_0p065"


def _configure_modules() -> None:
    base_exp.EXPERIMENT_ID = EXPERIMENT_ID
    base_exp.STEM = STEM
    base_exp.TRIAL_FAMILY = TRIAL_FAMILY
    base_exp.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base_exp.CHANGED_VARIABLE = CHANGED_VARIABLE
    base_exp.RULE_VERSION = RULE_VERSION
    base_exp.OUT_DIR = OUT_DIR
    base_exp.OUT_JSON = OUT_JSON
    base_exp.LOG_JSON = LOG_JSON
    base_exp.TICKET_JSON = TICKET_JSON
    base_exp.DOC_TICKET_JSON = TICKET_JSON
    base_exp.CARD_MD = CARD_MD
    base_exp.ARTIFACT_MD = CARD_MD
    base_exp.MANIFEST_JSON = MANIFEST_JSON
    base_exp.EXPERIMENT_LOG = EXPERIMENT_LOG
    base_exp.REGISTRY_JSON = REGISTRY_JSON
    base_exp.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base_exp.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base_exp.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base_exp.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base_exp.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base_exp.PREDICTION = PREDICTION
    base_exp.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base_exp.QUALITY_SELECTION_AUDIT = OPERATING_EFFICIENCY_AUDIT
    OPERATING_EFFICIENCY_AUDIT.clear()
    base_exp._configure_modules()
    _base()._select_paper_trades = _select_operating_efficiency_paper_trades


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = base_exp._update_payload(payload)
    numeric_gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "positive_replay_lead_not_promoted_operating_efficiency_assets_selector"
        if numeric_gate4_passed
        else "rejected_operating_efficiency_assets_candidate_pool"
    )
    status = "positive_replay_lead_not_promoted" if numeric_gate4_passed else "rejected"
    aggregate = payload["delta_metrics"]["aggregate"]
    completed_at = _utc_now()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": completed_at,
            "completed_at": completed_at,
            "lane": "alpha_search",
            "status": status,
            "accepted": False,
            "accepted_alpha": False,
            "decision": decision,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_selection_scout",
            "mechanism_family": "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "prior_trial_count": 18,
            "nearby_prior_experiments": [
                "exp-20260528-004",
                "exp-20260528-006",
                "exp-20260528-012",
                "exp-20260528-017",
                "exp-20260609-006",
                "exp-20260610-019",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "production_visible_sec_companyfacts_operating_efficiency_field",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "gate_questions": PRE_RUN_QUESTIONS,
            "operating_efficiency_audit": OPERATING_EFFICIENCY_AUDIT,
            "quality_selection_audit": OPERATING_EFFICIENCY_AUDIT,
            "anti_js": "No JavaScript was used.",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        }
    )
    payload["gate4"]["decision"] = decision
    payload["gate4"]["numeric_gate4_passed"] = numeric_gate4_passed
    payload["parameters"]["operating_efficiency_assets_selector"] = {
        "operating_income_assets_min": OPERATING_INCOME_ASSETS_MIN,
        "canonical_operating_income": "operating_income",
        "canonical_assets": "assets",
        "selection_order": (
            "prefilter candidate rows by operating_income/assets, then reuse the "
            "existing Fundamental Growth RS score order and daily top-1 selector"
        ),
        "uses_future_data": False,
        "production_visible_fields": [
            "SEC Companyfacts operating_income filed date <= signal_date",
            "SEC Companyfacts assets filed date <= signal_date",
            "signal-date and trailing OHLCV rows",
        ],
    }
    payload["parameters"]["locked_variables"] = [
        "all exp-20260528-017 low-liability scalar semantics",
        "all exp-20260528-016 filing-recency scalar semantics",
        "all exp-20260528-015 low-volume participation logic",
        "all exp-20260528-008 closed-ledger governor logic",
        "all exp-20260528-004 positive operating-profit quality logic",
        "all exp-20260527-017 Companyfacts growth thresholds",
        "all exp-20260527-017 RS proxy thresholds",
        "paper notional base",
        "10-trading-day paper hold",
        "core signal generation/ranking/sizing/exits",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
    ]
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "operating_income_current_value with filed <= signal_date",
        "assets_current_value with filed <= signal_date",
        "operating_income/assets efficiency ratio",
    ]
    payload["gate2"]["note"] = (
        "The selector uses only SEC Companyfacts rows with filed dates <= signal_date "
        "plus signal-date/trailing OHLCV. Paper entry remains next open and the "
        "closed-ledger governor uses only rows with exit_date < entry_date."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No live or core filter was added. The stricter selector changes only a "
        "private default-off paper candidate pool, so core survival is unchanged."
    )
    if numeric_gate4_passed:
        interpretation = (
            "The operating-efficiency selector beat the accepted low-liability "
            "Companyfacts comparator as a replay lead, but no production/shared "
            "path changed."
        )
        why = (
            "The ratio isolated capital-efficient growth rows that retained "
            "next-open 10d replacement value after the accepted Companyfacts "
            "scalars. It still needs shared daily parity before retention."
        )
    else:
        interpretation = (
            "The operating-efficiency selector did not clear Gate 4. The likely "
            "mechanism is that operating income/assets is useful context but too "
            "blunt as a hard replacement selector inside the accepted Companyfacts "
            "source."
        )
        why = (
            "The selector likely rejected high-ranked winners, starved one or more "
            "standard windows, or failed to beat the accepted low-liability stack "
            "after next-open execution, costs, and concentration controls."
        )
    payload["interpretation"] = interpretation
    payload["negative_reflection"] = None if numeric_gate4_passed else interpretation
    payload["rejection_reason"] = None if numeric_gate4_passed else "; ".join(
        payload["gate4"].get("failed_reasons")
        or payload["gate4"].get("accepted_low_liability_failed_checks")
        or []
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why,
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping operating_income/assets threshold, "
            "operating-margin threshold, top-N, hold-day, paper notional, "
            "filing-age, liabilities/assets, or RS thresholds on the same windows."
        ),
        "new_evidence_required": (
            "A retry needs forward closed replacement-value rows or a materially "
            "different PIT source-quality field outside profitability, balance "
            "sheet leverage, gross margin, cash conversion, and basic growth/RS."
        ),
    }
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Efficient candidates | Replacement days |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["operating_efficiency_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | {efficient} | {replacement} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                efficient=audit.get("operating_efficiency_passed_candidates"),
                replacement=audit.get("replacement_day_count"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    target = payload["target_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Fundamental Growth RS Operating Efficiency",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}`",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}`",
            f"- target trades: `{aggregate['target_trade_count_sum']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": bool(payload["gate4"].get("numeric_gate4_passed")),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    base_exp.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )

    ticket = _load_ticket()
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["completed_at"],
            "updated_at": payload["completed_at"],
            "decision": payload["decision"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    _write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": {
            _repo_rel(path): _sha256(path)
            for path in paths
            if path.exists()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _base()._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_ticket_and_registry(payload)
    _write_manifest(payload)


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
                    "operating_efficiency_audit": payload["operating_efficiency_audit"],
                    "artifact": _repo_rel(OUT_JSON),
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
