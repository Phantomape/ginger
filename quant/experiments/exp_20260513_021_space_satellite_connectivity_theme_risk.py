"""exp-20260513-021: Space satellite-connectivity theme risk.

Tests one causal variable on top of the accepted exp-20260513-015 default-off
Space stack: an extra risk scalar for official Space signals whose production
registry theme segment is satellite_connectivity.
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
)
from exp_20260513_015_space_government_contract_peer_leader_risk import (  # noqa: E402
    ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
    _field_check_government_contract_profile,
    _install_space_policy as _install_accepted_exp015_policy,
    _run_variant as _run_accepted_exp015_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402
from universe_manager import records_as_of  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-021"
STEM = "space_satellite_connectivity_theme_risk"
ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR = 1.05
TARGET_THEME_SEGMENT = "satellite_connectivity"
SATELLITE_CONNECTIVITY_THEME_RISK_SCALARS = (
    0.50,
    0.75,
    0.90,
    1.00,
    1.05,
    1.10,
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


def _registry_theme_gate() -> dict[str, Any]:
    records = records_as_of("2026-05-10", prefer_events=True)
    target_records = {}
    missing_required_fields = []
    for ticker in OFFICIAL_SPACE_TICKERS:
        record = records.get(ticker) or {}
        if str(record.get("theme_segment") or "") != TARGET_THEME_SEGMENT:
            continue
        target_records[ticker] = {
            "theme": record.get("theme"),
            "theme_segment": record.get("theme_segment"),
            "status": record.get("status"),
            "eligible_as_of": record.get("eligible_as_of"),
            "first_trade_allowed_as_of": record.get("first_trade_allowed_as_of"),
        }
        for field in ("theme", "theme_segment", "status"):
            if not record.get(field):
                missing_required_fields.append(f"{ticker}.{field}")
    return {
        "passed": bool(target_records) and not missing_required_fields,
        "source": "data/universe_registry.json plus data/universe_events.jsonl",
        "target_theme_segment": TARGET_THEME_SEGMENT,
        "target_tickers": sorted(target_records),
        "records": target_records,
        "missing_required_fields": missing_required_fields,
    }


def _runtime_theme_gate(before: dict[str, Any]) -> dict[str, Any]:
    counts = Counter()
    samples = []
    for label, row in before["by_window"].items():
        window_counts = row.get("space_theme_segment_signal_counts") or {}
        counts.update(window_counts)
        theme_adjustment = row.get("space_launch_lunar_theme_adjustment") or {}
        for sample in theme_adjustment.get("sample_adjusted") or []:
            if sample.get("space_theme_segment") and len(samples) < 12:
                samples.append(
                    {
                        "window": label,
                        "ticker": sample.get("ticker"),
                        "strategy": sample.get("strategy"),
                        "space_theme_segment": sample.get("space_theme_segment"),
                    }
                )
    return {
        "passed": counts.get(TARGET_THEME_SEGMENT, 0) > 0,
        "field": "space_theme_segment",
        "target_theme_segment": TARGET_THEME_SEGMENT,
        "state_counts": dict(sorted(counts.items())),
        "sample_runtime_values": samples,
    }


def _install_space_policy(
    satellite_connectivity_scalar: float,
    registry_theme_gate: dict[str, Any],
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
    target_tickers = set(registry_theme_gate["target_tickers"])
    theme_profiles = registry_theme_gate["records"]
    satellite_adjustments: list[dict[str, Any]] = []
    satellite_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            signal_theme = str(signal.get("space_theme_segment") or "")
            eligible = (
                ticker in target_tickers and signal_theme == TARGET_THEME_SEGMENT
            )
            if eligible and sizing:
                satellite_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    satellite_connectivity_scalar,
                    portfolio_value,
                    "space_satellite_connectivity_theme_risk",
                )
                satellite_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_satellite_connectivity_theme_risk",
                        "space_theme_segment": signal_theme,
                        "space_theme_profile": theme_profiles.get(ticker),
                        "space_basket_momentum_state": signal.get(
                            "space_basket_momentum_state"
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
                        "scalar": satellite_connectivity_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_satellite_connectivity_theme_eligible": True,
                    "space_satellite_connectivity_theme_profile": theme_profiles.get(
                        ticker
                    ),
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return {
        "originals": (original_generate, original_enrich, original_size),
        "satellite_adjustments": satellite_adjustments,
        "satellite_counts": satellite_counts,
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
    satellite_connectivity_scalar: float,
    registry_theme_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        satellite_connectivity_scalar,
        registry_theme_gate,
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
            before_satellite = len(installed["satellite_adjustments"])
            before_source_peer = len(installed["source_peer_leader_adjustments"])
            before_government = len(installed["government_contract_adjustments"])
            before_multi = len(installed["multi_event_adjustments"])
            before_watch = len(installed["watch_adjustments"])
            before_company = len(installed["company_release_adjustments"])
            before_financing = len(installed["financing_adjustments"])
            before_source = len(installed["source_adjustments"])
            before_liquidity = len(installed["liquidity_ok_adjustments"])
            before_theme = len(installed["theme_adjustments"])
            before_iwm = len(installed["iwm_adjustments"])
            before_peer = len(installed["peer_nonleader_breakout_adjustments"])
            before_near = len(installed["near_perfect_adjustments"])
            before_perfect = len(installed["perfect_adjustments"])
            before_basket = len(installed["basket_adjustments"])
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_satellite_connectivity_theme_adjustment": _slice_summary(
                    installed,
                    "satellite_adjustments",
                    before_satellite,
                ),
                "space_customer_source_peer_leader_adjustment": _slice_summary(
                    installed,
                    "source_peer_leader_adjustments",
                    before_source_peer,
                ),
                "space_government_contract_peer_leader_adjustment": _slice_summary(
                    installed,
                    "government_contract_adjustments",
                    before_government,
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
                "space_liquidity_tier_adjustment": _slice_summary(
                    installed,
                    "liquidity_ok_adjustments",
                    before_liquidity,
                ),
                "space_launch_lunar_theme_adjustment": _slice_summary(
                    installed,
                    "theme_adjustments",
                    before_theme,
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
                "space_satellite_connectivity_theme_signal_counts": dict(
                    sorted(installed["satellite_counts"].items())
                ),
                "space_customer_source_peer_leader_signal_counts": dict(
                    sorted(installed["source_peer_leader_counts"].items())
                ),
                "space_government_contract_peer_leader_signal_counts": dict(
                    sorted(installed["government_contract_counts"].items())
                ),
                "space_multi_event_depth_signal_counts": dict(
                    sorted(installed["multi_event_counts"].items())
                ),
                "space_watch_liquidity_tier_signal_counts": dict(
                    sorted(installed["watch_counts"].items())
                ),
                "space_company_release_source_signal_counts": dict(
                    sorted(installed["company_release_counts"].items())
                ),
                "space_financing_dilution_profile_signal_counts": dict(
                    sorted(installed["financing_counts"].items())
                ),
                "space_source_eligible_signal_counts": dict(
                    sorted(installed["source_counts"].items())
                ),
                "space_theme_segment_signal_counts": dict(
                    sorted(installed["theme_counts"].items())
                ),
                "space_iwm_relative_state_counts": dict(
                    sorted(installed["iwm_state_counts"].items())
                ),
                "space_peer_momentum_state_counts": dict(
                    sorted(installed["peer_counts"].items())
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
        "target_definition": "official Space theme_segment=satellite_connectivity",
        "target_tickers": registry_theme_gate["target_tickers"],
        "space_satellite_connectivity_theme_risk_scalar": (
            satellite_connectivity_scalar
        ),
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
    improved_windows = [
        label
        for label, row in by_window_delta.items()
        if row.get("expected_value_score", 0) > 0
    ]
    regressed_windows = [
        label
        for label, row in by_window_delta.items()
        if row.get("expected_value_score", 0) < 0
    ]
    adjusted_count = sum(
        row["space_satellite_connectivity_theme_adjustment"][
            "adjusted_signal_count"
        ]
        for row in variant["by_window"].values()
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved_windows) >= 2
        and not regressed_windows
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
        and adjusted_count > 0
        and variant["space_satellite_connectivity_theme_risk_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "adjusted_signal_count": adjusted_count,
    }


def _sweep_summary(variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for variant in variants.values():
        gate = variant["gate"]
        rows.append(
            {
                "variant": variant["variant"],
                "risk_scalar": variant["space_satellite_connectivity_theme_risk_scalar"],
                "expected_value_score_delta": gate["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                "total_pnl_delta": gate["aggregate_delta_vs_before"]["total_pnl_sum"],
                "max_drawdown_worse": gate["aggregate_delta_vs_before"][
                    "max_drawdown_pct_max"
                ],
                "improved_windows": gate["improved_windows"],
                "regressed_windows": gate["regressed_windows"],
                "adjusted_signal_count": gate["adjusted_signal_count"],
                "passed": gate["passed"],
            }
        )
    return rows


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {payload['experiment_id']} {STEM}",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        f"Hypothesis: {payload['hypothesis']}",
        "",
        f"Changed variable: `{payload['changed_variable']}`",
        "",
        f"Best scalar: `{best['space_satellite_connectivity_theme_risk_scalar']}`",
        "",
        "## Gate 4",
        "",
        json.dumps(payload["gate4"], sort_keys=True),
        "",
        "## Window Metrics vs Accepted exp-20260513-015 Stack",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Trades | Max DD | Survival | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_satellite_connectivity_theme_adjustment"
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
            "## Sweep Summary",
            "",
            json.dumps(payload["sweep_summary"], sort_keys=True),
            "",
            "## Field Checks",
            "",
            json.dumps(payload["gate2"]["registry_theme_segment"], sort_keys=True),
            "",
            json.dumps(payload["gate2"]["runtime_theme_segment"], sort_keys=True),
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
        "selected_risk_scalar": best["space_satellite_connectivity_theme_risk_scalar"],
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

    registry_theme_gate = _registry_theme_gate()
    if not registry_theme_gate["passed"]:
        raise RuntimeError(
            f"Satellite-connectivity registry field check failed: {registry_theme_gate}"
        )
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
    runtime_theme_gate = _runtime_theme_gate(before)
    if not runtime_theme_gate["passed"]:
        raise RuntimeError(
            f"Runtime theme segment field check failed: {runtime_theme_gate}"
        )
    peer_state_gate = _field_check_peer_leader_state(before)
    if not peer_state_gate["passed"]:
        raise RuntimeError(f"Peer momentum state field check failed: {peer_state_gate}")

    variants = {}
    for scalar in SATELLITE_CONNECTIVITY_THEME_RISK_SCALARS:
        name = f"satellite_connectivity_theme_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(
            name,
            scalar,
            registry_theme_gate,
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
        "accepted_default_off_space_satellite_connectivity_theme_risk"
        if accepted
        else "rejected_space_satellite_connectivity_theme_risk"
    )
    interpretation = (
        "The satellite-connectivity theme scalar cleared the three-window gate on "
        "top of exp-20260513-015. Promotion must be shared/default-off with live "
        "Space slots unchanged at zero."
        if accepted
        else (
            "The satellite-connectivity theme scalar did not clear the three-window "
            "gate on top of exp-20260513-015. Keep Space theme-segment risk "
            "allocation limited to the accepted launch/lunar helper."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_satellite_connectivity_theme_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals with "
            "theme_segment=satellite_connectivity"
        ),
        "hypothesis": (
            "The accepted Space stack has shown value in production-visible "
            "catalyst quality fields. Satellite-connectivity signals may deserve a "
            "separate risk allocation because their regulatory/direct-to-device "
            "catalysts differ from launch/lunar and data/defense catalysts, without "
            "adding tickers, changing ranking, or using LLM soft-ranking."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale official Space signals whose registry "
                "theme_segment is satellite_connectivity."
            ),
            "2_history_check": {
                "exp-20260512-032": (
                    "Accepted launch_lunar theme top-up; this tests a different "
                    "theme_segment and does not retune launch_lunar."
                ),
                "exp-20260513-014/015": (
                    "Accepted customer-source/government-contract peer-leader "
                    "helpers are fixed as the before stack."
                ),
                "exp-20260513-019": (
                    "Rejected customer-source peer-nonleader complement; this run "
                    "uses theme segment rather than source/peer complement."
                ),
                "llm_soft_ranking": (
                    "Still label-limited, so this run avoids LLM scoring."
                ),
            },
            "3_single_causal_variable": (
                "space_satellite_connectivity_theme_risk_scalar. Candidate pool, "
                "accepted Space stack, source/peer helpers, targets, stops, ranking, "
                "LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp-015 accepted stack, at least 2/3 improved EV "
                "windows, no EV-regressed window, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, >=50 total trades, nonzero adjusted signals, and "
                "non-1.0 scalar."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_021_space_satellite_connectivity_theme_risk.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_theme_segment": TARGET_THEME_SEGMENT,
            "target_tickers": registry_theme_gate["target_tickers"],
            "target_registry_records": registry_theme_gate["records"],
            "tested_satellite_connectivity_theme_scalars": list(
                SATELLITE_CONNECTIVITY_THEME_RISK_SCALARS
            ),
            "accepted_before_experiment": "exp-20260513-015",
            "accepted_customer_source_peer_leader_risk_scalar": (
                ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR
            ),
            "accepted_government_contract_peer_leader_risk_scalar": (
                ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR
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
                "from a 2026-05-10 research universe. Theme fields are "
                "production-visible registry metadata, but any accepted Space change "
                "must remain default-off until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "registry_theme_segment": registry_theme_gate,
            "runtime_theme_segment": runtime_theme_gate,
            "official_customer_source_profile": source_gate,
            "peer_momentum_state": peer_state_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "watch_liquidity_tier_registry": liquidity_gate,
            "accepted_multi_event_depth": multi_event_gate,
            "government_contract_profile": government_contract_gate,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe registry theme_segment",
                "accepted Space signal enrichment space_theme_segment",
                "portfolio_engine sizing shares_to_buy",
            ],
            "passed": (
                gate2_open["passed"]
                and registry_theme_gate["passed"]
                and runtime_theme_gate["passed"]
                and source_gate["passed"]
                and peer_state_gate["passed"]
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
        "total_pnl_delta": best_variant["gate"]["aggregate_delta_vs_before"][
            "total_pnl_sum"
        ],
        "gate_results": best_variant["gate"],
        "gate4": best_variant["gate"],
        "sweep_summary": _sweep_summary(variants),
        "variants": variants,
        "best_variant": best_variant,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space soft-ranking remains label-limited; this run uses deterministic "
                "production-visible theme metadata."
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
            "If rejected, do not add a satellite-connectivity theme top-up on "
            "these frozen snapshots. Future Space alpha should use forward "
            "replacement value by catalyst family/source/peer/theme bucket or a "
            "new production-visible official catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_021_space_satellite_connectivity_theme_risk.py",
            "data/experiments/exp-20260513-021/space_satellite_connectivity_theme_risk.json",
            "docs/experiments/logs/exp-20260513-021.json",
            "docs/experiments/tickets/exp-20260513-021.json",
            "docs/experiments/artifacts/exp-20260513-021_space_satellite_connectivity_theme_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; noisy ticker additions are avoided; "
            "watch-liquidity peer/TQS/strategy scopes and customer-source "
            "peer-nonleader top-ups were already rejected or underpowered. This "
            "tests a different production-visible theme segment on the fixed "
            "accepted Space stack."
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
