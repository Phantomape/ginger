"""exp-20260513-025: Space peer-leader breakout risk.

Tests one causal variable on top of the accepted exp-20260513-020 default-off
Space stack: an extra risk scalar for official Space breakout_long signals when
the ticker is leading the official Space peer basket. This is not LLM
soft-ranking or candidate-pool expansion; it only tests whether peer leadership
rescues the otherwise fragile Space breakout sleeve.
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
)
from exp_20260512_112_space_watch_liquidity_risk import (  # noqa: E402
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    TARGET_LIQUIDITY_TIER,
    _field_check_watch_liquidity_tier,
)
from exp_20260513_012_space_multi_event_depth_risk import (  # noqa: E402
    MULTI_EVENT_MIN_COUNT,
    WATCH_LIQUIDITY_RISK_SCALAR,
    _field_check_multi_event_depth,
)
from exp_20260513_014_space_customer_source_peer_leader_risk import (  # noqa: E402
    ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
    _field_check_peer_leader_state,
    _is_peer_leader,
)
from exp_20260513_015_space_government_contract_peer_leader_risk import (  # noqa: E402
    ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
    _field_check_government_contract_profile,
)
from exp_20260513_020_space_iwm_peer_leader_trend_risk import (  # noqa: E402
    ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
    _field_check_iwm_peer_leader_trend,
    _install_space_policy as _install_accepted_exp020_policy,
    _run_variant as _run_accepted_exp020_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-025"
STEM = "space_peer_leader_breakout_risk"
ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR = 1.15
PEER_LEADER_BREAKOUT_RISK_SCALARS = (
    0.50,
    0.75,
    0.90,
    1.00,
    1.025,
    1.05,
    1.075,
    1.10,
    1.15,
    1.20,
    1.25,
)


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


def _field_check_peer_leader_breakout(before: dict[str, Any]) -> dict[str, Any]:
    peer_counts = Counter()
    strategy_counts = Counter()
    samples: list[dict[str, Any]] = []
    leader_samples: list[dict[str, Any]] = []
    sample_keys = (
        "space_basket_positive_adjustment",
        "space_iwm_relative_momentum_adjustment",
        "space_official_customer_source_adjustment",
        "space_government_contract_peer_leader_adjustment",
        "space_peer_nonleader_breakout_adjustment",
    )
    for label, row in before.get("by_window", {}).items():
        peer_counts.update(row.get("space_peer_momentum_state_counts") or {})
        for key in sample_keys:
            for sample in (row.get(key) or {}).get("sample_adjusted") or []:
                if sample.get("strategy") != "breakout_long":
                    continue
                strategy_counts["breakout_long"] += 1
                if "space_peer_momentum_state" not in sample:
                    continue
                record = {
                    "window": label,
                    "ticker": sample.get("ticker"),
                    "strategy": sample.get("strategy"),
                    "source_adjustment": key,
                    "space_peer_momentum_state": sample.get("space_peer_momentum_state"),
                    "space_peer_excess_momentum_20d_pct": sample.get(
                        "space_peer_excess_momentum_20d_pct"
                    ),
                    "trade_quality_score": sample.get("trade_quality_score"),
                }
                samples.append(record)
                if sample.get("space_peer_momentum_state") == "leader":
                    leader_samples.append(record)

    return {
        "passed": peer_counts.get("leader", 0) > 0 and bool(leader_samples),
        "fields": [
            "strategy",
            "space_peer_momentum_state",
            "space_peer_excess_momentum_20d_pct",
            "sizing.shares_to_buy",
        ],
        "peer_momentum_state_counts": dict(sorted(peer_counts.items())),
        "sample_breakout_rows_with_peer_state": samples[:12],
        "sample_peer_leader_breakout_rows": leader_samples[:12],
        "strategy_counts_seen_in_samples": dict(sorted(strategy_counts.items())),
    }


def _install_space_policy(
    peer_leader_breakout_scalar: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    accepted = _install_accepted_exp020_policy(
        ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    accepted_size = portfolio_engine.size_signals
    target_tickers = set(OFFICIAL_SPACE_TICKERS)
    peer_leader_breakout_adjustments: list[dict[str, Any]] = []
    peer_leader_breakout_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            sizing = deepcopy(signal.get("sizing") or {})
            eligible = (
                ticker in target_tickers
                and strategy == "breakout_long"
                and _is_peer_leader(signal)
            )
            if eligible and sizing:
                peer_leader_breakout_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    peer_leader_breakout_scalar,
                    portfolio_value,
                    "space_peer_leader_breakout_risk",
                )
                peer_leader_breakout_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_peer_leader_breakout_risk",
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_peer_momentum_20d_pct": signal.get(
                            "space_peer_momentum_20d_pct"
                        ),
                        "space_peer_excess_momentum_20d_pct": signal.get(
                            "space_peer_excess_momentum_20d_pct"
                        ),
                        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                        "space_iwm_excess_vs_spy_20d_pct": signal.get(
                            "space_iwm_excess_vs_spy_20d_pct"
                        ),
                        "scalar": peer_leader_breakout_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_peer_leader_breakout_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return {
        "originals": accepted["originals"],
        "accepted": accepted,
        "peer_leader_breakout_adjustments": peer_leader_breakout_adjustments,
        "peer_leader_breakout_counts": peer_leader_breakout_counts,
    }


def _slice_summary(installed: dict[str, Any], key: str, before_count: int) -> dict[str, Any]:
    return _adjustment_summary(installed["accepted"][key][before_count:])


def _run_variant(
    name: str,
    peer_leader_breakout_scalar: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        peer_leader_breakout_scalar,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            accepted = installed["accepted"]
            before_target = len(installed["peer_leader_breakout_adjustments"])
            before_iwm_trend = len(accepted["iwm_peer_leader_trend_adjustments"])
            before_government = len(accepted["government_contract_adjustments"])
            before_source_peer = len(accepted["source_peer_leader_adjustments"])
            before_multi = len(accepted["multi_event_adjustments"])
            before_watch = len(accepted["watch_adjustments"])
            before_company = len(accepted["company_release_adjustments"])
            before_financing = len(accepted["financing_adjustments"])
            before_source = len(accepted["source_adjustments"])
            before_iwm = len(accepted["iwm_adjustments"])
            before_peer = len(accepted["peer_nonleader_breakout_adjustments"])
            before_near = len(accepted["near_perfect_adjustments"])
            before_perfect = len(accepted["perfect_adjustments"])
            before_basket = len(accepted["basket_adjustments"])
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_peer_leader_breakout_adjustment": _adjustment_summary(
                    installed["peer_leader_breakout_adjustments"][before_target:]
                ),
                "space_iwm_peer_leader_trend_adjustment": _slice_summary(
                    installed, "iwm_peer_leader_trend_adjustments", before_iwm_trend
                ),
                "space_government_contract_peer_leader_adjustment": _slice_summary(
                    installed, "government_contract_adjustments", before_government
                ),
                "space_customer_source_peer_leader_adjustment": _slice_summary(
                    installed, "source_peer_leader_adjustments", before_source_peer
                ),
                "space_multi_event_depth_adjustment": _slice_summary(
                    installed, "multi_event_adjustments", before_multi
                ),
                "space_watch_liquidity_tier_adjustment": _slice_summary(
                    installed, "watch_adjustments", before_watch
                ),
                "space_company_release_source_adjustment": _slice_summary(
                    installed, "company_release_adjustments", before_company
                ),
                "space_financing_dilution_profile_adjustment": _slice_summary(
                    installed, "financing_adjustments", before_financing
                ),
                "space_official_customer_source_adjustment": _slice_summary(
                    installed, "source_adjustments", before_source
                ),
                "space_iwm_relative_momentum_adjustment": _slice_summary(
                    installed, "iwm_adjustments", before_iwm
                ),
                "space_peer_nonleader_breakout_adjustment": _slice_summary(
                    installed, "peer_nonleader_breakout_adjustments", before_peer
                ),
                "space_near_perfect_tqs_trend_adjustment": _slice_summary(
                    installed, "near_perfect_adjustments", before_near
                ),
                "space_perfect_tqs_risk_adjustment": _slice_summary(
                    installed, "perfect_adjustments", before_perfect
                ),
                "space_basket_positive_adjustment": _slice_summary(
                    installed, "basket_adjustments", before_basket
                ),
                "space_peer_leader_breakout_signal_counts": dict(
                    sorted(installed["peer_leader_breakout_counts"].items())
                ),
                "space_iwm_peer_leader_trend_signal_counts": dict(
                    sorted(accepted["iwm_peer_leader_trend_counts"].items())
                ),
                "space_iwm_relative_state_counts": dict(
                    sorted(accepted["iwm_state_counts"].items())
                ),
                "space_peer_momentum_state_counts": dict(
                    sorted(accepted["peer_counts"].items())
                ),
                "space_theme_segment_signal_counts": dict(
                    sorted(accepted["theme_counts"].items())
                ),
                "space_basket_signal_state_counts": dict(
                    sorted(accepted["basket_counts"].items())
                ),
                "space_iwm_relative_day_counts": dict(
                    sorted(accepted["day_counts"].items())
                ),
            }
    finally:
        _restore_policy(*installed["originals"])

    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "target_definition": "official Space breakout_long with peer momentum leadership",
        "target_tickers": list(OFFICIAL_SPACE_TICKERS),
        "space_peer_leader_breakout_risk_scalar": peer_leader_breakout_scalar,
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _gate(
    variant: dict[str, Any],
    before: dict[str, Any],
    core: dict[str, Any],
) -> dict[str, Any]:
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
        row["space_peer_leader_breakout_adjustment"]["adjusted_signal_count"]
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
        and variant["space_peer_leader_breakout_risk_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_peer_leader_breakout_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space peer-leader breakout risk",
        "",
        f"- decision: `{payload['decision']}`",
        f"- best variant: `{best['variant']}`",
        f"- aggregate EV delta: `{payload['expected_value_score_delta']:+.4f}`",
        f"- aggregate PnL delta: `${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Target signals |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_peer_leader_breakout_adjustment"
        ]["adjusted_signal_count"]
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
            "## Field Checks",
            "",
            json.dumps(payload["gate2"]["peer_leader_breakout_state"], sort_keys=True),
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
    multi_event_gate = _field_check_multi_event_depth()
    if not multi_event_gate["passed"]:
        raise RuntimeError(f"Multi-event catalyst-depth field check failed: {multi_event_gate}")
    government_contract_gate = _field_check_government_contract_profile()
    if not government_contract_gate["passed"]:
        raise RuntimeError(
            f"Government-contract profile field check failed: {government_contract_gate}"
        )

    core = _run_core_baseline()
    before = _run_accepted_exp020_variant(
        "accepted_exp020_iwm_peer_leader_trend_stack",
        ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    peer_state_gate = _field_check_peer_leader_state(before)
    if not peer_state_gate["passed"]:
        raise RuntimeError(f"Peer momentum state field check failed: {peer_state_gate}")
    iwm_peer_leader_gate = _field_check_iwm_peer_leader_trend(before)
    if not iwm_peer_leader_gate["passed"]:
        raise RuntimeError(
            f"IWM peer-leader trend field check failed: {iwm_peer_leader_gate}"
        )
    peer_leader_breakout_gate = _field_check_peer_leader_breakout(before)
    if not peer_leader_breakout_gate["passed"]:
        raise RuntimeError(
            f"Peer-leader breakout field check failed: {peer_leader_breakout_gate}"
        )

    variants = {}
    for scalar in PEER_LEADER_BREAKOUT_RISK_SCALARS:
        name = f"peer_leader_breakout_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(
            name,
            scalar,
            government_contract_gate,
            source_gate,
            multi_event_gate,
            liquidity_gate,
            company_release_gate,
            financing_gate,
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
        "accepted_default_off_space_peer_leader_breakout_risk"
        if accepted
        else "rejected_space_peer_leader_breakout_risk"
    )
    interpretation = (
        "The peer-leader breakout scalar cleared the three-window gate on top of "
        "the exp-020 accepted Space stack. Before promotion, this scalar must be "
        "implemented in shared default-off Space policy and mirrored in run/report "
        "metadata so production and replay remain aligned."
        if accepted
        else (
            "Peer leadership did not justify another Space breakout risk scalar on top "
            "of the accepted exp-020 stack. The stronger next Space alpha direction is "
            "forward replacement value by catalyst/source/peer bucket, not another "
            "breakout allocation slice on frozen snapshots."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_peer_leader_breakout_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space breakout_long signals when the ticker is "
            "a Space peer momentum leader"
        ),
        "hypothesis": (
            "Space breakout trades are fragile, but exp-20260512-013 already showed "
            "peer-nonleader breakouts deserve zero extra risk. The narrow alpha question "
            "left is whether peer-leader breakouts are the positive complement worth "
            "sizing up or whether the breakout sleeve should remain governed only by "
            "existing catalyst-quality scalars."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale only official Space breakout_long signals whose "
                "ticker leads the official Space peer basket."
            ),
            "2_history_check": {
                "exp-20260512-009": (
                    "Rejected generic peer-leader risk because drawdown cost was too high; "
                    "this run isolates breakout_long on top of the newer exp-020 stack."
                ),
                "exp-20260512-013": (
                    "Accepted zero extra risk for peer-nonleader breakouts; this tests the "
                    "leader complement rather than retuning that haircut."
                ),
                "exp-20260513-020": (
                    "Accepted IWM+peer-leader trend risk. This run keeps that scalar fixed "
                    "at 1.15 and does not retune trend behavior."
                ),
                "exp-20260513-021": (
                    "Rejected satellite-connectivity theme risk; this avoids theme slicing."
                ),
                "exp-20260513-022": (
                    "Rejected government-contract peer-nonleader risk; this avoids source "
                    "profile complement mining."
                ),
            },
            "3_single_causal_variable": (
                "space_peer_leader_breakout_risk_scalar. Candidate pool, accepted Space "
                "stack, targets, stops, ranking, add-ons, LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate EV/PnL "
                "versus exp-020 accepted stack, at least 2/3 improved EV windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival >= 5%, >=50 "
                "total trades, nonzero adjusted signals, and non-1.0 scalar."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_025_space_peer_leader_breakout_risk.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "peer_leader_definition": (
                "ticker momentum_20d_pct > equal-weight official Space basket momentum_20d_pct"
            ),
            "strategy_scope": "breakout_long",
            "tested_peer_leader_breakout_scalars": list(PEER_LEADER_BREAKOUT_RISK_SCALARS),
            "accepted_before_experiment": "exp-20260513-020",
            "accepted_iwm_peer_leader_trend_risk_scalar": (
                ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR
            ),
            "accepted_government_contract_peer_leader_risk_scalar": (
                ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR
            ),
            "accepted_customer_source_peer_leader_risk_scalar": (
                ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR
            ),
            "accepted_multi_event_depth_risk_scalar": (
                ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR
            ),
            "accepted_multi_event_min_count": MULTI_EVENT_MIN_COUNT,
            "accepted_watch_liquidity_risk_scalar": WATCH_LIQUIDITY_RISK_SCALAR,
            "target_liquidity_tier": TARGET_LIQUIDITY_TIER,
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
                "accepted IWM+peer-leader trend scalar",
                "accepted launch/lunar theme scalar",
                "accepted liquidity_tier=ok scalar",
                "accepted watch-liquidity scalar",
                "accepted broad official customer-source scalar",
                "accepted company-release customer-source scalar",
                "accepted financing/dilution profile scalar",
                "accepted multi-event catalyst-depth scalar",
                "accepted customer-source peer-leader scalar",
                "accepted government-contract peer-leader scalar",
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
            "The accepted_before variant reproduces exp-20260513-020 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. The tested fields are "
                "production-visible, but accepted positive changes must be promoted "
                "through shared default-off Space policy before use."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "official_customer_source_profile": source_gate,
            "peer_momentum_state": peer_state_gate,
            "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
            "peer_leader_breakout_state": peer_leader_breakout_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "watch_liquidity_tier_registry": liquidity_gate,
            "accepted_multi_event_depth": multi_event_gate,
            "government_contract_profile": government_contract_gate,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "strategy from signal engine",
                "space_peer_momentum_state from accepted Space signal enrichment",
                "space_peer_excess_momentum_20d_pct from accepted Space signal enrichment",
                "sizing.shares_to_buy from shared sizing engine",
            ],
            "passed": (
                gate2_open["passed"]
                and source_gate["passed"]
                and peer_state_gate["passed"]
                and iwm_peer_leader_gate["passed"]
                and peer_leader_breakout_gate["passed"]
                and financing_gate["passed"]
                and company_release_gate["passed"]
                and liquidity_gate["passed"]
                and multi_event_gate["passed"]
                and government_contract_gate["passed"]
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
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
                "production-visible peer-momentum metadata."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": accepted,
            "daily_report_metadata_changed": False,
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
            "Do not retest adjacent Space breakout peer-leader scalars on the same "
            "frozen snapshots if rejected. Next Space alpha should close forward "
            "replacement-value labels by catalyst family/source/peer bucket or add "
            "production-visible official-catalyst attribution, not noisy tickers."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_025_space_peer_leader_breakout_risk.py",
            "data/experiments/exp-20260513-025/space_peer_leader_breakout_risk.json",
            "experiments/logs/exp-20260513-025.json",
            "experiments/tickets/exp-20260513-025.json",
            "experiments/artifacts/exp-20260513-025_space_peer_leader_breakout_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; noisy ticker additions, mature satcom "
            "breadth, watch-liquidity peer/TQS/strategy scopes, broad defense-budget "
            "source scalars, primary-authority source scalars, customer-source "
            "peer-nonleader scaling, government-contract peer-nonleader scaling, and "
            "adjacent trend/TQS retunes were already rejected, accepted, or underpowered."
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
