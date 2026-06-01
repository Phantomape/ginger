"""exp-20260601-032: RS-line low-participation cooldown scout.

Replay-only alpha scout. It refines the rejected RS-line accepted-source
candidate pool by keeping only orderly participation breakouts and applying a
same-ticker de-clustering cooldown.

No production orders, ranking, sizing, exits, watchlists, LLM, or news paths
are changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_005_rs_line_accepted_source_consensus as source  # noqa: E402


EXPERIMENT_ID = "exp-20260601-032"
STEM = "rs_line_low_participation_cooldown"
TRIAL_FAMILY = "rs_line_accepted_source_low_participation_cooldown"
TRIAL_VARIANT_ID = "low_participation_lte_1p2_same_ticker_10d_cooldown"
CHANGED_VARIABLE = "rs_line_accepted_source_low_participation_cooldown_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = "exp-20260601-005"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260601_005_rs_line_accepted_source_consensus.json"
)

MAX_VOLUME_RATIO_20 = 1.20
SAME_TICKER_COOLDOWN_DAYS = 10
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 6.3596
CANONICAL_DOC_PNL = 192_538.61

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_032_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return source._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return source._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return source._repo_rel(path)


def _load_json(path: Path) -> Any:
    return source._load_json(path)


def _write_json(path: Path, payload: Any) -> None:
    source._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    source._write_text(path, text)


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _parse_day(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _row_date(row: dict[str, Any]) -> str:
    for key in ("signal_date", "date", "entry_date"):
        value = row.get(key)
        if value:
            return str(value)[:10]
    return ""


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _candidate_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _row_date(row),
        str(row.get("ticker") or ""),
        str(row.get("entry_date") or ""),
        str(row.get("exit_date") or ""),
    )


def _selected_trade_context(row: dict[str, Any]) -> dict[str, Any]:
    volume_ratio = _as_float(row.get("volume_ratio_20"))
    pnl = _as_float(row.get("pnl"))
    signal_date = _row_date(row)
    return {
        **row,
        "ticker": str(row.get("ticker") or "").upper(),
        "date": signal_date,
        "signal_date": signal_date,
        "pnl": _round(pnl, 2),
        "paper_pnl": _round(pnl, 2),
        "strategy": "rs_line_low_participation_cooldown_candidate_pool",
        "rule_version": RULE_VERSION,
        "candidate_pool_rule_version": RULE_VERSION,
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_artifact": _repo_rel(SOURCE_ARTIFACT),
        "low_participation_volume_ratio_20": _round(volume_ratio, 6),
        "low_participation_volume_ratio_20_max": MAX_VOLUME_RATIO_20,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "known_at": "OHLCV signal-day close before next-open paper entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _select_trades() -> tuple[OrderedDict[str, list[dict[str, Any]]], dict[str, Any]]:
    payload = _load_json(SOURCE_ARTIFACT)
    source_rows_by_window = source._target_rows_by_window(payload)
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    diagnostics: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label in source.base.WINDOWS:
        selected: list[dict[str, Any]] = []
        rejections: Counter[str] = Counter()
        volume_values: list[float] = []
        source_combo_counts: Counter[str] = Counter()
        last_selected_by_ticker: dict[str, datetime] = {}

        for row in sorted(source_rows_by_window.get(label, []), key=_candidate_sort_key):
            ticker = str(row.get("ticker") or "").upper()
            signal_date = _row_date(row)
            signal_day = _parse_day(signal_date)
            pnl = _as_float(row.get("pnl"))
            volume_ratio = _as_float(row.get("volume_ratio_20"))
            if not ticker or signal_day is None:
                rejections["missing_ticker_or_signal_date"] += 1
                continue
            if pnl is None:
                rejections["missing_paper_pnl"] += 1
                continue
            if int(row.get("accepted_source_confirmation_count") or 0) < 1:
                rejections["missing_accepted_source_confirmation"] += 1
                continue
            if volume_ratio is None:
                rejections["missing_volume_ratio_20"] += 1
                continue
            if volume_ratio > MAX_VOLUME_RATIO_20:
                rejections["volume_ratio_20_above_1p2"] += 1
                continue

            last_day = last_selected_by_ticker.get(ticker)
            if last_day is not None and (signal_day - last_day).days < SAME_TICKER_COOLDOWN_DAYS:
                rejections["same_ticker_cooldown"] += 1
                continue

            trade = _selected_trade_context(row)
            selected.append(trade)
            last_selected_by_ticker[ticker] = signal_day
            volume_values.append(volume_ratio)
            source_combo_counts[
                "+".join(trade.get("accepted_source_confirmation_sources") or [])
            ] += 1

        selected_by_window[label] = selected
        diagnostics[label] = {
            "source_trade_count": len(source_rows_by_window.get(label, [])),
            "selected_trade_count": len(selected),
            "selected_trade_pnl_usd": _round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
            "rejection_counts": dict(sorted(rejections.items())),
            "source_combo_counts_selected": dict(sorted(source_combo_counts.items())),
            "selected_volume_ratio_20_min": _round(min(volume_values), 6) if volume_values else None,
            "selected_volume_ratio_20_max": _round(max(volume_values), 6) if volume_values else None,
        }
    return selected_by_window, {"by_window": diagnostics}


def _overlay_from_paper_trades(
    before_result: dict[str, Any],
    paper_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    pnl_by_exit_date: Counter[str] = Counter()
    overlay_days: list[dict[str, Any]] = []
    for trade in paper_trades:
        exit_date = str(trade.get("exit_date") or "")
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_exit_date[exit_date] += pnl
        overlay_days.append(
            {
                "date": exit_date,
                "ticker": trade.get("ticker"),
                "signal_date": trade.get("signal_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": exit_date,
                "pnl": _round(pnl, 2),
                "source": STEM,
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in before_result.get("equity_curve") or []:
        cumulative_overlay += float(pnl_by_exit_date.get(str(day), 0.0))
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "overlay_total_pnl": _round(sum(pnl_by_exit_date.values()), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": overlay_days,
        "overlay_day_count": len(overlay_days),
    }


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    selected_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for label, cfg in source.base.WINDOWS.items():
        target_trades = selected_by_window.get(label, [])
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = _overlay_from_paper_trades(before_result, target_trades)
        after = source.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = source.base.overlay_helper._delta(after, before)
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
                "target_trade_pnl_usd": _round(
                    sum(float(row.get("pnl", 0.0)) for row in target_trades), 2
                ),
            }
        )
    return results


def _aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in results)
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in results)
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in results)
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in results)
    return {
        "before": {
            "expected_value_score": _round(before_ev, 6),
            "total_pnl": _round(before_pnl, 2),
            "strategy_total_pnl": _round(before_pnl, 2),
        },
        "after": {
            "expected_value_score": _round(after_ev, 6),
            "total_pnl": _round(after_pnl, 2),
            "strategy_total_pnl": _round(after_pnl, 2),
        },
        "comparison": {
            "expected_value_score_delta": _round(after_ev - before_ev, 6),
            "expected_value_score_delta_pct": _round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl_delta": _round(after_pnl - before_pnl, 2),
            "total_pnl_delta": _round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_delta_pct": _round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
        },
    }


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    current_ev = float(aggregate["before"]["expected_value_score"])
    current_pnl = float(aggregate["before"]["total_pnl"])
    return {
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": _round(current_ev, 6),
        "current_replay_pnl": _round(current_pnl, 2),
        "ev_delta_vs_docs": _round(current_ev - CANONICAL_DOC_EV, 6),
        "pnl_delta_vs_docs": _round(current_pnl - CANONICAL_DOC_PNL, 2),
        "note": (
            "Current replay baseline matches docs/backtesting.md within rounding."
            if abs(current_ev - CANONICAL_DOC_EV) <= 0.001
            and abs(current_pnl - CANONICAL_DOC_PNL) <= 1.0
            else "Current replay baseline differs from docs/backtesting.md; do not promote without a clean baseline parity check."
        ),
    }


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    max_drawdown_delta = max(
        float(row["comparison"].get("max_drawdown_delta") or 0.0) for row in results
    )
    ev_windows = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for row in results if int(row["target_trade_count"]) > 0)
    concentration_passed = (
        float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
        and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI
    )
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", ev_delta > 0.0),
            ("aggregate_pnl_positive", pnl_delta > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows) == len(results)),
            ("all_windows_pnl_improved", len(pnl_windows) == len(results)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            ("concentration_guard_passed", concentration_passed),
        ]
    )
    failed = [name for name, passed in gates.items() if not passed]
    alpha_passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_requires_forward_rows"
        if alpha_passed
        else "rejected_rs_line_low_participation_cooldown_candidate_pool"
    )
    rationale = (
        "The low-participation cooldown RS-line scout passed the three-window replay gate, but it is a high multiple-testing composite on a previously rejected RS-line family. Retain only as a replay lead until forward replacement-value rows and a shared parity-tested adapter justify promotion."
        if alpha_passed
        else "Gate 4 failed, so no strategy, production, or shared adapter change is retained."
    )
    return {
        "passed": alpha_passed,
        "alpha_passed": alpha_passed,
        "promotable_now": False,
        "anti_repeat_blocked": alpha_passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_forward_replacement_value_before_promotion": True,
        "requires_shared_adapter_before_promotion": True,
        "requires_parity_before_promotion": True,
    }


def _calibration(prediction: dict[str, Any], gate4: dict[str, Any]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual_success = 1 if gate4["alpha_passed"] else 0
    predicted_modes = prediction.get("main_failure_modes") or []
    failed = set(gate4.get("failed_gates") or [])
    realized = []
    if "all_windows_expected_value_improved" in failed or "all_windows_pnl_improved" in failed:
        realized.append("window_regression")
    if "drawdown_drift_passed" in failed:
        realized.append("drawdown_drift")
    if "target_trade_count_passed" in failed or "target_window_count_passed" in failed:
        realized.append("thin_sample")
    if "concentration_guard_passed" in failed:
        realized.append("concentration_failed")
    if gate4["alpha_passed"]:
        realized.append("composite_overfit_risk")
    return {
        "actual_decision": gate4["decision"],
        "actual_alpha_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": _round((probability - actual_success) ** 2, 6),
        "calibration_direction": "underconfident_success" if actual_success else "directionally_calibrated",
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": realized,
        "predicted_failure_mode_hit": bool(set(predicted_modes) & set(realized)),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = source.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    selected_by_window, selection_diagnostics = _select_trades()
    baselines = source._load_baselines()
    results = _run_windows(baselines, selected_by_window)
    aggregate = _aggregate_results(results)
    target_summary = source._target_summary(selected_by_window)
    gate4 = _gate4(aggregate, results, target_summary)
    baseline_caveat = _baseline_caveat(aggregate)
    timestamp = _utc_now()
    ticket = _load_ticket()
    prediction = ticket.get("prediction") or {
        "success_probability": 0.24,
        "expected_ev_delta": 0.05,
        "expected_pnl_delta": 6000.0,
        "main_failure_modes": [
            "late_strong_regression",
            "concentration_failed",
            "drawdown_drift",
            "composite_overfit",
            "thin_sample",
        ],
    }
    accepted = False
    before_metrics = OrderedDict((row["label"], row["before"]) for row in results)
    after_metrics = OrderedDict((row["label"], row["after"]) for row in results)
    delta_metrics = OrderedDict((row["label"], row["comparison"]["raw_delta"]) for row in results)

    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "default_off_paper_only": True,
        "parity_test_added": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "production_watchlist_changed": False,
        "llm_or_news_changed": False,
        "trade_enabled": False,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "completed",
        "lane": "alpha_search",
        "decision": gate4["decision"],
        "accepted": accepted,
        "hypothesis": (
            "RS-line accepted-source candidates should have better replacement value "
            "when signal-day participation is orderly and repeated same-ticker "
            "crowding is de-clustered."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "rs_line_accepted_source_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260527-013",
            "exp-20260528-024",
            "exp-20260601-005",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": (
            "production_visible_ohlcv_participation_plus_same_ticker_declustering_on_rejected_rs_line_source"
        ),
        "prediction": prediction,
        "calibration": _calibration(prediction, gate4),
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "max_volume_ratio_20": MAX_VOLUME_RATIO_20,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "paper_pnl_source": "exp-20260601-005 selected RS-line paper trade pnl",
            "locked_variables": [
                "RS-line source exp-20260527-013",
                "accepted-source confirmation exp-20260601-005",
                "fixed 10000 paper notional",
                "next-open entry",
                "10 trading-day close exit",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "watchlists",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": source.base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Selected RS-line trades use their existing slippage-adjusted next-open "
                "entry and ten-trading-day close-exit PnL from exp-20260601-005. "
                "The overlay is booked on each paper exit date against the canonical "
                "core baseline equity curve."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: improve a free-OHLCV RS-line candidate "
                "expansion by requiring orderly participation and de-clustering "
                "repeat same-ticker breakouts."
            ),
            "2_history_check": {
                "exp-20260527-013": (
                    "Raw RS-line new-high paper sleeve improved aggregate EV/PnL but "
                    "failed late_strong and drawdown gates."
                ),
                "exp-20260528-024": (
                    "Closed-ledger governor on the same RS-line source was rejected; "
                    "do not retune governor thresholds."
                ),
                "exp-20260601-005": (
                    "Accepted-source RS-line consensus improved aggregate EV/PnL but "
                    "failed late_strong, drawdown, and concentration gates."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three PIT-DTE windows; aggregate EV/PnL positive; "
                "all windows improve; drawdown drift <=0.5pp; survival >=5%; "
                "target trades >=20 across all three windows; concentration guards pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_032_rs_line_low_participation_cooldown.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_source": "docs/backtesting.md PIT-DTE canonical three-window baseline",
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_metrics": before_metrics,
            "baseline_caveat": baseline_caveat,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "source target_trades_by_window ticker",
                "source target_trades_by_window signal_date",
                "source target_trades_by_window entry_date",
                "source target_trades_by_window exit_date",
                "source target_trades_by_window pnl",
                "source target_trades_by_window volume_ratio_20",
                "source target_trades_by_window accepted_source_confirmation_count",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results) >= 0.05,
            "note": (
                "No core production filter was added; survival rates are inherited "
                "from the canonical core baseline plus a default-off paper overlay."
            ),
            "signals_generated_survived_by_window": {
                row["label"]: {
                    "signals_generated": row["after"].get("signals_generated"),
                    "signals_survived": row["after"].get("signals_survived"),
                    "survival_rate": row["after"].get("survival_rate"),
                }
                for row in results
            },
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "aggregate": aggregate,
        "window_results": results,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "selection_diagnostics": selection_diagnostics,
        "baseline_caveat": baseline_caveat,
        "production_impact": production_impact,
        "expected_value_score_delta": aggregate["comparison"]["expected_value_score_delta"],
        "total_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "rejection_reason": "; ".join(gate4["failed_gates"]) if not gate4["alpha_passed"] else None,
        "next_retry_requires": [
            "forward RS-line replacement-value rows",
            "materially orthogonal production-visible source-quality field",
            "no nearby RS-line threshold/notional/hold/governor retune on frozen windows",
            "shared production/backtest adapter and parity tests before any promotion",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(payload: dict[str, Any]) -> str:
    rows = [
        "| window | target trades | target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["window_results"]:
        rows.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(rows)


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: RS-line Low Participation Cooldown",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['comparison']['expected_value_score_delta']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['comparison']['strategy_total_pnl_delta']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        _window_table(payload),
        "",
        "## Production Parity",
        "",
        "This replay uses OHLCV volume participation and same-ticker de-clustering "
        "on already persisted default-off RS-line paper rows. No shared adapter, "
        "live/default orders, core signal generation, ranking, sizing, exits, LLM, "
        "news, or watchlist path changed. Promotion would require a shared "
        "production-visible adapter plus backtest/production parity tests.",
        "",
        "## Conclusion",
        "",
        payload["gate4"]["rationale"],
        "",
        "## Top Positive Incremental Contributors",
        "",
        "| ticker | trades | paper PnL | positive PnL share |",
        "|---|---:|---:|---:|",
    ]
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.extend(["", "No JavaScript was used.", ""])
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]["comparison"]
    target = payload["target_trade_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} RS-line low-participation cooldown",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {float(agg['expected_value_score_delta']):+.4f}",
            f"- Aggregate PnL delta: ${float(agg['strategy_total_pnl_delta']):+,.2f}",
            f"- Target trades: {target['target_trade_count']}",
            f"- Max single positive share: {target['max_single_positive_share']}",
            f"- Positive PnL HHI: {target['positive_pnl_hhi']}",
            "- Production impact: replay-only/default-off evidence; no live orders changed.",
            "",
            "## Three-Window Result",
            "",
            _window_table(payload),
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
        ]
    )


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "aggregate": payload["aggregate"],
        "target_trade_summary": {
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_trade_summary"]["target_trade_pnl_usd"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
            "trades_by_window": payload["target_trade_summary"]["trades_by_window"],
            "pnl_by_window": payload["target_trade_summary"]["pnl_by_window"],
        },
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "anti_js": payload["anti_js"],
    }


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(_safe(record), ensure_ascii=True, sort_keys=True)
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


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_ticket()
    allowed_scope = list(ticket.get("allowed_write_scope") or [])
    for path in payload["related_files"] + [_repo_rel(MANIFEST_JSON)]:
        if path not in allowed_scope:
            allowed_scope.append(path)
    ticket["allowed_write_scope"] = allowed_scope
    ticket["status"] = "completed"
    ticket["decision"] = payload["decision"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "artifact": _repo_rel(OUT_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "gate4_failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.setdefault("experiments", [])
    entry = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": "alpha-search",
        "hypothesis": payload["hypothesis"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "completed_at": payload["timestamp"],
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, row in enumerate(experiments):
        if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
            merged = dict(row)
            merged.update(entry)
            experiments[idx] = merged
            replaced = True
            break
    if not replaced:
        experiments.append(entry)
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    files = manifest.setdefault("files", {})
    for name, path in {
        "runner": Path(__file__),
        "artifact": OUT_JSON,
        "before_aggregate": BEFORE_JSON,
        "after_aggregate": AFTER_JSON,
        "log": LOG_JSON,
        "card": CARD_MD,
        "report": ARTIFACT_MD,
        "ticket": TICKET_JSON,
        "experiment_log": EXPERIMENT_LOG,
        "registry": REGISTRY_JSON,
    }.items():
        files[name] = {
            "path": _repo_rel(path),
            "exists": path.exists(),
            "sha256": _sha256(path),
        }
    manifest["experiment_id"] = EXPERIMENT_ID
    manifest["updated_at"] = payload["timestamp"]
    manifest["final_decision"] = payload["decision"]
    manifest["final_artifact"] = _repo_rel(OUT_JSON)
    _write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "windows": payload["before_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _card(payload))
    _write_text(ARTIFACT_MD, _artifact(payload))
    _upsert_jsonl(EXPERIMENT_LOG, _log_record(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _update_manifest(payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": {
                        "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
                        "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
                        "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
                    },
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
