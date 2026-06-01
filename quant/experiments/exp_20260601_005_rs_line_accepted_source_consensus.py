"""exp-20260601-005: RS-line new-high accepted-source consensus scout.

Replay-only alpha scout. It tests whether the rejected raw RS-line new-high
paper candidate pool becomes higher quality when the same ticker and signal
date are also selected by at least one already accepted free-data paper sleeve.

No production orders, ranking, sizing, exits, watchlists, LLM, or news paths
are changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260601-005"
STEM = "rs_line_accepted_source_consensus"
TRIAL_FAMILY = "rs_line_new_high_accepted_source_consensus_candidate_pool"
CHANGED_VARIABLE = "rs_line_new_high_accepted_source_consensus_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE

RS_SOURCE_FILE = Path(
    "data/experiments/exp-20260527-013/rs_line_new_high_paper_sleeve.json"
)
ACCEPTED_SOURCE_FILES = OrderedDict(
    [
        (
            "FUNDAMENTAL_GROWTH_RS_PAPER",
            Path(
                "data/experiments/exp-20260528-017/"
                "fundamental_growth_rs_low_liability_support.json"
            ),
        ),
        (
            "VOLUME_BREADTH_BREAKOUT_PAPER",
            Path(
                "data/experiments/exp-20260529-004/"
                "exp_20260529_004_vbb_cost_liquidity_support.json"
            ),
        ),
        (
            "FINRA_IWM_CONFIRMED_PAPER",
            Path(
                "data/experiments/exp-20260530-007/"
                "exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.json"
            ),
        ),
        (
            "ALPHA_SCORE_MARKET_REGIME_PAPER",
            Path(
                "data/experiments/exp-20260531-021/"
                "exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json"
            ),
        ),
    ]
)
SOURCE_EXPERIMENT_IDS = {
    "RS_LINE_NEW_HIGH_PAPER": "exp-20260527-013",
    "FUNDAMENTAL_GROWTH_RS_PAPER": "exp-20260528-017",
    "VOLUME_BREADTH_BREAKOUT_PAPER": "exp-20260529-004",
    "FINRA_IWM_CONFIRMED_PAPER": "exp-20260530-007",
    "ALPHA_SCORE_MARKET_REGIME_PAPER": "exp-20260531-021",
}

MIN_ACCEPTED_SOURCE_COUNT = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260601_005_rs_line_accepted_source_consensus.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _round(value: Any, digits: int = 4) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _row_date(row: dict[str, Any]) -> str:
    for key in ("date", "signal_date", "entry_date"):
        value = row.get(key)
        if value:
            return str(value)[:10]
    return ""


def _target_rows_by_window(payload: dict[str, Any]) -> OrderedDict[str, list[dict[str, Any]]]:
    explicit = payload.get("target_trades_by_window")
    rows_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    if isinstance(explicit, dict):
        for label in base.WINDOWS:
            rows = explicit.get(label) or []
            rows_by_window[label] = [row for row in rows if isinstance(row, dict)]
        return rows_by_window

    for result in payload.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        label = str(result.get("label") or result.get("window_label") or "")
        if not label:
            continue
        rows = result.get("target_trades") or result.get("paper_trades") or []
        rows_by_window[label] = [row for row in rows if isinstance(row, dict)]
    for label in base.WINDOWS:
        rows_by_window.setdefault(label, [])
    return rows_by_window


def _source_row_summary(source_name: str, row: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "source_name": source_name,
        "source_experiment_id": SOURCE_EXPERIMENT_IDS[source_name],
    }
    for key in (
        "date",
        "signal_date",
        "entry_date",
        "ticker",
        "paper_pnl",
        "pnl",
        "alpha_score",
        "fundamental_growth_rs_score",
        "volume_breadth_breakout_score",
        "candidate_selection_score",
        "source_count",
        "source_names",
    ):
        if key in row:
            summary[key] = row.get(key)
    return summary


def _accepted_source_map() -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    source_map: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for source_name, rel_path in ACCEPTED_SOURCE_FILES.items():
        payload = _load_json(ROOT / rel_path)
        for label, rows in _target_rows_by_window(payload).items():
            for row in rows:
                signal_date = _row_date(row)
                ticker = str(row.get("ticker") or "").upper()
                if not signal_date or not ticker:
                    continue
                source_map[label][(signal_date, ticker)].append(
                    _source_row_summary(source_name, row)
                )
    return source_map


def _select_confirmed_rs_trades(
    rs_rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    source_map: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[OrderedDict[str, list[dict[str, Any]]], dict[str, Any]]:
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    diagnostics: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, rows in rs_rows_by_window.items():
        selected: list[dict[str, Any]] = []
        rejections: Counter[str] = Counter()
        source_combo_counts: Counter[str] = Counter()
        for row in rows:
            signal_date = _row_date(row)
            ticker = str(row.get("ticker") or "").upper()
            key = (signal_date, ticker)
            accepted_rows = source_map.get(label, {}).get(key, [])
            source_names = sorted({str(item["source_name"]) for item in accepted_rows})
            if len(source_names) < MIN_ACCEPTED_SOURCE_COUNT:
                rejections["missing_accepted_source_confirmation"] += 1
                continue
            pnl = _as_float(row.get("pnl"))
            if pnl is None:
                rejections["missing_rs_line_paper_pnl"] += 1
                continue
            trade = {
                **row,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "pnl": _round(pnl, 2),
                "paper_pnl": _round(pnl, 2),
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "strategy": "rs_line_new_high_accepted_source_consensus",
                "rs_line_source_experiment_id": "exp-20260527-013",
                "accepted_source_confirmation_count": len(source_names),
                "accepted_source_confirmation_sources": source_names,
                "accepted_source_confirmation_rows": sorted(
                    accepted_rows,
                    key=lambda item: str(item.get("source_name") or ""),
                ),
                "accepted_source_confirmation_known_at": (
                    "after_signal_date_close_before_next_open_paper_entry"
                ),
                "trade_enabled": False,
                "alters_orders": False,
            }
            selected.append(trade)
            source_combo_counts["+".join(source_names)] += 1

        selected_by_window[label] = selected
        diagnostics[label] = {
            "raw_rs_line_target_trade_count": len(rows),
            "selected_confirmed_trade_count": len(selected),
            "rejection_counts": dict(sorted(rejections.items())),
            "source_combo_counts_selected": dict(sorted(source_combo_counts.items())),
        }
    return selected_by_window, {"by_window": diagnostics}


def _load_baselines() -> dict[str, dict[str, Any]]:
    baselines: dict[str, dict[str, Any]] = {}
    universe = sorted(base.get_universe())
    for label, cfg in base.WINDOWS.items():
        result = base.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": result,
            "metrics": base.overlay_helper._metrics(result),
        }
    return baselines


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
    for label, cfg in base.WINDOWS.items():
        target_trades = selected_by_window.get(label, [])
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = _overlay_from_paper_trades(before_result, target_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = base.overlay_helper._delta(after, before)
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
    comparison = {
        "expected_value_score_delta": _round(after_ev - before_ev, 6),
        "expected_value_score_delta_pct": _round((after_ev - before_ev) / before_ev, 6)
        if before_ev
        else None,
        "strategy_total_pnl_delta": _round(after_pnl - before_pnl, 2),
        "total_pnl_delta": _round(after_pnl - before_pnl, 2),
        "strategy_total_pnl_delta_pct": _round((after_pnl - before_pnl) / before_pnl, 6)
        if before_pnl
        else None,
    }
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
        "comparison": comparison,
    }


def _target_summary(
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    positive_total = sum(max(float(trade.get("pnl", 0.0)), 0.0) for trade in all_trades)
    by_ticker: dict[str, dict[str, Any]] = {}
    by_source_combo: Counter[str] = Counter()
    for trade in all_trades:
        ticker = str(trade.get("ticker") or "")
        bucket = by_ticker.setdefault(
            ticker,
            {
                "ticker": ticker,
                "trade_count": 0,
                "paper_pnl_usd": 0.0,
                "positive_pnl_usd": 0.0,
            },
        )
        pnl = float(trade.get("pnl", 0.0))
        bucket["trade_count"] += 1
        bucket["paper_pnl_usd"] += pnl
        bucket["positive_pnl_usd"] += max(pnl, 0.0)
        by_source_combo[
            "+".join(trade.get("accepted_source_confirmation_sources") or [])
        ] += 1

    ticker_rows = sorted(
        by_ticker.values(),
        key=lambda row: (-float(row["paper_pnl_usd"]), -int(row["trade_count"]), str(row["ticker"])),
    )
    for row in ticker_rows:
        row["paper_pnl_usd"] = _round(row["paper_pnl_usd"], 2)
        row["positive_pnl_usd"] = _round(row["positive_pnl_usd"], 2)
        row["positive_pnl_share"] = _round(
            float(row["positive_pnl_usd"]) / positive_total if positive_total > 0.0 else 0.0,
            6,
        )

    max_positive_share = max((float(row["positive_pnl_share"]) for row in ticker_rows), default=0.0)
    positive_hhi = sum(float(row["positive_pnl_share"]) ** 2 for row in ticker_rows)
    return {
        "target_trade_count": len(all_trades),
        "target_trade_pnl_usd": _round(sum(float(row.get("pnl", 0.0)) for row in all_trades), 2),
        "positive_pnl_total_usd": _round(positive_total, 2),
        "max_single_positive_share": _round(max_positive_share, 6),
        "positive_pnl_hhi": _round(positive_hhi, 6),
        "ticker_rows": ticker_rows,
        "source_combo_counts": dict(sorted(by_source_combo.items())),
        "trades_by_window": {label: len(rows) for label, rows in target_trades_by_window.items()},
        "pnl_by_window": {
            label: _round(sum(float(row.get("pnl", 0.0)) for row in rows), 2)
            for label, rows in target_trades_by_window.items()
        },
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    max_drawdown_delta = max(float(row["comparison"].get("max_drawdown_delta") or 0.0) for row in results)
    ev_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_trade_count = int(target_summary["target_trade_count"])
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", ev_delta > 0.0),
            ("aggregate_pnl_positive", pnl_delta > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows_improved) == len(results)),
            ("all_windows_pnl_improved", len(pnl_windows_improved) == len(results)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            (
                "target_window_count_passed",
                sum(1 for row in results if int(row["target_trade_count"]) > 0) >= MIN_TARGET_WINDOWS,
            ),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            (
                "concentration_guard_passed",
                float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
                and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI,
            ),
        ]
    )
    passed = all(gates.values())
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if passed
        else "rejected_rs_line_accepted_source_consensus_candidate_pool"
    )
    rationale = (
        "Gate 4 passed, but promotion would require a shared production-visible "
        "default-off adapter and parity tests before retention."
        if passed
        else "Gate 4 failed, so no strategy, production, or shared adapter change is retained."
    )
    return {
        "decision": decision,
        "passed": passed,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": [name for name, passed_gate in gates.items() if not passed_gate],
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_parity_before_promotion": passed,
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
            "Current replay baseline matches the docs/backtesting.md accepted aggregate "
            "within rounding."
            if abs(current_ev - CANONICAL_DOC_EV) <= 0.001 and abs(current_pnl - CANONICAL_DOC_PNL) <= 1.0
            else "Current replay baseline differs from docs/backtesting.md; positive alpha would require a clean parity baseline before retention."
        ),
    }


def _calibration(prediction: dict[str, Any], gate4: dict[str, Any]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual_success = 1 if gate4["passed"] else 0
    predicted_modes = prediction.get("main_failure_modes") or []
    if isinstance(predicted_modes, str):
        predicted_modes = [item.strip() for item in predicted_modes.split(",") if item.strip()]
    failed = set(gate4.get("failed_gates") or [])
    realized = []
    if "all_windows_expected_value_improved" in failed or "all_windows_pnl_improved" in failed:
        realized.append("window_regression")
    if "drawdown_drift_passed" in failed:
        realized.append("drawdown_drift")
    if "target_trade_count_passed" in failed or "target_window_count_passed" in failed:
        realized.append("thin_overlap")
    if "concentration_guard_passed" in failed:
        realized.append("concentration_failed")
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": _round((probability - actual_success) ** 2, 6),
        "calibration_direction": "directionally_calibrated" if actual_success == 0 else "underconfident_success",
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": realized,
        "predicted_failure_mode_hit": bool(set(predicted_modes) & set(realized)),
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    rs_payload = _load_json(ROOT / RS_SOURCE_FILE)
    rs_rows_by_window = _target_rows_by_window(rs_payload)
    source_map = _accepted_source_map()
    selected_by_window, selection_diagnostics = _select_confirmed_rs_trades(
        rs_rows_by_window, source_map
    )
    baselines = _load_baselines()
    results = _run_windows(baselines, selected_by_window)
    aggregate = _aggregate_results(results)
    target_summary = _target_summary(selected_by_window)
    gate4 = _gate4_decision(aggregate, results, target_summary)
    baseline_caveat = _baseline_caveat(aggregate)

    prediction = {
        "success_probability": 0.32,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "late_strong_regression",
            "drawdown_drift",
            "thin_overlap",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Raw RS-line has broad gross EV but failed risk; accepted free-data "
            "source agreement has passed, so overlap may de-noise without retuning thresholds."
        ),
        "recorded_at": "2026-06-01T03:07:07+00:00",
    }
    calibration = _calibration(prediction, gate4)
    decision = gate4["decision"]
    accepted = bool(gate4["passed"])

    before_metrics = OrderedDict((row["label"], row["before"]) for row in results)
    after_metrics = OrderedDict((row["label"], row["after"]) for row in results)
    delta_metrics = OrderedDict((row["label"], row["comparison"]["raw_delta"]) for row in results)

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "RS-line new-high candidates should have better replacement value when "
            "the same ticker and signal date are confirmed by at least one accepted "
            "free-data paper sleeve."
        ),
        "change_summary": (
            "Admit raw RS-line new-high paper trades only when at least one accepted "
            "free-data sleeve selected the same ticker on the same signal date."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "free_ohlcv_relative_strength_candidate_pool",
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260527-013",
            "exp-20260528-024",
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260601-003",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_source_confirmation",
        "prediction": prediction,
        "calibration": calibration,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Selected RS-line trades use their existing slippage-adjusted next-open "
                "entry and ten-trading-day close-exit PnL from exp-20260527-013. "
                "The overlay is booked on each paper exit date against the canonical "
                "core baseline equity curve."
            ),
        },
        "parameters": {
            "rs_source_file": _repo_rel(RS_SOURCE_FILE),
            "accepted_source_files": {
                name: _repo_rel(path) for name, path in ACCEPTED_SOURCE_FILES.items()
            },
            "min_accepted_source_count": MIN_ACCEPTED_SOURCE_COUNT,
            "paper_pnl_source": "exp-20260527-013 RS-line selected paper trade pnl",
            "locked_variables": [
                "raw RS-line source thresholds",
                "raw RS-line ranking",
                "raw RS-line notional",
                "raw RS-line 10-trading-day hold",
                "accepted sleeve thresholds and notionals",
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
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "survival_rate_floor": 0.05,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: RS-line new-high is a broad free-OHLCV "
                "candidate expansion lead; accepted free-data source confirmation "
                "may remove noisy RS-only rows."
            ),
            "2_history_check": {
                "exp-20260527-013": (
                    "Raw RS-line new-high paper sleeve improved aggregate EV/PnL but "
                    "failed Gate 4 due late_strong regression and drawdown drift."
                ),
                "exp-20260528-024": (
                    "Closed-ledger governor on the same RS-line source was rejected; "
                    "do not retune governor thresholds."
                ),
                "exp-20260531-030/exp-20260601-001": (
                    "Accepted/free-data cross-source consensus works as a default-off "
                    "paper adapter, but its source set/thresholds should not be retuned. "
                    "This is a separate scout for an unaccepted RS-line source requiring "
                    "accepted-source confirmation."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
                "all three windows improve; >=20 target trades across all windows; "
                "target trades in all three windows; drawdown drift <=0.5pp; "
                "survival >=5%; max single positive share <=0.50 and HHI <=0.30."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_005_rs_line_accepted_source_consensus.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": before_metrics,
            "baseline_caveat": baseline_caveat,
            "baseline_artifact": "data/experiments/exp-20260517-009/",
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "RS-line target trade date/signal_date",
                "RS-line target trade ticker",
                "RS-line target trade entry_date",
                "RS-line target trade exit_date",
                "RS-line target trade pnl",
                "accepted source target trade date/signal_date/entry_date",
                "accepted source target trade ticker",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results) >= 0.05,
            "note": (
                "No core production filter was added. Survival rates are inherited "
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
        "results": results,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "selection_diagnostics": selection_diagnostics,
        "baseline_caveat": baseline_caveat,
        "expected_value_score_delta": aggregate["comparison"]["expected_value_score_delta"],
        "total_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "production_impact": {
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
            "trade_enabled": False,
        },
        "rejection_reason": "; ".join(gate4["failed_gates"]) if not accepted else None,
        "next_retry_requires": [
            "forward RS-line replacement-value rows",
            "materially orthogonal production-visible source-quality field",
            "no RS-line threshold/notional/hold/governor retune on frozen windows",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _window_table(payload: dict[str, Any]) -> str:
    rows = [
        "| window | target trades | target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
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


def _card(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]["comparison"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: RS-line accepted-source consensus",
        "",
        f"- decision: `{payload['decision']}`",
        f"- changed variable: `{CHANGED_VARIABLE}`",
        f"- aggregate EV delta: `{float(agg['expected_value_score_delta']):+.4f}`",
        f"- aggregate PnL delta: `${float(agg['strategy_total_pnl_delta']):+,.2f}`",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        _window_table(payload),
        "",
        "## Conclusion",
        "",
        payload["gate4"]["rationale"],
        "",
        "This scout made no production/shared policy, run adapter, backtester adapter, "
        "live/default order, ranking, sizing, exit, LLM, news, or watchlist change.",
        "",
        "## Top Contributors",
        "",
        "| ticker | trades | paper PnL | positive share |",
        "|---|---:|---:|---:|",
    ]
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | ${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.extend(["", "No JavaScript was used.", ""])
    return "\n".join(lines)


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


def _upsert_registry(payload: dict[str, Any]) -> None:
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
        "log": _repo_rel(LOG_JSON),
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, row in enumerate(experiments):
        if isinstance(row, dict) and row.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = entry
            replaced = True
            break
    if not replaced:
        experiments.append(entry)
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON)
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _upsert_registry(payload)


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
