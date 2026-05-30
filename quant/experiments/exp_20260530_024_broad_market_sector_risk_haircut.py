"""exp-20260530-024: broad-market sector-risk paper haircut scout.

Alpha search. This keeps the accepted broad-market paper candidate definition,
ranking, slots, hold period, and current accepted notional stack fixed, then
changes one variable: already-selected paper candidates in a predeclared weak
sector-risk bucket receive a 0.75x paper-notional haircut.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260530-024"
EXPERIMENT_SLUG = "broad_market_sector_risk_haircut"
BASELINE_EXPERIMENT_ID = "exp-20260519-033"
CURRENT_BROAD_MARKET_BASELINE = "current_accepted_broad_market_stack_through_exp_20260520_004"
SECTOR_HAIRCUT_RULE_VERSION = "broad_market_negative_sector_notional_haircut_v1"

WEAK_SECTOR_BUCKETS = frozenset({"Healthcare", "Energy", "Financial Services"})
WEAK_SECTOR_HAIRCUT_SCALAR = 0.75

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as parent  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    RULE_VERSION as BROAD_MARKET_RULE_VERSION,
    backtest_trade_from_feature,
    build_broad_market_feature,
    candidate_passes_profile,
    select_broad_market_features,
)


WINDOWS = parent.WINDOWS
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260530_024_{EXPERIMENT_SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

PROFILE_CONFIG = {
    **DEFAULT_CONFIG,
    "ret20_excess_spy_min": 0.035,
    "ret60_min": 0.08,
    "near_high_60_min": 0.93,
    "volume_ratio_20_min": 1.00,
    "decision_close_price_min": 40.0,
    "paper_notional_usd": 7_500.0,
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _apply_sector_haircut(trade: dict[str, Any]) -> dict[str, Any]:
    sector = trade.get("sector")
    adjusted = dict(trade)
    before_notional = float(adjusted.get("notional") or 0.0)
    net_return = float(adjusted.get("net_return_pct") or 0.0)
    if sector in WEAK_SECTOR_BUCKETS and before_notional > 0:
        after_notional = round(before_notional * WEAK_SECTOR_HAIRCUT_SCALAR, 2)
        entry_open = float(adjusted.get("entry_open") or 0.0)
        adjusted.update(
            {
                "notional_before_sector_haircut": round(before_notional, 2),
                "notional": after_notional,
                "pnl_before_sector_haircut": adjusted.get("pnl"),
                "pnl": round(after_notional * net_return, 2),
                "shares": round(after_notional / entry_open, 8) if entry_open > 0 else adjusted.get("shares"),
                "broad_market_sector_risk_haircut_applied": True,
                "broad_market_sector_risk_haircut_scalar": WEAK_SECTOR_HAIRCUT_SCALAR,
                "broad_market_sector_risk_haircut_rule_version": SECTOR_HAIRCUT_RULE_VERSION,
                "broad_market_sector_risk_bucket": "weak_historical_sector_bucket",
            }
        )
    else:
        adjusted.update(
            {
                "notional_before_sector_haircut": round(before_notional, 2),
                "pnl_before_sector_haircut": adjusted.get("pnl"),
                "broad_market_sector_risk_haircut_applied": False,
                "broad_market_sector_risk_haircut_scalar": 1.0,
                "broad_market_sector_risk_haircut_rule_version": SECTOR_HAIRCUT_RULE_VERSION,
                "broad_market_sector_risk_bucket": "not_targeted",
            }
        )
    return adjusted


def _simulate_window(
    *,
    label: str,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    apply_haircut: bool,
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = parent._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    trades: list[dict[str, Any]] = []
    daily_counts: dict[str, int] = {}

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(PROFILE_CONFIG["max_active_positions"]) - len(active)
        if capacity <= 0:
            continue
        active_tickers = {row["ticker"] for row in active}
        features: list[dict[str, Any]] = []
        for ticker in candidate_tickers:
            if ticker in active_tickers:
                continue
            rows = prices.get(ticker) or []
            idx = (indexes.get(ticker) or {}).get(day)
            if idx is None:
                continue
            feature = build_broad_market_feature(
                ticker=ticker,
                rows=rows,
                idx=idx,
                spy_rows=spy_rows,
                spy_index=spy_index,
            )
            if feature and candidate_passes_profile(feature, PROFILE_CONFIG):
                features.append(feature)

        selected = select_broad_market_features(
            features,
            capacity=capacity,
            config=PROFILE_CONFIG,
        )
        for rank, feature in enumerate(selected, start=1):
            trade = backtest_trade_from_feature(
                feature=feature,
                prices_by_ticker=prices,
                window_end=spec["end"],
                rank=rank,
                config=PROFILE_CONFIG,
            )
            if trade is None:
                continue
            trade["window"] = label
            if apply_haircut:
                trade = _apply_sector_haircut(trade)
            else:
                trade["broad_market_sector_risk_haircut_applied"] = False
            trades.append(trade)
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])
        daily_counts[day] = len(features)

    return {
        "window": label,
        "trades": trades,
        "candidate_signal_days": sum(1 for count in daily_counts.values() if count > 0),
        "candidate_signal_count": sum(daily_counts.values()),
        "max_daily_candidate_count": max(daily_counts.values()) if daily_counts else 0,
    }


def _metrics_for_trades(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = OrderedDict()
    for label, spec in WINDOWS.items():
        trades = trades_by_window[label]
        curve = parent._event_equity_curve(
            trades=trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        metrics[label] = parent._metrics_from_overlay(
            baseline_metrics=baseline_metrics[label],
            event_curve=curve,
            event_trades=trades,
        )
    return metrics


def _sector_summary(trades: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "trade_count": 0,
            "pnl": 0.0,
            "adjusted_trade_count": 0,
            "pnl_before_sector_haircut": 0.0,
            "notional_before_sector_haircut": 0.0,
            "notional_after_sector_haircut": 0.0,
        }
    )
    for trade in trades:
        sector = str(trade.get("sector") or "Unknown")
        row = summary[sector]
        row["trade_count"] += 1
        row["pnl"] = round(float(row["pnl"]) + float(trade.get("pnl") or 0.0), 2)
        row["pnl_before_sector_haircut"] = round(
            float(row["pnl_before_sector_haircut"])
            + float(trade.get("pnl_before_sector_haircut") or trade.get("pnl") or 0.0),
            2,
        )
        row["notional_before_sector_haircut"] = round(
            float(row["notional_before_sector_haircut"])
            + float(trade.get("notional_before_sector_haircut") or trade.get("notional") or 0.0),
            2,
        )
        row["notional_after_sector_haircut"] = round(
            float(row["notional_after_sector_haircut"]) + float(trade.get("notional") or 0.0),
            2,
        )
        if trade.get("broad_market_sector_risk_haircut_applied"):
            row["adjusted_trade_count"] += 1
    return dict(sorted(summary.items()))


def _positive_hhi(trades: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = defaultdict(float)
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl > 0:
            by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(sum((value / total) ** 2 for value in by_ticker.values()), 6)


def build_payload() -> dict[str, Any]:
    gate2 = parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = parent._json_load(parent.BASELINE_JSON)
    baseline_metrics = baseline_payload["after_metrics"]
    universe_state = parent._load_tradeable_universe()
    tradeable_universe = set(universe_state["excluded_tradeable_universe"])
    warehouse = parent._warehouse_audit()
    candidate_universe = parent._candidate_universe(tradeable_universe)
    prices = parent._load_price_rows(candidate_universe["tickers"])
    indexes = parent._index_by_date(prices)

    before_scouts: dict[str, dict[str, Any]] = OrderedDict()
    after_scouts: dict[str, dict[str, Any]] = OrderedDict()
    before_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    after_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    for label in WINDOWS:
        before_scout = _simulate_window(
            label=label,
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
            apply_haircut=False,
        )
        after_scout = _simulate_window(
            label=label,
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
            apply_haircut=True,
        )
        before_scouts[label] = before_scout
        after_scouts[label] = after_scout
        before_trades_by_window[label] = before_scout["trades"]
        after_trades_by_window[label] = after_scout["trades"]

    before_metrics = _metrics_for_trades(
        baseline_metrics=baseline_metrics,
        prices=prices,
        trades_by_window=before_trades_by_window,
    )
    after_metrics = _metrics_for_trades(
        baseline_metrics=baseline_metrics,
        prices=prices,
        trades_by_window=after_trades_by_window,
    )

    delta = parent._aggregate_delta(before_metrics, after_metrics)
    delta_vs_core_before = parent._aggregate_delta(baseline_metrics, before_metrics)
    delta_vs_core_after = parent._aggregate_delta(baseline_metrics, after_metrics)
    all_before_trades = [trade for rows in before_trades_by_window.values() for trade in rows]
    all_after_trades = [trade for rows in after_trades_by_window.values() for trade in rows]
    adjusted_trades = [
        trade for trade in all_after_trades if trade.get("broad_market_sector_risk_haircut_applied")
    ]
    adjusted_windows = sorted({trade["window"] for trade in adjusted_trades})
    selected_windows = sum(1 for rows in after_trades_by_window.values() if rows)

    sample_guard_passed = len(adjusted_trades) >= 8 and len(adjusted_windows) >= 2
    window_guard_passed = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= parent.MAX_DRAWDOWN_WORSE
    concentration = {
        "single_ticker_positive_share": parent._single_ticker_positive_share(all_after_trades),
        "top5_positive_share": parent._top5_positive_share(all_after_trades),
        "positive_pnl_hhi": _positive_hhi(all_after_trades),
        "single_ticker_positive_share_guardrail": parent.MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "top5_positive_share_guardrail": parent.MAX_TOP5_POSITIVE_SHARE,
        "positive_pnl_hhi_guardrail": 0.30,
    }
    concentration_guard_passed = (
        (concentration["single_ticker_positive_share"] is None
         or concentration["single_ticker_positive_share"] <= parent.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (concentration["top5_positive_share"] is None
             or concentration["top5_positive_share"] <= parent.MAX_TOP5_POSITIVE_SHARE)
        and (concentration["positive_pnl_hhi"] is None
             or concentration["positive_pnl_hhi"] <= concentration["positive_pnl_hhi_guardrail"])
    )
    gate4_passed = bool(
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and window_guard_passed
        and sample_guard_passed
        and drawdown_guard_passed
        and concentration_guard_passed
    )

    failed_reasons = []
    if delta["aggregate_ev_delta"] <= 0:
        failed_reasons.append("aggregate_ev_not_positive")
    if delta["aggregate_pnl_delta"] <= 0:
        failed_reasons.append("aggregate_pnl_not_positive")
    if not window_guard_passed:
        failed_reasons.append("window_stability_failed")
    if not sample_guard_passed:
        failed_reasons.append("adjusted_sample_guard_failed")
    if not drawdown_guard_passed:
        failed_reasons.append("drawdown_guard_failed")
    if not concentration_guard_passed:
        failed_reasons.append("concentration_guard_failed")

    decision = (
        "promising_requires_shared_adapter"
        if gate4_passed
        else "rejected_broad_market_sector_risk_haircut"
    )
    status = "observed_only" if gate4_passed else "rejected"
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "default_off_paper_only": True,
        "parity_test_added": False,
        "live_order_path_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Broad-market default-off paper candidates in historically weak "
            "sector-risk buckets may have lower replacement value; a sector-risk "
            "paper notional haircut can improve EV without adding tickers or "
            "changing live orders."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "default_off_paper_allocation",
        "trial_family": "broad_market_sector_risk_allocation",
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": "broad_market_negative_sector_notional_haircut_v1",
        "single_causal_variable": "broad_market_negative_sector_notional_haircut_v1",
        "nearby_prior_experiments": [
            "exp-20260525-038",
            "exp-20260524-027",
            "exp-20260528-036",
            "exp-20260519-036",
            "exp-20260520-004",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_sector_context",
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "before_stack": CURRENT_BROAD_MARKET_BASELINE,
            "broad_market_rule_version": BROAD_MARKET_RULE_VERSION,
            "sector_haircut_rule_version": SECTOR_HAIRCUT_RULE_VERSION,
            "weak_sector_buckets": sorted(WEAK_SECTOR_BUCKETS),
            "weak_sector_haircut_scalar": WEAK_SECTOR_HAIRCUT_SCALAR,
            "profile_config": {
                key: PROFILE_CONFIG[key]
                for key in (
                    "ret20_excess_spy_min",
                    "ret60_min",
                    "near_high_60_min",
                    "volume_ratio_20_min",
                    "decision_close_price_min",
                    "paper_notional_usd",
                    "rank_notional_multipliers",
                    "low_extension_ret5_max",
                    "low_extension_notional_scalar",
                    "high_volatility_20_min",
                    "high_volatility_notional_scalar",
                    "trend_persistence_positive_day_ratio_20_min",
                    "trend_persistence_notional_scalar",
                    "max_active_positions",
                    "daily_entry_slots",
                    "hold_days",
                )
            },
            "locked_variables": [
                "candidate universe",
                "candidate definition",
                "candidate ranking",
                "daily entry slots",
                "max active paper positions",
                "hold days",
                "current accepted broad-market rank/extension/volatility/persistence notional stack",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news",
                "live/default orders",
            ],
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"], "snapshot": row["snapshot"]}
            for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Before metrics "
            "are the current accepted broad-market paper stack through "
            "exp-20260520-004; after metrics apply only the predeclared sector-risk haircut."
        ),
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(parent.BASELINE_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "core_baseline_aggregate": parent._aggregate(baseline_metrics),
            "before_broad_market_aggregate": parent._aggregate(before_metrics),
            "known_measurement_boundary": "Historical broad-market replay uses exp-20260519-030 warehouse; no live order path changed.",
        },
        "gate2": {
            **gate2,
            "required_runtime_fields": [
                "operator_inputs/open_positions.json positions[].entry_date",
                "operator_inputs/open_positions.json positions[].target_price",
                "broad_market_paper_sleeve trade.sector",
                "broad_market_paper_sleeve trade.notional",
                "broad_market_paper_sleeve trade.net_return_pct",
            ],
            "llm_dependency": "none",
        },
        "gate3": {
            "new_core_filter_added": False,
            "core_survival_changed": False,
            "minimum_core_survival_rate": parent._aggregate(baseline_metrics)["survival_rate_min"],
            "passed": parent._aggregate(baseline_metrics)["survival_rate_min"] >= 0.05,
            "note": "Default-off paper allocation only; core signals_generated/signals_survived unchanged.",
        },
        "gate4": {
            "passed": gate4_passed,
            "failed_reasons": failed_reasons,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "windows_ev_improved": delta["windows_ev_improved"],
            "windows_ev_regressed": delta["windows_ev_regressed"],
            "windows_pnl_improved": delta["windows_pnl_improved"],
            "windows_pnl_regressed": delta["windows_pnl_regressed"],
            "adjusted_trade_count": len(adjusted_trades),
            "adjusted_trade_count_min": 8,
            "adjusted_windows": adjusted_windows,
            "adjusted_window_count_min": 2,
            "sample_guard_passed": sample_guard_passed,
            "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": parent.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
            "concentration": concentration,
            "concentration_guard_passed": concentration_guard_passed,
            "production_promotion_required_for_acceptance": True,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "delta_vs_core_before": delta_vs_core_before,
        "delta_vs_core_after": delta_vs_core_after,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        },
        "selected_trade_count": len(all_after_trades),
        "selected_windows": selected_windows,
        "adjusted_trade_count": len(adjusted_trades),
        "adjusted_ticker_count": len({trade["ticker"] for trade in adjusted_trades}),
        "before_sector_summary": _sector_summary(all_before_trades),
        "after_sector_summary": _sector_summary(all_after_trades),
        "before_sleeve": {
            label: parent._window_sleeve_summary(before_trades_by_window[label], before_scouts[label])
            for label in WINDOWS
        },
        "after_sleeve": {
            label: parent._window_sleeve_summary(after_trades_by_window[label], after_scouts[label])
            for label in WINDOWS
        },
        "adjusted_trades_sample": parent._trade_rows(adjusted_trades, limit=80),
        "all_after_trades_sample": parent._trade_rows(all_after_trades, limit=40),
        "event_risk_after": parent._event_risk(all_after_trades),
        "candidate_universe": candidate_universe,
        "warehouse_audit": warehouse,
        "prediction": {
            "success_probability": 0.27,
            "expected_ev_delta": None,
            "expected_pnl_delta": None,
            "main_failure_modes": [
                "late_strong_regression",
                "sector_overfit",
                "insufficient_all_window_improvement",
                "concentration_failed",
            ],
            "confidence_reason": (
                "Sector cache is production-visible and current_state explicitly "
                "unblocked sector-aware broad-market alpha hooks, but prior "
                "broad-market breadth gates and sector/market agreement regressed one window."
            ),
            "recorded_at": "2026-05-30T23:06:48+00:00",
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if gate4_passed else 0,
            "predicted_success_probability": 0.27,
            "brier_score": round((0.27 - (1 if gate4_passed else 0)) ** 2, 4),
            "expected_ev_delta": None,
            "actual_ev_delta": delta["aggregate_ev_delta"],
            "expected_pnl_delta": None,
            "actual_pnl_delta": delta["aggregate_pnl_delta"],
            "predicted_failure_modes": [
                "late_strong_regression",
                "sector_overfit",
                "insufficient_all_window_improvement",
                "concentration_failed",
            ],
            "realized_failure_mode": ";".join(failed_reasons) if failed_reasons else None,
            "predicted_failure_mode_hit": bool(set(failed_reasons) & {"window_stability_failed", "concentration_guard_failed"}),
        },
        "production_impact": production_impact,
        "preflight_questions": {
            "1_alpha_hypothesis": "capital allocation / candidate-pool quality: broad-market paper candidates in weak sector-risk buckets may have lower replacement value.",
            "2_history_check": "exp-20260525-038 made sector context available; exp-20260524-027 rejected broad candidate-count gates; exp-20260528-036 rejected sector/market breadth agreement due one-window regression; current accepted broad-market stack is through exp-20260520-004.",
            "3_single_causal_variable": "broad_market_negative_sector_notional_haircut_v1",
            "4_acceptance_standard": "Same three-window protocol; aggregate EV/PnL positive, no EV/PnL-regressed window, adjusted sample >=8 across >=2 windows, drawdown/concentration guards pass.",
            "5_reproducibility": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260530_024_broad_market_sector_risk_haircut.py",
        },
        "interpretation": (
            "This is a default-off replay scout only. A positive result cannot be "
            "retained as executable behavior until the same field is moved into "
            "shared broad_market_paper_sleeve.py with tests and parity docs."
        ),
        "rejection_reason": None
        if gate4_passed
        else ";".join(failed_reasons),
        "next_retry_requires": [
            "forward broad-market sector replacement-value rows",
            "a materially different sector/theme crowding field",
            "or shared adapter implementation if this replay-only result is later promoted",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            "quant/broad_market_paper_sleeve.py",
            "data/reference/broad_market_sector_map.json",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": 0,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def _card_markdown(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    lines = [
        "---",
        f'experiment_id: "{EXPERIMENT_ID}"',
        f'status: "{payload["status"]}"',
        'lane: "alpha_search"',
        'change_type: "default_off_paper_allocation"',
        'trial_family: "broad_market_sector_risk_allocation"',
        'changed_variable: "broad_market_negative_sector_notional_haircut_v1"',
        "---",
        "",
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        "## Summary",
        "",
        payload["hypothesis"],
        "",
        "## Result",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Aggregate EV delta vs current broad-market stack: `{gate4['aggregate_ev_delta']:+.4f}`",
        f"- Aggregate PnL delta vs current broad-market stack: `${gate4['aggregate_pnl_delta']:+,.2f}`",
        f"- Adjusted trades: `{gate4['adjusted_trade_count']}` across `{len(gate4['adjusted_windows'])}` windows",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        drow = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(drow["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(drow["total_pnl"]),
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Replay-only default-off paper scout. No shared policy, run adapter, live orders, core ranking, sizing, exits, or LLM/news path changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_markdown(payload: dict[str, Any]) -> str:
    return _card_markdown(payload) + "\n```json\n" + json.dumps(
        _safe(payload["gate4"]), indent=2, sort_keys=True
    ) + "\n```\n"


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _upsert_jsonl(EXPERIMENT_LOG, _log_payload(payload))
    CARD_MD.write_text(_card_markdown(payload), encoding="utf-8")
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "gate4": payload["gate4"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "output": _repo_rel(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
