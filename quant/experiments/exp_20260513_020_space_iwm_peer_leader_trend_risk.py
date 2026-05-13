"""exp-20260513-020: Space small-cap peer-leader trend risk.

Tests one causal variable on top of the accepted exp-20260513-015 default-off
Space stack: an extra risk scalar for official Space trend_long signals when
IWM is leading SPY and the ticker is also leading the official Space basket.
"""

from __future__ import annotations

import json
import logging
import math
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
    _install_space_policy as _install_accepted_exp015_policy,
    _run_variant as _run_accepted_exp015_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-020"
STEM = "space_iwm_peer_leader_trend_risk"
ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR = 1.05
IWM_PEER_LEADER_TREND_RISK_SCALARS = (
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


def _as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_smallcap_leader(signal: dict[str, Any]) -> bool:
    state = str(signal.get("space_iwm_relative_state") or "")
    if state == "smallcap_leader":
        return True
    if state == "smallcap_laggard":
        return False
    excess = _as_float(signal.get("space_iwm_excess_vs_spy_20d_pct"))
    return excess is not None and excess > 0


def _field_check_iwm_peer_leader_trend(before: dict[str, Any]) -> dict[str, Any]:
    iwm_counts = Counter()
    peer_counts = Counter()
    samples: list[dict[str, Any]] = []
    for row in before["by_window"].values():
        iwm_counts.update(row.get("space_iwm_relative_state_counts") or {})
        peer_counts.update(row.get("space_peer_momentum_state_counts") or {})
        for key in (
            "space_basket_positive_adjustment",
            "space_near_perfect_tqs_trend_adjustment",
            "space_government_contract_peer_leader_adjustment",
            "space_watch_liquidity_tier_adjustment",
        ):
            for sample in (row.get(key) or {}).get("sample_adjusted") or []:
                if sample.get("strategy") != "trend_long":
                    continue
                if "space_peer_momentum_state" not in sample:
                    continue
                samples.append(
                    {
                        "ticker": sample.get("ticker"),
                        "strategy": sample.get("strategy"),
                        "space_peer_momentum_state": sample.get(
                            "space_peer_momentum_state"
                        ),
                        "space_peer_excess_momentum_20d_pct": sample.get(
                            "space_peer_excess_momentum_20d_pct"
                        ),
                        "trade_quality_score": sample.get("trade_quality_score"),
                    }
                )
                if len(samples) >= 12:
                    break
            if len(samples) >= 12:
                break
    return {
        "passed": (
            iwm_counts.get("smallcap_leader", 0) > 0
            and peer_counts.get("leader", 0) > 0
            and bool(samples)
        ),
        "fields": [
            "space_iwm_relative_state",
            "space_iwm_excess_vs_spy_20d_pct",
            "space_peer_momentum_state",
            "space_peer_excess_momentum_20d_pct",
            "strategy",
        ],
        "iwm_relative_state_counts": dict(sorted(iwm_counts.items())),
        "peer_momentum_state_counts": dict(sorted(peer_counts.items())),
        "sample_trend_rows_with_peer_state": samples,
    }


def _install_space_policy(
    iwm_peer_leader_trend_scalar: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    installed = _install_accepted_exp015_policy(
        ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    (
        original_generate,
        original_enrich,
        original_size,
        government_contract_adjustments,
        government_contract_counts,
        source_peer_leader_adjustments,
        source_peer_leader_counts,
        multi_event_adjustments,
        multi_event_counts,
        watch_adjustments,
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
    ) = installed

    accepted_size = portfolio_engine.size_signals
    target_tickers = set(OFFICIAL_SPACE_TICKERS)
    iwm_peer_leader_trend_adjustments: list[dict[str, Any]] = []
    iwm_peer_leader_trend_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            sizing = deepcopy(signal.get("sizing") or {})
            eligible = (
                ticker in target_tickers
                and strategy == "trend_long"
                and _is_peer_leader(signal)
                and _is_smallcap_leader(signal)
            )
            if eligible and sizing:
                iwm_peer_leader_trend_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    iwm_peer_leader_trend_scalar,
                    portfolio_value,
                    "space_iwm_peer_leader_trend_risk",
                )
                iwm_peer_leader_trend_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_iwm_peer_leader_trend_risk",
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                        "space_iwm_excess_vs_spy_20d_pct": signal.get(
                            "space_iwm_excess_vs_spy_20d_pct"
                        ),
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_peer_momentum_20d_pct": signal.get(
                            "space_peer_momentum_20d_pct"
                        ),
                        "space_peer_excess_momentum_20d_pct": signal.get(
                            "space_peer_excess_momentum_20d_pct"
                        ),
                        "scalar": iwm_peer_leader_trend_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_iwm_peer_leader_trend_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return {
        "originals": (original_generate, original_enrich, original_size),
        "iwm_peer_leader_trend_adjustments": iwm_peer_leader_trend_adjustments,
        "iwm_peer_leader_trend_counts": iwm_peer_leader_trend_counts,
        "government_contract_adjustments": government_contract_adjustments,
        "government_contract_counts": government_contract_counts,
        "source_peer_leader_adjustments": source_peer_leader_adjustments,
        "source_peer_leader_counts": source_peer_leader_counts,
        "multi_event_adjustments": multi_event_adjustments,
        "multi_event_counts": multi_event_counts,
        "watch_adjustments": watch_adjustments,
        "watch_counts": watch_counts,
        "company_release_adjustments": company_release_adjustments,
        "company_release_counts": company_release_counts,
        "financing_adjustments": financing_adjustments,
        "financing_counts": financing_counts,
        "source_adjustments": source_adjustments,
        "source_counts": source_counts,
        "liquidity_ok_adjustments": liquidity_ok_adjustments,
        "theme_adjustments": theme_adjustments,
        "iwm_adjustments": iwm_adjustments,
        "peer_nonleader_breakout_adjustments": peer_nonleader_breakout_adjustments,
        "near_perfect_adjustments": near_perfect_adjustments,
        "perfect_adjustments": perfect_adjustments,
        "basket_adjustments": basket_adjustments,
        "theme_counts": theme_counts,
        "iwm_state_counts": iwm_state_counts,
        "peer_counts": peer_counts,
        "near_perfect_counts": near_perfect_counts,
        "perfect_counts": perfect_counts,
        "basket_counts": basket_counts,
        "day_counts": day_counts,
    }


def _slice_summary(installed: dict[str, Any], key: str, before_count: int) -> dict[str, Any]:
    return _adjustment_summary(installed[key][before_count:])


def _run_variant(
    name: str,
    iwm_peer_leader_trend_scalar: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        iwm_peer_leader_trend_scalar,
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
            before_target = len(installed["iwm_peer_leader_trend_adjustments"])
            before_government = len(installed["government_contract_adjustments"])
            before_source_peer = len(installed["source_peer_leader_adjustments"])
            before_multi = len(installed["multi_event_adjustments"])
            before_watch = len(installed["watch_adjustments"])
            before_company = len(installed["company_release_adjustments"])
            before_financing = len(installed["financing_adjustments"])
            before_source = len(installed["source_adjustments"])
            before_iwm = len(installed["iwm_adjustments"])
            before_peer = len(installed["peer_nonleader_breakout_adjustments"])
            before_near = len(installed["near_perfect_adjustments"])
            before_perfect = len(installed["perfect_adjustments"])
            before_basket = len(installed["basket_adjustments"])
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_iwm_peer_leader_trend_adjustment": _slice_summary(
                    installed,
                    "iwm_peer_leader_trend_adjustments",
                    before_target,
                ),
                "space_government_contract_peer_leader_adjustment": _slice_summary(
                    installed,
                    "government_contract_adjustments",
                    before_government,
                ),
                "space_customer_source_peer_leader_adjustment": _slice_summary(
                    installed,
                    "source_peer_leader_adjustments",
                    before_source_peer,
                ),
                "space_multi_event_depth_adjustment": _slice_summary(
                    installed,
                    "multi_event_adjustments",
                    before_multi,
                ),
                "space_watch_liquidity_tier_adjustment": _slice_summary(
                    installed,
                    "watch_adjustments",
                    before_watch,
                ),
                "space_company_release_source_adjustment": _slice_summary(
                    installed,
                    "company_release_adjustments",
                    before_company,
                ),
                "space_financing_dilution_profile_adjustment": _slice_summary(
                    installed,
                    "financing_adjustments",
                    before_financing,
                ),
                "space_official_customer_source_adjustment": _slice_summary(
                    installed,
                    "source_adjustments",
                    before_source,
                ),
                "space_iwm_relative_momentum_adjustment": _slice_summary(
                    installed,
                    "iwm_adjustments",
                    before_iwm,
                ),
                "space_peer_nonleader_breakout_adjustment": _slice_summary(
                    installed,
                    "peer_nonleader_breakout_adjustments",
                    before_peer,
                ),
                "space_near_perfect_tqs_trend_adjustment": _slice_summary(
                    installed,
                    "near_perfect_adjustments",
                    before_near,
                ),
                "space_perfect_tqs_risk_adjustment": _slice_summary(
                    installed,
                    "perfect_adjustments",
                    before_perfect,
                ),
                "space_basket_positive_adjustment": _slice_summary(
                    installed,
                    "basket_adjustments",
                    before_basket,
                ),
                "space_iwm_peer_leader_trend_signal_counts": dict(
                    sorted(installed["iwm_peer_leader_trend_counts"].items())
                ),
                "space_iwm_relative_state_counts": dict(
                    sorted(installed["iwm_state_counts"].items())
                ),
                "space_peer_momentum_state_counts": dict(
                    sorted(installed["peer_counts"].items())
                ),
                "space_theme_segment_signal_counts": dict(
                    sorted(installed["theme_counts"].items())
                ),
                "space_near_perfect_tqs_trend_signal_counts": dict(
                    sorted(installed["near_perfect_counts"].items())
                ),
                "space_perfect_tqs_signal_counts": dict(
                    sorted(installed["perfect_counts"].items())
                ),
                "space_basket_signal_state_counts": dict(
                    sorted(installed["basket_counts"].items())
                ),
                "space_iwm_relative_day_counts": dict(
                    sorted(installed["day_counts"].items())
                ),
            }
    finally:
        _restore_policy(*installed["originals"])
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "target_definition": (
            "official Space trend_long with IWM>SPY and peer momentum leadership"
        ),
        "target_tickers": list(OFFICIAL_SPACE_TICKERS),
        "space_iwm_peer_leader_trend_risk_scalar": iwm_peer_leader_trend_scalar,
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
        row["space_iwm_peer_leader_trend_adjustment"]["adjusted_signal_count"]
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
        and variant["space_iwm_peer_leader_trend_risk_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_iwm_peer_leader_trend_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space IWM peer-leader trend risk",
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
            "space_iwm_peer_leader_trend_adjustment"
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
            json.dumps(payload["gate2"]["iwm_peer_leader_trend_state"], sort_keys=True),
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
    before = _run_accepted_exp015_variant(
        "accepted_exp015_government_contract_peer_leader_stack",
        ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
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

    variants = {}
    for scalar in IWM_PEER_LEADER_TREND_RISK_SCALARS:
        name = f"iwm_peer_leader_trend_{str(scalar).replace('.', '_')}"
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
        "accepted_default_off_space_iwm_peer_leader_trend_risk"
        if accepted
        else "rejected_space_iwm_peer_leader_trend_risk"
    )
    interpretation = (
        "The IWM-relative peer-leader trend scalar improved the accepted default-off "
        "Space stack under the three-window gate. Promotion must stay shared and "
        "metadata-only with live Space slots at zero."
        if accepted
        else (
            "The IWM-relative peer-leader trend scalar did not clear the three-window "
            "gate on top of exp-20260513-015. Do not add another trend/relative-strength "
            "top-up on these frozen snapshots without forward replacement-value evidence."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_iwm_peer_leader_trend_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space trend_long signals when IWM 20d momentum "
            "is above SPY and the ticker is a Space peer momentum leader"
        ),
        "hypothesis": (
            "The accepted Space sleeve already rewards IWM-relative small-cap appetite "
            "and several catalyst-quality fields. Trend entries may still be under-sized "
            "when broad small-cap appetite and in-basket relative strength align. This "
            "tests only that capital-allocation state without changing pool membership, "
            "ranking, exits, LLM/news logic, or live slots."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale official Space trend_long signals only when "
                "IWM leads SPY and the ticker leads the official Space basket."
            ),
            "2_history_check": {
                "exp-20260512-009": (
                    "Rejected generic peer-leader risk because drawdown cost was too high. "
                    "This run restricts the state to trend_long and IWM-relative small-cap "
                    "risk appetite."
                ),
                "exp-20260512-031": (
                    "Accepted broad IWM-relative Space risk at 1.10x; this run does not "
                    "retune that helper and only tests the peer-leader trend intersection."
                ),
                "exp-20260512-008": (
                    "Accepted near-perfect TQS trend top-up; this run uses peer/IWM state, "
                    "not another TQS bucket."
                ),
                "exp-20260513-015": (
                    "Accepted government-contract peer-leader scalar; this is the fixed "
                    "before state."
                ),
                "exp-20260513-019": (
                    "Rejected customer-source peer-nonleader complement, so this run avoids "
                    "another customer-source slice."
                ),
            },
            "3_single_causal_variable": (
                "space_iwm_peer_leader_trend_risk_scalar. Candidate pool, accepted Space "
                "stack, targets, stops, ranking, add-ons, LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate EV/PnL "
                "versus exp-015 accepted stack, at least 2/3 improved EV windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival >= 5%, >=50 "
                "total trades, nonzero adjusted signals, and non-1.0 scalar."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_020_space_iwm_peer_leader_trend_risk.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "peer_leader_definition": (
                "ticker momentum_20d_pct > equal-weight official Space basket momentum_20d_pct"
            ),
            "smallcap_leader_definition": "IWM momentum_20d_pct > SPY momentum_20d_pct",
            "strategy_scope": "trend_long",
            "tested_iwm_peer_leader_trend_scalars": list(
                IWM_PEER_LEADER_TREND_RISK_SCALARS
            ),
            "accepted_before_experiment": "exp-20260513-015",
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
            "The accepted_before variant reproduces exp-20260513-015 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Peer/IWM state fields are "
                "production-visible, but any accepted Space change must remain "
                "default-off until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "official_customer_source_profile": source_gate,
            "peer_momentum_state": peer_state_gate,
            "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "watch_liquidity_tier_registry": liquidity_gate,
            "accepted_multi_event_depth": multi_event_gate,
            "government_contract_profile": government_contract_gate,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "space_peer_momentum_state from accepted Space signal enrichment",
                "space_iwm_relative_state from accepted Space signal enrichment",
                "strategy from signal engine",
            ],
            "passed": (
                gate2_open["passed"]
                and source_gate["passed"]
                and peer_state_gate["passed"]
                and iwm_peer_leader_gate["passed"]
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
                "production-visible IWM-relative and peer-momentum metadata."
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
            "If rejected, do not promote IWM+peer-leader trend scaling on these "
            "frozen snapshots. Future Space alpha should use closed forward "
            "replacement value by catalyst/source/peer bucket or a genuinely new "
            "production-visible official catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_020_space_iwm_peer_leader_trend_risk.py",
            "data/experiments/exp-20260513-020/space_iwm_peer_leader_trend_risk.json",
            "docs/experiments/logs/exp-20260513-020.json",
            "docs/experiments/tickets/exp-20260513-020.json",
            "docs/experiments/artifacts/exp-20260513-020_space_iwm_peer_leader_trend_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; noisy ticker additions, watch-liquidity "
            "peer/TQS/strategy scopes, broad defense-budget source scalars, primary-authority "
            "source scalars, customer-source peer-nonleader scaling, and adjacent TQS "
            "risk scalars were already rejected or underpowered. This tests a different "
            "production-visible relative-strength plus small-cap-appetite state."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "docs"
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
