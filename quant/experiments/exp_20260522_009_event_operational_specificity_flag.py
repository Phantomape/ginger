"""exp-20260522-009: SEC operational-specificity event scout.

Alpha search. Tests one SEC text disclosure-quality allocation variable on
top of the accepted exp-20260522-007 default-off event overlay adapter:
whether event rows whose archived filing text contains concrete operating or
financial specificity deserve a modest paper-notional scalar.

No JavaScript is used. Live/default orders remain disabled.
"""

from __future__ import annotations

import json
import math
import re
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260522_007_event_governance_503_haircut as exp007
from sec_event_queue import load_sec_filing_text_rows, semantic_text


EXPERIMENT_ID = "exp-20260522-009"
EXPERIMENT_SLUG = "event_operational_specificity_flag"

REPO_ROOT = exp007.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
TEXT_ARCHIVE = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"

BASELINE_VARIANT = "accepted_event_governance_503_haircut_adapter"
MIN_SPECIFICITY_CATEGORIES = 2
MAX_DRAWDOWN_DRIFT = 0.0200
MAX_TARGET_POSITIVE_PNL_SHARE = 0.45

SPECIFICITY_PATTERNS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    [
        (
            "quantified_financial",
            (
                r"\$\s?\d",
                r"\b\d+(?:\.\d+)?\s?%",
                r"\b(?:revenue|sales|eps|ebitda|margin|cash flow)\b.{0,80}\b\d",
            ),
        ),
        (
            "forward_commitment",
            (
                r"\bguidance\b",
                r"\boutlook\b",
                r"\bexpects?\b",
                r"\bforecast\b",
                r"\breaffirms?\b",
                r"\braises?\b",
                r"\blowers?\b",
            ),
        ),
        (
            "commercial_activity",
            (
                r"\bcontract(?:s|ed|ing)?\b",
                r"\bagreement(?:s)?\b",
                r"\border(?:s)?\b",
                r"\bbacklog\b",
                r"\bcustomer(?:s)?\b",
                r"\baward(?:ed|s)?\b",
            ),
        ),
        (
            "operational_milestone",
            (
                r"\bshipment(?:s)?\b",
                r"\bproduction\b",
                r"\blaunch(?:ed|es)?\b",
                r"\bapproval\b",
                r"\btrial\b",
                r"\bmilestone(?:s)?\b",
                r"\bdeliver(?:y|ies|ed)?\b",
            ),
        ),
    ]
)

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260522-007 event adapter.",
                "operational_specificity_scalar": 1.00,
            },
        ),
        (
            "operational_specificity_105",
            {
                "description": "1.05x paper notional for operational-specificity SEC rows.",
                "operational_specificity_scalar": 1.05,
            },
        ),
        (
            "operational_specificity_110",
            {
                "description": "1.10x paper notional for operational-specificity SEC rows.",
                "operational_specificity_scalar": 1.10,
            },
        ),
        (
            "operational_specificity_115",
            {
                "description": "1.15x paper notional for operational-specificity SEC rows.",
                "operational_specificity_scalar": 1.15,
            },
        ),
        (
            "operational_specificity_120",
            {
                "description": "1.20x paper notional for operational-specificity SEC rows.",
                "operational_specificity_scalar": 1.20,
            },
        ),
    ]
)


def _parent():
    return exp007._parent()


def _configure_modules() -> None:
    exp007._configure_modules()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _accepted_event_scalar_after_exp007(trade: dict[str, Any]) -> float:
    scalar = _safe_float(exp007.base._accepted_event_scalar_after_exp013(trade), 1.0)
    if exp007._is_target_governance_503(trade):
        scalar *= 0.25
    return scalar


def _text_rows_by_accession() -> dict[str, dict[str, Any]]:
    rows = load_sec_filing_text_rows(TEXT_ARCHIVE)
    return {
        str(row.get("accession_number")): row
        for row in rows
        if row.get("accession_number")
    }


def _specificity_hits(text: str) -> dict[str, int]:
    hits: dict[str, int] = {}
    lowered = text.lower()
    for category, patterns in SPECIFICITY_PATTERNS.items():
        count = sum(len(re.findall(pattern, lowered)) for pattern in patterns)
        if count:
            hits[category] = count
    return hits


def _specificity_metadata(
    trade: dict[str, Any],
    text_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    accession = str(trade.get("accession_number") or "")
    text_row = text_by_accession.get(accession)
    if not text_row:
        return {
            "text_join_available": False,
            "operational_specificity_flag": False,
            "operational_specificity_categories": [],
            "operational_specificity_category_count": 0,
            "operational_specificity_hit_count": 0,
            "text_word_count": None,
        }
    text = semantic_text(text_row)
    hits = _specificity_hits(text)
    categories = sorted(hits)
    return {
        "text_join_available": True,
        "operational_specificity_flag": len(categories) >= MIN_SPECIFICITY_CATEGORIES,
        "operational_specificity_categories": categories,
        "operational_specificity_category_count": len(categories),
        "operational_specificity_hit_count": sum(hits.values()),
        "operational_specificity_hits": hits,
        "text_word_count": text_row.get("text_word_count"),
    }


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
    text_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar_after_exp007(trade)
    metadata = _specificity_metadata(trade, text_by_accession)
    specificity_scalar = (
        float(variant["operational_specificity_scalar"])
        if metadata["operational_specificity_flag"]
        else 1.0
    )
    scalar = accepted_scalar * specificity_scalar
    base_notional = _safe_float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = _safe_float(trade.get("shares"))
    return {
        **trade,
        **metadata,
        "variant": variant_name,
        "accepted_event_scalar_after_exp007": round(accepted_scalar, 4),
        "operational_specificity_scalar": round(specificity_scalar, 4),
        "state_surface_scalar": round(scalar, 4),
        "event_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(_safe_float(trade.get("pnl")) * scalar, 2),
    }


def _max_positive_share(rows: list[dict[str, Any]]) -> float | None:
    positives = [
        _safe_float(row.get("pnl"))
        for row in rows
        if _safe_float(row.get("pnl")) > 0.0
    ]
    total = sum(positives)
    if total <= 0.0:
        return None
    return round(max(positives) / total, 4)


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    text_rows = [row for row in all_rows if row.get("text_join_available")]
    targets = [row for row in all_rows if row.get("operational_specificity_flag")]
    for label, rows in rows_by_window.items():
        window_text_rows = [row for row in rows if row.get("text_join_available")]
        window_targets = [
            row for row in rows if row.get("operational_specificity_flag")
        ]
        target_by_window[label] = {
            "text_join_count": len(window_text_rows),
            "trade_count": len(window_targets),
            "wins": sum(1 for row in window_targets if _safe_float(row.get("pnl")) > 0),
            "total_pnl": round(
                sum(_safe_float(row.get("pnl")) for row in window_targets),
                2,
            ),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_targets}),
            "sources": sorted({str(row.get("source") or "") for row in window_targets}),
            "hit_categories": sorted(
                {
                    hit
                    for row in window_targets
                    for hit in row.get("operational_specificity_categories") or []
                }
            ),
        }
    wins = sum(1 for row in targets if _safe_float(row.get("pnl")) > 0)
    source_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    for row in targets:
        source_counts[str(row.get("source") or "")] += 1
        for category in row.get("operational_specificity_categories") or []:
            category_counts[str(category)] += 1
    return {
        "target_field": "operational_specificity_flag",
        "target_rule": (
            f"text_join_available AND at least {MIN_SPECIFICITY_CATEGORIES} "
            "specificity categories are present"
        ),
        "specificity_patterns": {
            category: list(patterns)
            for category, patterns in SPECIFICITY_PATTERNS.items()
        },
        "all_event_trade_count": len(all_rows),
        "text_join_count": len(text_rows),
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted(source_counts.items()),
        "target_category_counts": sorted(category_counts.items()),
        "target_wins": wins,
        "target_win_rate": round(wins / len(targets), 4) if targets else None,
        "target_scaled_total_pnl": round(
            sum(_safe_float(row.get("pnl")) for row in targets),
            2,
        ),
        "target_max_single_positive_pnl_share": _max_positive_share(targets),
        "target_by_window": target_by_window,
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    gate = _parent().base._gate_summary(baseline_metrics, after_metrics)
    max_drawdown_drift = max(
        (
            _safe_float(after_metrics[label].get("max_drawdown_pct"))
            - _safe_float(baseline_metrics[label].get("max_drawdown_pct"))
        )
        for label in baseline_metrics
    )
    sample_ok = (
        (selection.get("target_trade_count") or 0) >= 10
        and (selection.get("target_windows_present") or 0) >= 3
        and len(selection.get("target_tickers") or []) >= 6
        and (selection.get("target_win_rate") or 0.0) >= 0.55
        and (selection.get("target_scaled_total_pnl") or 0.0) > 0.0
        and (
            selection.get("target_max_single_positive_pnl_share") is None
            or selection["target_max_single_positive_pnl_share"]
            <= MAX_TARGET_POSITIVE_PNL_SHARE
        )
    )
    risk_ok = max_drawdown_drift <= MAX_DRAWDOWN_DRIFT
    return {
        **gate,
        "sample_guard_passed": bool(sample_ok),
        "risk_guard_passed": bool(risk_ok),
        "max_drawdown_drift_limit": MAX_DRAWDOWN_DRIFT,
        "max_window_drawdown_drift": round(max_drawdown_drift, 6),
        "passed": bool(gate["passed"] and sample_ok and risk_ok),
        "sample_guard": {
            "min_target_trades": 10,
            "min_target_windows": 3,
            "min_target_tickers": 6,
            "min_target_win_rate": 0.55,
            "requires_positive_baseline_target_pnl": True,
            "max_target_positive_pnl_share": MAX_TARGET_POSITIVE_PNL_SHARE,
            "actual_target_trades": selection.get("target_trade_count"),
            "actual_target_windows": selection.get("target_windows_present"),
            "actual_target_tickers": selection.get("target_tickers"),
            "actual_target_win_rate": selection.get("target_win_rate"),
            "actual_target_scaled_total_pnl": selection.get(
                "target_scaled_total_pnl"
            ),
            "actual_target_max_single_positive_pnl_share": selection.get(
                "target_max_single_positive_pnl_share"
            ),
        },
    }


def _choose_best(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in VARIANTS if name != BASELINE_VARIANT]
    passed = [name for name in names if gates[name]["passed"]]
    candidates = passed if passed else names
    return max(
        candidates,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
            -abs(VARIANTS[name]["operational_specificity_scalar"] - 1.0),
        ),
    )


def _compact_metrics_by_window(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
        "worst_trade_pct",
        "max_consecutive_losses",
        "tail_loss_share",
    ]
    return OrderedDict(
        (
            label,
            {field: metrics.get(field) for field in fields if field in metrics},
        )
        for label, metrics in rows.items()
    )


def _compact_variant_gates(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return OrderedDict(
        (
            name,
            {
                "passed": gate["passed"],
                "sample_guard_passed": gate["sample_guard_passed"],
                "risk_guard_passed": gate["risk_guard_passed"],
                "max_window_drawdown_drift": gate["max_window_drawdown_drift"],
                "aggregate_ev_delta": gate["delta"]["aggregate_ev_delta"],
                "aggregate_pnl_delta": gate["delta"]["aggregate_pnl_delta"],
                "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                "after_ev_sum": gate["delta"]["after_ev_sum"],
                "baseline_ev_sum": gate["delta"]["baseline_ev_sum"],
            },
        )
        for name, gate in rows.items()
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    operator_check = exp007.base.exp010._operator_position_field_check()
    text_by_accession = _text_rows_by_accession()
    raw_event_trades, source_coverage, prices = parent.base._load_event_trades()
    event_trades = parent.base._enrich_event_trades(raw_event_trades)
    core_results = {
        label: parent.base._load_core_result(window)
        for label, window in parent.base.WINDOWS.items()
    }
    core_metrics = OrderedDict(
        (label, parent.base._core_metrics(result))
        for label, result in core_results.items()
    )

    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    for label, window in parent.base.WINDOWS.items():
        for name, variant in VARIANTS.items():
            scaled = [
                _scaled_trade(trade, name, variant, text_by_accession)
                for trade in event_trades[label]
            ]
            curve = parent.base._event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = parent.base._combined_metrics(
                core_results[label],
                curve,
                scaled,
            )
            variant_events[name][label] = scaled

    baseline_metrics = variant_metrics[BASELINE_VARIANT]
    selection_by_variant = OrderedDict(
        (name, _selection_summary(variant_events[name])) for name in VARIANTS
    )
    gates_vs_baseline = OrderedDict(
        (
            name,
            _gate_vs_baseline(
                baseline_metrics,
                variant_metrics[name],
                selection_by_variant[BASELINE_VARIANT],
            ),
        )
        for name in VARIANTS
        if name != BASELINE_VARIANT
    )
    best_variant = _choose_best(gates_vs_baseline)
    best_gate = gates_vs_baseline[best_variant]
    accepted = bool(best_gate["passed"])
    decision = (
        "accepted_replay_evidence_requires_shared_text_field"
        if accepted
        else "rejected_event_operational_specificity_flag"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` changed aggregate EV by "
            f"{best_gate['delta']['aggregate_ev_delta']} and PnL by "
            f"{best_gate['delta']['aggregate_pnl_delta']}, but Gate 4 failed: "
            f"EV improved/regressed windows "
            f"{best_gate['delta']['windows_ev_improved']}/"
            f"{best_gate['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={best_gate['sample_guard_passed']}, "
            f"risk_guard_passed={best_gate['risk_guard_passed']}."
        )

    compact_after_metrics = OrderedDict(
        (name, _compact_metrics_by_window(metrics))
        for name, metrics in variant_metrics.items()
    )
    compact_parameters = {
        "acceptance_baseline": BASELINE_VARIANT,
        "baseline_experiment": "exp-20260522-007",
        "target_field": "operational_specificity_flag",
        "target_rule": selection_by_variant[BASELINE_VARIANT]["target_rule"],
        "text_archive": _repo_rel(TEXT_ARCHIVE),
        "min_specificity_categories": MIN_SPECIFICITY_CATEGORIES,
        "specificity_patterns": {
            category: list(patterns)
            for category, patterns in SPECIFICITY_PATTERNS.items()
        },
        "selected_operational_specificity_scalar": VARIANTS[best_variant][
            "operational_specificity_scalar"
        ],
        "variant_scalars": {
            name: row["operational_specificity_scalar"]
            for name, row in VARIANTS.items()
        },
        "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
        "hold_days": parent.base.HOLD_DAYS,
        "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
        "sample_guard": best_gate["sample_guard"],
        "risk_guard": {"max_window_drawdown_drift": MAX_DRAWDOWN_DRIFT},
        "locked_variables": [
            "core universe",
            "core signal generation",
            "core candidate ranking",
            "core position sizing",
            "core exits",
            "event source definitions",
            "event source capacity",
            "event source thresholds",
            "event holding period",
            "front-rank rotation event scalar",
            "broad-breadth event scalar",
            "governance-source quality scalar",
            "negative-reaction context scalar",
            "positive-state context scalar",
            "non-narrow state-bucket context scalar",
            "governance 5.03 haircut scalar",
            "LLM prompt and replay",
            "news veto",
            "production orders",
        ],
        "anti_js": "No JavaScript was used.",
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "notes": (
            "No strategy behavior was changed in this experiment. Any positive "
            "result must first be promoted through a shared SEC text-derived "
            "candidate field and default-off event_sleeve_bundle adapter before "
            "it can affect production paper accounting."
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_disclosure_quality_allocation_scout",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_operational_specificity_disclosure_quality",
        "trial_variant_id": "operational_specificity_notional_scalar",
        "changed_variable": "event_operational_specificity_scalar",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260521-016",
            "exp-20260521-019",
            "exp-20260522-007",
            "exp-20260522-008",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_historical_sec_text_specificity_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, SEC event rows whose "
            "archived filing text contains concrete operating or financial "
            "specificity may have higher replacement value than generic event "
            "rows. A single paper-notional scalar tests that disclosure-quality "
            "field without touching core entries, exits, ranking, or source "
            "capacity."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event disclosure-quality scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses the playbook's SEC/event disclosure-quality lane while "
                "avoiding blocked LLM soft-ranking, adjacent 5.03 retunes, "
                "core-overlap retunes, broad-market identity drift, and "
                "state-surface same-family scalar tuning."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed accepted event rows whose historical "
            "SEC filing text joins by accession_number and matches the fixed "
            "operational_specificity_flag; all existing event scalars, event "
            "definitions, source capacity, holding period, and core strategy "
            "behavior stay fixed"
        ),
        "parameters": compact_parameters,
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in parent.base.WINDOWS.items()
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Capital allocation / event disclosure quality: boost fixed "
                "event rows with concrete operating or financial specificity."
            ),
            "2_history_check": (
                "Special-call and attention-persistence SEC text lanes were "
                "nearby but different fields; 5.03 and core-overlap work should "
                "not be retuned on this frozen sample."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for the fixed "
                "operational_specificity_flag cohort changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260522-007 event adapter baseline, require "
                "aggregate EV/PnL improvement, no EV-regressed window, sample "
                "guard pass, risk guard pass, and no production/backtest "
                "divergence before any promotion."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260522_009_event_operational_specificity_flag.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260521-016": (
                "Special-call flag was rejected because one window regressed; "
                "this run uses a broader operating/financial specificity field, "
                "not another special-call phrase scalar."
            ),
            "exp-20260522-007": (
                "Governance item 5.03 haircut was accepted and is included in "
                "the baseline, so this run does not retune item-code scalars."
            ),
            "exp-20260522-008": (
                "Core independence replay was rejected for risk/concentration; "
                "this run does not use core-overlap context."
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": exp007.base.exp010._compact_windows(parent.base.WINDOWS),
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "event_overlay": "default_off_paper_replay",
            },
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_artifact": (
                "data/experiments/exp-20260522-007/"
                "event_governance_503_haircut.json"
            ),
        },
        "gate2": {
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "accession_number",
                "SEC semantic_text archive row",
                "reaction_bucket",
                "eight_k_item_codes",
            ],
            "operator_position_field_check": operator_check,
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(
                operator_check["passed"]
                and selection_by_variant[BASELINE_VARIANT]["text_join_count"] > 0
                and selection_by_variant[BASELINE_VARIANT]["target_trade_count"] > 0
            ),
        },
        "gate3": {
            "survival_rate_by_window": {
                label: metrics.get("survival_rate")
                for label, metrics in baseline_metrics.items()
            },
            "signals_generated": {
                label: metrics.get("signals_generated")
                for label, metrics in baseline_metrics.items()
                if "signals_generated" in metrics
            },
            "signals_survived": {
                label: metrics.get("signals_survived")
                for label, metrics in baseline_metrics.items()
                if "signals_survived" in metrics
            },
            "filter_added": False,
            "passed": True,
        },
        "gate4": best_gate,
        "variant_gates": _compact_variant_gates(gates_vs_baseline),
        "baseline_metrics": _compact_metrics_by_window(baseline_metrics),
        "after_metrics": compact_after_metrics[best_variant],
        "all_variant_metrics": compact_after_metrics,
        "baseline_selection": selection_by_variant[BASELINE_VARIANT],
        "best_variant": best_variant,
        "best_variant_parameters": VARIANTS[best_variant],
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If a future forward row set supports this field, first make the "
            "operational_specificity_flag a shared sec_event_queue payload field "
            "and add an event_sleeve_bundle parity test before promotion."
        ),
        "production_impact": production_impact,
        "why_not_other_changes": (
            "LLM soft-ranking has sparse attribution, broad-market candidate "
            "expansion still has identity-drift/PIT limits, state-surface scalar "
            "work is in a high multiple-testing bucket, and adjacent 5.03/core "
            "overlap retunes were just tested."
        ),
        "known_risks": [
            "SEC text archive is historical replay evidence; positive results "
            "need a shared production-visible payload field before behavior "
            "changes.",
            "Moderate multiple-testing risk remains because this is another SEC "
            "disclosure-quality field on the same frozen windows.",
            "Text regexes may capture generic boilerplate despite the two-category "
            "specificity guard.",
        ],
        "source_coverage": {
            "sec_negative_price_ready_candidates": source_coverage.get(
                "sec_negative_price_ready_candidates"
            ),
            "form4_price_ready_candidates": source_coverage.get(
                "form4_price_ready_candidates"
            ),
            "source_skipped_counts": source_coverage.get("source_skipped_counts"),
        },
        "decision_summary": (
            "Accepted as replay evidence only; not promoted without shared field."
            if accepted
            else "Rejected: operational_specificity_flag scalar did not clear Gate 4."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_SLUG}",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Trial accounting",
        "```json",
        json.dumps(
            {
                "trial_family": payload["trial_family"],
                "changed_variable": payload["changed_variable"],
                "prior_trial_count": payload["prior_trial_count"],
                "nearby_prior_experiments": payload["nearby_prior_experiments"],
                "multiple_testing_risk_bucket": payload[
                    "multiple_testing_risk_bucket"
                ],
                "new_evidence_type": payload["new_evidence_type"],
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## Best variant",
        f"- variant: `{payload['best_variant']}`",
        f"- scalar: `{payload['best_variant_parameters']['operational_specificity_scalar']}`",
        f"- aggregate EV delta: `{payload['expected_value_score_delta']}`",
        f"- aggregate PnL delta: `{payload['total_pnl_delta']}`",
        f"- decision: `{payload['decision']}`",
        "",
        "## Gate 4",
        "```json",
        json.dumps(gate, indent=2, sort_keys=True),
        "```",
        "",
        "## Production impact",
        "```json",
        json.dumps(payload["production_impact"], indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def _upsert_experiment_log(record: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = [
            line
            for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines()
            if line.strip()
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
            and f'"id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(record, sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_payload(payload: dict[str, Any]) -> None:
    for path in (OUT_JSON, LOG_JSON, TICKET_JSON, ARTIFACT_MD):
        path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "experiment_id",
                    "timestamp",
                    "lane",
                    "decision",
                    "hypothesis",
                    "trial_family",
                    "changed_variable",
                    "prior_trial_count",
                    "multiple_testing_risk_bucket",
                    "new_evidence_type",
                    "backtest_protocol",
                    "gate1",
                    "gate2",
                    "gate3",
                    "gate4",
                    "expected_value_score_delta",
                    "total_pnl_delta",
                    "production_impact",
                    "known_risks",
                    "decision_summary",
                )
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_experiment_log(
        {
            "experiment_id": payload["experiment_id"],
            "timestamp": payload["timestamp"],
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "trial_family": payload["trial_family"],
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "parameters": payload["parameters"],
            "date_range": payload["date_range"],
            "backtest_protocol": payload["backtest_protocol"],
            "before_metrics": payload["baseline_metrics"],
            "after_metrics": payload["after_metrics"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "decision": payload["decision"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "production_impact": payload["production_impact"],
        }
    )


def main() -> None:
    payload = build_payload()
    write_payload(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
