"""exp-20260607-025: PEAD broad universe historical replay.

Replay alpha search for the existing production-visible
PEAD_BROAD_UNIVERSE_PAPER helper. The decision variable is whether the
already-shared positive-EPS-surprise broad-universe candidate source adds
replacement value across the three canonical windows.

No production code, live/default orders, ranking, sizing, exits, LLM/news path,
or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
import pead_broad_universe_paper_sleeve as pead
from pead_broad_universe_tickers import get_pead_broad_universe_tickers


EXPERIMENT_ID = "exp-20260607-025"
STEM = "pead_broad_universe_historical_replay"
TRIAL_FAMILY = "pead_broad_universe_historical_candidate_pool"
TRIAL_VARIANT_ID = "pead_broad_universe_eps_surprise_only_existing_helper_10d_v1"
CHANGED_VARIABLE = "pead_broad_universe_historical_replay_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_025_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = framework.WINDOWS
WAREHOUSE = framework.WAREHOUSE

HELPER_CONFIG = deepcopy(pead.DEFAULT_CONFIG)
BASE_NOTIONAL_USD = float(HELPER_CONFIG["paper_notional_usd"])
HOLD_DAYS = int(HELPER_CONFIG["hold_days"])
MAX_PAPER_TRADES_PER_DAY = int(HELPER_CONFIG["daily_entry_slots"])
MAX_ACTIVE_POSITIONS = int(HELPER_CONFIG["max_active_positions"])

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "large_gap_chase",
        "thin_sample",
        "concentration_failed",
        "earnings_snapshot_transition_artifacts",
    ],
    "confidence_reason": (
        "The helper is already production-visible and uses local daily "
        "earnings snapshot transitions plus free OHLCV. Narrower PEAD worked "
        "before, but broad EPS-surprise-only PEAD can become gap-chasing, and "
        "peer-transfer PEAD neighbors failed."
    ),
    "recorded_at": "2026-06-07T21:05:54Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "existing_shared_default_off_adapter_replayed_no_promotion",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "replay_uses_existing_daily_helper": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "daily_helper": "quant/pead_broad_universe_paper_sleeve.py",
    "daily_snapshot_function": "build_pead_broad_universe_paper_sleeve_snapshot",
    "production_consistency_note": (
        "Historical replay calls the same default-off PEAD broad helper used by "
        "daily snapshots with the same config, next-open pending-entry fill, "
        "10-trading-day exit, slippage, costs, max-active capacity, and "
        "trade_enabled=False. This experiment changes no production surface."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _write_json(path: Path, payload: Any) -> None:
    framework._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    framework._write_text(path, text)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < len(WINDOWS):
        failed.append("not_all_windows_ev_improved")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_existing_shared_default_off_pead_broad_historical_replay"
            if passed
            else "rejected_pead_broad_universe_historical_replay"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _copy_closed_trade(row: dict[str, Any], window_end: str) -> dict[str, Any] | None:
    candidate = row.get("candidate") or {}
    signal_date = str(candidate.get("date") or candidate.get("event_confirmed_date") or "")
    exit_date = str(row.get("exit_date") or "")
    if not signal_date or not exit_date:
        return None
    if exit_date > window_end:
        return None
    copied = deepcopy(row)
    copied["signal_date"] = signal_date
    copied["source"] = "PEAD_BROAD_UNIVERSE_PAPER"
    copied["paper_notional_usd"] = copied.get("notional")
    copied["pnl_pct_net"] = copied.get("return_pct_net")
    copied["known_at"] = candidate.get("known_at")
    copied["rule_version"] = RULE_VERSION
    copied["helper_rule_version"] = pead.RULE_VERSION
    return copied


def _replay_pead_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]],
    candidate_universe: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    state = pead.empty_pead_broad_universe_paper_state()
    all_dates = framework.shadow._trading_dates(snapshot)
    replay_dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    carry_dates = [
        date_value
        for date_value in all_dates
        if str(cfg["end"]) < date_value
    ][: HOLD_DAYS + 5]
    raw_candidate_counts: Counter[str] = Counter()
    reject_counts: Counter[str] = Counter()
    candidate_samples: list[dict[str, Any]] = []
    closed_samples: list[dict[str, Any]] = []
    daily_snapshots: list[dict[str, Any]] = []
    closed_history: list[dict[str, Any]] = []
    skipped_history: list[dict[str, Any]] = []

    for as_of in [*replay_dates, *carry_dates]:
        active_universe = candidate_universe if as_of <= str(cfg["end"]) else []
        snapshot_today = pead.build_pead_broad_universe_paper_sleeve_snapshot(
            as_of=as_of,
            ohlcv_by_ticker=snapshot,
            candidate_universe=active_universe,
            earnings_index=earnings_index,
            state=state,
            config=HELPER_CONFIG,
            persist=False,
        )
        closed_today = deepcopy(snapshot_today.get("closed_positions_today") or [])
        skipped_today = deepcopy(snapshot_today.get("skipped_entries_today") or [])
        closed_history.extend(closed_today)
        skipped_history.extend(skipped_today)
        state = pead.empty_pead_broad_universe_paper_state()
        state["pending_entries"] = deepcopy(snapshot_today.get("pending_entries") or [])
        state["open_positions"] = deepcopy(snapshot_today.get("open_positions") or [])
        state["closed_positions"] = closed_history
        state["skipped_entries"] = skipped_history
        if as_of <= str(cfg["end"]):
            raw_candidate_counts["raw_candidate_rows"] += int(
                snapshot_today.get("raw_candidate_count") or 0
            )
            raw_candidate_counts["candidate_rows_after_daily_limit"] += int(
                snapshot_today.get("candidate_count") or 0
            )
            if int(snapshot_today.get("raw_candidate_count") or 0) > 0:
                raw_candidate_counts["candidate_days"] += 1
            for reason, count in (snapshot_today.get("candidate_reject_counts") or {}).items():
                reject_counts[str(reason)] += int(count or 0)
            if len(candidate_samples) < 80:
                candidate_samples.extend(
                    deepcopy(snapshot_today.get("raw_candidates_sample") or [])[
                        : max(0, 80 - len(candidate_samples))
                    ]
                )
        if len(closed_samples) < 80:
            closed_samples.extend(closed_today[: max(0, 80 - len(closed_samples))])
        if len(daily_snapshots) < 30 and (
            snapshot_today.get("raw_candidate_count")
            or snapshot_today.get("closed_count_today")
            or snapshot_today.get("filled_count")
        ):
            daily_snapshots.append(
                {
                    "asof_date": snapshot_today.get("asof_date"),
                    "raw_candidate_count": snapshot_today.get("raw_candidate_count"),
                    "candidate_count": snapshot_today.get("candidate_count"),
                    "new_pending_count": snapshot_today.get("new_pending_count"),
                    "filled_count": snapshot_today.get("filled_count"),
                    "closed_count_today": snapshot_today.get("closed_count_today"),
                    "pending_count": snapshot_today.get("pending_count"),
                    "open_position_count": snapshot_today.get("open_position_count"),
                    "closed_position_count": snapshot_today.get("closed_position_count"),
                    "realized_pnl_to_date": snapshot_today.get("realized_pnl_to_date"),
                }
            )

    closed_trades = [
        copied
        for row in closed_history
        if (copied := _copy_closed_trade(row, str(cfg["end"]))) is not None
    ]
    scan = {
        "scanned_trading_days": len(replay_dates),
        "carry_forward_days_for_closure": len(carry_dates),
        "raw_candidate_rows": int(raw_candidate_counts["raw_candidate_rows"]),
        "candidate_rows_after_daily_limit": int(
            raw_candidate_counts["candidate_rows_after_daily_limit"]
        ),
        "candidate_days": int(raw_candidate_counts["candidate_days"]),
        "selected_closed_trade_count": len(closed_trades),
        "unique_closed_trade_tickers": len({row.get("ticker") for row in closed_trades}),
        "state_closed_positions_total": len(state.get("closed_positions") or []),
        "open_positions_left_after_replay": len(state.get("open_positions") or []),
        "pending_entries_left_after_replay": len(state.get("pending_entries") or []),
        "candidate_reject_counts": dict(sorted(reject_counts.items())),
        "helper_rule_version": pead.RULE_VERSION,
        "config": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
            "max_active_positions": MAX_ACTIVE_POSITIONS,
            "hold_days": HOLD_DAYS,
            "min_latest_surprise_pct": HELPER_CONFIG["min_latest_surprise_pct"],
            "max_earnings_day_gap_pct": HELPER_CONFIG["max_earnings_day_gap_pct"],
            "min_avg_dollar_volume_20d": HELPER_CONFIG["min_avg_dollar_volume_20d"],
        },
    }
    return closed_trades, scan, candidate_samples, daily_snapshots


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    core_universe = sorted(framework.get_universe())
    candidate_universe = get_pead_broad_universe_tickers()
    earnings_index = pead.load_earnings_snapshot_index()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    pead_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    candidate_samples_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    daily_snapshot_samples_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and PEAD broad helper replay")
        before_result = framework.shadow._run_baseline(core_universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(candidate_universe),
        )
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "candidate_universe_count": len(candidate_universe),
            "loaded_candidate_ticker_count": len(set(snapshot).intersection(candidate_universe)),
            "source": _repo_rel(WAREHOUSE),
        }
        selected_trades, scan, candidate_samples, daily_snapshot_samples = _replay_pead_window(
            snapshot=snapshot,
            cfg=cfg,
            earnings_index=earnings_index,
            candidate_universe=candidate_universe,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        pead_scan_by_window[label] = scan
        candidate_samples_by_window[label] = candidate_samples[:80]
        daily_snapshot_samples_by_window[label] = daily_snapshot_samples
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": scan["raw_candidate_rows"],
            "raw_candidate_days": scan["candidate_days"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework.sleeve._aggregate(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    old_thin_delta = framework.overlay_helper._delta(
        after_metrics["old_thin"], before_metrics["old_thin"]
    )
    total_trade_count = target_summary["total_trade_count"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1 if gate4["passed"] else 0,
        "actual_gate4_passed": gate4["passed"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (
                PREDICTION["success_probability"]
                - (1.0 if gate4["passed"] else 0.0)
            )
            ** 2,
            6,
        ),
    }
    negative_reflection = (
        "If rejected, the likely reason is that broad EPS-surprise-only PEAD "
        "is already priced by the next open for many large-cap reports, while "
        "the 5% gap-cancel and no-RS/no-MA design still admit mixed-quality "
        "post-report drift. Do not retry by sweeping surprise, gap, notional, "
        "hold-day, daily-slot, or liquidity thresholds on these frozen windows."
    )
    post_run_reflection = {
        "why_result_happened": (
            "Gate 4 observed {count} closed target trades; old_thin changed by "
            "{ev:+.4f} EV and ${pnl:+,.2f}. The evidence suggests the broad "
            "direct issuer PEAD source is {result} as a replacement-value "
            "candidate pool under the existing helper semantics."
        ).format(
            count=total_trade_count,
            ev=old_thin_delta["expected_value_score"],
            pnl=old_thin_delta["total_pnl"],
            result="credible" if gate4["passed"] else "not credible",
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by tuning min surprise, gap-cancel, hold days, "
            "daily slots, max active positions, notional, or liquidity on the "
            "same frozen windows."
        ),
        "new_evidence_required": (
            "A retry after rejection needs a materially new PIT earnings data "
            "edge: revision trajectory, analyst estimate dispersion, call "
            "tone, guidance classification, or closed forward replacement rows."
        ),
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "The existing broad-universe PEAD default-off helper may surface "
            "replacement-value positive-EPS-surprise candidates across the "
            "three canonical windows because direct issuer earnings surprise "
            "is a slower semantic/flow event than raw same-day OHLCV momentum."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_earnings_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260604-021",
            "exp-20260607-003",
            "exp-20260602-026",
            "exp-20260607-013",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "existing_forward_shared_helper_tested_on_three_canonical_windows",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "existing PEAD_BROAD_UNIVERSE_PAPER helper historical overlay"
            ),
            "windows": WINDOWS,
            "baseline_result_file": (
                "data/backtests/"
                "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "candidate_ohlcv_source": _repo_rel(WAREHOUSE),
            "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal is produced after a local earnings snapshot transition "
                "confirms a positive EPS surprise. Paper entry is next "
                "available open using the PEAD helper pending-entry fill model; "
                "exit is after 10 observed trading days using target-side sell "
                "slippage and ROUND_TRIP_COST_PCT. trade_enabled remains False."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
            "max_active_positions": MAX_ACTIVE_POSITIONS,
            "min_latest_surprise_pct": HELPER_CONFIG["min_latest_surprise_pct"],
            "min_avg_historical_surprise_pct": HELPER_CONFIG[
                "min_avg_historical_surprise_pct"
            ],
            "min_positive_surprise_count": HELPER_CONFIG["min_positive_surprise_count"],
            "min_surprise_history_count": HELPER_CONFIG["min_surprise_history_count"],
            "min_price": HELPER_CONFIG["min_price"],
            "min_avg_dollar_volume_20d": HELPER_CONFIG["min_avg_dollar_volume_20d"],
            "max_earnings_day_gap_pct": HELPER_CONFIG["max_earnings_day_gap_pct"],
            "single_causal_variable": CHANGED_VARIABLE,
            "helper_rule_version": pead.RULE_VERSION,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool: direct issuer positive EPS surprise may "
                "continue after the next open, and the existing broad helper "
                "expands candidates without adding noise-only tickers."
            ),
            "2_history_check": {
                "exp-20260604-021": (
                    "Created the PEAD broad default-off helper for forward "
                    "observation, but did not provide a canonical three-window "
                    "historical replay result."
                ),
                "exp-20260607-003": (
                    "Expanded PEAD broad data coverage to roughly 500 tickers; "
                    "it remained forward-observation rather than accepted alpha."
                ),
                "exp-20260602-026": (
                    "Accepted a narrower underpriced post-earnings drift sleeve; "
                    "this tests the broader direct surprise source without MA/RS "
                    "prefilters."
                ),
                "exp-20260607-013": (
                    "Rejected PEAD peer-transfer continuation; this experiment "
                    "uses direct issuer surprises, not peer inference."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows. Accept only "
                "if aggregate EV/PnL improve, all windows improve EV, no PnL "
                "regression window, target sample >=20 across all 3 windows, "
                "survival >=5%, drawdown drift <=0.5pp, and concentration pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260607_025_pead_broad_universe_historical_replay.py"
            ),
        },
        "pre_run_questions": None,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "data/backtests/"
                "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "data/daily/snapshots/earnings earnings snapshot transition rows",
                "PEAD broad helper candidate fields",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "passed": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            )
            >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The PEAD broad "
                "historical source is additive default-off paper replay of an "
                "existing daily helper, so core signals generated/survived are "
                "unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "pead_scan_by_window": pead_scan_by_window,
        "candidate_samples_by_window": candidate_samples_by_window,
        "daily_snapshot_samples_by_window": daily_snapshot_samples_by_window,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The existing PEAD broad helper cleared Gate 4 as an accepted "
            "shared default-off historical lead. No production behavior was "
            "promoted and trade_enabled remains False."
            if gate4["passed"]
            else (
                "The existing PEAD broad helper did not clear Gate 4 on the "
                "canonical windows. Keep the forward observer default-off and "
                "do not promote or retune this EPS-surprise-only source on the "
                "same frozen windows."
            )
        ),
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "negative_reflection": negative_reflection,
        "post_run_reflection": post_run_reflection,
        "next_evidence_needed": post_run_reflection["new_evidence_required"],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | PEAD days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["pead_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("candidate_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} PEAD Broad Universe Historical Replay",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
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
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only measurement of the existing shared default-off "
                "PEAD broad helper. No production code, run adapter, "
                "watchlist, order path, core entry, ranking, sizing, or exit "
                "behavior changed. trade_enabled remains false."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_earnings_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "pead_candidate_day_count": payload["pead_scan_by_window"][label][
                    "candidate_days"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(_safe(registry), ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
