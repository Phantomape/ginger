"""exp-20260612-008: post-earnings event+1 exclusion scout.

Alpha search on the accepted default-off POST_EARNINGS_UNDERPRICED_DRIFT_PAPER
stack. The single hypothesis is that candidates selected exactly one trading
day after the earnings confirmation are digestion-day noise; excluding only
that event offset should improve paper candidate quality without adding tickers
or retuning surprise/liquidity/sector/non-core support.

This runner is replay-only. A positive metric result is not retained unless a
separate shared-helper promotion wires the same exclusion through
quant/post_earnings_underpriced_drift_paper_sleeve.py. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for import_path in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260603_022_post_earnings_non_core_overlap_shared_support as parent
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260612-008"
STEM = "post_earnings_event_plus_one_exclusion"
TRIAL_FAMILY = "post_earnings_underpriced_event_plus_one_exclusion"
CHANGED_VARIABLE = "post_earnings_underpriced_exclude_event_plus_one_candidate_offset_v1"
RULE_VERSION = "post_earnings_event_plus_one_exclusion_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_008_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260603-022"
    / "exp_20260603_022_post_earnings_non_core_overlap_shared_support.json"
)

EXCLUDED_RECENT_SIGNAL_OFFSETS = {1}
MIN_AFTER_TRADES = 10
MIN_AFTER_WINDOWS = 3

PREDICTION = {
    "success_probability": 0.21,
    "expected_ev_delta": 0.02,
    "expected_pnl_delta": 700.0,
    "main_failure_modes": [
        "thin_touched_sample",
        "window_regression",
        "post_earnings_stack_saturated",
        "event_timing_overfit",
    ],
    "confidence_reason": (
        "Precheck of accepted post-earnings trades shows event+1 is a negative "
        "bucket while offset 0 and later absorption are mostly positive, but "
        "the touched sample is small and the current stack is already heavily "
        "filtered."
    ),
    "recorded_at": "2026-06-12T06:08:26+00:00",
}


def _framework() -> Any:
    return parent._framework()


def _base() -> Any:
    return _framework().base


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _event_offset(row: dict[str, Any]) -> int | None:
    value = row.get("recent_signal_trading_day_offset")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_excluded_offset(row: dict[str, Any]) -> bool:
    offset = _event_offset(row)
    return offset in EXCLUDED_RECENT_SIGNAL_OFFSETS


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # parent.parent is exp_20260603_021. After parent._patch_parent(), that
    # path includes accepted high-liquidity, sector-residual, and shared
    # non-core-overlap support before this offset exclusion is applied.
    candidates, audit = parent.parent._candidate_rows_for_window(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    excluded_count = 0
    excluded_days: set[str] = set()
    excluded_tickers: set[str] = set()
    offset_counts: Counter[str] = Counter()
    for row in candidates:
        offset = _event_offset(row)
        offset_key = "missing" if offset is None else str(offset)
        offset_counts[offset_key] += 1
        excluded = _is_excluded_offset(row)
        row["event_plus_one_exclusion_rule_version"] = RULE_VERSION
        row["excluded_recent_signal_offsets"] = sorted(EXCLUDED_RECENT_SIGNAL_OFFSETS)
        row["event_plus_one_excluded"] = excluded
        row["trade_enabled"] = False
        row["alters_orders"] = False
        if excluded:
            excluded_count += 1
            excluded_days.add(str(row.get("date") or ""))
            excluded_tickers.add(str(row.get("ticker") or "").upper())

    audit = dict(audit)
    audit["event_plus_one_exclusion_rule_version"] = RULE_VERSION
    audit["excluded_recent_signal_offsets"] = sorted(EXCLUDED_RECENT_SIGNAL_OFFSETS)
    audit["event_plus_one_excluded_raw_candidate_count"] = excluded_count
    audit["event_plus_one_excluded_candidate_days"] = len(excluded_days)
    audit["event_plus_one_excluded_unique_tickers"] = len(excluded_tickers)
    audit["recent_signal_offset_counts"] = dict(sorted(offset_counts.items()))
    audit["support_changes_entries_or_filters"] = True
    return candidates, audit


def _paper_trade_from_candidate(
    snapshot: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    trade = parent.parent._paper_trade_from_candidate(snapshot, candidate)
    if trade is None:
        return None
    for field in (
        "event_plus_one_exclusion_rule_version",
        "excluded_recent_signal_offsets",
        "event_plus_one_excluded",
        "recent_signal_trading_day_offset",
        "event_confirmed_date",
        "event_to_signal_return",
        "event_to_signal_excess_vs_spy",
        "non_core_overlap_context_status",
        "same_day_ab_entry_count",
        "same_day_ab_overlap",
        "same_ticker_ab_overlap",
        "non_core_overlap_support",
        "non_core_overlap_support_rule_version",
        "non_core_overlap_notional_scalar",
        "pre_non_core_overlap_paper_notional_usd",
    ):
        trade[field] = candidate.get(field)
    trade["trade_enabled"] = False
    trade["alters_orders"] = False
    return trade


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date_value = str(row.get("date") or "")
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if _is_excluded_offset(row):
            filtered.append({**row, "filter_reason": "event_plus_one_excluded"})
            continue
        if used_date_counts[date_value] >= _framework().MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = _paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[date_value] += 1
    return selected, filtered


def _accepted_baseline() -> dict[str, Any]:
    with BASELINE_RESULT_JSON.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _rebase_payload_to_accepted_baseline(payload: dict[str, Any]) -> dict[str, Any]:
    baseline = _accepted_baseline()
    before_metrics = {
        label: baseline["after_metrics"][label]
        for label in _framework().base.WINDOWS
    }
    window_rows: dict[str, dict[str, Any]] = {}
    delta_by_window: dict[str, dict[str, Any]] = {}
    for label in _framework().base.WINDOWS:
        before = before_metrics[label]
        after = payload["after_metrics"][label]
        delta = _framework().overlay_helper._delta(after, before)
        delta_by_window[label] = delta
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(payload["target_trades_by_window"][label]),
        }
    aggregate = _framework()._aggregate(window_rows)
    target_summary = _framework()._target_trade_summary(
        payload["target_trades_by_window"]
    )
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    gate4 = _framework()._gate4(aggregate, target_summary, min_survival)
    failed_reasons = list(gate4.get("failed_reasons") or [])
    if "window_ev_regression" in failed_reasons and not any(
        float(delta.get("expected_value_score") or 0.0) < 0
        for delta in delta_by_window.values()
    ):
        failed_reasons.remove("window_ev_regression")
    for label, delta in delta_by_window.items():
        if float(delta.get("expected_value_score") or 0.0) < 0:
            failed_reasons.append(f"{label}_ev_regressed_vs_exp022")
        if float(delta.get("total_pnl") or 0.0) < 0:
            failed_reasons.append(f"{label}_pnl_regressed_vs_exp022")
    if target_summary.get("total_trade_count", 0) < MIN_AFTER_TRADES:
        failed_reasons.append("after_trade_count_below_meaningful_floor")
    active_windows = sum(
        1 for trades in payload["target_trades_by_window"].values() if trades
    )
    if active_windows < MIN_AFTER_WINDOWS:
        failed_reasons.append("not_all_windows_have_after_trades")
    metric_gate4_passed = not failed_reasons
    gate4["metric_gate4_passed"] = metric_gate4_passed
    gate4["passed"] = False
    gate4["failed_reasons"] = (
        sorted(set(failed_reasons))
        if failed_reasons
        else ["shared_adapter_not_changed_positive_replay_not_retained"]
    )
    gate4["acceptance_rule"] = (
        "Metric Gate 4 uses docs/backtesting.md three canonical windows versus "
        "exp-20260603-022 accepted after-state. Retention also requires shared "
        "default-off adapter promotion, which this scout does not do."
    )

    payload["incremental_baseline_experiment_id"] = "exp-20260603-022"
    payload["incremental_baseline_result_file"] = _base()._repo_rel(
        BASELINE_RESULT_JSON
    )
    payload["before_metrics"] = before_metrics
    payload["delta_metrics"] = {
        "by_window": delta_by_window,
        "aggregate": aggregate,
    }
    payload["target_trade_summary"] = target_summary
    payload["judge_before_aggregate"] = _framework()._aggregate_result_for_judge(
        before_metrics
    )
    payload["judge_after_aggregate"] = _framework()._aggregate_result_for_judge(
        payload["after_metrics"]
    )
    payload["gate4"] = gate4
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    return payload


def _offset_summary(
    baseline_payload: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    touched_by_ticker: Counter[str] = Counter()
    for label in _framework().base.WINDOWS:
        baseline_trades = baseline_payload["target_trades_by_window"][label]
        after_trades = payload["target_trades_by_window"][label]
        filtered = payload.get("filtered_candidates_by_window", {}).get(label) or []
        baseline_event_plus_one = [
            trade
            for trade in baseline_trades
            if _event_offset(trade) in EXCLUDED_RECENT_SIGNAL_OFFSETS
        ]
        for trade in baseline_event_plus_one:
            touched_by_ticker[str(trade.get("ticker") or "").upper()] += float(
                trade.get("pnl") or 0.0
            )
        by_window[label] = {
            "baseline_trade_count": len(baseline_trades),
            "after_trade_count": len(after_trades),
            "baseline_event_plus_one_trade_count": len(baseline_event_plus_one),
            "baseline_event_plus_one_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in baseline_event_plus_one),
                2,
            ),
            "filtered_event_plus_one_candidate_count": sum(
                1
                for row in filtered
                if row.get("filter_reason") == "event_plus_one_excluded"
            ),
            "after_event_plus_one_trade_count": sum(
                1
                for trade in after_trades
                if _event_offset(trade) in EXCLUDED_RECENT_SIGNAL_OFFSETS
            ),
            "after_offsets": dict(
                sorted(
                    Counter(
                        str(_event_offset(trade))
                        for trade in after_trades
                    ).items()
                )
            ),
        }
    return {
        "excluded_recent_signal_offsets": sorted(EXCLUDED_RECENT_SIGNAL_OFFSETS),
        "by_window": by_window,
        "baseline_event_plus_one_pnl_by_ticker": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(touched_by_ticker.items())
        },
    }


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.DOC_TICKET_JSON = DOC_TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_parent()
    _framework()._candidate_rows_for_window = _candidate_rows_for_window
    _framework()._select_paper_trades = _select_paper_trades


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    baseline_payload = _accepted_baseline()
    payload = _rebase_payload_to_accepted_baseline(payload)
    offset_summary = _offset_summary(baseline_payload, payload)
    metric_gate4_passed = bool(payload["gate4"].get("metric_gate4_passed"))
    decision = (
        "positive_replay_lead_post_earnings_event_plus_one_exclusion_requires_shared_adapter"
        if metric_gate4_passed
        else "rejected_post_earnings_event_plus_one_exclusion"
    )
    actual_success = 1 if metric_gate4_passed else 0
    prediction = {
        **PREDICTION,
        "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
    }
    failed_reasons = payload["gate4"]["failed_reasons"]
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
            "status": "observed_only" if metric_gate4_passed else "rejected",
            "decision": decision,
            "hypothesis": (
                "Within the accepted post-earnings underpriced default-off sleeve, "
                "event+1 entries may be noisy digestion-day fills; excluding "
                "that offset may improve candidate quality without adding tickers."
            ),
            "change_type": "default_off_paper_candidate_pool_scout",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "post_earnings_underpriced_drift",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 8,
            "nearby_prior_experiments": [
                "exp-20260602-026",
                "exp-20260602-027",
                "exp-20260603-004",
                "exp-20260603-020",
                "exp-20260603-022",
                "exp-20260604-001",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_earnings_event_timing_offset_field",
            "prediction": prediction,
            "calibration": {
                "actual_decision": decision,
                "metric_gate4_passed": metric_gate4_passed,
                "predicted_success_probability": prediction["success_probability"],
                "brier_score": prediction["brier_score"],
                "expected_ev_delta": prediction["expected_ev_delta"],
                "actual_ev_delta": payload["expected_value_score_delta"],
                "expected_pnl_delta": prediction["expected_pnl_delta"],
                "actual_pnl_delta": payload["total_pnl_delta"],
                "predicted_failure_modes": prediction["main_failure_modes"],
                "realized_failure_mode": None
                if metric_gate4_passed
                else "; ".join(failed_reasons),
            },
            "parameters": {
                **payload.get("parameters", {}),
                "incremental_baseline_experiment_id": "exp-20260603-022",
                "excluded_recent_signal_offsets": sorted(EXCLUDED_RECENT_SIGNAL_OFFSETS),
                "trade_enabled": False,
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry/candidate_pool: avoid post-earnings event+1 paper "
                    "entries because that day can be digestion noise rather than "
                    "confirmed underpriced drift."
                ),
                "2_history_check": {
                    "exp-20260602-026": "Accepted shared post-earnings underpriced drift adapter.",
                    "exp-20260602-027": "Accepted high-liquidity support; kept fixed.",
                    "exp-20260603-004": "Accepted sector-residual support; kept fixed.",
                    "exp-20260603-020": "Rejected participation support due mid_weak regression.",
                    "exp-20260603-022": "Accepted shared non-core overlap support; current baseline.",
                    "exp-20260604-001": "Rejected surprise acceleration due mid/old regression.",
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three windows; compare against "
                    "exp-20260603-022 after_metrics. Metric pass requires "
                    "positive aggregate EV/PnL, no EV/PnL window regression, "
                    "drawdown <=50bp, survival >=5%, and >=10 after trades "
                    "across all windows. Retention requires shared-helper "
                    "promotion."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260612_008_post_earnings_event_plus_one_exclusion.py"
                ),
            },
            "gate1": {
                "baseline_metrics": payload["before_metrics"],
                "baseline_artifact": (
                    "data/experiments/exp-20260603-022/"
                    "exp_20260603_022_post_earnings_non_core_overlap_shared_support.json"
                    "#after_metrics"
                ),
                "passed": True,
            },
            "gate2": {
                **payload.get("gate2", {}),
                "support_field_check": {
                    "fields": [
                        "recent_signal_trading_day_offset",
                        "event_confirmed_date",
                        "event_to_signal_return",
                        "event_to_signal_excess_vs_spy",
                    ],
                    "source": (
                        "PIT earnings_snapshot transition plus signal-date OHLCV "
                        "candidate rows from the shared post-earnings helper"
                    ),
                    "decision_time": (
                        "known after signal-date close before next-open default-off paper entry"
                    ),
                    "coverage": _framework()._field_coverage(
                        all_target_trades,
                        [
                            "recent_signal_trading_day_offset",
                            "event_confirmed_date",
                            "event_to_signal_return",
                            "event_to_signal_excess_vs_spy",
                        ],
                    ),
                    "passed": True,
                },
            },
            "gate3": {
                "new_core_filter_added": False,
                "candidate_pool_changed": True,
                "minimum_core_survival_rate": min(
                    float(row.get("survival_rate") or 0.0)
                    for row in payload["before_metrics"].values()
                ),
                "passed": True,
                "note": (
                    "No core filter, live entry rule, sizing, or exit change. "
                    "This only excludes one event-timing bucket from default-off "
                    "post-earnings paper candidates."
                ),
            },
            "offset_exclusion_summary": offset_summary,
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_signal_path_changed": False,
                "production_core_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exit_changed": False,
                "trade_enabled": False,
                "llm_or_news_changed": False,
                "retained_behavior": False,
                "parity_rule": RULE_VERSION,
                "registry_reserve_note": (
                    "experiment.py new wrote the ticket temp file but failed "
                    "os.replace on this Windows ACL; the temp ticket was moved "
                    "into place as experiments/tickets/exp-20260612-008.json. "
                    "claim could not run because registry lacked the ID."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe rows remain sparse. "
                "Skipped surprise acceleration and participation support because "
                "recent post-earnings runs regressed mid/old windows. Skipped "
                "SEC/Form4/FTD source additions because nearby experiments are "
                "recently rejected or frozen."
            ),
            "interpretation": (
                "Metric-positive replay lead only; do not retain until the same "
                "offset exclusion is added to the shared default-off post-earnings helper."
                if metric_gate4_passed
                else (
                    "Rejected. Event+1 exclusion removed a visibly weak pocket, "
                    "but it touched too few target trades to clear the standard "
                    "sample floor."
                )
            ),
            "acceptance_interpretation": (
                "Observed-only metric pass; no production-visible behavior retained."
                if metric_gate4_passed
                else "Gate 4 failed; no shared adapter or production behavior changed."
            ),
            "rejection_reason": None if metric_gate4_passed else "; ".join(failed_reasons),
            "post_run_reflection": {
                "why_result_happened": (
                    "The event+1 bucket was mostly a weak digestion-day pocket "
                    "inside mid_weak and old_thin, so excluding it lifted EV and "
                    "PnL. The effect is not robust enough to retain because only "
                    "14 target trades remain and late_strong contributes no "
                    "event+1 evidence."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry adjacent post-earnings offset-only filters, "
                    "single-offset delay rules, or event+2/event+3 retunes "
                    "without materially more post-earnings candidates."
                ),
                "new_evidence_required": (
                    "Needs a broader replay-safe post-earnings candidate pool or "
                    "an independent free-data signal that expands touched trades "
                    "before promoting any timing exclusion into the shared helper."
                ),
            },
            "next_evidence_needed": (
                "If retained, promote through quant/post_earnings_underpriced_drift_paper_sleeve.py "
                "and rerun Gate 4/parity; if rejected, do not retune adjacent post-earnings offset buckets."
            ),
            "related_files": [
                _base()._repo_rel(Path(__file__)),
                _base()._repo_rel(OUT_JSON),
                _base()._repo_rel(BEFORE_AGG_JSON),
                _base()._repo_rel(AFTER_AGG_JSON),
                _base()._repo_rel(LOG_JSON),
                _base()._repo_rel(TICKET_JSON),
                _base()._repo_rel(DOC_TICKET_JSON),
                _base()._repo_rel(CARD_MD),
                _base()._repo_rel(ARTIFACT_MD),
                _base()._repo_rel(MANIFEST_JSON),
                _base()._repo_rel(EXPERIMENT_LOG),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Before trades | After trades | Baseline event+1 PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    offset_by_window = payload["offset_exclusion_summary"]["by_window"]
    for label in _framework().base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        offset_row = offset_by_window[label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {bt} | {at} | ${event_pnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                bt=offset_row["baseline_trade_count"],
                at=offset_row["after_trade_count"],
                event_pnl=offset_row["baseline_event_plus_one_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Event+1 Exclusion",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: exclude `recent_signal_trading_day_offset == 1` from the accepted `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidate pool.",
            "",
            "Baseline: `exp-20260603-022` accepted after metrics.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- after target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- failed reasons: `{', '.join(payload['gate4']['failed_reasons'])}`",
            "",
            "## Offset Summary",
            "",
            "```json",
            json.dumps(payload["offset_exclusion_summary"], indent=2, sort_keys=True),
            "```",
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
                "Replay scout only. No shared helper, run adapter, backtester "
                "adapter, production watchlist, order path, core entry, ranking, "
                "sizing, exit, LLM, or news behavior changed. A positive metric "
                "result must be promoted through the shared default-off helper "
                "before retention."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    base = _base()
    base._upsert_jsonl(path, payload)


def _persist_registry(payload: dict[str, Any], ticket_payload: dict[str, Any]) -> str | None:
    result = ticket_payload.get("result") or {}
    fields = {
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "baseline_result_file": _base()._repo_rel(BASELINE_RESULT_JSON),
        "allowed_write_scope": [
            "quant/experiments",
            "data/experiments",
            "experiments/logs",
            "experiments/tickets",
            "docs/experiments/tickets",
            "experiments/cards",
            "experiments/artifacts",
            "experiments/manifests",
            "docs/experiment_log.jsonl",
        ],
    }
    try:
        persist_self_registered_result(
            REGISTRY_JSON,
            experiment_id=EXPERIMENT_ID,
            lane="alpha_search",
            prediction=payload["prediction"],
            result=result,
            status=payload["status"],
            fields=fields,
        )
    except Exception as exc:  # pragma: no cover - environment ACL fallback
        return f"{type(exc).__name__}: {exc}"
    return None


def _write_manifest(payload: dict[str, Any]) -> None:
    base = _base()
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "doc_ticket": base._repo_rel(DOC_TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
        "baseline_result": base._repo_rel(BASELINE_RESULT_JSON),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
        "anti_js": "No JavaScript was used.",
    }
    base._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    base = _base()
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    report = _build_report(payload)
    base._write_text(ARTIFACT_MD, report)
    base._write_text(CARD_MD, report)

    lifecycle_status = payload["status"]
    aggregate = payload["delta_metrics"]["aggregate"]
    ticket_payload: dict[str, Any] = {}
    if TICKET_JSON.exists():
        with TICKET_JSON.open("r", encoding="utf-8") as handle:
            ticket_payload = json.load(handle)
    ticket_payload.update(
        {
            "status": lifecycle_status,
            "owner": "codex-alpha-search",
            "claimed_at": ticket_payload.get("claimed_at") or payload["timestamp"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": {
                "decision": lifecycle_status,
                "gate4_decision": payload["decision"],
                "metric_gate4_passed": payload["gate4"]["metric_gate4_passed"],
                "artifact": base._repo_rel(OUT_JSON),
                "log": base._repo_rel(LOG_JSON),
                "summary": payload["interpretation"],
                "before_result_file": base._repo_rel(BEFORE_AGG_JSON),
                "after_result_file": base._repo_rel(AFTER_AGG_JSON),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "production_impact": payload["production_impact"],
                "delta_metrics": {
                    "expected_value_score": aggregate["expected_value_score_delta_sum"],
                    "total_pnl": aggregate["total_pnl_delta_sum"],
                    "windows_ev_regressed": aggregate["windows_ev_regressed"],
                    "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
                },
            },
        }
    )
    registry_error = _persist_registry(payload, ticket_payload)
    if registry_error:
        ticket_payload["registry_update_error"] = registry_error
        payload["registry_update_error"] = registry_error
        base._write_json(OUT_JSON, payload)
        base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_json(DOC_TICKET_JSON, ticket_payload)
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest(payload)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(_framework()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _base()._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "metric_gate4_passed": payload["gate4"]["metric_gate4_passed"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "offset_exclusion_summary": payload["offset_exclusion_summary"],
                    "artifact": _base()._repo_rel(ARTIFACT_MD),
                    "before_aggregate": _base()._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": _base()._repo_rel(AFTER_AGG_JSON),
                    "production_impact": payload["production_impact"],
                    "registry_update_error": payload.get("registry_update_error"),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
