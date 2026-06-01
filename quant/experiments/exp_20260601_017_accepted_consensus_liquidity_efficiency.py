"""exp-20260601-017: accepted consensus liquidity efficiency gate.

Lane: alpha_search.
Single causal variable:
    accepted_free_data_consensus_liquidity_efficiency_gate_v1.

This tests whether the accepted free-data cross-source consensus paper queue
has better default-off replacement value after adding a production-visible
OHLCV cost/liquidity discriminator. It changes no shared policy, production
adapter, orders, core ranking, sizing, exits, watchlists, or LLM/news inputs.

No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import (  # noqa: E402
    exp_20260531_030_accepted_free_data_cross_source_consensus as source,
)


EXPERIMENT_ID = "exp-20260601-017"
STEM = "accepted_consensus_liquidity_efficiency"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_liquidity_efficiency"
CHANGED_VARIABLE = "accepted_free_data_consensus_liquidity_efficiency_gate_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_AVG_DOLLAR_VOLUME_20 = 200_000_000.0
MAX_SIGNAL_DAY_RANGE_CLOSE = 0.10
MIN_FEATURE_LOOKBACK_DAYS = 20

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {"expected_value_score": 5.1628, "total_pnl": 117_072.92},
    "mid_weak": {"expected_value_score": 2.1402, "total_pnl": 78_110.11},
    "old_thin": {"expected_value_score": 0.5911, "total_pnl": 39_667.96},
}

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_017_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260601_017_{STEM}_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260601_017_{STEM}_after.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

PRODUCTION_IMPACT = {
    "replay_only": True,
    "default_off_paper_only": True,
    "shared_policy_changed": False,
    "run_adapter_changed": False,
    "backtester_adapter_changed": False,
    "parity_test_added": False,
    "trade_enabled": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_safe(record), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                item = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if item.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _row_float(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in row:
            continue
        try:
            value = float(row[key])
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            return value
    return None


def _liquidity_features(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any]:
    rows = snapshot.get(str(ticker).upper()) or []
    index = None
    for idx, row in enumerate(rows):
        if _row_date(row) == signal_date:
            index = idx
            break
    if index is None:
        return {"passed": False, "reason": "missing_signal_day_ohlcv"}
    window = rows[max(0, index - MIN_FEATURE_LOOKBACK_DAYS + 1) : index + 1]
    if len(window) < MIN_FEATURE_LOOKBACK_DAYS:
        return {
            "passed": False,
            "reason": "insufficient_20d_ohlcv_lookback",
            "lookback_rows": len(window),
        }

    dollar_volumes: list[float] = []
    for row in window:
        close = _row_float(row, "Close", "close")
        volume = _row_float(row, "Volume", "volume")
        if close is None or volume is None:
            continue
        dollar_volumes.append(close * volume)
    if len(dollar_volumes) < MIN_FEATURE_LOOKBACK_DAYS:
        return {
            "passed": False,
            "reason": "insufficient_20d_dollar_volume_values",
            "lookback_rows": len(dollar_volumes),
        }

    row = rows[index]
    close = _row_float(row, "Close", "close")
    high = _row_float(row, "High", "high")
    low = _row_float(row, "Low", "low")
    if close is None or high is None or low is None or close <= 0:
        return {"passed": False, "reason": "missing_signal_day_range_values"}

    avg_dollar_volume_20 = sum(dollar_volumes) / len(dollar_volumes)
    range_close = (high - low) / close
    passed = (
        avg_dollar_volume_20 >= MIN_AVG_DOLLAR_VOLUME_20
        and range_close <= MAX_SIGNAL_DAY_RANGE_CLOSE
    )
    reason = "passed" if passed else "liquidity_efficiency_gate_failed"
    return {
        "passed": passed,
        "reason": reason,
        "avg_dollar_volume_20": round(avg_dollar_volume_20, 2),
        "signal_day_range_close_ratio": round(range_close, 6),
        "signal_day_close": round(close, 4),
        "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
        "max_signal_day_range_close_ratio": MAX_SIGNAL_DAY_RANGE_CLOSE,
        "rule_version": RULE_VERSION,
    }


def _annotate_and_filter_candidates(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        features = _liquidity_features(
            snapshot,
            str(candidate.get("ticker") or ""),
            str(candidate.get("date") or ""),
        )
        annotated = dict(candidate)
        annotated["liquidity_efficiency"] = features
        annotated["liquidity_efficiency_rule_version"] = RULE_VERSION
        if features["passed"]:
            accepted.append(annotated)
        else:
            rejected.append(annotated)
    return accepted, rejected


def _baseline_drift(core_metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    for label, expected in DOCS_ACCEPTED_BASELINE.items():
        actual = core_metrics_by_window.get(label) or {}
        ev_delta = float(actual.get("expected_value_score") or 0.0) - expected[
            "expected_value_score"
        ]
        pnl_delta = float(actual.get("total_pnl") or 0.0) - expected["total_pnl"]
        rows[label] = {
            "docs_expected_value_score": expected["expected_value_score"],
            "current_expected_value_score": actual.get("expected_value_score"),
            "expected_value_score_delta": round(ev_delta, 6),
            "docs_total_pnl": expected["total_pnl"],
            "current_total_pnl": actual.get("total_pnl"),
            "total_pnl_delta": round(pnl_delta, 2),
            "matches_docs_baseline": abs(ev_delta) <= 0.01 and abs(pnl_delta) <= 100.0,
        }
    return {
        "docs_source": "docs/backtesting.md accepted exp-20260517-009 metrics",
        "current_source": "current replay in the same docs/backtesting.md windows",
        "matches_all_windows": all(row["matches_docs_baseline"] for row in rows.values()),
        "rows": rows,
    }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in results)
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in results)
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in results)
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in results)
    return {
        "before": {
            "expected_value_score": round(before_ev, 6),
            "total_pnl": round(before_pnl, 2),
            "strategy_total_pnl": round(before_pnl, 2),
        },
        "after": {
            "expected_value_score": round(after_ev, 6),
            "total_pnl": round(after_pnl, 2),
            "strategy_total_pnl": round(after_pnl, 2),
        },
        "comparison": {
            "expected_value_score_delta": round(after_ev - before_ev, 6),
            "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
            "total_pnl_delta": round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
        },
    }


def _target_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = float(trade.get("pnl") or 0.0)
        by_ticker_count[ticker] += 1
        by_ticker_pnl[ticker] += pnl
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        max(positive.values()) / positive_total if positive_total > 0 and positive else None
    )
    positive_hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive.values())
        if positive_total > 0 and positive
        else None
    )
    ticker_rows = []
    for ticker, pnl in sorted(by_ticker_pnl.items()):
        ticker_rows.append(
            {
                "ticker": ticker,
                "trade_count": by_ticker_count[ticker],
                "paper_pnl_usd": round(pnl, 2),
                "positive_pnl_usd": round(max(pnl, 0.0), 2),
                "positive_pnl_share": round(pnl / positive_total, 6)
                if pnl > 0 and positive_total > 0
                else None,
            }
        )
    ticker_rows.sort(
        key=lambda row: (
            -(row["positive_pnl_usd"] or 0.0),
            -abs(row["paper_pnl_usd"] or 0.0),
            row["ticker"],
        )
    )
    return {
        "target_trade_count": len(trades),
        "target_trade_pnl_usd": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "positive_pnl_total_usd": round(positive_total, 2),
        "max_single_positive_share": round(max_positive_share, 6)
        if max_positive_share is not None
        else None,
        "positive_pnl_hhi": round(positive_hhi, 6) if positive_hhi is not None else None,
        "trades_by_window": {label: len(rows) for label, rows in target_trades_by_window.items()},
        "pnl_by_window": {
            label: round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
            for label, rows in target_trades_by_window.items()
        },
        "ticker_rows": ticker_rows,
    }


def _run_windows() -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    source_rows = source._source_rows_by_window()
    baselines = source._load_baselines()
    results: list[dict[str, Any]] = []
    core_metrics_by_window: dict[str, dict[str, Any]] = {}
    after_target_trades_by_window: dict[str, list[dict[str, Any]]] = {}

    for label, cfg in source.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        core_metrics = baselines[label]["metrics"]
        core_metrics_by_window[label] = core_metrics
        snapshot = source.base.shadow._load_snapshot(cfg["snapshot"])

        raw_candidates = source._consensus_candidates_for_window(label, source_rows)
        after_candidates, rejected_candidates = _annotate_and_filter_candidates(
            snapshot,
            raw_candidates,
        )

        before_trades, before_diagnostics = source._select_target_trades(snapshot, raw_candidates)
        after_trades, after_diagnostics = source._select_target_trades(snapshot, after_candidates)
        for trade in after_trades:
            trade["liquidity_efficiency_rule_version"] = RULE_VERSION
            trade["liquidity_efficiency_gate"] = {
                "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
                "max_signal_day_range_close_ratio": MAX_SIGNAL_DAY_RANGE_CLOSE,
            }

        before_overlay = source.base._overlay_from_paper_trades(before_result, before_trades)
        after_overlay = source.base._overlay_from_paper_trades(before_result, after_trades)
        before = source.base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        after = source.base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        comparison = source.base.overlay_helper._delta(after, before)
        core_before_comparison = source.base.overlay_helper._delta(before, core_metrics)
        core_after_comparison = source.base.overlay_helper._delta(after, core_metrics)

        rejected_reasons = Counter(
            str((row.get("liquidity_efficiency") or {}).get("reason") or "unknown")
            for row in rejected_candidates
        )
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "core_metrics": core_metrics,
                "before": before,
                "after": after,
                "comparison": {
                    "expected_value_score_delta": comparison["expected_value_score"],
                    "strategy_total_pnl_delta": comparison["total_pnl"],
                    "total_pnl_delta": comparison["total_pnl"],
                    "max_drawdown_delta": comparison["max_drawdown_pct"],
                    "raw_delta": comparison,
                },
                "core_before_comparison": core_before_comparison,
                "core_after_comparison": core_after_comparison,
                "raw_consensus_candidate_count": len(raw_candidates),
                "liquidity_pass_candidate_count": len(after_candidates),
                "liquidity_rejected_candidate_count": len(rejected_candidates),
                "liquidity_rejected_reasons": dict(sorted(rejected_reasons.items())),
                "before_target_trade_count": len(before_trades),
                "after_target_trade_count": len(after_trades),
                "before_target_trade_pnl_usd": round(
                    sum(float(row.get("pnl") or 0.0) for row in before_trades), 2
                ),
                "after_target_trade_pnl_usd": round(
                    sum(float(row.get("pnl") or 0.0) for row in after_trades), 2
                ),
                "before_target_diagnostics": before_diagnostics,
                "after_target_diagnostics": after_diagnostics,
            }
        )
        after_target_trades_by_window[label] = after_trades
    return results, core_metrics_by_window, after_target_trades_by_window


def _judge(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_drift: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison["expected_value_score_delta"])
    pnl_delta = float(comparison["strategy_total_pnl_delta"])
    ev_windows = [
        row["label"] for row in results if float(row["comparison"]["expected_value_score_delta"]) > 0
    ]
    pnl_windows = [
        row["label"] for row in results if float(row["comparison"]["strategy_total_pnl_delta"]) > 0
    ]
    max_drawdown_delta = max(float(row["comparison"]["max_drawdown_delta"]) for row in results)
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_window_count = sum(1 for row in results if int(row["after_target_trade_count"]) > 0)
    concentration_passed = (
        target_summary["max_single_positive_share"] is not None
        and target_summary["max_single_positive_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gates = {
        "aggregate_expected_value_positive": ev_delta > 0,
        "aggregate_pnl_positive": pnl_delta > 0,
        "all_windows_expected_value_improved": len(ev_windows) == len(results),
        "all_windows_pnl_improved": len(pnl_windows) == len(results),
        "target_trade_count_passed": target_summary["target_trade_count"] >= MIN_TARGET_TRADES,
        "target_window_count_passed": target_window_count >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": concentration_passed,
        "baseline_matches_docs": bool(baseline_drift["matches_all_windows"]),
    }
    alpha_checks_passed = all(value for key, value in gates.items() if key != "baseline_matches_docs")
    retained = alpha_checks_passed and gates["baseline_matches_docs"]
    if retained:
        decision = "accepted_replay_lead_requires_shared_liquidity_adapter"
        rationale = (
            "The liquidity-efficiency gate improved the accepted consensus overlay and "
            "the current baseline matched docs; a shared adapter would still be required."
        )
    elif alpha_checks_passed:
        decision = "positive_replay_lead_not_promoted_requires_clean_baseline_and_shared_adapter"
        rationale = (
            "The liquidity-efficiency gate passed alpha checks, but current-code baseline "
            "metrics drift from docs/backtesting.md; no shared behavior is retained."
        )
    else:
        decision = "rejected_accepted_consensus_liquidity_efficiency_gate"
        rationale = (
            "The liquidity-efficiency gate did not improve the accepted consensus paper "
            "overlay across the canonical three windows. No production/shared behavior is retained."
        )
    failed_gates = [key for key, value in gates.items() if not value]
    return {
        "passed": retained,
        "alpha_checks_passed": alpha_checks_passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed_gates,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": round(max_drawdown_delta, 6),
        "min_survival_rate": round(min_survival_rate, 6),
        "requires_parity_before_promotion": True,
    }


def _prediction() -> dict[str, Any]:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    return ticket.get("prediction") or {
        "success_probability": 0.35,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "sample_too_thin",
            "window_regression",
            "pnl_cut_too_much",
            "baseline_matches_docs",
        ],
        "confidence_reason": "Fallback copied from ticket reservation intent.",
        "recorded_at": "2026-06-01T09:06:06+00:00",
    }


def _calibration(prediction: dict[str, Any], gate4: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    probability = float(prediction.get("success_probability") or 0.0)
    predicted_failure_modes = prediction.get("main_failure_modes") or []
    realized = gate4["failed_gates"]
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual_success) ** 2, 6),
        "actual_ev_delta": aggregate["comparison"]["expected_value_score_delta"],
        "actual_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "predicted_failure_modes": predicted_failure_modes,
        "realized_failure_mode": realized,
        "predicted_failure_mode_hit": any(
            "sample" in mode and "target_trade_count_passed" in realized
            or "window" in mode
            and (
                "all_windows_expected_value_improved" in realized
                or "all_windows_pnl_improved" in realized
            )
            or "baseline" in mode and "baseline_matches_docs" in realized
            for mode in predicted_failure_modes
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": payload["gate4"]["decision"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Added a production-visible OHLCV liquidity-efficiency gate to the "
            "accepted free-data cross-source consensus paper overlay."
        ),
        "change_type": "default_off_paper_candidate_quality_gate",
        "mechanism_family": "default_off_paper_candidate_quality_gate",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260601-015",
            "exp-20260529-004",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_production_visible_cost_liquidity_discriminator",
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "parameters": payload["rule"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            **comparison,
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "before_target_trade_count": row["before_target_trade_count"],
                "after_target_trade_count": row["after_target_trade_count"],
            }
            for row in payload["results"]
        ],
        "production_impact": PRODUCTION_IMPACT,
        "decision_basis": payload["gate4"],
        "rejection_reason": "; ".join(payload["gate4"]["failed_gates"]) or None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} accepted consensus liquidity efficiency",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Incremental EV delta vs accepted consensus overlay: `{comp['expected_value_score_delta']:+.4f}`",
        f"- Incremental PnL delta vs accepted consensus overlay: `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- After-gate target trades: `{payload['target_summary']['target_trade_count']}`",
        f"- Max positive ticker share: `{payload['target_summary']['max_single_positive_share']}`",
        f"- Positive PnL HHI: `{payload['target_summary']['positive_pnl_hhi']}`",
        f"- Baseline matches docs: `{payload['baseline_drift']['matches_all_windows']}`",
        "",
        "## Three-Window Evidence",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | before trades | after trades | pass candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['before_target_trade_count']} | {row['after_target_trade_count']} | "
            f"{row['liquidity_pass_candidate_count']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "No production orders, core ranking/sizing/exits, LLM/news inputs, "
            "watchlists, or shared adapters changed in this replay.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "observed_only" if not payload["gate4"]["passed"] else "accepted",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item["status"] = ticket["status"]
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
                break
    _write_json(REGISTRY_JSON, registry)


def run() -> dict[str, Any]:
    gate2 = source.base._audit_open_positions()
    if not gate2.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    results, core_metrics_by_window, target_trades_by_window = _run_windows()
    aggregate = _aggregate(results)
    target_summary = _target_summary(target_trades_by_window)
    baseline_drift = _baseline_drift(core_metrics_by_window)
    gate4 = _judge(aggregate, results, target_summary, baseline_drift)
    prediction = _prediction()
    calibration = _calibration(prediction, gate4, aggregate)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "preflight": {
            "alpha_hypothesis": (
                "Accepted free-data cross-source consensus candidates with high dollar "
                "liquidity and tight signal-day range should have better default-off "
                "replacement value than the full accepted consensus queue."
            ),
            "category": "candidate_pool_quality / cost_liquidity",
            "playbook_alignment": (
                "Follows the playbook's transaction-cost-aware allocation and candidate-pool "
                "sleeve maturation queue. It avoids LLM soft-ranking, state-surface retunes, "
                "source-count/cooldown/hold/notional retunes, and noisy ticker expansion."
            ),
            "history_check": {
                "exp-20260531-030": "accepted free-data consensus replay lead",
                "exp-20260601-001": "shared observe-only free-data consensus adapter",
                "exp-20260601-015": "positive no-core capacity gate, blocked by baseline drift",
                "exp-20260529-004": "accepted VBB cost/liquidity support using the same threshold family",
            },
            "single_causal_variable": CHANGED_VARIABLE,
            "acceptance_standard": (
                "docs/backtesting.md three-window before/after comparison. Retain only if "
                "aggregate EV/PnL and all three windows improve, risk/sample/concentration "
                "guards pass, and baseline/parity is clean."
            ),
            "reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_017_accepted_consensus_liquidity_efficiency.py"
            ),
        },
        "prediction": prediction,
        "calibration": calibration,
        "rule": {
            "rule_version": RULE_VERSION,
            "source_adapter_experiment_id": "exp-20260601-001",
            "source_replay_experiment_id": "exp-20260531-030",
            "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
            "max_signal_day_range_close_ratio": MAX_SIGNAL_DAY_RANGE_CLOSE,
            "feature_lookback_days": MIN_FEATURE_LOOKBACK_DAYS,
            "base_notional_usd": source.BASE_NOTIONAL_USD,
            "hold_days": source.HOLD_DAYS,
            "max_paper_trades_per_day": source.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": source.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate1": {
            "source": "docs/backtesting.md canonical three-window replay",
            "core_baseline_metrics": core_metrics_by_window,
            "baseline_drift": baseline_drift,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2,
            "runtime_fields": [
                "accepted free-data source paper rows",
                "signal-date ticker OHLCV rows",
                "20d average dollar volume through signal date",
                "signal-day high/low/close range ratio",
                "entry_date and target_price in operator_inputs/open_positions.json",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in results) >= 0.05,
            "note": "No core/live filter was added; this is a default-off paper candidate-quality gate.",
            "survival_by_window": {
                row["label"]: row["after"].get("survival_rate") for row in results
            },
        },
        "gate4": gate4,
        "aggregate": aggregate,
        "baseline_drift": baseline_drift,
        "results": results,
        "target_summary": target_summary,
        "after_target_trades_by_window": target_trades_by_window,
        "next_retry_requires": [
            "do not retry nearby liquidity/range thresholds on this frozen consensus sample",
            "clean current-code baseline parity versus docs/backtesting.md before any positive retention",
            "forward closed replacement-value rows before activation",
            "materially new cost field such as spread/borrow/availability if revisiting this lane",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_card(payload)
    _update_ticket_and_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_record(payload))
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "gate4": payload["gate4"],
                "target_summary": {
                    key: payload["target_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "pnl_by_window",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
