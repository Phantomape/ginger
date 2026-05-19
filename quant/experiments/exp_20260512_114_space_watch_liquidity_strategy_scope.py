"""exp-20260512-114: Space watch-liquidity strategy scope.

Tests one causal variable on top of the accepted exp-20260512-112 default-off
Space stack: whether the accepted liquidity_tier=watch 1.10x risk top-up should
apply only to trend_long signals instead of every strategy. This is a scope
refinement for an existing production-visible risk-allocation helper, not a
scalar retune, candidate-pool expansion, LLM ranking change, or live-slot change.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_20260511_115_space_basket_momentum_risk import (  # noqa: E402
    OFFICIAL_SPACE_TICKERS,
    PROJECT_ROOT,
    WINDOWS,
    _adjustment_summary,
    _aggregate,
    _aggregate_delta,
    _delta,
    _gate2_open_positions,
    _metrics,
    _restore_policy,
    _run_core_baseline,
    _run_window,
    _safe,
    _scale_sizing,
    _space_trade_attribution,
    _write_json,
)
from exp_20260512_038_space_official_customer_source_risk import (  # noqa: E402
    _event_seed_profiles,
)
from exp_20260512_041_space_financing_dilution_profile_risk import (  # noqa: E402
    _field_check_event_guard_profiles as _accepted_financing_profile_gate,
)
from exp_20260512_110_space_company_release_source_risk import (  # noqa: E402
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    _field_check_company_release_source,
    _install_space_policy as _install_accepted_exp110_policy,
)
from exp_20260512_112_space_watch_liquidity_risk import (  # noqa: E402
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    TARGET_LIQUIDITY_TIER,
    _field_check_watch_liquidity_tier,
    _run_variant as _run_accepted_exp112_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-114"
STEM = "space_watch_liquidity_strategy_scope"
WATCH_LIQUIDITY_RISK_SCALAR = 1.10
STRATEGY_SCOPE_VARIANTS = {
    "watch_liquidity_trend_only": ("trend_long",),
    "watch_liquidity_breakout_only": ("breakout_long",),
}


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _install_space_policy(
    strategy_scope: tuple[str, ...],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
    source_gate: dict[str, Any],
) -> tuple[Any, ...]:
    installed = _install_accepted_exp110_policy(
        ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    (
        original_generate,
        original_enrich,
        original_size,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = installed

    accepted_size = portfolio_engine.size_signals
    target_tickers = set(liquidity_gate["target_tickers"])
    tiers = liquidity_gate["tiers"]
    allowed = {str(item).lower() for item in strategy_scope}
    watch_adjustments: list[dict[str, Any]] = []
    watch_out_of_scope: list[dict[str, Any]] = []
    watch_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                watch_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                if strategy in allowed:
                    _scale_sizing(
                        sizing,
                        WATCH_LIQUIDITY_RISK_SCALAR,
                        portfolio_value,
                        "space_watch_liquidity_strategy_scope",
                    )
                    watch_counts["adjusted_signal"] += 1
                    watch_adjustments.append(
                        {
                            "ticker": ticker,
                            "strategy": signal.get("strategy"),
                            "marker": "space_watch_liquidity_strategy_scope",
                            "space_liquidity_tier": tiers.get(ticker),
                            "strategy_scope": list(strategy_scope),
                            "scalar": WATCH_LIQUIDITY_RISK_SCALAR,
                            "shares_before_scalar": shares_before,
                            "shares_after_scalar": int(
                                sizing.get("shares_to_buy") or 0
                            ),
                            "trade_quality_score": signal.get("trade_quality_score"),
                            "confidence_score": signal.get("confidence_score"),
                        }
                    )
                    signal = {
                        **signal,
                        "sizing": sizing,
                        "space_watch_liquidity_tier": tiers.get(ticker),
                        "space_watch_liquidity_strategy_scope": list(strategy_scope),
                        "space_watch_liquidity_strategy_scope_eligible": True,
                    }
                else:
                    watch_counts["out_of_scope_signal"] += 1
                    watch_out_of_scope.append(
                        {
                            "ticker": ticker,
                            "strategy": signal.get("strategy"),
                            "marker": "space_watch_liquidity_strategy_scope_skipped",
                            "space_liquidity_tier": tiers.get(ticker),
                            "strategy_scope": list(strategy_scope),
                            "shares_without_watch_scope": shares_before,
                            "trade_quality_score": signal.get("trade_quality_score"),
                            "confidence_score": signal.get("confidence_score"),
                        }
                    )
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        watch_adjustments,
        watch_out_of_scope,
        watch_counts,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    )


def _run_variant(
    name: str,
    strategy_scope: tuple[str, ...],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
    source_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        watch_adjustments,
        watch_out_of_scope,
        watch_counts,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(
        strategy_scope,
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_watch = len(watch_adjustments)
            before_skipped = len(watch_out_of_scope)
            before_company = len(company_release_adjustments)
            before_financing = len(financing_adjustments)
            before_source = len(source_adjustments)
            before_liquidity_ok = len(liquidity_ok_adjustments)
            before_theme = len(theme_adjustments)
            before_iwm = len(iwm_adjustments)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_watch_liquidity_strategy_scope_adjustment": (
                    _adjustment_summary(watch_adjustments[before_watch:])
                ),
                "space_watch_liquidity_strategy_scope_skipped": (
                    _adjustment_summary(watch_out_of_scope[before_skipped:])
                ),
                "space_company_release_source_adjustment": _adjustment_summary(
                    company_release_adjustments[before_company:]
                ),
                "space_financing_dilution_profile_adjustment": _adjustment_summary(
                    financing_adjustments[before_financing:]
                ),
                "space_official_customer_source_adjustment": _adjustment_summary(
                    source_adjustments[before_source:]
                ),
                "space_liquidity_tier_adjustment": _adjustment_summary(
                    liquidity_ok_adjustments[before_liquidity_ok:]
                ),
                "space_launch_lunar_theme_adjustment": _adjustment_summary(
                    theme_adjustments[before_theme:]
                ),
                "space_iwm_relative_momentum_adjustment": _adjustment_summary(
                    iwm_adjustments[before_iwm:]
                ),
                "space_peer_nonleader_breakout_adjustment": _adjustment_summary(
                    peer_nonleader_breakout_adjustments[before_peer:]
                ),
                "space_near_perfect_tqs_trend_adjustment": _adjustment_summary(
                    near_perfect_adjustments[before_near:]
                ),
                "space_perfect_tqs_risk_adjustment": _adjustment_summary(
                    perfect_adjustments[before_perfect:]
                ),
                "space_basket_positive_adjustment": _adjustment_summary(
                    basket_adjustments[before_basket:]
                ),
                "space_watch_liquidity_strategy_scope_signal_counts": dict(
                    sorted(watch_counts.items())
                ),
                "space_company_release_source_signal_counts": dict(
                    sorted(company_release_counts.items())
                ),
                "space_financing_dilution_profile_signal_counts": dict(
                    sorted(financing_counts.items())
                ),
                "space_source_eligible_signal_counts": dict(sorted(source_counts.items())),
                "space_theme_segment_signal_counts": dict(sorted(theme_counts.items())),
                "space_iwm_relative_state_counts": dict(sorted(iwm_state_counts.items())),
                "space_peer_momentum_state_counts": dict(sorted(peer_counts.items())),
                "space_near_perfect_tqs_trend_signal_counts": dict(
                    sorted(near_perfect_counts.items())
                ),
                "space_perfect_tqs_signal_counts": dict(sorted(perfect_counts.items())),
                "space_basket_signal_state_counts": dict(sorted(basket_counts.items())),
                "space_iwm_relative_day_counts": dict(sorted(day_counts.items())),
            }
    finally:
        _restore_policy(original_generate, original_enrich, original_size)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "target_liquidity_tier": TARGET_LIQUIDITY_TIER,
        "target_tickers": liquidity_gate["target_tickers"],
        "space_watch_liquidity_risk_scalar": WATCH_LIQUIDITY_RISK_SCALAR,
        "space_watch_liquidity_strategy_scope": list(strategy_scope),
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _gate(variant: dict[str, Any], before: dict[str, Any], core: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
    aggregate_delta_vs_core = _aggregate_delta(variant["aggregate"], core["aggregate"])
    by_window_delta = {
        label: _delta(row["metrics"], before["by_window"][label]["metrics"])
        for label, row in variant["by_window"].items()
    }
    windows_ev_improved = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) > 0
    )
    windows_ev_regressed = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) < 0
    )
    adjusted_count = sum(
        row["space_watch_liquidity_strategy_scope_adjustment"]["adjusted_signal_count"]
        for row in variant["by_window"].values()
    )
    skipped_count = sum(
        row["space_watch_liquidity_strategy_scope_skipped"]["adjusted_signal_count"]
        for row in variant["by_window"].values()
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
        and adjusted_count > 0
        and skipped_count > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_watch_liquidity_strategy_scope_adjusted_signal_count": adjusted_count,
        "space_watch_liquidity_strategy_scope_skipped_signal_count": skipped_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space watch-liquidity strategy scope",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: strategy scope for the accepted watch-liquidity "
            "1.10x top-up."
        ),
        f"- Best variant: `{best['variant']}`",
        f"- Aggregate EV delta vs accepted: `{payload['expected_value_score_delta']:+.4f}`",
        (
            "- Aggregate PnL delta vs accepted: "
            f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`"
        ),
        "",
        "## Sweep",
        "",
        (
            "| Variant | Scope | Gate | dEV | dPnL | Improved windows | "
            "Regressed windows | Adjusted | Out of scope |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        delta = gate["aggregate_delta_vs_before"]
        scope = ",".join(variant["space_watch_liquidity_strategy_scope"])
        lines.append(
            f"| {name} | {scope} | {'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_watch_liquidity_strategy_scope_adjusted_signal_count']} | "
            f"{gate['space_watch_liquidity_strategy_scope_skipped_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Adjusted | Out of scope |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_watch_liquidity_strategy_scope_adjustment"
        ]["adjusted_signal_count"]
        skipped = best["by_window"][label][
            "space_watch_liquidity_strategy_scope_skipped"
        ]["adjusted_signal_count"]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} | {adjusted} | {skipped} |".format(
                label=label,
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before["total_pnl"],
                after_pnl=after["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after["trade_count"],
                max_dd=after["max_drawdown_pct"],
                survival=after["survival_rate"],
                adjusted=adjusted,
                skipped=skipped,
            )
        )
    lines.extend(
        [
            "",
            "## Field Check",
            "",
            json.dumps(payload["gate2"]["watch_liquidity_tier_registry"], sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], sort_keys=True),
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": best["variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    gate2_open = _gate2_open_positions()
    if not gate2_open["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_open}")
    source_gate = _event_seed_profiles()
    if not source_gate["passed"]:
        raise RuntimeError(f"Accepted event source field check failed: {source_gate}")
    financing_gate = _accepted_financing_profile_gate()
    if not financing_gate["passed"]:
        raise RuntimeError(f"Accepted financing profile field check failed: {financing_gate}")
    company_release_gate = _field_check_company_release_source()
    if not company_release_gate["passed"]:
        raise RuntimeError(
            f"Accepted company-release source field check failed: {company_release_gate}"
        )
    liquidity_gate = _field_check_watch_liquidity_tier()
    if not liquidity_gate["passed"]:
        raise RuntimeError(f"Watch-liquidity field check failed: {liquidity_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp112_variant(
        "accepted_exp112_watch_liquidity_all_strategies",
        WATCH_LIQUIDITY_RISK_SCALAR,
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    variants = {}
    for name, scope in STRATEGY_SCOPE_VARIANTS.items():
        variants[name] = _run_variant(
            name,
            scope,
            liquidity_gate,
            company_release_gate,
            financing_gate,
            source_gate,
        )

    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    best_variant = max(
        variants.values(),
        key=lambda variant: (
            variant["gate"]["passed"],
            variant["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    accepted = best_variant["gate"]["passed"]
    decision = (
        "accepted_default_off_space_watch_liquidity_strategy_scope"
        if accepted
        else "rejected_space_watch_liquidity_strategy_scope"
    )
    interpretation = (
        "Restricting the watch-liquidity top-up by strategy improved the accepted "
        "default-off Space stack under the three-window gate. Promotion must remain "
        "shared and metadata-only with live Space slots at zero."
        if accepted
        else (
            "Restricting the accepted watch-liquidity top-up by strategy did not "
            "clear the three-window gate versus exp-20260512-112. Keep the current "
            "all-strategy watch-liquidity helper and do not retry nearby strategy "
            "scope splits on the same frozen snapshots without forward evidence."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_watch_liquidity_strategy_scope",
        "single_causal_variable": (
            "strategy scope for the accepted 1.10x watch-liquidity risk top-up"
        ),
        "hypothesis": (
            "The accepted Space watch-liquidity scalar may be carried mainly by "
            "trend continuation rather than breakouts. Since Space trend quality "
            "ladders have generalized better than breakout retunes, restricting "
            "the existing watch-liquidity 1.10x top-up to trend_long may improve "
            "risk-adjusted replacement value without changing the candidate pool, "
            "risk scalar, ranking, exits, LLM/news, or live slots."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: keep the accepted watch-liquidity scalar at 1.10x "
                "but test its strategy scope."
            ),
            "2_history_check": {
                "exp-20260512-112": (
                    "Accepted liquidity_tier=watch 1.10x across all strategies; this "
                    "is the fixed before state."
                ),
                "exp-20260512-013": (
                    "Accepted zero extra risk for peer-nonleader Space breakouts, "
                    "showing breakout quality needs tighter discrimination."
                ),
                "exp-20260512-010": (
                    "Rejected near-perfect TQS breakout scalar; trend TQS was the "
                    "more robust Space quality surface."
                ),
                "exp-20260512-109": (
                    "Rejected generic cumulative risk cap; this is a strategy-scope "
                    "test for one accepted helper, not a broad cap."
                ),
            },
            "3_single_causal_variable": (
                "space_watch_liquidity_strategy_scope. Candidate pool, scalar value, "
                "accepted Space stack, targets, stops, ranking, add-ons, LLM/news, "
                "and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp-112, at least 2/3 improved EV windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival >= 5%, "
                ">=50 total trades, nonzero adjusted in-scope signals, and nonzero "
                "out-of-scope watch signals."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260512_114_space_watch_liquidity_strategy_scope.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_liquidity_tier": TARGET_LIQUIDITY_TIER,
            "target_liquidity_tickers": liquidity_gate["target_tickers"],
            "watch_liquidity_risk_scalar": WATCH_LIQUIDITY_RISK_SCALAR,
            "tested_strategy_scopes": {
                name: list(scope) for name, scope in STRATEGY_SCOPE_VARIANTS.items()
            },
            "accepted_before_experiment": "exp-20260512-112",
            "accepted_company_release_source_risk_scalar": (
                ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR
            ),
            "accepted_financing_dilution_profile_risk_scalar": (
                ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR
            ),
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "accepted Space basket-positive scalar",
                "accepted perfect-TQS risk scalar",
                "accepted near-perfect trend TQS scalar",
                "accepted peer-nonleader breakout scalar",
                "accepted IWM-relative small-cap leader scalar",
                "accepted launch/lunar theme scalar",
                "accepted liquidity_tier=ok scalar",
                "accepted broad official customer-source scalar",
                "accepted company-release customer-source scalar",
                "accepted financing/dilution profile scalar",
                "accepted watch-liquidity scalar value",
                "accepted Space trend targets",
                "core production universe",
                "core signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use exp-20260510-028 augmented Space snapshots. "
            "The accepted_before variant reproduces exp-20260512-112 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Strategy and liquidity-tier "
                "metadata are production-observable, but any accepted change must "
                "remain default-off until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "accepted_official_customer_source_profile": source_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "watch_liquidity_tier_registry": liquidity_gate,
            "passed": (
                gate2_open["passed"]
                and source_gate["passed"]
                and financing_gate["passed"]
                and company_release_gate["passed"]
                and liquidity_gate["passed"]
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "strategy_scope_refinement_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_variant": before,
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": best_variant["aggregate"],
            **{label: row["metrics"] for label, row in best_variant["by_window"].items()},
        },
        "delta_metrics": {
            "aggregate": best_variant["gate"]["aggregate_delta_vs_before"],
            "by_window": best_variant["gate"]["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": best_variant["gate"][
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "gate_results": best_variant["gate"],
        "gate4": best_variant["gate"],
        "variants": variants,
        "best_variant": best_variant,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space soft-ranking remains label-limited; this run uses deterministic "
                "production metadata already present in the observation slot."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "daily_report_metadata_changed": accepted,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not retry nearby strategy-scope splits for the accepted "
            "watch-liquidity helper on these frozen snapshots. Future Space work "
            "should use forward replacement value or a new production-visible "
            "catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_114_space_watch_liquidity_strategy_scope.py",
            "data/experiments/exp-20260512-114/space_watch_liquidity_strategy_scope.json",
            "experiments/logs/exp-20260512-114.json",
            "experiments/tickets/exp-20260512-114.json",
            "experiments/artifacts/exp-20260512-114_space_watch_liquidity_strategy_scope.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; noisy ticker additions, broad "
            "defense-budget source scalars, primary-authority source scalars, "
            "contract-profile scalars, and generic risk caps are already rejected. "
            "This tests one production-visible scope variable for an accepted helper."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        payload,
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "pnl_delta": result["delta_metrics"]["aggregate"]["total_pnl_sum"],
                "best_variant": result["best_variant"]["variant"],
                "gate4_passed": result["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
