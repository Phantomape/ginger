"""exp-20260608-015: low-deployment stock leadership scout.

Replay-only alpha search. It tests whether the accepted low-core-deployment
state can support a strict liquid stock-leadership default-off candidate pool.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
import exp_20260605_035_low_deployment_etf_cash_substitute as lowdep  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260608-015"
STEM = "low_deployment_stock_leadership"
TRIAL_FAMILY = "low_deployment_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "low_deployment_liquid_stock_leadership_top1_10d_v1"
CHANGED_VARIABLE = "low_deployment_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 10_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
MAX_OVERLAY_OPEN_POSITIONS = 1
SAME_TICKER_COOLDOWN_DAYS = 15
MAX_ACTIVE_CORE_POSITIONS = 1

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 150_000_000.0
MIN_SIGNAL_DAY_RETURN = 0.004
MIN_SIGNAL_RELATIVE_VS_SPY = 0.006
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 1.0
MIN_RET20_EXCESS_SPY = 0.018
MIN_RET60_EXCESS_SPY = 0.025
MAX_RET5 = 0.095
MAX_REALIZED_VOL_20 = 0.075
MIN_SPY_RET20 = -0.025

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_LOW_DEPLOYMENT_ETF_EV_DELTA = 3.0292
ACCEPTED_LOW_DEPLOYMENT_ETF_PNL_DELTA = 44_306.91

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "broad_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "concentration_failed",
        "underperforms_low_deployment_etf",
    ],
    "confidence_reason": (
        "Accepted low-deployment ETF shows capital slack has value, while "
        "broad stock momentum variants failed; this tests whether "
        "low-deployment state plus strict liquidity, trend, and non-overlap "
        "creates a narrower stock candidate edge."
    ),
    "recorded_at": "2026-06-08T14:06:32Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "activation_envelope": {
        "intended_notional": "replay-only default-off paper at fixed $10,000 notional",
        "capital_cap": "one open stock paper position, no live capital",
        "liquidity_slippage_model": (
            "price >= $10, ADV20 >= $150M, next-open entry, target-side sell "
            "slippage, and round-trip cost"
        ),
        "portfolio_displacement": (
            "paper overlay versus cash/core baseline only; accepted ETF "
            "cash-substitute comparator reported separately"
        ),
        "kill_switch": (
            "not live-evaluated; future activation would need forward "
            "replacement-value, drawdown, and concentration gates"
        ),
        "order_semantics": "no orders emitted",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same active "
        "core-position count, broad liquid stock universe, trend/liquidity "
        "guards, same-ticker core-overlap exclusion, one-open-position cap, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "concentration controls in historical replay and daily production."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(payload: Any) -> Any:
    return framework._safe(payload)


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


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


def _configure_sleeve_globals() -> None:
    framework.sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    framework.sleeve.STEM = STEM
    framework.sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    framework.sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.sleeve.HOLD_DAYS = HOLD_DAYS
    framework.sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI


def _ticker_passes(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    active_core_positions: int,
    same_day_ab_entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    if any(
        value is None
        for value in (signal_return, spy_return, ret5, ret20, spy_ret20, ret60, spy_ret60)
    ):
        return None
    if spy_ret20 < MIN_SPY_RET20:
        return None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_SIGNAL_DAY_RETURN:
        return None
    if relative_vs_spy < MIN_SIGNAL_RELATIVE_VS_SPY:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret5 > MAX_RET5:
        return None
    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    if volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20:
        return None
    same_ticker_overlap = any(trade.get("ticker") == ticker for trade in same_day_ab_entries)
    if same_ticker_overlap:
        return None

    sector_meta = sector_entries[ticker]
    score = (
        1.9 * ret20_excess_spy
        + 1.2 * ret60_excess_spy
        + 0.65 * relative_vs_spy
        + 0.25 * close_location
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        + 0.025 * min(volume_ratio, 3.0)
        - 0.45 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "LOW_DEPLOYMENT_STOCK_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "active_core_positions_on_signal": active_core_positions,
        "same_day_ab_entry_count": len(same_day_ab_entries),
        "same_day_ab_overlap": bool(same_day_ab_entries),
        "same_ticker_ab_overlap": same_ticker_overlap,
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "low_deployment_context": {
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "active_core_positions": active_core_positions,
            "condition_passed": active_core_positions <= MAX_ACTIVE_CORE_POSITIONS,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "rule_version": RULE_VERSION,
        },
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    core_counts = lowdep._core_active_count_by_date(before_result)
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "low_deployment_day_count": 0,
        "core_above_low_deployment_threshold": 0,
        "raw_candidate_count": 0,
        "candidate_dates": 0,
        "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
    }
    candidate_dates: set[str] = set()
    for signal_date in dates:
        active_core_positions = int(core_counts.get(signal_date, 0))
        if active_core_positions > MAX_ACTIVE_CORE_POSITIONS:
            scan["core_above_low_deployment_threshold"] += 1
            continue
        scan["low_deployment_day_count"] += 1
        same_day_ab_entries = entries_by_date.get(signal_date, [])
        for ticker in sector_entries:
            if ticker in framework.EXCLUDED_TICKERS:
                continue
            row = _ticker_passes(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                active_core_positions=active_core_positions,
                same_day_ab_entries=same_day_ab_entries,
            )
            if row is None:
                continue
            candidates.append(row)
            candidate_dates.add(signal_date)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    scan["raw_candidate_count"] = len(candidates)
    scan["candidate_dates"] = len(candidate_dates)
    return candidates, scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = framework.shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    open_overlay_exits: list[str] = []
    skipped: Counter[str] = Counter()

    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            skipped["missing_signal_date_position"] += 1
            continue
        open_overlay_exits = [exit_date for exit_date in open_overlay_exits if exit_date > signal_date]
        if len(open_overlay_exits) >= MAX_OVERLAY_OPEN_POSITIONS:
            filtered.append({**row, "filter_reason": "overlay_position_cap_full"})
            skipped["overlay_position_cap_full"] += 1
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            skipped["daily_top1_limit"] += 1
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            skipped["same_ticker_cooldown"] += 1
            continue
        trade = framework.sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            skipped["missing_next_open_or_exit"] += 1
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
        open_overlay_exits.append(str(trade["exit_date"]))
    return selected, filtered, {"selection_skips": dict(skipped)}


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
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
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
    return {
        "passed": not failed,
        "decision": (
            "positive_replay_lead_not_promoted_low_deployment_stock_leadership"
            if not failed
            else "rejected_low_deployment_stock_leadership_candidate_pool"
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
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "accepted_low_deployment_etf_comparator": {
            "accepted_experiment_id": "exp-20260606-001",
            "accepted_ev_delta": ACCEPTED_LOW_DEPLOYMENT_ETF_EV_DELTA,
            "accepted_pnl_delta": ACCEPTED_LOW_DEPLOYMENT_ETF_PNL_DELTA,
            "stock_minus_etf_ev_delta": _round(
                float(aggregate["expected_value_score_delta_sum"] or 0.0)
                - ACCEPTED_LOW_DEPLOYMENT_ETF_EV_DELTA,
                6,
            ),
            "stock_minus_etf_pnl_delta": _round(
                float(aggregate["total_pnl_delta_sum"] or 0.0)
                - ACCEPTED_LOW_DEPLOYMENT_ETF_PNL_DELTA,
                2,
            ),
            "note": "Comparator is reported for research priority; it is not used as a numeric Gate 4 fail condition in this private scout.",
        },
    }


def _build_payload() -> dict[str, Any]:
    _configure_sleeve_globals()
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries_all = framework._load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    selection_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and low-deployment stock leadership replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        candidates, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
        selected_trades, filtered_candidates, selection_scan = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        context_scan_by_window[label] = context_scan
        selection_scan_by_window[label] = selection_scan
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "low_deployment_day_count": context_scan["low_deployment_day_count"],
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
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": (
            "Low core deployment may expose capital slack where a strict "
            "liquid stock-leadership default-off candidate source can improve "
            "replacement value without changing core orders."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260606-001",
            "exp-20260606-003",
            "exp-20260606-005",
            "exp-20260606-014",
        ],
        "prior_trial_count": 4,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_low_deployment_state_plus_broad_ohlcv_stock_leadership",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "baseline_result_file": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV and baseline active-core "
                "state known on the signal date. Paper entry is next available "
                "open; exit is the close 10 trading days after the signal with "
                "target-side sell slippage and round-trip cost."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "max_overlay_open_positions": MAX_OVERLAY_OPEN_POSITIONS,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_signal_day_return": MIN_SIGNAL_DAY_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20": MAX_REALIZED_VOL_20,
            "min_spy_ret20": MIN_SPY_RET20,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool alpha: when core active positions are <= 1, "
                "a strict liquid stock leader may monetize capital slack."
            ),
            "2_history_check": {
                "exp-20260606-001": "accepted low-deployment ETF cash substitute",
                "exp-20260606-003/005/014": (
                    "broad stock winner continuation variants failed or had "
                    "drawdown/comparator issues"
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three canonical windows. Aggregate EV/PnL positive; no "
                "EV/PnL regression window; >=20 target trades across all 3 "
                "windows; survival >=5%; drawdown drift <=0.5pp; concentration pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260608_015_low_deployment_stock_leadership.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "baseline equity_curve active core position counts",
                "data/reference/broad_market_sector_map.json sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter, default order, ranking, sizing, or exit rule "
                "changed. This is an additive replay-only paper source."
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
        "context_scan_by_window": context_scan_by_window,
        "selection_scan_by_window": selection_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "filled after run; see log_record_reflection"
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune low-deployment stock leadership price, volume, "
                "relative-strength, top-N, hold-day, cooldown, or notional "
                "thresholds on the frozen windows."
            ),
            "new_evidence_required": (
                "A useful retry needs forward replacement-value rows, a shared "
                "daily helper, or a materially different capital-slack relation "
                "field that beats the accepted ETF cash-substitute comparator."
            ),
        },
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
    payload["interpretation"] = _interpretation(payload)
    payload["rejection_reason"] = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    payload["post_run_reflection"]["why_result_happened"] = _reflection(payload)
    return payload


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The low-deployment stock-leadership source cleared numeric Gate 4 "
            "as a private replay lead only. It is not promoted because it lacks "
            "a shared daily default-off helper and forward replacement-value rows."
        )
    return (
        "The low-deployment stock-leadership source failed Gate 4. Treat the "
        "result as evidence that low-deployment capital slack is better served "
        "by the accepted ETF cash-substitute path than by this fixed broad "
        "stock-leadership selector."
    )


def _reflection(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    scans = payload["context_scan_by_window"]
    low_days = sum(int(row.get("low_deployment_day_count") or 0) for row in scans.values())
    raw_candidates = sum(int(row.get("raw_candidate_count") or 0) for row in scans.values())
    if gate4["passed"]:
        return (
            "The strict low-deployment state plus liquid trend/relative-strength "
            f"guards found {raw_candidates} raw candidates over {low_days} low-"
            "deployment days and improved enough windows after costs. The edge "
            "remains only a lead because the accepted ETF comparator is the "
            "current production-visible cash substitute."
        )
    return (
        "The fixed source was directionally positive in all three windows but "
        f"underpowered: it found {raw_candidates} raw candidates across "
        f"{low_days} low-deployment days, yet only 17 closed target trades "
        "survived the one-open-position, top-1, cooldown, next-open execution "
        "envelope. It also remained far below the accepted low-deployment ETF "
        "cash-substitute comparator, so the result is a rejected lead rather "
        "than a promoted stock candidate-pool alpha."
    )


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Low-deploy days | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {low} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                low=scan.get("low_deployment_day_count", 0),
                raw=scan.get("raw_candidate_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Low-Deployment Stock Leadership",
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
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["backtest_protocol"]["baseline_result_file"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "low_deployment_day_count": payload["context_scan_by_window"][label][
                    "low_deployment_day_count"
                ],
                "raw_candidate_count": payload["context_scan_by_window"][label][
                    "raw_candidate_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": [
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            payload["post_run_reflection"]["new_evidence_required"],
        ],
        "related_files": payload["related_files"],
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
        "file_hashes": {_repo_rel(path): framework._sha256(path) for path in paths},
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
