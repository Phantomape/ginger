"""exp-20260603-025: accepted consensus VIX low-stress scout.

Replay-only alpha search. This keeps the accepted independent-source
free-data consensus candidate source fixed, then tests one new free external
macro context variable: signal-day VIX daily close must be <= 20.

No shared adapter, production order path, ranking, sizing, exits, LLM, news,
watchlists, source thresholds, hold period, or notional policy is changed.
No JavaScript is used.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260603_014_accepted_consensus_independent_source_family as consensus


EXPERIMENT_ID = "exp-20260603-025"
STEM = "accepted_consensus_vix_low_stress"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_external_macro_context"
CHANGED_VARIABLE = "accepted_consensus_vix_low_stress_context_v1"
RULE_VERSION = "accepted_consensus_vix_lte_20_v1"
VIX_THRESHOLD = 20.0

ROOT = consensus.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_025_{STEM}.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = Path("experiments/manifests") / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

CURRENT_ACCEPTED_CONSENSUS_ARTIFACT = Path(
    "data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json"
)
VIX_SOURCE_CACHE = Path("data/experiments/exp-20260603-024/vix_daily_close_source.txt")
YAHOO_VIX_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
    "?period1=1727827200&period2=1776902400&interval=1d"
)

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
        "This experiment changes no production code. A retained result would "
        "need shared production/backtest VIX ingestion and parity tests before "
        "any daily report, candidate queue, or order surface could change."
    ),
}

_VIX_SOURCE_STATUS: dict[str, Any] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_consensus_module() -> None:
    consensus.EXPERIMENT_ID = EXPERIMENT_ID
    consensus.STEM = STEM
    consensus.TRIAL_FAMILY = TRIAL_FAMILY
    consensus.CHANGED_VARIABLE = CHANGED_VARIABLE
    consensus.RULE_VERSION = RULE_VERSION
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()


def _parse_yahoo_vix_json(raw_text: str) -> tuple[dict[str, float], str]:
    payload = json.loads(raw_text)
    result = (((payload.get("chart") or {}).get("result") or []) + [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError("Yahoo VIX chart response missing result")
    timestamps = result.get("timestamp") or []
    quote = ((((result.get("indicators") or {}).get("quote") or []) + [None])[0]) or {}
    closes = quote.get("close") or []
    values: dict[str, float] = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        date = datetime.fromtimestamp(float(ts), timezone.utc).date().isoformat()
        values[date] = float(close)
    if not values:
        raise RuntimeError("Yahoo VIX chart response produced no usable rows")
    return values, "Yahoo:^VIX"


def _parse_vix_csv(raw_text: str) -> tuple[dict[str, float], str]:
    values: dict[str, float] = {}
    reader = csv.DictReader(raw_text.splitlines())
    fieldnames = {str(name) for name in (reader.fieldnames or [])}
    if {"observation_date", "VIXCLS"}.issubset(fieldnames):
        date_field = "observation_date"
        value_field = "VIXCLS"
        source_name = "FRED:VIXCLS"
    elif {"Date", "Close"}.issubset(fieldnames):
        date_field = "Date"
        value_field = "Close"
        source_name = "Stooq:^VIX"
    else:
        raise RuntimeError(f"Unrecognized VIX CSV columns: {sorted(fieldnames)}")
    for row in reader:
        date = str(row.get(date_field) or "")
        value = row.get(value_field)
        if not date or value in (None, "", "."):
            continue
        try:
            values[date] = float(value)
        except ValueError:
            continue
    if not values:
        raise RuntimeError("VIX daily close load produced no usable rows")
    return values, source_name


def _parse_vix_payload(raw_text: str) -> tuple[dict[str, float], str]:
    if raw_text.lstrip().startswith("{"):
        return _parse_yahoo_vix_json(raw_text)
    return _parse_vix_csv(raw_text)


def _download_vix_text() -> str:
    request = urllib.request.Request(
        YAHOO_VIX_URL,
        headers={"User-Agent": "Mozilla/5.0 ginger-alpha-search-vix"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _load_vix_by_date() -> dict[str, float]:
    if VIX_SOURCE_CACHE.exists():
        raw_text = VIX_SOURCE_CACHE.read_text(encoding="utf-8")
        values, source_name = _parse_vix_payload(raw_text)
        source_status = "cache"
        source_path = str(VIX_SOURCE_CACHE).replace("\\", "/")
    else:
        raw_text = _download_vix_text()
        values, source_name = _parse_yahoo_vix_json(raw_text)
        source_status = "downloaded_not_cached"
        source_path = None
    _VIX_SOURCE_STATUS.update(
        {
            "source_name": source_name,
            "source_status": source_status,
            "source_path": source_path,
            "fallback_url": YAHOO_VIX_URL,
            "usable_rows": len(values),
            "min_date": min(values),
            "max_date": max(values),
            "known_at": "signal_day_close_before_next_open_paper_entry",
        }
    )
    return values


def _candidate_vix_date(candidate: dict[str, Any]) -> str:
    return str(candidate.get("date") or candidate.get("signal_date") or "")


def _filter_candidates_with_vix(
    candidates: list[dict[str, Any]],
    vix_by_date: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    reject_counts = {
        "missing_vix": 0,
        "vix_above_threshold": 0,
    }
    bucket_counts = {
        "vix_lte_20": 0,
    }
    for candidate in candidates:
        signal_date = _candidate_vix_date(candidate)
        vix_value = vix_by_date.get(signal_date)
        if vix_value is None:
            reject_counts["missing_vix"] += 1
            continue
        if vix_value > VIX_THRESHOLD:
            reject_counts["vix_above_threshold"] += 1
            continue
        bucket_counts["vix_lte_20"] += 1
        kept.append(
            {
                **candidate,
                "strategy": "accepted_free_data_cross_source_consensus_vix_low_stress",
                "rule_version": RULE_VERSION,
                "vix_context_rule_version": RULE_VERSION,
                "vix_daily_close": consensus.prior.base._round(vix_value, 4),
                "vix_threshold_max": VIX_THRESHOLD,
                "vix_regime_bucket": "vix_lte_20",
                "vix_known_at": "signal_day_close_before_next_open_paper_entry",
                "vix_data_source": _VIX_SOURCE_STATUS.get("source_name"),
                "macro_context_alters_orders": False,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    return kept, {
        "candidate_count_before_vix_filter": len(candidates),
        "candidate_count_after_vix_filter": len(kept),
        "vix_threshold_max": VIX_THRESHOLD,
        "vix_source": dict(_VIX_SOURCE_STATUS),
        "vix_reject_counts": reject_counts,
        "vix_kept_counts": bucket_counts,
    }


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    vix_by_date: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in consensus.prior.base.WINDOWS.items():
        snapshot = consensus.prior.base.shadow._load_snapshot(cfg["snapshot"])
        raw_candidates = consensus._consensus_candidates_for_window(label, source_rows_by_window)
        candidates, vix_audit = _filter_candidates_with_vix(raw_candidates, vix_by_date)
        target_trades, target_diagnostics = consensus._select_target_trades(snapshot, candidates)
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
                "target_trade_pnl_usd": sum(float(row.get("pnl", 0.0)) for row in target_trades),
                "raw_consensus_candidate_count": len(raw_candidates),
                "vix_audit": vix_audit,
                "target_diagnostics": target_diagnostics,
            }
        )
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _current_accepted_consensus_comparison(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source = consensus.prior._load_json(ROOT / CURRENT_ACCEPTED_CONSENSUS_ARTIFACT)
    source_results = {str(row["label"]): row for row in source.get("results", [])}
    source_target_rows = source.get("target_trades_by_window") or {}
    window_rows: list[dict[str, Any]] = []
    windows_ev_regressed: list[str] = []
    windows_pnl_regressed: list[str] = []
    target_key_changes: dict[str, Any] = {}
    for row in results:
        label = str(row["label"])
        source_row = source_results[label]
        candidate_after_ev = float(row["after"]["expected_value_score"])
        source_after_ev = float(source_row["after"]["expected_value_score"])
        candidate_after_pnl = float(row["after"]["total_pnl"])
        source_after_pnl = float(source_row["after"]["total_pnl"])
        ev_delta = round(candidate_after_ev - source_after_ev, 6)
        pnl_delta = round(candidate_after_pnl - source_after_pnl, 2)
        if ev_delta < 0:
            windows_ev_regressed.append(label)
        if pnl_delta < 0:
            windows_pnl_regressed.append(label)
        current_keys = {
            (str(trade.get("signal_date") or trade.get("date") or ""), str(trade.get("ticker") or ""))
            for trade in target_trades_by_window.get(label, [])
        }
        source_keys = {
            (str(trade.get("signal_date") or trade.get("date") or ""), str(trade.get("ticker") or ""))
            for trade in source_target_rows.get(label, [])
        }
        target_key_changes[label] = {
            "added": sorted(current_keys - source_keys),
            "removed": sorted(source_keys - current_keys),
            "unchanged_count": len(current_keys & source_keys),
        }
        window_rows.append(
            {
                "label": label,
                "candidate_after_expected_value": candidate_after_ev,
                "current_accepted_after_expected_value": source_after_ev,
                "after_expected_value_delta_vs_current_accepted": ev_delta,
                "candidate_after_total_pnl": candidate_after_pnl,
                "current_accepted_after_total_pnl": source_after_pnl,
                "after_total_pnl_delta_vs_current_accepted": pnl_delta,
                "candidate_target_trade_count": row["target_trade_count"],
                "current_accepted_target_trade_count": source_row["target_trade_count"],
            }
        )
    aggregate_ev_delta = round(
        float(aggregate["after"]["expected_value_score"])
        - float(source["aggregate"]["after"]["expected_value_score"]),
        6,
    )
    aggregate_pnl_delta = round(
        float(aggregate["after"]["strategy_total_pnl"])
        - float(source["aggregate"]["after"]["strategy_total_pnl"]),
        2,
    )
    changed_targets = any(
        row["added"] or row["removed"] for row in target_key_changes.values()
    )
    return {
        "comparison_artifact": str(CURRENT_ACCEPTED_CONSENSUS_ARTIFACT).replace("\\", "/"),
        "current_accepted_experiment_id": str(source.get("experiment_id")),
        "candidate_after_expected_value": aggregate["after"]["expected_value_score"],
        "current_accepted_after_expected_value": source["aggregate"]["after"]["expected_value_score"],
        "after_expected_value_delta_vs_current_accepted": aggregate_ev_delta,
        "candidate_after_strategy_total_pnl": aggregate["after"]["strategy_total_pnl"],
        "current_accepted_after_strategy_total_pnl": source["aggregate"]["after"][
            "strategy_total_pnl"
        ],
        "after_strategy_total_pnl_delta_vs_current_accepted": aggregate_pnl_delta,
        "beats_current_accepted_ev": aggregate_ev_delta > 0,
        "beats_current_accepted_pnl": aggregate_pnl_delta > 0,
        "windows_ev_regressed_vs_current_accepted": windows_ev_regressed,
        "windows_pnl_regressed_vs_current_accepted": windows_pnl_regressed,
        "target_keys_changed_vs_current_accepted": changed_targets,
        "target_key_changes": target_key_changes,
        "by_window": window_rows,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Accepted independent-source free-data consensus paper candidates may "
            "have cleaner replacement value when free signal-day VIX stress is low."
        ),
        "category": "entry/candidate_pool/risk_allocation",
        "playbook_alignment": (
            "Meta research favors production-visible default-off paper adapters. "
            "This tests a new free external macro field on the accepted consensus "
            "adapter rather than another source-family, FINRA, Companyfacts, "
            "post-earnings, state-surface, or raw alpha_score threshold retune."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260603-016",
            "exp-20260603-017",
            "exp-20260603-023",
            "exp-20260603-024",
        ],
        "prior_difference": (
            "exp-20260603-024 tested VIX on alpha_score market-regime candidates; "
            "this tests the accepted independent-source consensus adapter. "
            "Source sets, thresholds, notional, hold period, and live behavior "
            "are locked."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "beats_current_accepted_consensus": "required",
            "target_set_changes_vs_current_accepted": "required",
            "minimum_target_trades": consensus.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": consensus.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
            "shared_vix_ingestion_required_for_promotion": True,
        },
        "reproducibility": (
            "The runner persists the fixed VIX threshold, VIX source status, "
            "canonical before/after metrics, target trades, and Gate 4 diagnostics."
        ),
    }


def _apply_current_accepted_and_parity_guard(
    gate4: dict[str, Any],
    current_comparison: dict[str, Any],
) -> dict[str, Any]:
    numeric_passed_before_extra_guards = bool(gate4["passed"])
    gate4["gates"]["beats_current_accepted_consensus_ev"] = bool(
        current_comparison["beats_current_accepted_ev"]
    )
    gate4["gates"]["beats_current_accepted_consensus_pnl"] = bool(
        current_comparison["beats_current_accepted_pnl"]
    )
    gate4["gates"]["no_window_ev_regression_vs_current_accepted_consensus"] = not bool(
        current_comparison["windows_ev_regressed_vs_current_accepted"]
    )
    gate4["gates"]["no_window_pnl_regression_vs_current_accepted_consensus"] = not bool(
        current_comparison["windows_pnl_regressed_vs_current_accepted"]
    )
    gate4["gates"]["target_set_changed_vs_current_accepted_consensus"] = bool(
        current_comparison["target_keys_changed_vs_current_accepted"]
    )
    gate4["gates"]["shared_vix_ingestion_exists"] = False
    gate4["numeric_passed_before_parity_guard"] = numeric_passed_before_extra_guards and all(
        value
        for key, value in gate4["gates"].items()
        if key != "shared_vix_ingestion_exists"
    )
    gate4["passed"] = False
    gate4["requires_parity_before_promotion"] = False
    if gate4["numeric_passed_before_parity_guard"]:
        gate4["decision"] = "positive_replay_lead_not_promoted_requires_shared_vix_ingestion"
        gate4["rationale"] = (
            "The VIX low-stress consensus replay cleared numeric gates, but it "
            "is not retained because shared production/backtest VIX ingestion "
            "does not exist yet."
        )
    else:
        gate4["decision"] = "rejected_accepted_consensus_vix_low_stress"
        gate4["rationale"] = (
            "The VIX low-stress consensus replay failed numeric/comparator gates. "
            "Do not retune VIX thresholds on this frozen sample."
        )
    return gate4


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    prediction = {
        "success_probability": 0.24,
        "expected_ev_delta": 0.2,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "underperforms_current_accepted_consensus",
            "vix_overlap_identity",
            "window_regression",
            "production_vix_ingestion_missing",
        ],
        "confidence_reason": (
            "Meta research favors default-off paper adapters, but source-family "
            "and alpha_score macro variants are heavily explored; this only "
            "tests a different accepted adapter with one free macro field."
        ),
        "recorded_at": "2026-06-03T22:07:17+00:00",
    }
    actual_success = 1 if payload["gate4"]["numeric_passed_before_parity_guard"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "observed_only" if actual_success else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_macro_context_scout",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 1,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "free_external_macro_regime_field_on_different_adapter",
        "decision": payload["gate4"]["decision"],
        "accepted": False,
        "rejection_reason": payload["gate4"]["rationale"],
        "prediction": prediction,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - prediction["expected_ev_delta"], 6
            ),
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - prediction["expected_pnl_delta"], 2
            ),
            "realized_failure_mode": None
            if actual_success
            else "accepted_consensus_vix_low_stress_gate4_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(
            payload["gate4"]["numeric_passed_before_parity_guard"]
        ),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "after_ev_delta_vs_current_accepted_consensus": payload[
                "current_accepted_consensus_comparison"
            ]["after_expected_value_delta_vs_current_accepted"],
            "after_pnl_delta_vs_current_accepted_consensus": payload[
                "current_accepted_consensus_comparison"
            ]["after_strategy_total_pnl_delta_vs_current_accepted"],
            "vix_threshold_max": VIX_THRESHOLD,
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
                "vix_audit": row["vix_audit"],
            }
            for row in payload["results"]
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]["comparison"]
    comparator = payload["current_accepted_consensus_comparison"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'status: "{payload["gate4"]["decision"]}"',
        'lane: "alpha_search"',
        f'changed_variable: "{CHANGED_VARIABLE}"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Numeric passed before parity guard: `{payload['gate4']['numeric_passed_before_parity_guard']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-Window Result",
        "",
        "| Window | EV Before | EV After | dEV | PnL d | Target Trades | VIX kept/raw |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["results"]:
        vix_audit = row["vix_audit"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${dpnl:+,.2f} | {trades} | {kept}/{raw} |".format(
                label=row["label"],
                bev=row["before"]["expected_value_score"],
                aev=row["after"]["expected_value_score"],
                dev=row["comparison"]["expected_value_score_delta"],
                dpnl=row["comparison"]["strategy_total_pnl_delta"],
                trades=row["target_trade_count"],
                kept=vix_audit["candidate_count_after_vix_filter"],
                raw=vix_audit["candidate_count_before_vix_filter"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core baseline: `{aggregate['expected_value_score_delta']}`",
            f"- PnL delta vs core baseline: `${aggregate['strategy_total_pnl_delta']:,.2f}`",
            f"- Target trades: `{payload['target_summary']['target_trade_count']}`",
            f"- Max single positive share: `{payload['target_summary']['max_single_positive_share']}`",
            f"- Positive PnL HHI: `{payload['target_summary']['positive_pnl_hhi']}`",
            "",
            "## Accepted Comparator",
            "",
            f"- EV delta vs current accepted consensus: `{comparator['after_expected_value_delta_vs_current_accepted']}`",
            f"- PnL delta vs current accepted consensus: `${comparator['after_strategy_total_pnl_delta_vs_current_accepted']:,.2f}`",
            f"- Target set changed: `{comparator['target_keys_changed_vs_current_accepted']}`",
            "",
            "## Production Impact",
            "",
            "Replay-only/default-off paper scout. No shared adapter, run adapter, "
            "backtester adapter, production watchlist, order path, core entry, "
            "ranking, sizing, exit, LLM, or news behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = consensus.prior._load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "card": str(CARD_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
            },
        }
    )
    consensus.prior._write_json(TICKET_JSON, ticket)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    raw_text = REGISTRY_JSON.read_text(encoding="utf-8")
    marker = "\n  ],\n  \"schema_version\""
    if marker not in raw_text:
        return
    artifact_path = str(OUT_JSON).replace("\\", "/")
    card_path = str(CARD_MD).replace("\\", "/")
    log_path = str(LOG_JSON).replace("\\", "/")
    manifest_path = str(MANIFEST_JSON).replace("\\", "/")
    ticket_path = str(TICKET_JSON).replace("\\", "/")
    entry = "\n".join(
        [
            "    {",
            f'      "aggregate_expected_value_delta": {payload["aggregate"]["comparison"]["expected_value_score_delta"]},',
            f'      "aggregate_strategy_total_pnl_delta": {payload["aggregate"]["comparison"]["strategy_total_pnl_delta"]},',
            f'      "artifact": "{artifact_path}",',
            f'      "card_file": "{card_path}",',
            f'      "completed_at": "{payload["completed_at"]}",',
            f'      "decision": "{payload["gate4"]["decision"]}",',
            f'      "experiment_id": "{EXPERIMENT_ID}",',
            '      "hypothesis": "Accepted independent-source free-data consensus paper candidates may have cleaner replacement value when free signal-day VIX stress is low.",',
            '      "lane": "alpha_search",',
            f'      "log": "{log_path}",',
            '      "owner": "alpha-search",',
            f'      "revision_manifest_file": "{manifest_path}",',
            '      "status": "completed",',
            f'      "ticket_file": "{ticket_path}",',
            f'      "updated_at": "{payload["completed_at"]}"',
            "    }",
        ]
    )
    needle = f'      "experiment_id": "{EXPERIMENT_ID}"'
    pos = raw_text.find(needle)
    if pos >= 0:
        start = raw_text.rfind("\n    {", 0, pos)
        end = raw_text.find("\n    }", pos)
        if start < 0 or end < 0:
            return
        end += len("\n    }")
        suffix = "," if raw_text[end : end + 1] == "," else ""
        raw_text = raw_text[:start] + "\n" + entry + suffix + raw_text[end + len(suffix) :]
    else:
        raw_text = raw_text.replace(marker, ",\n" + entry + marker, 1)
    raw_text = re.sub(
        r'("schema_version": 1,\n  "updated_at": ")[^"]+(")',
        rf'\g<1>{payload["completed_at"]}\2',
        raw_text,
        count=1,
    )
    REGISTRY_JSON.write_text(raw_text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_status_short() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return [line for line in proc.stdout.splitlines() if line]


def _update_manifest(payload: dict[str, Any]) -> None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "git": {
            "commit": proc.stdout.strip() if proc.returncode == 0 else None,
            "dirty": True,
            "status_short": _git_status_short(),
        },
        "files": {
            "runner": {
                "path": "quant/experiments/exp_20260603_025_accepted_consensus_vix_low_stress.py",
                "sha256": _sha256(Path("quant/experiments/exp_20260603_025_accepted_consensus_vix_low_stress.py")),
            },
            "data": {"path": str(OUT_JSON).replace("\\", "/"), "sha256": _sha256(OUT_JSON)},
            "log": {"path": str(LOG_JSON).replace("\\", "/"), "sha256": _sha256(LOG_JSON)},
            "ticket": {"path": str(TICKET_JSON).replace("\\", "/"), "sha256": _sha256(TICKET_JSON)},
            "card": {"path": str(CARD_MD).replace("\\", "/"), "sha256": _sha256(CARD_MD)},
        },
        "decision": payload["gate4"]["decision"],
    }
    consensus.prior._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_consensus_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    vix_by_date = _load_vix_by_date()
    source_rows = consensus.prior._source_rows_by_window()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window = _run_windows(baselines, source_rows, vix_by_date)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = consensus._source_family_summary(target_trades_by_window)
    gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    current_comparison = _current_accepted_consensus_comparison(
        aggregate,
        results,
        target_trades_by_window,
    )
    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
    else:
        gate4["gates"]["source_family_min_count_passed"] = True
    gate4 = _apply_current_accepted_and_parity_guard(gate4, current_comparison)
    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "rule": {
            "rule_version": RULE_VERSION,
            "vix_threshold_max": VIX_THRESHOLD,
            "vix_bucket": "vix_lte_20",
            "source_families": consensus.SOURCE_FAMILIES,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "vix_source_status": dict(_VIX_SOURCE_STATUS),
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "default_off_paper_context_only": True,
        },
        "aggregate": aggregate,
        "current_accepted_consensus_comparison": current_comparison,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }
    consensus.prior._write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    consensus.prior._write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)
    _update_manifest(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "current_accepted_consensus_comparison": current_comparison,
                "vix_source_status": _VIX_SOURCE_STATUS,
                "target_summary": target_summary,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
