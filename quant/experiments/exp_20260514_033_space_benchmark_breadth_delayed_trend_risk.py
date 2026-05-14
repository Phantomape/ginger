"""exp-20260514-033: Space benchmark-breadth delayed trend risk.

Tests one causal variable on top of accepted exp-20260514-030: whether
official Space trend candidates whose 5d reaction is weak, 10d cash/same-theme
reaction is positive, and 10d SPY/QQQ/UFO/ARKX relative values are all positive
deserve a conservative extra default-off risk scalar when they do not already
clear the accepted same-theme strength floor.

This avoids LLM soft-ranking, noisy ticker expansion, lifecycle changes, and
nearby delayed-absorption scalar retunes.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (str(QUANT_DIR), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260513_038_space_source_diversity_risk as source_diversity_exp
import exp_20260514_002_space_forward_replacement_same_theme_strength_risk as same_theme_exp
import exp_20260514_028_space_source_diversity_trend_risk as accepted_exp
import exp_20260514_030_space_delayed_absorption_trend_risk as delayed_exp


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-033"
STEM = "space_benchmark_breadth_delayed_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-030"

ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR = 1.025
ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR = 1.025
BENCHMARK_BREADTH_RISK_SCALARS = (1.0, 1.025, 1.05, 1.075, 1.10)
TARGET_STRATEGY = "trend_long"

MAX_5D_CASH = 0.0
MIN_10D_CASH = 0.0
MIN_10D_SAME_THEME = 0.0
SAME_THEME_STRENGTH_CEILING = 500.0
MIN_10D_BENCHMARK_VALUE = 0.0
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(payload: Any) -> Any:
    return source_diversity_exp._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source_diversity_exp._write_json(path, payload)


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_jsonl_for_this_experiment(path: Path, entry: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    continue
            except json.JSONDecodeError:
                pass
            lines.append(line)
    lines.append(json.dumps(_safe(entry), separators=(",", ":"), sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _latest_closed_rows(path: Path) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ticker = str(row.get("ticker") or "").upper()
        event_id = str(row.get("event_id") or "")
        if not ticker or not event_id:
            continue
        key = (ticker, event_id)
        current_stamp = str(row.get("logged_at") or row.get("asof_date") or "")
        previous = latest.get(key)
        if previous is None:
            latest[key] = row
            continue
        previous_stamp = str(previous.get("logged_at") or previous.get("asof_date") or "")
        if current_stamp >= previous_stamp:
            latest[key] = row
    return list(latest.values())


def _horizon(row: dict[str, Any], name: str) -> dict[str, Any] | None:
    horizon = (row.get("horizons") or {}).get(name)
    if not isinstance(horizon, dict) or horizon.get("status") != "mature":
        return None
    return horizon


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _benchmark_breadth_profile_gate() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped: Counter[str] = Counter()
    official_tickers = set(source_diversity_exp.OFFICIAL_SPACE_TICKERS)

    for row in _latest_closed_rows(path):
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in official_tickers:
            skipped["not_official_space_ticker"] += 1
            continue
        if row.get("closed_decision") is not True:
            skipped["not_closed"] += 1
            continue
        if str(row.get("semantic_bucket") or "") == "attention_only":
            skipped["attention_only"] += 1
            continue
        h5 = _horizon(row, "5d")
        h10 = _horizon(row, "10d")
        if h5 is None or h10 is None:
            skipped["missing_mature_5d_or_10d"] += 1
            continue
        fields = {
            "5d_cash_relative_pnl": _as_float(h5.get("cash_relative_pnl")),
            "5d_same_theme_replacement_value": _as_float(
                h5.get("same_theme_replacement_value")
            ),
            "10d_cash_relative_pnl": _as_float(h10.get("cash_relative_pnl")),
            "10d_same_theme_replacement_value": _as_float(
                h10.get("same_theme_replacement_value")
            ),
            "10d_spy_relative_value": _as_float(h10.get("spy_relative_value")),
            "10d_qqq_relative_value": _as_float(h10.get("qqq_relative_value")),
            "10d_ufo_relative_value": _as_float(h10.get("ufo_relative_value")),
            "10d_arkx_relative_value": _as_float(h10.get("arkx_relative_value")),
        }
        if any(value is None for value in fields.values()):
            skipped["missing_forward_values"] += 1
            continue
        rows_by_ticker[ticker].append(
            {
                "ticker": ticker,
                "event_id": row.get("event_id"),
                "event_date": row.get("event_date"),
                "source_type": row.get("source_type"),
                "semantic_bucket": row.get("semantic_bucket"),
                "theme_segment": row.get("theme_segment"),
                "event_fields": row.get("event_fields"),
                **fields,
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    target_tickers: list[str] = []
    for ticker, rows in sorted(rows_by_ticker.items()):
        avg_5d_cash = _avg([float(row["5d_cash_relative_pnl"]) for row in rows])
        avg_5d_same = _avg([float(row["5d_same_theme_replacement_value"]) for row in rows])
        avg_10d_cash = _avg([float(row["10d_cash_relative_pnl"]) for row in rows])
        avg_10d_same = _avg(
            [float(row["10d_same_theme_replacement_value"]) for row in rows]
        )
        avg_10d_spy = _avg([float(row["10d_spy_relative_value"]) for row in rows])
        avg_10d_qqq = _avg([float(row["10d_qqq_relative_value"]) for row in rows])
        avg_10d_ufo = _avg([float(row["10d_ufo_relative_value"]) for row in rows])
        avg_10d_arkx = _avg([float(row["10d_arkx_relative_value"]) for row in rows])
        passed = bool(
            avg_5d_cash is not None
            and avg_10d_cash is not None
            and avg_10d_same is not None
            and avg_10d_spy is not None
            and avg_10d_qqq is not None
            and avg_10d_ufo is not None
            and avg_10d_arkx is not None
            and avg_5d_cash <= MAX_5D_CASH
            and avg_10d_cash > MIN_10D_CASH
            and MIN_10D_SAME_THEME < avg_10d_same < SAME_THEME_STRENGTH_CEILING
            and avg_10d_spy > MIN_10D_BENCHMARK_VALUE
            and avg_10d_qqq > MIN_10D_BENCHMARK_VALUE
            and avg_10d_ufo > MIN_10D_BENCHMARK_VALUE
            and avg_10d_arkx > MIN_10D_BENCHMARK_VALUE
        )
        profiles[ticker] = {
            "passed": passed,
            "closed_event_count": len(rows),
            "avg_5d_cash_relative_pnl": avg_5d_cash,
            "avg_5d_same_theme_replacement_value": avg_5d_same,
            "avg_10d_cash_relative_pnl": avg_10d_cash,
            "avg_10d_same_theme_replacement_value": avg_10d_same,
            "avg_10d_spy_relative_value": avg_10d_spy,
            "avg_10d_qqq_relative_value": avg_10d_qqq,
            "avg_10d_ufo_relative_value": avg_10d_ufo,
            "avg_10d_arkx_relative_value": avg_10d_arkx,
            "events": rows,
        }
        if passed:
            target_tickers.append(ticker)

    return {
        "passed": bool(target_tickers),
        "path": str(path.relative_to(PROJECT_ROOT)),
        "target_tickers": sorted(target_tickers),
        "profiles": profiles,
        "thresholds": {
            "max_avg_5d_cash_relative_pnl": MAX_5D_CASH,
            "min_avg_10d_cash_relative_pnl": MIN_10D_CASH,
            "min_avg_10d_same_theme_replacement_value": MIN_10D_SAME_THEME,
            "same_theme_strength_ceiling_to_avoid_exp002_overlap": (
                SAME_THEME_STRENGTH_CEILING
            ),
            "min_avg_10d_spy_qqq_ufo_arkx_relative_value": (
                MIN_10D_BENCHMARK_VALUE
            ),
        },
        "skipped_counts": dict(sorted(skipped.items())),
    }


def _scale_and_record_extra(
    *,
    signal: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    marker: str,
    counts: Counter[str],
    adjustments: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> None:
    ticker = str(signal.get("ticker") or "").upper()
    shares_before = int(sizing.get("shares_to_buy") or 0)
    dollars_before = float(sizing.get("position_size_dollars") or 0.0)
    source_diversity_exp._scale_sizing(sizing, scalar, portfolio_value, marker)
    shares_after = int(sizing.get("shares_to_buy") or 0)
    dollars_after = float(sizing.get("position_size_dollars") or 0.0)
    counts[f"{marker}_eligible_signal"] += 1
    counts[f"{marker}_eligible_{ticker}"] += 1
    if shares_after != shares_before:
        counts[f"{marker}_changed_signal"] += 1
        counts[f"{marker}_changed_{ticker}"] += 1
    adjustments.append(
        {
            "ticker": ticker,
            "strategy": signal.get("strategy"),
            "marker": marker,
            "scalar": scalar,
            "shares_before_scalar": shares_before,
            "shares_after_scalar": shares_after,
            "dollars_before_scalar": dollars_before,
            "dollars_after_scalar": dollars_after,
            "profile": profile,
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_exp030_stack_variant(
    label: str,
    *,
    benchmark_breadth_scalar: float,
    benchmark_breadth_gate: dict[str, Any],
    delayed_gate: dict[str, Any],
    forward_gate: dict[str, Any],
    source_diversity_gate: dict[str, Any],
    attention_gate: dict[str, Any],
    single_event_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    original_scale_and_record = accepted_exp._scale_and_record
    delayed_tickers = set(delayed_gate["target_tickers"])
    delayed_profiles = delayed_gate["profiles"]
    benchmark_tickers = set(benchmark_breadth_gate["target_tickers"])
    benchmark_profiles = benchmark_breadth_gate["profiles"]
    delayed_adjustments: list[dict[str, Any]] = []
    benchmark_adjustments: list[dict[str, Any]] = []

    def patched_scale_and_record(
        *,
        signal: dict[str, Any],
        sizing: dict[str, Any],
        scalar: float,
        portfolio_value: float,
        marker: str,
        counts: Counter[str],
        adjustments: list[dict[str, Any]],
        profile: dict[str, Any] | None,
    ) -> None:
        original_scale_and_record(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=marker,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        ticker = str(signal.get("ticker") or "").upper()
        strategy = str(signal.get("strategy") or "")
        if strategy != TARGET_STRATEGY or not sizing:
            return
        if ticker in delayed_tickers:
            _scale_and_record_extra(
                signal=signal,
                sizing=sizing,
                scalar=ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR,
                portfolio_value=portfolio_value,
                marker="space_delayed_absorption_trend_risk",
                counts=counts,
                adjustments=delayed_adjustments,
                profile=delayed_profiles.get(ticker),
            )
            signal["space_delayed_absorption_trend_bucket"] = True
            signal["space_delayed_absorption_trend_scalar"] = (
                ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR
            )
            signal["space_delayed_absorption_profile"] = delayed_profiles.get(ticker)
        if ticker in benchmark_tickers:
            _scale_and_record_extra(
                signal=signal,
                sizing=sizing,
                scalar=benchmark_breadth_scalar,
                portfolio_value=portfolio_value,
                marker="space_benchmark_breadth_delayed_trend_risk",
                counts=counts,
                adjustments=benchmark_adjustments,
                profile=benchmark_profiles.get(ticker),
            )
            signal["space_benchmark_breadth_delayed_trend_bucket"] = True
            signal["space_benchmark_breadth_delayed_trend_scalar"] = (
                benchmark_breadth_scalar
            )
            signal["space_benchmark_breadth_delayed_profile"] = (
                benchmark_profiles.get(ticker)
            )

    accepted_exp._scale_and_record = patched_scale_and_record
    try:
        variant = accepted_exp._run_variant(
            label,
            source_diversity_trend_scalar=ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR,
            forward_gate=forward_gate,
            source_diversity_gate=source_diversity_gate,
            attention_gate=attention_gate,
            single_event_gate=single_event_gate,
            government_contract_gate=government_contract_gate,
            source_gate=source_gate,
            multi_event_gate=multi_event_gate,
            liquidity_gate=liquidity_gate,
            company_release_gate=company_release_gate,
            financing_gate=financing_gate,
        )
    finally:
        accepted_exp._scale_and_record = original_scale_and_record

    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    delayed_counts = {
        key: value
        for key, value in sorted(counts.items())
        if "space_delayed_absorption_trend_risk" in key
    }
    benchmark_counts = {
        key: value
        for key, value in sorted(counts.items())
        if "space_benchmark_breadth_delayed_trend_risk" in key
    }
    by_window_counts = {
        name: {
            key: value
            for key, value in sorted(
                (row.get("source_diversity_trend_counts") or {}).items()
            )
            if "space_benchmark_breadth_delayed_trend_risk" in key
        }
        for name, row in variant["by_window"].items()
    }
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "accepted_source_diversity_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR
        ),
        "accepted_delayed_absorption_trend_scalar": (
            ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR
        ),
        "space_benchmark_breadth_delayed_trend_scalar": benchmark_breadth_scalar,
        "benchmark_breadth_target_tickers": sorted(benchmark_tickers),
        "benchmark_breadth_thresholds": benchmark_breadth_gate["thresholds"],
    }
    variant["delayed_absorption_counts"] = delayed_counts
    variant["benchmark_breadth_counts"] = benchmark_counts
    variant["benchmark_breadth_counts_by_window"] = by_window_counts
    variant["delayed_absorption_adjustment_summary"] = (
        source_diversity_exp._adjustment_summary(delayed_adjustments)
    )
    variant["benchmark_breadth_adjustment_summary"] = (
        source_diversity_exp._adjustment_summary(benchmark_adjustments)
    )
    variant["benchmark_breadth_adjustment_sample"] = benchmark_adjustments[:25]
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        name: source_diversity_exp._delta(
            payload["metrics"],
            before["by_window"][name]["metrics"],
        )
        for name, payload in variant["by_window"].items()
    }
    ev_regressions = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] < -1e-9
    }
    ev_improvements = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] > 1e-9
    }
    counts = variant.get("benchmark_breadth_counts") or {}
    changed_count = int(
        counts.get("space_benchmark_breadth_delayed_trend_risk_changed_signal", 0)
    )
    eligible_count = int(
        counts.get("space_benchmark_breadth_delayed_trend_risk_eligible_signal", 0)
    )
    scalar = float(
        variant["parameters"]["space_benchmark_breadth_delayed_trend_scalar"]
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "eligible_benchmark_breadth_signal_count": eligible_count,
        "changed_benchmark_breadth_signal_count": changed_count,
        "accepted": bool(
            scalar != 1.0
            and changed_count > 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and aggregate_delta["max_drawdown_pct_max"]
            <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE
            and variant["aggregate"]["trade_count_sum"] >= MIN_TRADE_COUNT
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space benchmark-breadth delayed trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_benchmark_breadth_delayed_trend_scalar` for official Space "
            "`trend_long` signals whose closed event-state profile has weak "
            "average 5d cash reaction, positive 10d cash and same-theme value, "
            "same-theme value below the accepted $500 strength floor, and "
            "positive 10d SPY/QQQ/UFO/ARKX relative value. Candidate pool, "
            "ranking, targets, stops, LLM/news, and accepted exp030 stack stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        f"- Best scalar: `{best['parameters']['space_benchmark_breadth_delayed_trend_scalar']}`",
        (
            "- Aggregate delta vs exp030: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Benchmark-breadth signals changed: "
            f"`{gate['changed_benchmark_breadth_signal_count']}` of "
            f"`{gate['eligible_benchmark_breadth_signal_count']}` eligible"
        ),
        (
            "- Target tickers: "
            f"`{', '.join(best['parameters']['benchmark_breadth_target_tickers'])}`"
        ),
        "",
        "## Three-Window Deltas vs Exp030",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        counts = best["benchmark_breadth_counts_by_window"][name]
        adjusted = counts.get(
            "space_benchmark_breadth_delayed_trend_risk_changed_signal",
            0,
        )
        lines.append(
            "| {name} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {trades} | {survival:.6f} | {adjusted} |".format(
                name=name,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            "## Gate Checks",
            f"- Gate 2 passed: `{payload['gate2_field_checks']['passed']}`",
            f"- Gate 3 survival passed: `{payload['gate3']['passed']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "best_parameters": payload["best_variant"]["parameters"],
        "aggregate_delta_vs_before": payload["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
    }


def run() -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc).isoformat()
    core = source_diversity_exp._run_core_baseline()
    attention_gate = source_diversity_exp._field_check_attention_overlay_profile()
    single_event_gate = source_diversity_exp._field_check_single_event_defense_profile()
    government_contract_gate = (
        source_diversity_exp._field_check_government_contract_profile()
    )
    source_gate = source_diversity_exp._event_seed_profiles()
    multi_event_gate = source_diversity_exp._field_check_multi_event_depth()
    liquidity_gate = source_diversity_exp._field_check_watch_liquidity_tier()
    company_release_gate = source_diversity_exp._field_check_company_release_source()
    financing_gate = source_diversity_exp._accepted_financing_profile_gate()
    source_diversity_gate = source_diversity_exp._field_check_source_diversity_profile()
    forward_gate = same_theme_exp._forward_replacement_profile_gate()
    delayed_gate = delayed_exp._delayed_absorption_profile_gate(forward_gate)
    benchmark_breadth_gate = _benchmark_breadth_profile_gate()

    variants = [
        _run_exp030_stack_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            benchmark_breadth_scalar=scalar,
            benchmark_breadth_gate=benchmark_breadth_gate,
            delayed_gate=delayed_gate,
            forward_gate=forward_gate,
            source_diversity_gate=source_diversity_gate,
            attention_gate=attention_gate,
            single_event_gate=single_event_gate,
            government_contract_gate=government_contract_gate,
            source_gate=source_gate,
            multi_event_gate=multi_event_gate,
            liquidity_gate=liquidity_gate,
            company_release_gate=company_release_gate,
            financing_gate=financing_gate,
        )
        for scalar in BENCHMARK_BREADTH_RISK_SCALARS
    ]
    before = variants[0]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

    accepted_variants = [variant for variant in variants if variant["gate"]["accepted"]]
    if accepted_variants:
        best = max(
            accepted_variants,
            key=lambda variant: (
                variant["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda variant: (
                variant["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    runtime_gate = {
        "passed": best["gate"]["eligible_benchmark_breadth_signal_count"] > 0,
        "eligible_signal_count": best["gate"][
            "eligible_benchmark_breadth_signal_count"
        ],
        "required_runtime_fields": [
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.5d",
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d",
            "horizons.5d.cash_relative_pnl",
            "horizons.10d.cash_relative_pnl",
            "horizons.10d.same_theme_replacement_value",
            "horizons.10d.spy_relative_value",
            "horizons.10d.qqq_relative_value",
            "horizons.10d.ufo_relative_value",
            "horizons.10d.arkx_relative_value",
            "signal.strategy",
            "signal.sizing.shares_to_buy",
        ],
        "sample_rows": best.get("benchmark_breadth_adjustment_sample", [])[:10],
    }
    gate2 = {
        "open_positions": source_diversity_exp._gate2_open_positions(),
        "attention_overlay_profile": attention_gate,
        "single_event_defense_profile": single_event_gate,
        "government_contract_profile": government_contract_gate,
        "official_customer_source_profile": source_gate,
        "multi_event_depth": multi_event_gate,
        "liquidity_tier": liquidity_gate,
        "company_release_source": company_release_gate,
        "financing_dilution_profile": financing_gate,
        "source_diversity_profile": source_diversity_gate,
        "forward_replacement_profile": forward_gate,
        "delayed_absorption_profile": delayed_gate,
        "benchmark_breadth_profile": benchmark_breadth_gate,
        "benchmark_breadth_runtime_state": runtime_gate,
    }
    gate2["passed"] = all(
        [
            gate2["open_positions"]["passed"],
            attention_gate["passed"],
            single_event_gate["passed"],
            government_contract_gate["passed"],
            source_gate["passed"],
            multi_event_gate["passed"],
            liquidity_gate["passed"],
            company_release_gate["passed"],
            financing_gate["passed"],
            source_diversity_gate["passed"],
            forward_gate["passed"],
            delayed_gate["passed"],
            benchmark_breadth_gate["passed"],
            runtime_gate["passed"],
        ]
    )

    decision = "accepted" if best["gate"]["accepted"] else "rejected"
    status = (
        "accepted_default_off_space_benchmark_breadth_delayed_trend_risk"
        if decision == "accepted"
        else "rejected_space_benchmark_breadth_delayed_trend_risk"
    )
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "The benchmark-breadth delayed trend state did not clear Gate 4 "
            "versus the accepted exp030 stack. Do not retry this exact LUNR-like "
            "broad-benchmark substitute for same-theme strength without new "
            "closed forward rows."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "Space official catalysts can be alpha-positive even when "
            "same-theme replacement strength is below the accepted $500 floor, "
            "provided the 5d reaction is still weak and the 10d move beats cash, "
            "SPY, QQQ, UFO, and ARKX. This should help trend continuation "
            "allocation without adding tickers or LLM authority."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_benchmark_breadth_delayed_trend_scalar",
        "single_causal_variable": (
            "extra trend_long risk scalar for the broad-benchmark delayed "
            "forward profile; all accepted Space helpers through exp030 stay fixed"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol plus Space frozen snapshots",
            "windows": source_diversity_exp.WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"]
                for label, window in source_diversity_exp.WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "risk allocation: a broad-benchmark-confirmed delayed Space "
                "trend profile may add alpha when same-theme strength is "
                "positive but below the $500 strength bucket."
            ),
            "q2_prior_experiments": [
                "exp-20260514-030 accepted delayed absorption only where weak 5d became strong 10d same-theme evidence.",
                "exp-20260514-031 rejected all-trend scope broadening because the new scope touched only old_thin.",
                "exp-20260514-020 rejected same-theme-negative benchmark laggards; this requires same-theme > 0 and all four broad benchmarks > 0.",
                "VSAT/IRDM candidate-pool expansion failed gates, so ticker breadth is fixed.",
            ],
            "q3_single_causal_variable": (
                "Only this broad-benchmark delayed trend scalar changes; no "
                "entry, exit, ranking, target, LLM/news, or live-slot change."
            ),
            "q4_acceptance_standard": (
                "Same three Space windows; require positive aggregate EV/PnL, "
                "at least two EV-improved windows, no EV-regressed windows, max "
                "DD damage <= 0.5pp, survival >= 5%, >=50 trades, and nonzero "
                "changed benchmark-breadth signals."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best["aggregate"]["min_survival_rate"],
            "passed": best["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "tested_scalars": list(BENCHMARK_BREADTH_RISK_SCALARS),
            "selected_scalar": best["parameters"][
                "space_benchmark_breadth_delayed_trend_scalar"
            ],
            "benchmark_breadth_target_tickers": benchmark_breadth_gate[
                "target_tickers"
            ],
            "benchmark_breadth_thresholds": benchmark_breadth_gate["thresholds"],
            "locked_variables": [
                "official Space candidate pool",
                "all accepted Space scalars through exp030",
                "entry filters",
                "candidate ranking",
                "targets/stops",
                "MAX_POSITIONS",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best,
        "best_variant_gate": best["gate"],
        "decision": decision,
        "status": status,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only with shared Space metadata/helper and parity tests; "
            "live Space slots remain zero."
            if decision == "accepted"
            else "Needs new closed Space forward rows or a different catalyst-quality field."
        ),
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": decision == "accepted",
            "shared_policy_changed": decision == "accepted",
            "backtester_adapter_changed": False,
            "daily_report_metadata_changed": decision == "accepted",
            "run_adapter_changed": decision == "accepted",
            "replay_only": True,
            "parity_test_added": decision == "accepted",
            "live_slots": 0,
            "live_slots_changed": False,
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains sparse. Nearby source-diversity, company-source, "
            "and delayed-absorption scalars are anti-repeat families. This tests a "
            "new closed forward state using already logged broad benchmark values."
        ),
        "known_risks": [
            "Space remains default-off; this does not authorize live Space slots.",
            "The target slice may be narrow and must be rejected if it is single-window only.",
        ],
        "llm_metrics": {"used_llm": False},
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    logs_dir = PROJECT_ROOT / "docs" / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "docs" / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "docs" / "experiments" / "artifacts"
    for directory in (exp_dir, logs_dir, tickets_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    artifact = _artifact_markdown(payload)
    payload["artifact_markdown"] = artifact
    _write_json(exp_dir / f"{STEM}.json", payload)
    _write_json(logs_dir / f"{EXPERIMENT_ID}.json", payload)
    _write_json(tickets_dir / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (artifacts_dir / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        artifact,
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": payload["experiment_id"],
            "timestamp": payload["run_finished_at"],
            "lane": payload["lane"],
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "parameters": payload["parameters"],
            "date_range": payload["backtest_protocol"]["windows"],
            "before_metrics": payload["before"]["by_window"],
            "after_metrics": payload["best_variant"]["by_window"],
            "delta_metrics": payload["best_variant_gate"],
            "expected_value_score_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["expected_value_score_sum"],
            "total_pnl_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["total_pnl_sum"],
            "production_impact": payload["production_impact"],
            "decision": payload["decision"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "related_files": [
                f"quant/experiments/{Path(__file__).name}",
                f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
                f"docs/experiments/logs/{EXPERIMENT_ID}.json",
                f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
                f"docs/experiments/artifacts/{EXPERIMENT_ID}_{STEM}.md",
                "docs/experiment_log.jsonl",
            ],
        },
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    summary = {
        "experiment_id": result["experiment_id"],
        "status": result["status"],
        "decision": result["decision"],
        "selected_scalar": result["parameters"]["selected_scalar"],
        "target_tickers": result["parameters"]["benchmark_breadth_target_tickers"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "eligible_benchmark_breadth_signal_count": result["best_variant_gate"][
            "eligible_benchmark_breadth_signal_count"
        ],
        "changed_benchmark_breadth_signal_count": result["best_variant_gate"][
            "changed_benchmark_breadth_signal_count"
        ],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
