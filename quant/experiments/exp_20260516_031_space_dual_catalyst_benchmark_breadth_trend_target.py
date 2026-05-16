"""exp-20260516-031: Space dual-catalyst benchmark-breadth trend target.

Tests one lifecycle variable on top of accepted exp-20260516-029: whether
source-diverse dual-catalyst Space trend signals that also pass the closed
benchmark-breadth profile deserve a wider target ATR floor.

This deliberately avoids another nearby benchmark-breadth risk scalar. The
candidate pool, entries, risk scalars, ranking, LLM/news boundary, and live
Space slots stay fixed.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260516_029_space_dual_catalyst_benchmark_breadth_trend_risk as prior
import risk_engine
from risk_engine import _retarget_signal_with_atr_mult


LOGGER = logging.getLogger(__name__)

BASE = prior.BASE

EXPERIMENT_ID = "exp-20260516-031"
STEM = "space_dual_catalyst_benchmark_breadth_trend_target"
BEFORE_EXPERIMENT_ID = prior.EXPERIMENT_ID
BEFORE_STEM = prior.STEM

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
ACCEPTED_BENCHMARK_BREADTH_SCALAR = 1.0125
TARGET_ATR_FLOORS = (5.0, 6.0, 7.0, 8.0)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
MIN_SURVIVAL_RATE = BASE.MIN_SURVIVAL_RATE
MIN_TRADE_COUNT = BASE.MIN_TRADE_COUNT
MIN_ADJUSTED_TICKERS = BASE.MIN_ADJUSTED_TICKERS
MIN_ADJUSTED_WINDOWS = BASE.MIN_ADJUSTED_WINDOWS


def _safe(value: Any) -> Any:
    return prior._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> Any:
    numeric = _as_float(value)
    return round(numeric, digits) if numeric is not None else None


def _metric_rows(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {label: row["metrics"] for label, row in variant["by_window"].items()}


def _window_label(window: dict[str, Any]) -> str:
    for label, spec in BASE.exp041.source_diversity_exp.WINDOWS.items():
        if spec is window or (
            spec.get("start") == window.get("start")
            and spec.get("end") == window.get("end")
        ):
            return label
    return "unknown"


def _is_target_signal(
    signal: dict[str, Any],
    source_profile: dict[str, Any] | None,
    benchmark_tickers: set[str],
) -> bool:
    ticker = str(signal.get("ticker") or "").upper()
    return (
        str(signal.get("strategy") or "").lower() == TARGET_STRATEGY
        and ticker in benchmark_tickers
        and BASE.exp014._is_dual_catalyst_profile(source_profile)
    )


def _target_adjustment_summary(adjustments: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker = Counter(str(row.get("ticker") or "") for row in adjustments)
    by_window = Counter(str(row.get("window") or "") for row in adjustments)
    by_previous_mult = Counter(
        str(row.get("previous_target_mult")) for row in adjustments
    )
    return {
        "adjusted_signal_count": len(adjustments),
        "changed_tickers": sorted(ticker for ticker, count in by_ticker.items() if count),
        "changed_windows": sorted(window for window, count in by_window.items() if count),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_window": dict(sorted(by_window.items())),
        "by_previous_target_mult": dict(sorted(by_previous_mult.items())),
        "sample_adjusted": adjustments[:25],
    }


def _target_input_summary(
    *,
    eligible: list[dict[str, Any]],
    missing_inputs: list[dict[str, Any]],
    skipped_existing_width: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "eligible_signal_count": len(eligible),
        "missing_input_count": len(missing_inputs),
        "skipped_existing_width_count": len(skipped_existing_width),
        "eligible_by_ticker": dict(
            sorted(Counter(row.get("ticker") for row in eligible).items())
        ),
        "eligible_by_window": dict(
            sorted(Counter(row.get("window") for row in eligible).items())
        ),
        "missing_inputs_sample": missing_inputs[:12],
        "skipped_existing_width_sample": skipped_existing_width[:12],
    }


def _benchmark_breadth_target_field_check(gates: dict[str, Any]) -> dict[str, Any]:
    benchmark_gate = gates["benchmark_breadth_gate"]
    source_profiles = gates["source_diversity_gate"]["profiles"]
    benchmark_profiles = benchmark_gate.get("profiles") or {}
    benchmark_tickers = set(benchmark_gate.get("target_tickers") or [])
    target_tickers = [
        ticker
        for ticker, profile in source_profiles.items()
        if ticker in benchmark_tickers
        and BASE.exp014._is_dual_catalyst_profile(profile)
    ]
    required_profile_fields = [
        "avg_10d_cash_relative_pnl",
        "avg_10d_spy_relative_value",
        "avg_10d_qqq_relative_value",
        "avg_10d_ufo_relative_value",
        "avg_10d_arkx_relative_value",
    ]
    missing_profile_fields = {
        ticker: [
            field
            for field in required_profile_fields
            if benchmark_profiles.get(ticker, {}).get(field) is None
        ]
        for ticker in target_tickers
    }
    missing_profile_fields = {
        ticker: fields for ticker, fields in missing_profile_fields.items() if fields
    }
    return {
        "passed": bool(benchmark_gate.get("passed"))
        and bool(target_tickers)
        and not missing_profile_fields,
        "benchmark_gate_passed": bool(benchmark_gate.get("passed")),
        "target_profile_gate": "benchmark_breadth_gate",
        "target_tickers": sorted(target_tickers),
        "all_benchmark_tickers": sorted(benchmark_tickers),
        "required_signal_fields": [
            "signal.entry_price",
            "signal.stop_price",
            "signal.target_price",
            "signal.strategy",
            "signal.ticker",
            "features_by_ticker[ticker].atr",
            *required_profile_fields,
        ],
        "missing_profile_fields": missing_profile_fields,
    }


def _run_before_variant(gates: dict[str, Any]) -> dict[str, Any]:
    return prior._run_variant(
        benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
        gates=gates,
    )


def _run_target_variant(target_floor: float, gates: dict[str, Any]) -> dict[str, Any]:
    original_enrich = risk_engine.enrich_signals
    original_run_window = BASE.exp041.source_diversity_exp._run_window
    source_profiles = gates["source_diversity_gate"]["profiles"]
    benchmark_tickers = set(gates["benchmark_breadth_gate"]["target_tickers"])
    benchmark_profiles = gates["benchmark_breadth_gate"].get("profiles") or {}
    current_window = {"label": "unknown"}
    adjustments: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    missing_inputs: list[dict[str, Any]] = []
    skipped_existing_width: list[dict[str, Any]] = []

    def wrapped_run_window(window: dict[str, Any], universe: list[str], snapshot_key: str):
        previous_label = current_window["label"]
        current_window["label"] = _window_label(window)
        try:
            return original_run_window(window, universe, snapshot_key)
        finally:
            current_window["label"] = previous_label

    def wrapped_enrich(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            source_profile = source_profiles.get(ticker)
            if not _is_target_signal(signal, source_profile, benchmark_tickers):
                continue
            window = current_window["label"]
            strategy = str(signal.get("strategy") or "").lower()
            atr = _as_float((features_dict.get(ticker) or {}).get("atr"))
            entry = _as_float(signal.get("entry_price"))
            stop = _as_float(signal.get("stop_price"))
            previous_target = _as_float(signal.get("target_price"))
            previous_mult = _as_float(signal.get("target_mult_used"))
            if previous_mult is None:
                previous_mult = _as_float(atr_target_mult)
            if previous_mult is None and atr and entry is not None and previous_target is not None:
                previous_mult = (previous_target - entry) / atr
            eligible.append(
                {
                    "ticker": ticker,
                    "window": window,
                    "strategy": strategy,
                    "previous_target_mult": _round(previous_mult, 4),
                    "previous_target_price": _round(previous_target, 4),
                    "benchmark_profile": benchmark_profiles.get(ticker),
                }
            )
            missing = []
            if atr is None or atr <= 0:
                missing.append("features_by_ticker[ticker].atr")
            if entry is None:
                missing.append("signal.entry_price")
            if stop is None:
                missing.append("signal.stop_price")
            if previous_target is None:
                missing.append("signal.target_price")
            if previous_mult is None:
                missing.append("signal.target_mult_used_or_inferred")
            if missing:
                missing_inputs.append(
                    {
                        "ticker": ticker,
                        "window": window,
                        "strategy": strategy,
                        "missing": missing,
                    }
                )
                continue
            applied_mult = max(float(previous_mult), float(target_floor))
            if applied_mult <= float(previous_mult) + 1e-12:
                skipped_existing_width.append(
                    {
                        "ticker": ticker,
                        "window": window,
                        "strategy": strategy,
                        "target_floor": target_floor,
                        "previous_target_mult": _round(previous_mult, 4),
                    }
                )
                continue
            retargeted = _retarget_signal_with_atr_mult(signal, atr, applied_mult)
            retargeted["space_dual_catalyst_benchmark_breadth_trend_target_bucket"] = True
            retargeted[
                "space_dual_catalyst_benchmark_breadth_trend_target_floor"
            ] = target_floor
            retargeted[
                "space_dual_catalyst_benchmark_breadth_trend_target_previous_mult"
            ] = previous_mult
            retargeted[
                "space_dual_catalyst_benchmark_breadth_trend_target_previous_price"
            ] = previous_target
            signal.clear()
            signal.update(retargeted)
            adjustments.append(
                {
                    "ticker": ticker,
                    "window": window,
                    "strategy": strategy,
                    "target_floor": target_floor,
                    "previous_target_mult": _round(previous_mult, 4),
                    "applied_target_mult": _round(applied_mult, 4),
                    "previous_target_price": _round(previous_target, 4),
                    "target_price": _round(signal.get("target_price"), 4),
                    "entry_price": _round(entry, 4),
                    "stop_price": _round(stop, 4),
                    "atr": _round(atr, 4),
                    "trade_quality_score": _round(
                        signal.get("trade_quality_score"), 4
                    ),
                    "confidence_score": _round(signal.get("confidence_score"), 4),
                    "space_peer_momentum_state": signal.get(
                        "space_peer_momentum_state"
                    ),
                    "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                    "benchmark_profile": benchmark_profiles.get(ticker),
                }
            )
        return enriched

    risk_engine.enrich_signals = wrapped_enrich
    BASE.exp041.source_diversity_exp._run_window = wrapped_run_window
    try:
        variant = _run_before_variant(gates)
    finally:
        risk_engine.enrich_signals = original_enrich
        BASE.exp041.source_diversity_exp._run_window = original_run_window

    variant["label"] = f"{STEM}_{str(target_floor).replace('.', '_')}"
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "space_dual_catalyst_benchmark_breadth_trend_scalar": (
            ACCEPTED_BENCHMARK_BREADTH_SCALAR
        ),
        "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor": (
            target_floor
        ),
        "target_strategy": TARGET_STRATEGY,
        "target_profile_gate": "benchmark_breadth_gate",
        "target_rule": (
            "Floor target ATR multiple only for source-diverse dual-catalyst "
            "benchmark-breadth Space trend_long signals."
        ),
    }
    variant["target_input_summary"] = _target_input_summary(
        eligible=eligible,
        missing_inputs=missing_inputs,
        skipped_existing_width=skipped_existing_width,
    )
    variant["target_adjustment_summary"] = _target_adjustment_summary(adjustments)
    variant["target_adjustment_sample"] = adjustments[:25]
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = BASE.exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        label: BASE.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in variant["by_window"].items()
    }
    ev_improved = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] < -1e-9
    }
    adjustment_summary = variant.get("target_adjustment_summary") or {}
    input_summary = variant.get("target_input_summary") or {}
    changed_count = int(adjustment_summary.get("adjusted_signal_count", 0) or 0)
    changed_tickers = adjustment_summary.get("changed_tickers") or []
    changed_windows = adjustment_summary.get("changed_windows") or []
    target_floor = float(
        variant["parameters"][
            "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor"
        ]
    )
    passed = bool(
        target_floor > 0.0
        and input_summary.get("eligible_signal_count", 0) > 0
        and input_summary.get("missing_input_count", 0) == 0
        and changed_count > 0
        and len(changed_tickers) >= MIN_ADJUSTED_TICKERS
        and len(changed_windows) >= MIN_ADJUSTED_WINDOWS
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"]
        <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "eligible_target_signal_count": input_summary.get("eligible_signal_count", 0),
        "missing_target_input_count": input_summary.get("missing_input_count", 0),
        "changed_target_signal_count": changed_count,
        "changed_tickers": changed_tickers,
        "changed_windows": changed_windows,
        "reasons": {
            "eligible_target_signals": input_summary.get("eligible_signal_count", 0),
            "target_inputs_complete": input_summary.get("missing_input_count", 0) == 0,
            "changed_signals": changed_count,
            "adjusted_ticker_count_ok": len(changed_tickers) >= MIN_ADJUSTED_TICKERS,
            "adjusted_window_count_ok": len(changed_windows) >= MIN_ADJUSTED_WINDOWS,
            "aggregate_ev_delta_positive": aggregate_delta[
                "expected_value_score_sum"
            ]
            > 0.0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= MIN_TRADE_COUNT,
        },
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    selected_floor = best["parameters"][
        "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor"
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": (
            "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor"
        ),
        "parameters": {
            "target_atr_floors_tested": list(TARGET_ATR_FLOORS),
            "selected_target_atr_floor": selected_floor,
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_benchmark_breadth_scalar": ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "target_strategy": TARGET_STRATEGY,
            "target_profile_gate": "benchmark_breadth_gate",
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in BASE.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": _metric_rows(before),
        "by_window_after_metrics": _metric_rows(best),
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "total_pnl_delta": gate["aggregate_delta_vs_before"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": BASE._risk_distribution(before),
            "after": BASE._risk_distribution(best),
        },
        "gate_answers": {
            "1_alpha_hypothesis": payload["hypothesis"],
            "2_prior_similar_experiments": [
                "exp-20260511-032 tested broad official Space trend target width.",
                "exp-20260513-026 rejected IWM peer-leader target floors.",
                "exp-20260516-029 accepted a tiny benchmark-breadth dual-catalyst risk scalar on LUNR/RKLB.",
                "This run does not retry risk scalar strength; it isolates target geometry on the current exp029 bucket.",
            ],
            "3_single_causal_variable": (
                "Only target ATR floor changes for the source-diverse "
                "dual-catalyst benchmark-breadth trend bucket; pool, entries, "
                "risk scalars, stops, ranking, LLM/news, and live slots stay fixed."
            ),
            "4_success_criteria": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV/PnL, at least two EV-improved windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival "
                ">= 5%, trade count >= 50, complete target inputs, and changed "
                "signals across at least two tickers and two windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_031_space_dual_catalyst_benchmark_breadth_trend_target.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: the target ATR floor did not satisfy the fixed "
            "three-window EV/PnL, drawdown, window breadth, and cohort guards."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry this target-floor axis on the frozen LUNR/RKLB cohort "
            "without new target-touch or mature forward replacement evidence."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted helper must be promoted only through shared "
                "space_catalyst_sleeve.py target policy and parity tests; "
                "live Space slots remain zero."
                if promoted
                else "Experiment-only replay patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "Recent Space risk scalars are already concentrated in the same "
            "LUNR/RKLB bucket, LLM soft-ranking lacks dense attribution, and "
            "pool expansion has been noisy. This tests lifecycle capture on the "
            "existing production-visible cohort instead of adding tickers or "
            "another scalar."
        ),
        "related_files": [
            "quant/experiments/exp_20260516_031_space_dual_catalyst_benchmark_breadth_trend_target.py",
            "data/experiments/exp-20260516-031/space_dual_catalyst_benchmark_breadth_trend_target.json",
            "docs/experiments/logs/exp-20260516-031.json",
            "docs/experiments/tickets/exp-20260516-031.json",
            "docs/experiments/artifacts/exp-20260516-031_space_dual_catalyst_benchmark_breadth_trend_target.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space dual-catalyst benchmark-breadth trend target",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_dual_catalyst_benchmark_breadth_trend_target_atr_floor` "
            f"on top of accepted `{BEFORE_EXPERIMENT_ID}`."
        ),
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- dual catalyst profile field check passed: `{payload['dual_profile_field_check']['passed']}`",
        f"- benchmark-breadth target field check passed: `{payload['benchmark_breadth_target_field_check']['passed']}`",
        f"- target input check passed: `{payload['target_input_gate']['passed']}`",
        f"- target tickers: `{payload['benchmark_breadth_target_field_check'].get('target_tickers')}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; this is a target-width sweep.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = best["by_window"][label]["metrics"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant",
            f"- target ATR floor: `{best['parameters']['space_dual_catalyst_benchmark_breadth_trend_target_atr_floor']}`",
            f"- eligible signals: `{gate['eligible_target_signal_count']}`",
            f"- changed signals: `{gate['changed_target_signal_count']}`",
            f"- changed tickers: `{gate['changed_tickers']}`",
            f"- changed windows: `{gate['changed_windows']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- max drawdown pct max delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            f"  backtester_adapter_changed: {str(promoted).lower()}",
            f"  run_adapter_changed: {str(promoted).lower()}",
            f"  replay_only: {str(not promoted).lower()}",
            f"  parity_test_added: {str(promoted).lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Benchmark-breadth dual-catalyst Space target floor "
            f"{best['parameters']['space_dual_catalyst_benchmark_breadth_trend_target_atr_floor']} "
            f"changed {gate['changed_target_signal_count']} signals with aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    BASE.exp008._install_experiment_path_compat()
    gates = BASE.exp021._collect_gates()
    field_check = BASE.exp051._open_position_field_check()
    dual_profile_field_check = BASE.exp014._field_check_dual_catalyst_profiles()
    benchmark_breadth_target_field_check = _benchmark_breadth_target_field_check(gates)
    if not field_check["passed"]:
        raise RuntimeError(f"Open-position field check failed: {field_check}")
    if not dual_profile_field_check["passed"]:
        raise RuntimeError(
            f"Dual-catalyst profile field check failed: {dual_profile_field_check}"
        )
    if not benchmark_breadth_target_field_check["passed"]:
        raise RuntimeError(
            "Benchmark-breadth target field check failed: "
            f"{benchmark_breadth_target_field_check}"
        )

    before = _run_before_variant(gates)
    variants = [_run_target_variant(floor, gates) for floor in TARGET_ATR_FLOORS]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)
    accepted = [variant for variant in variants if variant["gate"]["passed"]]
    if accepted:
        best = max(
            accepted,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    target_input_gate = {
        "passed": bool(
            (best.get("target_input_summary") or {}).get("eligible_signal_count", 0)
            > 0
            and (best.get("target_input_summary") or {}).get("missing_input_count", 0)
            == 0
        ),
        **(best.get("target_input_summary") or {}),
    }
    decision = "accept" if best["gate"]["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "gates": gates,
        "field_check": field_check,
        "dual_profile_field_check": dual_profile_field_check,
        "benchmark_breadth_target_field_check": benchmark_breadth_target_field_check,
        "target_input_gate": target_input_gate,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_floor": [
            {
                "target_atr_floor": variant["parameters"][
                    "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "hypothesis": (
            "The current accepted Space alpha is concentrated in source-diverse "
            "dual-catalyst benchmark-breadth trend signals. If this is a true "
            "convex event-trend state rather than only a sizing state, widening "
            "the target ATR floor should capture more upside without adding "
            "tickers, LLM soft-ranking, or another risk scalar."
        ),
        "changed_variable": (
            "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor"
        ),
    }
    payload["experiment_log_record"] = _experiment_record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    payload = run()
    persist(payload)
    best = payload["best_variant"]
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_target_atr_floor": best["parameters"][
                        "space_dual_catalyst_benchmark_breadth_trend_target_atr_floor"
                    ],
                    "eligible_signals": gate["eligible_target_signal_count"],
                    "changed_signals": gate["changed_target_signal_count"],
                    "changed_tickers": gate["changed_tickers"],
                    "changed_windows": gate["changed_windows"],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "max_drawdown_delta": gate["aggregate_delta_vs_before"][
                        "max_drawdown_pct_max"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                    "gate_reasons": gate["reasons"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
