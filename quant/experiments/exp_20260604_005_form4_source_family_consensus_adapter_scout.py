"""exp-20260604-005: Form 4 source-family consensus scout.

Replay-only alpha search. The accepted independent-source free-data consensus
candidate source is fixed, then PIT-safe SEC Form 4 forward-queue meaningful
purchase events are added as one new independent source family. This tests
whether insider purchase confirmation improves the accepted consensus adapter
without adding standalone noisy tickers.

No production code, live orders, ranking, sizing, exits, LLM, news, watchlists,
source thresholds, hold period, or candidate admission policy is changed. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260603_014_accepted_consensus_independent_source_family as consensus  # noqa: E402
from form4_event_queue import (  # noqa: E402
    QUEUE_NAME as FORM4_QUEUE_NAME,
    RULE_VERSION as FORM4_RULE_VERSION,
    aggregate_purchase_events,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXPERIMENT_ID = "exp-20260604-005"
STEM = "form4_source_family_consensus_adapter_scout"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
CHANGED_VARIABLE = "form4_meaningful_purchase_source_family_added_to_accepted_consensus_v1"
RULE_VERSION = CHANGED_VARIABLE
FORM4_SOURCE_NAME = "FORM4_MEANINGFUL_PURCHASE_PAPER"
FORM4_SOURCE_FAMILY = "form4_insider_purchase"
FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID = "exp-20260603-014"
CURRENT_ACCEPTED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID
    / "accepted_consensus_independent_source_family.json"
)

SOURCE_FAMILIES = {
    **consensus.SOURCE_FAMILIES,
    FORM4_SOURCE_NAME: FORM4_SOURCE_FAMILY,
}
SOURCE_EXPERIMENT_IDS = {
    **consensus.SOURCE_EXPERIMENT_IDS,
    FORM4_SOURCE_NAME: "quant/form4_event_queue.py",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained Form 4 source "
        "family would need the shared free-data consensus paper adapter to load "
        "the same PIT Form 4 forward queue in daily production and historical "
        "replay, plus parity tests, before any report queue, notional, candidate "
        "priority, or order surface could change."
    ),
}

PREDICTION = {
    "success_probability": 0.19,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1000.0,
    "main_failure_modes": [
        "no_same_day_overlap",
        "accepted_comparator_not_beaten",
        "window_regression",
        "form4_concentration",
        "production_adapter_parity_required",
    ],
    "confidence_reason": (
        "Meta research favors default-off adapters and recent playbook guidance "
        "favors new production-visible free-data sources. Raw Form 4 qualifiers "
        "were positive but not promotable; this tests Form 4 only as an "
        "independent confirmation source against the accepted consensus comparator."
    ),
    "recorded_at": "2026-06-04T04:10:28+00:00",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _window_label(value: str) -> str | None:
    for label, cfg in consensus.prior.base.WINDOWS.items():
        if cfg["start"] <= value <= cfg["end"]:
            return label
    return None


def _source_family(source_name: str) -> str:
    return SOURCE_FAMILIES.get(source_name, source_name)


def _form4_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not FORM4_TRANSACTIONS_PATH.exists():
        return {}, {
            "source_status": "missing_form4_transactions",
            "path": _repo_rel(FORM4_TRANSACTIONS_PATH),
        }

    transaction_rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    start = min(cfg["start"] for cfg in consensus.prior.base.WINDOWS.values())
    end = max(cfg["end"] for cfg in consensus.prior.base.WINDOWS.values())
    raw_events = aggregate_purchase_events(transaction_rows, start=start, end=end)
    forward_events = [event for event in raw_events if qualifies_forward_queue_event(event)]

    skipped_outside_window = 0
    for event in forward_events:
        signal_date = str(event.get("usable_trade_date") or "")[:10]
        ticker = str(event.get("ticker") or "").upper()
        label = _window_label(signal_date)
        if not signal_date or not ticker or label is None:
            skipped_outside_window += 1
            continue
        rows_by_window[label][(signal_date, ticker)].append(
            {
                "source_name": FORM4_SOURCE_NAME,
                "source_experiment_id": SOURCE_EXPERIMENT_IDS[FORM4_SOURCE_NAME],
                "date": signal_date,
                "ticker": ticker,
                "form4_queue_name": FORM4_QUEUE_NAME,
                "form4_rule_version": FORM4_RULE_VERSION,
                "form4_total_purchase_value": event.get("total_purchase_value"),
                "form4_max_purchase_value": event.get("max_purchase_value"),
                "form4_purchase_transaction_count": event.get("purchase_transaction_count"),
                "form4_owner_count": event.get("owner_count"),
                "form4_filing_count": event.get("filing_count"),
                "form4_any_ceo_cfo_or_president": event.get("any_ceo_cfo_or_president"),
                "form4_any_officer": event.get("any_officer"),
                "form4_any_director": event.get("any_director"),
                "form4_any_10pct_owner": event.get("any_10pct_owner"),
                "meaningful_purchase_v1": event.get("meaningful_purchase_v1"),
                "form4_forward_queue_candidate": event.get("form4_forward_queue_candidate"),
            }
        )

    by_window_counts = {
        label: sum(len(rows) for rows in date_ticker.values())
        for label, date_ticker in sorted(rows_by_window.items())
    }
    return rows_by_window, {
        "source_status": "loaded",
        "path": _repo_rel(FORM4_TRANSACTIONS_PATH),
        "transaction_rows": len(transaction_rows),
        "raw_meaningful_event_count": len(raw_events),
        "forward_queue_event_count": len(forward_events),
        "forward_queue_event_count_by_window": by_window_counts,
        "skipped_outside_window": skipped_outside_window,
        "source_name": FORM4_SOURCE_NAME,
        "source_family": FORM4_SOURCE_FAMILY,
        "form4_rule_version": FORM4_RULE_VERSION,
    }


def _merge_source_rows(
    base_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    form4_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    merged: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for source in (base_rows, form4_rows):
        for label, rows_by_key in source.items():
            for key, rows in rows_by_key.items():
                merged[label][key].extend(rows)
    return merged


def _consensus_candidates_for_window(
    label: str,
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for (signal_date, ticker), source_rows in source_rows_by_window.get(label, {}).items():
        source_names = sorted({str(row["source_name"]) for row in source_rows})
        source_families = sorted({_source_family(source_name) for source_name in source_names})
        if len(source_families) < consensus.MIN_SOURCE_FAMILY_COUNT:
            continue
        source_family_map: dict[str, list[str]] = {}
        for source_name in source_names:
            source_family_map.setdefault(_source_family(source_name), []).append(source_name)
        candidates.append(
            {
                "date": signal_date,
                "ticker": ticker,
                "source_count": len(source_names),
                "source_family_count": len(source_families),
                "source_names": source_names,
                "source_families": source_families,
                "source_family_map": {
                    family: sorted(names) for family, names in sorted(source_family_map.items())
                },
                "source_experiment_ids": {
                    source_name: SOURCE_EXPERIMENT_IDS[source_name]
                    for source_name in source_names
                },
                "source_rows": sorted(
                    source_rows,
                    key=lambda row: str(row.get("source_name") or ""),
                ),
                "fundamental_growth_rs_score": consensus.prior._extract_source_numeric(
                    source_rows,
                    "fundamental_growth_rs_score",
                ),
                "alpha_score": consensus.prior._extract_source_numeric(source_rows, "alpha_score"),
                "volume_breadth_breakout_score": consensus.prior._extract_source_numeric(
                    source_rows,
                    "volume_breadth_breakout_score",
                ),
                "finra_candidate_selection_score": consensus.prior._extract_source_numeric(
                    source_rows,
                    "candidate_selection_score",
                ),
                "form4_total_purchase_value": consensus.prior._extract_source_numeric(
                    source_rows,
                    "form4_total_purchase_value",
                ),
                "source_agreement_rule": (
                    "same_date_ticker_selected_by_at_least_two_independent_source_families_"
                    "including_optional_form4"
                ),
                "known_at": f"{signal_date}T21:00:00Z",
                "trade_enabled": False,
                "alters_orders": False,
                "rule_version": RULE_VERSION,
                "strategy": "paper_candidate_pool_default_off",
            }
        )
    return sorted(
        candidates,
        key=lambda row: (
            str(row["date"]),
            -int(row["source_family_count"]),
            -int(row["source_count"]),
            "+".join(row["source_families"]),
            "+".join(row["source_names"]),
            str(row["ticker"]),
        ),
    )


def _select_target_trades(
    snapshot: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected, diagnostics = consensus.prior._select_target_trades(snapshot, candidates)
    family_combos = Counter("+".join(trade.get("source_families") or []) for trade in selected)
    form4_selected = [
        trade for trade in selected if FORM4_SOURCE_NAME in (trade.get("source_names") or [])
    ]
    diagnostics["source_family_combo_counts_selected"] = dict(
        sorted(family_combos.items(), key=lambda item: (-item[1], item[0]))
    )
    diagnostics["form4_selected_trade_count"] = len(form4_selected)
    diagnostics["form4_selected_trade_dates"] = sorted(
        {str(trade.get("entry_date") or trade.get("date") or "")[:10] for trade in form4_selected}
    )
    diagnostics["form4_selected_tickers"] = sorted(
        {str(trade.get("ticker") or "").upper() for trade in form4_selected}
    )
    return selected, diagnostics


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in consensus.prior.base.WINDOWS.items():
        snapshot = consensus.prior.base.shadow._load_snapshot(cfg["snapshot"])
        candidates = _consensus_candidates_for_window(label, source_rows_by_window)
        target_trades, target_diagnostics = _select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = consensus.prior.base._overlay_from_paper_trades(before_result, target_trades)
        after = consensus.prior.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = consensus.prior.base.overlay_helper._delta(after, before)
        comparison = {
            "expected_value_score_delta": raw_delta["expected_value_score"],
            "strategy_total_pnl_delta": raw_delta["total_pnl"],
            "total_pnl_delta": raw_delta["total_pnl"],
            "max_drawdown_delta": raw_delta["max_drawdown_pct"],
            "raw_delta": raw_delta,
        }
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": before,
                "after": after,
                "comparison": comparison,
                "target_trade_count": len(target_trades),
                "target_trade_pnl_usd": round(
                    sum(_safe_float(row.get("pnl")) for row in target_trades),
                    2,
                ),
                "raw_consensus_candidate_count": len(candidates),
                "target_diagnostics": target_diagnostics,
            }
        )
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _target_summary(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary = consensus.prior._target_summary(trades_by_window)
    rows = [row for rows in trades_by_window.values() for row in rows]
    form4_rows = [row for row in rows if FORM4_SOURCE_NAME in (row.get("source_names") or [])]
    summary["form4_selected_trade_count"] = len(form4_rows)
    summary["form4_selected_trade_count_by_window"] = {
        label: sum(1 for row in trades if FORM4_SOURCE_NAME in (row.get("source_names") or []))
        for label, trades in trades_by_window.items()
    }
    summary["form4_selected_trade_pnl_usd"] = round(
        sum(_safe_float(row.get("pnl")) for row in form4_rows),
        2,
    )
    summary["form4_selected_tickers"] = sorted(
        {str(row.get("ticker") or "").upper() for row in form4_rows}
    )
    return summary


def _source_family_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
    *,
    raw_form4_candidate_counts: dict[str, int],
) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    family_combo_counts = Counter("+".join(trade.get("source_families") or []) for trade in all_trades)
    raw_combo_counts = Counter("+".join(trade.get("source_names") or []) for trade in all_trades)
    form4_rows = [
        trade for trade in all_trades if FORM4_SOURCE_NAME in (trade.get("source_names") or [])
    ]
    return {
        "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
        "source_families": SOURCE_FAMILIES,
        "selected_family_combo_counts": dict(sorted(family_combo_counts.items())),
        "selected_raw_source_combo_counts": dict(sorted(raw_combo_counts.items())),
        "form4_selected_trade_count": len(form4_rows),
        "form4_selected_trade_count_by_window": {
            label: sum(1 for row in trades if FORM4_SOURCE_NAME in (row.get("source_names") or []))
            for label, trades in target_trades_by_window.items()
        },
        "form4_raw_candidate_count_by_window": raw_form4_candidate_counts,
        "total_trade_count": len(all_trades),
        "all_selected_have_min_family_count": all(
            len(trade.get("source_families") or []) >= consensus.MIN_SOURCE_FAMILY_COUNT
            for trade in all_trades
        ),
    }


def _accepted_comparator_results(
    baselines: dict[str, dict[str, Any]],
    base_source_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    results, trades = consensus._run_windows(baselines, base_source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    return results, trades, aggregate


def _aggregate_after_vs_comparator(
    after_results: list[dict[str, Any]],
    comparator_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparator_by_label = {row["label"]: row for row in comparator_results}
    rows = []
    for row in after_results:
        comparator = comparator_by_label[row["label"]]
        delta = consensus.prior.base.overlay_helper._delta(row["after"], comparator["after"])
        rows.append(
            {
                "label": row["label"],
                "expected_value_score_delta": delta["expected_value_score"],
                "strategy_total_pnl_delta": delta["total_pnl"],
                "total_pnl_delta": delta["total_pnl"],
                "max_drawdown_delta": delta["max_drawdown_pct"],
            }
        )
    after_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in after_results)
    comparator_ev = sum(
        _safe_float(row["after"].get("expected_value_score")) for row in comparator_results
    )
    after_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in after_results)
    comparator_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in comparator_results)
    return {
        "after": {
            "expected_value_score": round(after_ev, 6),
            "strategy_total_pnl": round(after_pnl, 2),
            "total_pnl": round(after_pnl, 2),
        },
        "accepted_comparator_after": {
            "expected_value_score": round(comparator_ev, 6),
            "strategy_total_pnl": round(comparator_pnl, 2),
            "total_pnl": round(comparator_pnl, 2),
        },
        "comparison": {
            "expected_value_score_delta": round(after_ev - comparator_ev, 6),
            "strategy_total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "windows_ev_improved": sum(
                1 for row in rows if row["expected_value_score_delta"] > 0.0
            ),
            "windows_ev_regressed": sum(
                1 for row in rows if row["expected_value_score_delta"] < 0.0
            ),
            "windows_pnl_improved": sum(1 for row in rows if row["strategy_total_pnl_delta"] > 0.0),
            "windows_pnl_regressed": sum(1 for row in rows if row["strategy_total_pnl_delta"] < 0.0),
            "per_window": rows,
        },
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_comparator: dict[str, Any],
    source_family_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = consensus.prior._gate4_decision(aggregate, results, target_summary)
    comparator_delta = vs_comparator["comparison"]
    comparator_passed = (
        comparator_delta["expected_value_score_delta"] > 0.0
        and comparator_delta["strategy_total_pnl_delta"] > 0.0
        and comparator_delta["windows_ev_improved"] == 3
        and comparator_delta["windows_pnl_improved"] == 3
    )
    form4_trades = int(source_family_summary.get("form4_selected_trade_count") or 0)
    form4_sample_passed = form4_trades > 0
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_consensus_comparator": comparator_passed,
        "form4_selected_trade_count_positive": form4_sample_passed,
        "source_family_min_count_passed": source_family_summary["all_selected_have_min_family_count"],
    }
    passed = bool(base_gate["passed"] and comparator_passed and form4_sample_passed)
    if passed:
        decision = "positive_replay_lead_requires_shared_form4_consensus_adapter"
        rationale = (
            "Form 4 source-family consensus improved core and the current accepted "
            "consensus comparator in all three canonical windows. This is not "
            "promoted because the shared production/backtest adapter is not yet wired."
        )
    elif not form4_sample_passed:
        decision = "rejected_no_form4_consensus_selected_rows"
        rationale = (
            "Adding PIT-safe Form 4 as a source family produced no selected "
            "consensus paper trades, so it adds no alpha evidence."
        )
    elif not comparator_passed:
        decision = "rejected_form4_source_family_did_not_beat_accepted_consensus"
        rationale = (
            "The Form 4 source-family variant did not beat the current accepted "
            "independent-source consensus comparator across all three windows."
        )
    else:
        decision = "rejected_form4_source_family_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "PIT-safe SEC Form 4 meaningful purchases may improve the accepted "
            "free-data cross-source consensus when treated as a new independent "
            "source family, because insider buying can confirm existing candidates "
            "without adding standalone noisy tickers."
        ),
        "category": "entry/candidate_pool/default_off_paper_adapter",
        "playbook_alignment": (
            "Meta research ranks default-off paper adapters highest, and the "
            "playbook asks for materially new production-visible free-data sources "
            "rather than frozen threshold retunes."
        ),
        "nearby_prior_experiments": [
            "exp-20260531-002",
            "exp-20260602-016",
            "exp-20260602-031",
            "exp-20260603-008",
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260604-004",
        ],
        "prior_difference": (
            "Prior Form 4 runs tested standalone event qualifiers or FINRA/Form4 "
            "context. This run does not trade raw Form 4; it only asks whether "
            "Form 4 can serve as a new independent confirmation family inside the "
            "accepted consensus route."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_core": "> 0",
            "aggregate_pnl_delta_vs_core": "> 0",
            "per_window_expected_value_delta_vs_core": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_core": "3 of 3 windows > 0",
            "must_beat_current_accepted_consensus_comparator": True,
            "per_window_delta_vs_accepted_comparator": "3 of 3 windows > 0",
            "minimum_form4_selected_trades": 1,
            "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260604_005_form4_source_family_consensus_adapter_scout.py"
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    vs_comparator = payload["vs_accepted_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "form4_source_family_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_adapter_source_family_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 7,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "medium",
        "new_evidence_type": "new_pit_sec_form4_independent_source_family_on_accepted_consensus",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - PREDICTION["expected_ev_delta"],
                6,
            ),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - PREDICTION["expected_pnl_delta"],
                2,
            ),
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "accepted_comparator_ev_delta": vs_comparator["expected_value_score_delta"],
            "accepted_comparator_pnl_delta": vs_comparator["strategy_total_pnl_delta"],
            "accepted_comparator_windows_ev_improved": vs_comparator["windows_ev_improved"],
            "accepted_comparator_windows_pnl_improved": vs_comparator["windows_pnl_improved"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "form4_selected_trade_count": payload["target_summary"]["form4_selected_trade_count"],
            "form4_selected_trade_pnl_usd": payload["target_summary"]["form4_selected_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
                "form4_selected_trade_count": row["target_diagnostics"][
                    "form4_selected_trade_count"
                ],
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    vs_comparator = payload["vs_accepted_comparator"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} Form 4 source-family consensus scout",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-window result",
        "",
        (
            f"- Vs core: EV `{comparison['expected_value_score_delta']:+.4f}`, "
            f"PnL `${comparison['strategy_total_pnl_delta']:+,.2f}`"
        ),
        (
            f"- Vs accepted consensus comparator: EV "
            f"`{vs_comparator['expected_value_score_delta']:+.4f}`, "
            f"PnL `${vs_comparator['strategy_total_pnl_delta']:+,.2f}`"
        ),
        f"- Form 4 selected trades: `{payload['target_summary']['form4_selected_trade_count']}`",
        "",
        "## Production impact",
        "",
        "- Replay-only; no production code or live/default order behavior changed.",
        "- Positive retention would require a shared adapter/parity implementation first.",
        "",
        "No JavaScript was used.",
        "",
    ]
    _write_text(CARD_MD, "\n".join(lines))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            item["updated_at"] = payload["completed_at"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    consensus._configure_prior_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_source_rows = consensus.prior._source_rows_by_window()
    form4_source_rows, form4_diagnostics = _form4_rows_by_window()
    merged_source_rows = _merge_source_rows(base_source_rows, form4_source_rows)
    raw_form4_candidate_counts = {
        label: sum(len(rows) for rows in rows_by_key.values())
        for label, rows_by_key in sorted(form4_source_rows.items())
    }

    baselines = consensus.prior._load_baselines()
    accepted_results, accepted_trades_by_window, accepted_aggregate = _accepted_comparator_results(
        baselines,
        base_source_rows,
    )
    results, target_trades_by_window = _run_windows(baselines, merged_source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = _target_summary(target_trades_by_window)
    source_family_summary = _source_family_summary(
        target_trades_by_window,
        raw_form4_candidate_counts=raw_form4_candidate_counts,
    )
    vs_comparator = _aggregate_after_vs_comparator(results, accepted_results)
    gate4 = _gate4_decision(
        aggregate,
        results,
        target_summary,
        vs_comparator,
        source_family_summary,
    )
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: Form 4 meaningful purchases may add an "
                "independent confirmation family to accepted free-data consensus."
            ),
            "2_history_check": {
                "exp-20260531-002": "Form4 purchase-pressure was positive vs core but not promotable.",
                "exp-20260602-016": "Form4+FINRA short-pressure consensus rejected.",
                "exp-20260602-031": "Form4 underpriced qualifier positive vs core but not promotable.",
                "exp-20260603-008": "Form4 post-drawdown qualifier positive vs core but not promotable.",
                "exp-20260603-014": "Accepted independent-source consensus comparator.",
                "exp-20260604-004": "Core-overlap support failed accepted comparator.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; accept only if "
                "the variant beats core and current accepted consensus in all windows."
            ),
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "source_files": {
            **{
                name: str(path).replace("\\", "/")
                for name, path in consensus.SOURCE_FILES.items()
            },
            FORM4_SOURCE_NAME: _repo_rel(FORM4_TRANSACTIONS_PATH),
        },
        "form4_diagnostics": form4_diagnostics,
        "rule": {
            "rule_version": RULE_VERSION,
            "form4_source_name": FORM4_SOURCE_NAME,
            "form4_source_family": FORM4_SOURCE_FAMILY,
            "form4_rule_version": FORM4_RULE_VERSION,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
            "min_survival_rate": min(
                _safe_float(row["before"].get("survival_rate")) for row in results
            ),
        },
        "aggregate": aggregate,
        "accepted_comparator": {
            "experiment_id": CURRENT_ACCEPTED_COMPARATOR_EXPERIMENT_ID,
            "source_artifact": _repo_rel(CURRENT_ACCEPTED_COMPARATOR_JSON),
            "aggregate": accepted_aggregate,
            "target_summary": _target_summary(accepted_trades_by_window),
        },
        "vs_accepted_comparator": vs_comparator,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_consensus": vs_comparator["comparison"],
                "form4_selected_trade_count": target_summary["form4_selected_trade_count"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
