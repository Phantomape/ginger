"""exp-20260514-030: Space delayed-absorption trend risk.

Tests one causal variable on top of accepted exp-20260514-028: whether
official Space catalyst profiles whose 5d reaction is still weak but whose
closed 10d same-theme replacement value is strong deserve one additional
conservative risk scalar, restricted to `trend_long`.

This avoids LLM soft-ranking and ticker-pool expansion. It uses only closed
forward outcome metadata already recorded by the Space catalyst shadow ledger.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
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


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-030"
STEM = "space_delayed_absorption_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-028"

ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR = 1.025
DELAYED_ABSORPTION_RISK_SCALARS = (1.0, 1.025, 1.05, 1.075, 1.10)
DELAYED_ABSORPTION_MAX_5D_CASH = 0.0
DELAYED_ABSORPTION_MIN_10D_CASH = 0.0
DELAYED_ABSORPTION_MIN_10D_SAME_THEME = 500.0
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
TARGET_STRATEGY = "trend_long"


def _safe(payload: Any) -> Any:
    return source_diversity_exp._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source_diversity_exp._write_json(path, payload)


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


def _horizon(row: dict[str, Any], name: str) -> dict[str, Any] | None:
    horizon = (row.get("horizons") or {}).get(name)
    if not isinstance(horizon, dict) or horizon.get("status") != "mature":
        return None
    return horizon


def _value(horizon: dict[str, Any], key: str) -> float | None:
    value = horizon.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_closed_rows(path: Path) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ticker = str(row.get("ticker") or "").upper()
        event_id = str(row.get("event_id") or "")
        if not ticker or not event_id:
            continue
        key = (ticker, event_id)
        previous = latest.get(key)
        if previous is None:
            latest[key] = row
            continue
        current_stamp = str(row.get("logged_at") or row.get("asof_date") or "")
        previous_stamp = str(previous.get("logged_at") or previous.get("asof_date") or "")
        if current_stamp >= previous_stamp:
            latest[key] = row
    return list(latest.values())


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _delayed_absorption_profile_gate(forward_gate: dict[str, Any]) -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
    strength_tickers = set(
        same_theme_exp._target_tickers_for_floor(
            forward_gate,
            DELAYED_ABSORPTION_MIN_10D_SAME_THEME,
        )
    )
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped: Counter[str] = Counter()

    for row in _latest_closed_rows(path):
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in strength_tickers:
            skipped["not_in_existing_same_theme_strength_targets"] += 1
            continue
        if not source_diversity_exp._is_non_attention_official_event(row):
            skipped["not_official_non_attention"] += 1
            continue
        h5 = _horizon(row, "5d")
        h10 = _horizon(row, "10d")
        if h5 is None or h10 is None:
            skipped["missing_mature_5d_or_10d"] += 1
            continue
        h5_cash = _value(h5, "cash_relative_pnl")
        h5_same = _value(h5, "same_theme_replacement_value")
        h10_cash = _value(h10, "cash_relative_pnl")
        h10_same = _value(h10, "same_theme_replacement_value")
        if None in (h5_cash, h5_same, h10_cash, h10_same):
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
                "5d_cash_relative_pnl": h5_cash,
                "5d_same_theme_replacement_value": h5_same,
                "10d_cash_relative_pnl": h10_cash,
                "10d_same_theme_replacement_value": h10_same,
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    target_tickers: list[str] = []
    for ticker, rows in sorted(rows_by_ticker.items()):
        avg_5d_cash = _avg([row["5d_cash_relative_pnl"] for row in rows])
        avg_5d_same = _avg([row["5d_same_theme_replacement_value"] for row in rows])
        avg_10d_cash = _avg([row["10d_cash_relative_pnl"] for row in rows])
        avg_10d_same = _avg([row["10d_same_theme_replacement_value"] for row in rows])
        passed = bool(
            avg_5d_cash is not None
            and avg_10d_cash is not None
            and avg_10d_same is not None
            and avg_5d_cash <= DELAYED_ABSORPTION_MAX_5D_CASH
            and avg_10d_cash > DELAYED_ABSORPTION_MIN_10D_CASH
            and avg_10d_same >= DELAYED_ABSORPTION_MIN_10D_SAME_THEME
        )
        profiles[ticker] = {
            "passed": passed,
            "closed_event_count": len(rows),
            "avg_5d_cash_relative_pnl": avg_5d_cash,
            "avg_5d_same_theme_replacement_value": avg_5d_same,
            "avg_10d_cash_relative_pnl": avg_10d_cash,
            "avg_10d_same_theme_replacement_value": avg_10d_same,
            "events": rows,
        }
        if passed:
            target_tickers.append(ticker)

    return {
        "passed": bool(target_tickers),
        "path": str(path.relative_to(PROJECT_ROOT)),
        "base_same_theme_strength_target_tickers": sorted(strength_tickers),
        "target_tickers": sorted(target_tickers),
        "profiles": profiles,
        "thresholds": {
            "max_avg_5d_cash_relative_pnl": DELAYED_ABSORPTION_MAX_5D_CASH,
            "min_avg_10d_cash_relative_pnl": DELAYED_ABSORPTION_MIN_10D_CASH,
            "min_avg_10d_same_theme_replacement_value": (
                DELAYED_ABSORPTION_MIN_10D_SAME_THEME
            ),
        },
        "skipped_counts": dict(sorted(skipped.items())),
    }


def _run_accepted_before(
    label: str,
    *,
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
    return accepted_exp._run_variant(
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


def _run_delayed_variant(
    label: str,
    *,
    delayed_absorption_scalar: float,
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
    target_tickers = set(delayed_gate["target_tickers"])
    profiles = delayed_gate["profiles"]
    delayed_adjustments: list[dict[str, Any]] = []

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
        if ticker not in target_tickers or strategy != TARGET_STRATEGY or not sizing:
            return

        shares_before = int(sizing.get("shares_to_buy") or 0)
        dollars_before = float(sizing.get("position_size_dollars") or 0.0)
        source_diversity_exp._scale_sizing(
            sizing,
            delayed_absorption_scalar,
            portfolio_value,
            "space_delayed_absorption_trend_risk",
        )
        shares_after = int(sizing.get("shares_to_buy") or 0)
        dollars_after = float(sizing.get("position_size_dollars") or 0.0)
        counts["delayed_absorption_eligible_signal"] += 1
        counts[f"delayed_absorption_eligible_{ticker}"] += 1
        if shares_after != shares_before:
            counts["space_delayed_absorption_trend_risk_changed_signal"] += 1
            counts[f"space_delayed_absorption_trend_risk_changed_{ticker}"] += 1

        delayed_row = {
            "ticker": ticker,
            "strategy": strategy,
            "marker": "space_delayed_absorption_trend_risk",
            "scalar": delayed_absorption_scalar,
            "shares_before_scalar": shares_before,
            "shares_after_scalar": shares_after,
            "dollars_before_scalar": dollars_before,
            "dollars_after_scalar": dollars_after,
            "delayed_absorption_profile": profiles.get(ticker),
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
        delayed_adjustments.append(deepcopy(delayed_row))
        adjustments.append(delayed_row)
        signal["space_delayed_absorption_trend_bucket"] = True
        signal["space_delayed_absorption_trend_scalar"] = delayed_absorption_scalar
        signal["space_delayed_absorption_profile"] = profiles.get(ticker)

    accepted_exp._scale_and_record = patched_scale_and_record
    try:
        variant = _run_accepted_before(
            label,
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
        if "delayed_absorption" in key
        or key.startswith("space_delayed_absorption_trend_risk")
    }
    by_window_delayed_counts = {
        name: {
            key: value
            for key, value in sorted(
                (row.get("source_diversity_trend_counts") or {}).items()
            )
            if "delayed_absorption" in key
            or key.startswith("space_delayed_absorption_trend_risk")
        }
        for name, row in variant["by_window"].items()
    }
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "accepted_source_diversity_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR
        ),
        "space_delayed_absorption_trend_scalar": delayed_absorption_scalar,
        "delayed_absorption_target_tickers": sorted(target_tickers),
        "delayed_absorption_thresholds": delayed_gate["thresholds"],
    }
    variant["delayed_absorption_counts"] = delayed_counts
    variant["delayed_absorption_counts_by_window"] = by_window_delayed_counts
    variant["delayed_absorption_adjustment_summary"] = (
        source_diversity_exp._adjustment_summary(delayed_adjustments)
    )
    variant["delayed_absorption_adjustment_sample"] = delayed_adjustments[:25]
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
    counts = variant.get("delayed_absorption_counts") or {}
    changed_count = int(
        counts.get("space_delayed_absorption_trend_risk_changed_signal", 0)
    )
    eligible_count = int(counts.get("delayed_absorption_eligible_signal", 0))
    scalar = float(variant["parameters"]["space_delayed_absorption_trend_scalar"])
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "eligible_delayed_absorption_signal_count": eligible_count,
        "changed_delayed_absorption_signal_count": changed_count,
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


def _gate2_runtime_state(neutral_variant: dict[str, Any]) -> dict[str, Any]:
    eligible = int(
        (neutral_variant.get("delayed_absorption_counts") or {}).get(
            "delayed_absorption_eligible_signal",
            0,
        )
    )
    samples = neutral_variant.get("delayed_absorption_adjustment_sample", [])
    return {
        "passed": eligible > 0,
        "required_runtime_fields": [
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.5d",
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d",
            "horizons.5d.cash_relative_pnl",
            "horizons.10d.cash_relative_pnl",
            "horizons.10d.same_theme_replacement_value",
            "signal.strategy",
            "signal.sizing.shares_to_buy",
        ],
        "eligible_signal_count_at_neutral_before": eligible,
        "sample_rows": samples[:10],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space delayed-absorption trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_delayed_absorption_trend_scalar` for `trend_long` Space "
            "signals whose closed event-state profile has weak average 5d cash "
            "reaction but strong 10d cash and same-theme replacement value. "
            "Candidate pool, ranking, targets, stops, LLM/news, and accepted "
            "exp-028 stack stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        f"- Best scalar: `{best['parameters']['space_delayed_absorption_trend_scalar']}`",
        (
            "- Aggregate delta vs exp-028: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Delayed-absorption signals changed: "
            f"`{gate['changed_delayed_absorption_signal_count']}` of "
            f"`{gate['eligible_delayed_absorption_signal_count']}` eligible"
        ),
        (
            "- Target tickers: "
            f"`{', '.join(best['parameters']['delayed_absorption_target_tickers'])}`"
        ),
        "",
        "## Three-Window Deltas vs Exp-028",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | delayed adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        delayed_counts = best["delayed_absorption_counts_by_window"][name]
        adjusted = delayed_counts.get(
            "space_delayed_absorption_trend_risk_changed_signal",
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
    delayed_gate = _delayed_absorption_profile_gate(forward_gate)

    before = _run_accepted_before(
        "accepted_exp028_before",
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

    variants = [
        _run_delayed_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            delayed_absorption_scalar=scalar,
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
        for scalar in DELAYED_ABSORPTION_RISK_SCALARS
    ]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

    neutral_variant = variants[0]
    runtime_state_gate = _gate2_runtime_state(neutral_variant)
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
        "delayed_absorption_runtime_state": runtime_state_gate,
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
            runtime_state_gate["passed"],
        ]
    )

    best_variant = max(
        variants,
        key=lambda item: (
            item["gate"]["accepted"],
            item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    decision = "accepted" if best_variant["gate"]["accepted"] else "rejected"
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "No tested delayed-absorption trend scalar improved aggregate EV/PnL "
            "across the three windows without a window-level EV regression, "
            "drawdown/survival violation, or zero-adjustment result."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "Space official catalysts with delayed market absorption should be "
            "more valuable for trend continuation than same-day/5d confirmation. "
            "On top of accepted exp-20260514-028, a single extra trend_long scalar "
            "tests closed event-state profiles where average 5d cash reaction is "
            "weak but 10d cash and same-theme replacement value are strong."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_delayed_absorption_trend_risk_scalar",
        "single_causal_variable": (
            "extra risk scalar for Space trend_long signals whose closed forward "
            "event-state profile passes the delayed-absorption gate"
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
                "risk allocation: add a conservative incremental scalar only to "
                "Space trend_long signals with weak 5d absorption and strong "
                "closed 10d same-theme replacement evidence."
            ),
            "q2_prior_experiments": [
                "exp-20260514-011 rejected positive 5d confirmation; this tests the opposite delayed-absorption shape.",
                "exp-20260514-017 rejected breakout haircut, so this is restricted to trend_long.",
                "exp-20260514-021 rejected noisy IRDM forward expansion; this keeps the existing Space target pool fixed.",
                "exp-20260514-028 accepted source-diversity trend risk at 1.025x; this tests a closed-forward horizon-shape interaction on top.",
            ],
            "q3_single_causal_variable": (
                "Only the additional delayed-absorption trend risk scalar changes; "
                "accepted exp-028 stack and all entries/exits/ranking/targets stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least two EV-improved windows, no EV-regressed window, "
                "max drawdown damage <= 0.5pp, survival >= 5%, >=50 aggregate trades, "
                "and real adjusted signals."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies; "
                "the helper remains default-off metadata and live Space slots stay zero."
            ),
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"]
            >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "accepted_source_diversity_trend_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR
            ),
            "tested_delayed_absorption_trend_scalars": list(
                DELAYED_ABSORPTION_RISK_SCALARS
            ),
            "delayed_absorption_target_tickers": delayed_gate["target_tickers"],
            "delayed_absorption_profile_gate": delayed_gate,
            "target_strategy": TARGET_STRATEGY,
            "locked_variables": [
                "official Space candidate pool",
                "accepted source-diversity stack through exp-028",
                "accepted forward replacement stack",
                "entry filters",
                "candidate ranking",
                "targets/stops",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "status": (
            "accepted_default_off_space_delayed_absorption_trend_risk"
            if decision == "accepted"
            else "rejected_space_delayed_absorption_trend_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only as shared default-off Space metadata/helper; keep live "
            "Space slots at zero and continue validating closed forward outcomes."
            if decision == "accepted"
            else (
                "Do not promote delayed-absorption trend risk from this frozen replay. "
                "Use a different production-visible catalyst-quality axis."
            )
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
            "LLM soft-ranking data remains too thin for reliable attribution. "
            "VSAT/IRDM expansion, positive 5d confirmation, benchmark-laggard "
            "risk, peer-leader trend, and breakout haircut branches already failed "
            "recent gates. This keeps ticker breadth fixed and tests a closed-forward "
            "horizon-shape alpha instead."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and historical Space snapshots are frozen research copies.",
            "Closed event-state profiles are small-sample catalyst metadata, not standalone live trading proof.",
            "The experiment is a sizing helper only; it does not add live Space slots.",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    logs_dir = PROJECT_ROOT / "docs" / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "docs" / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "docs" / "experiments" / "artifacts"
    for directory in (exp_dir, logs_dir, tickets_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    _write_json(exp_dir / f"{STEM}.json", payload)
    _write_json(logs_dir / f"{EXPERIMENT_ID}.json", payload)
    _write_json(tickets_dir / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (artifacts_dir / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        _artifact_markdown(payload),
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "single_causal_variable": payload["single_causal_variable"],
            "parameters": payload["best_variant"]["parameters"],
            "date_range": [
                f"{label}:{window['start']}..{window['end']}"
                for label, window in source_diversity_exp.WINDOWS.items()
            ],
            "backtest_protocol": payload["backtest_protocol"],
            "before_metrics": payload["before"]["aggregate"],
            "after_metrics": payload["best_variant"]["aggregate"],
            "expected_value_score_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["expected_value_score_sum"],
            "decision": payload["status"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "production_impact": payload["production_impact"],
        },
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    summary = {
        "experiment_id": result["experiment_id"],
        "decision": result["status"],
        "best_scalar": result["best_variant"]["parameters"][
            "space_delayed_absorption_trend_scalar"
        ],
        "target_tickers": result["best_variant"]["parameters"][
            "delayed_absorption_target_tickers"
        ],
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "by_window_delta_vs_before": result["best_variant_gate"][
            "by_window_delta_vs_before"
        ],
        "changed_delayed_absorption_signal_count": result["best_variant_gate"][
            "changed_delayed_absorption_signal_count"
        ],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
