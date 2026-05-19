"""exp-20260512-037: Space liquidity-tier risk allocation.

Tests whether the production universe-registry ``liquidity_tier`` field is a
useful catalyst-quality discriminator for the default-off Space sleeve after
the accepted exp-20260512-032 stack. This avoids LLM soft-ranking because the
forward Space event ledger is still below the closed-decision gate, and it does
not expand the candidate pool.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_20260511_115_space_basket_momentum_risk import (
    BASE_SPACE_RISK_SCALAR,
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
from exp_20260512_009_space_peer_momentum_leader_risk import _adjustment_row
from exp_20260512_031_space_iwm_relative_momentum_risk import (
    _field_check_iwm_spy_snapshots,
)
from exp_20260512_032_space_launch_lunar_theme_risk import (
    ACCEPTED_IWM_RELATIVE_STATE_SCALARS,
    ACCEPTED_IWM_RELATIVE_STATE_SCALARS as _ACCEPTED_IWM_RELATIVE_STATE_SCALARS,
    SPACE_THEME_SEGMENTS,
    THEME_SEGMENT_RISK_SCALARS,
    _field_check_theme_segments,
    _install_space_policy as _install_accepted_exp032_policy,
    _run_variant as _run_accepted_exp032_variant,
)
from data_layer import get_universe
import portfolio_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-037"
STEM = "space_liquidity_tier_risk"
TARGET_LIQUIDITY_TIER = "ok"
ACCEPTED_LAUNCH_LUNAR_THEME_SCALAR = 1.10
LIQUIDITY_TIER_RISK_SCALARS = (0.75, 1.10, 1.25, 1.50)


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


def _official_space_registry() -> dict[str, dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "universe_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("tickers") or {}
    return {
        ticker: records.get(ticker) or {}
        for ticker in OFFICIAL_SPACE_TICKERS
    }


def _liquidity_tier_for_ticker(ticker: str) -> str | None:
    record = _official_space_registry().get(str(ticker or "").upper()) or {}
    value = record.get("liquidity_tier")
    return str(value) if value else None


def _field_check_liquidity_tier() -> dict[str, Any]:
    records = _official_space_registry()
    missing = []
    tiers: dict[str, str] = {}
    for ticker, record in records.items():
        tier = record.get("liquidity_tier")
        if not tier:
            missing.append(ticker)
            continue
        tiers[ticker] = str(tier)
    target_tickers = sorted(
        ticker for ticker, tier in tiers.items() if tier == TARGET_LIQUIDITY_TIER
    )
    return {
        "passed": not missing and bool(target_tickers),
        "path": "data/universe_registry.json",
        "field": "liquidity_tier",
        "target_liquidity_tier": TARGET_LIQUIDITY_TIER,
        "target_tickers": target_tickers,
        "tiers": dict(sorted(tiers.items())),
        "missing_liquidity_tier": missing,
    }


def _install_space_policy(liquidity_tier_scalar: float):
    installed = _install_accepted_exp032_policy(ACCEPTED_LAUNCH_LUNAR_THEME_SCALAR)
    (
        original_generate,
        original_enrich,
        original_size,
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
    liquidity_adjustments: list[dict[str, Any]] = []
    liquidity_tiers = _field_check_liquidity_tier()["tiers"]

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            tier = liquidity_tiers.get(ticker)
            sizing = deepcopy(signal.get("sizing") or {})
            if (
                ticker in OFFICIAL_SPACE_TICKERS
                and sizing
                and tier == TARGET_LIQUIDITY_TIER
            ):
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    liquidity_tier_scalar,
                    portfolio_value,
                    "space_liquidity_tier_ok_risk",
                )
                row = _adjustment_row(
                    signal,
                    sizing,
                    shares_before,
                    liquidity_tier_scalar,
                    "space_liquidity_tier_ok_risk",
                )
                row["space_liquidity_tier"] = tier
                liquidity_adjustments.append(row)
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_liquidity_tier": tier,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        liquidity_adjustments,
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


def _run_variant(name: str, liquidity_tier_scalar: float) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        liquidity_adjustments,
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
    ) = _install_space_policy(liquidity_tier_scalar)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_liquidity = len(liquidity_adjustments)
            before_theme = len(theme_adjustments)
            before_iwm = len(iwm_adjustments)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_liquidity_tier_adjustment": _adjustment_summary(
                    liquidity_adjustments[before_liquidity:]
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
        "space_liquidity_tier_risk_scalar": liquidity_tier_scalar,
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
        row["space_liquidity_tier_adjustment"]["adjusted_signal_count"]
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
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_liquidity_tier_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space liquidity-tier risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space signals whose "
            "universe-registry `liquidity_tier` is `ok`."
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
        "| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        delta = gate["aggregate_delta_vs_before"]
        lines.append(
            f"| {name} | {variant['space_liquidity_tier_risk_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_liquidity_tier_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Liquidity-tier signals |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label]["space_liquidity_tier_adjustment"][
            "adjusted_signal_count"
        ]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} | {adjusted} |".format(
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
            )
        )
    lines.extend(
        [
            "",
            "## Field Check",
            "",
            json.dumps(payload["gate2"]["liquidity_tier_registry"], sort_keys=True),
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
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")
    theme_gate = _field_check_theme_segments()
    if not theme_gate["passed"]:
        raise RuntimeError(f"Theme segment field check failed: {theme_gate}")
    liquidity_gate = _field_check_liquidity_tier()
    if not liquidity_gate["passed"]:
        raise RuntimeError(f"Liquidity field check failed: {liquidity_gate}")
    benchmark_gate = _field_check_iwm_spy_snapshots()
    if not benchmark_gate["passed"]:
        raise RuntimeError(f"IWM/SPY snapshot field check failed: {benchmark_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp032_variant(
        "accepted_exp032_stack",
        ACCEPTED_LAUNCH_LUNAR_THEME_SCALAR,
    )
    variants = {}
    for scalar in LIQUIDITY_TIER_RISK_SCALARS:
        name = f"liquidity_ok_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(name, scalar)

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
        "accepted_default_off_space_liquidity_tier_risk"
        if accepted
        else "rejected_space_liquidity_tier_risk"
    )
    interpretation = (
        "The official Space `liquidity_tier=ok` anchor risk scalar improved the "
        "accepted default-off Space stack under the three-window gate. Promotion "
        "must remain shared production-visible metadata/helper wiring only; live "
        "Space slots remain zero."
        if accepted
        else (
            "The official Space `liquidity_tier=ok` anchor risk scalar did not "
            "clear the three-window gate on top of exp-20260512-032. Do not retry "
            "nearby liquidity-tier Space scalars on these frozen snapshots; future "
            "Space work needs forward catalyst replacement value or a different "
            "production-observable catalyst-quality field."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_liquidity_tier_ok_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals keyed only to production "
            "universe-registry liquidity_tier == ok"
        ),
        "hypothesis": (
            "The next Space alpha should be catalyst-quality risk allocation, not "
            "LLM soft-ranking, ticker expansion, or another data/defense theme "
            "retune. A production-visible liquidity anchor may identify official "
            "Space signals that can carry more default-off risk without increasing "
            "live slots."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale official Space signals whose registry "
                "liquidity_tier is ok."
            ),
            "2_history_check": {
                "exp-20260512-032": (
                    "Accepted launch/lunar 1.10x theme scalar; this is the fixed "
                    "before state."
                ),
                "exp-20260512-035": (
                    "Rejected data/defense theme scalar; this test uses a different "
                    "registry field, not another data/defense scalar."
                ),
                "exp-20260512-023": (
                    "Rejected GSAT candidate-pool expansion; no ticker expansion "
                    "in this test."
                ),
                "exp-20260512-014/015/016/019/021": (
                    "Rejected peer-trend, 52w, breadth, R/R, and volume refinements; "
                    "those variables stay fixed."
                ),
            },
            "3_single_causal_variable": (
                "space_liquidity_tier_ok_risk_scalar. Candidate pool, accepted Space "
                "risk scalars, targets, stops, ranking, add-ons, LLM/news, and live "
                "slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, >=50 total trades, "
                "and nonzero adjusted liquidity-tier signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-032 Space stack, and "
                "each liquidity-tier scalar across the canonical augmented Space "
                "snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "theme_segments": SPACE_THEME_SEGMENTS,
            "target_liquidity_tier": TARGET_LIQUIDITY_TIER,
            "target_liquidity_tickers": liquidity_gate["target_tickers"],
            "liquidity_tiers": liquidity_gate["tiers"],
            "tested_liquidity_tier_scalars": list(LIQUIDITY_TIER_RISK_SCALARS),
            "accepted_before_experiment": "exp-20260512-032",
            "accepted_launch_lunar_theme_scalar": ACCEPTED_LAUNCH_LUNAR_THEME_SCALAR,
            "accepted_launch_lunar_tested_scalars": list(THEME_SEGMENT_RISK_SCALARS),
            "accepted_iwm_relative_state_scalars": _ACCEPTED_IWM_RELATIVE_STATE_SCALARS,
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "PL/BKSY breakout haircut",
                "RKLB/ASTS trend top-up",
                "accepted Space basket-positive scalar",
                "accepted perfect-TQS risk scalar",
                "accepted near-perfect trend TQS scalar",
                "accepted peer-nonleader breakout scalar",
                "accepted IWM-relative small-cap leader scalar",
                "accepted launch/lunar theme scalar",
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
            "The accepted_before variant reproduces exp-20260512-032 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe; any accepted change must remain "
                "default-off metadata until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "theme_segment_registry": theme_gate,
            "liquidity_tier_registry": liquidity_gate,
            "iwm_spy_snapshot_coverage": benchmark_gate,
            "passed": gate2["passed"]
            and theme_gate["passed"]
            and liquidity_gate["passed"]
            and benchmark_gate["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "new_liquidity_tier_scalar_added": True,
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
            **{
                label: row["metrics"]
                for label, row in best_variant["by_window"].items()
            },
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
                "Space event-state forward data remains below the closed-decision "
                "gate; this run uses deterministic production registry metadata."
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
            "If rejected, do not retry adjacent liquidity-tier Space scalars on "
            "the same frozen snapshots. Future Space work should use forward "
            "event replacement value or a genuinely new catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_037_space_liquidity_tier_risk.py",
            "data/experiments/exp-20260512-037/space_liquidity_tier_risk.json",
            "experiments/logs/exp-20260512-037.json",
            "experiments/tickets/exp-20260512-037.json",
            "experiments/artifacts/exp-20260512-037_space_liquidity_tier_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; GSAT and mature satcom candidate "
            "expansions are rejected; recent Space TQS, IWM, peer, 52w, breadth, "
            "R/R, volume, and data/defense variants are either accepted context "
            "or anti-repeat."
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
