"""exp-20260513-028: Space single-event defense-only risk.

Tests one causal variable on top of the accepted exp-20260513-020 default-off
Space stack: a risk scalar for official Space tickers whose current official
event-seed profile has exactly one non-attention event, that event is only a
government_space_contract/defense_budget_theme seed, and the ticker has no
customer_win event. This is a catalyst-depth/replacement-value alpha test, not
LLM soft-ranking, live routing, candidate-pool expansion, or a broad defense
theme retune.
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
    EXCLUDED_SEMANTIC_BUCKETS,
    MULTI_EVENT_MIN_COUNT,
    OFFICIAL_NON_ATTENTION_SOURCE_TYPES,
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

EXPERIMENT_ID = "exp-20260513-028"
STEM = "space_single_event_defense_haircut"
ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR = 1.15
TARGET_EVENT_FIELD = "government_space_contract"
EXCLUDED_EVENT_FIELD = "customer_win"
TARGET_SEMANTIC_BUCKET = "defense_budget_theme"
SINGLE_EVENT_DEFENSE_RISK_SCALARS = (
    0.50,
    0.65,
    0.75,
    0.90,
    1.00,
    1.05,
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


def _field_check_single_event_defense_profile() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_seeds.jsonl"
    if not path.exists():
        return {
            "passed": False,
            "path": str(path.relative_to(PROJECT_ROOT)),
            "missing": "file",
        }

    rows: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, Any]] = {}
    source_counts = Counter()
    semantic_counts = Counter()
    event_field_counts = Counter()

    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(row)
        required_missing = [
            field
            for field in ("event_id", "event_fields", "semantic_bucket", "source_type", "tickers")
            if not row.get(field)
        ]
        if required_missing:
            missing_fields.append(
                {
                    "line_number": line_number,
                    "event_id": row.get("event_id"),
                    "missing": required_missing,
                }
            )
            continue

        source_type = str(row.get("source_type") or "")
        semantic_bucket = str(row.get("semantic_bucket") or "")
        fields = [str(item) for item in row.get("event_fields") or []]
        source_counts[source_type] += 1
        semantic_counts[semantic_bucket] += 1
        for field in fields:
            event_field_counts[field] += 1

        if source_type not in OFFICIAL_NON_ATTENTION_SOURCE_TYPES:
            continue
        if semantic_bucket in EXCLUDED_SEMANTIC_BUCKETS:
            continue

        for raw_ticker in row.get("tickers") or []:
            ticker = str(raw_ticker or "").upper()
            if ticker not in OFFICIAL_SPACE_TICKERS:
                continue
            profile = profiles.setdefault(
                ticker,
                {
                    "event_ids": [],
                    "event_fields": set(),
                    "semantic_buckets": set(),
                    "source_types": set(),
                },
            )
            profile["event_ids"].append(str(row.get("event_id")))
            profile["event_fields"].update(fields)
            profile["semantic_buckets"].add(semantic_bucket)
            profile["source_types"].add(source_type)

    serialized_profiles = {}
    for ticker, profile in profiles.items():
        event_ids = sorted(set(profile["event_ids"]))
        serialized_profiles[ticker] = {
            "event_count": len(event_ids),
            "event_ids": event_ids,
            "event_fields": sorted(profile["event_fields"]),
            "semantic_buckets": sorted(profile["semantic_buckets"]),
            "source_types": sorted(profile["source_types"]),
        }

    target_tickers = sorted(
        ticker
        for ticker, profile in serialized_profiles.items()
        if int(profile["event_count"]) == 1
        and TARGET_EVENT_FIELD in profile["event_fields"]
        and EXCLUDED_EVENT_FIELD not in profile["event_fields"]
        and TARGET_SEMANTIC_BUCKET in profile["semantic_buckets"]
    )

    return {
        "passed": not missing_fields and bool(target_tickers),
        "path": str(path.relative_to(PROJECT_ROOT)),
        "event_seed_count": len(rows),
        "target_definition": (
            "official Space ticker with exactly one official non-attention seed, "
            "government_space_contract present, no customer_win, and defense_budget_theme"
        ),
        "target_source_types": list(OFFICIAL_NON_ATTENTION_SOURCE_TYPES),
        "target_event_field": TARGET_EVENT_FIELD,
        "excluded_event_field": EXCLUDED_EVENT_FIELD,
        "target_semantic_bucket": TARGET_SEMANTIC_BUCKET,
        "excluded_semantic_buckets": list(EXCLUDED_SEMANTIC_BUCKETS),
        "target_tickers": target_tickers,
        "profiles": serialized_profiles,
        "source_type_counts": dict(sorted(source_counts.items())),
        "semantic_bucket_counts": dict(sorted(semantic_counts.items())),
        "event_field_counts": dict(sorted(event_field_counts.items())),
        "missing_required_fields": missing_fields,
    }


def _install_space_policy(
    single_event_defense_scalar: float,
    single_event_gate: dict[str, Any],
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
    profiles = single_event_gate["profiles"]
    target_tickers = set(single_event_gate["target_tickers"])
    single_event_adjustments: list[dict[str, Any]] = []
    single_event_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                single_event_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                profile = profiles.get(ticker, {})
                _scale_sizing(
                    sizing,
                    single_event_defense_scalar,
                    portfolio_value,
                    "space_single_event_defense_risk",
                )
                single_event_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_single_event_defense_risk",
                        "scalar": single_event_defense_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "event_count": profile.get("event_count"),
                        "event_ids": profile.get("event_ids"),
                        "event_fields": profile.get("event_fields"),
                        "semantic_buckets": profile.get("semantic_buckets"),
                        "source_types": profile.get("source_types"),
                        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_single_event_defense_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return {
        "originals": accepted["originals"],
        "accepted": accepted,
        "single_event_adjustments": single_event_adjustments,
        "single_event_counts": single_event_counts,
    }


def _slice_summary(installed: dict[str, Any], key: str, before_count: int) -> dict[str, Any]:
    return _adjustment_summary(installed["accepted"][key][before_count:])


def _run_variant(
    name: str,
    single_event_defense_scalar: float,
    single_event_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        single_event_defense_scalar,
        single_event_gate,
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
            before_target = len(installed["single_event_adjustments"])
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
                "space_single_event_defense_adjustment": _adjustment_summary(
                    installed["single_event_adjustments"][before_target:]
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
                "space_single_event_defense_signal_counts": dict(
                    sorted(installed["single_event_counts"].items())
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
        "target_definition": single_event_gate["target_definition"],
        "target_tickers": single_event_gate["target_tickers"],
        "space_single_event_defense_risk_scalar": single_event_defense_scalar,
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
        row["space_single_event_defense_adjustment"]["adjusted_signal_count"]
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
        and variant["space_single_event_defense_risk_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_single_event_defense_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space single-event defense-only risk",
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
            "space_single_event_defense_adjustment"
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
            json.dumps(
                payload["gate2"]["single_event_defense_profile"],
                sort_keys=True,
            ),
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
    single_event_gate = _field_check_single_event_defense_profile()
    if not single_event_gate["passed"]:
        raise RuntimeError(
            f"Single-event defense profile field check failed: {single_event_gate}"
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

    variants = {}
    for scalar in SINGLE_EVENT_DEFENSE_RISK_SCALARS:
        name = f"single_event_defense_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(
            name,
            scalar,
            single_event_gate,
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
        "accepted_default_off_space_single_event_defense_risk"
        if accepted
        else "rejected_space_single_event_defense_risk"
    )
    interpretation = (
        "The single-event defense-only Space scalar cleared the three-window gate "
        "on top of the exp-020 accepted stack. The retained change is promoted "
        "through shared default-off Space policy metadata with live Space slots "
        "still zero, so production observation and replay attribution use the "
        "same production-visible event-seed profile boundary."
        if accepted
        else (
            "The single-event defense-only Space scalar did not clear the "
            "three-window gate on top of exp-020. Catalyst depth remains the "
            "strongest Space direction, but the evidence supports the accepted "
            "multi-event/customer-win/peer-leader helpers rather than a separate "
            "haircut for PL/RDW/BKSY-style single defense-budget exposure."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_single_event_defense_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose official non-attention "
            "event profile has exactly one defense-budget government contract seed "
            "and no customer_win seed"
        ),
        "hypothesis": (
            "Accepted multi-event catalyst depth implies replacement value improves "
            "when official Space tickers have multiple non-attention catalysts. The "
            "complement alpha question is whether single-event, defense-only tickers "
            "without customer_win have weaker replacement value and deserve lower "
            "risk than the accepted exp-020 stack grants them."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale only official Space signals for tickers with "
                "exactly one official non-attention event seed, "
                "government_space_contract present, defense_budget_theme bucket, and "
                "no customer_win seed."
            ),
            "2_history_check": {
                "exp-20260513-012": (
                    "Accepted multi-event official non-attention depth at 1.075x; "
                    "this tests the lower-depth complement rather than retuning that "
                    "accepted scalar."
                ),
                "exp-20260513-014": (
                    "Accepted customer_win + peer leader risk; this run deliberately "
                    "excludes customer_win profiles."
                ),
                "exp-20260513-015": (
                    "Accepted government_contract + peer leader risk at 1.05x; this "
                    "run does not alter peer-leader treatment."
                ),
                "exp-20260513-022": (
                    "Rejected government-contract peer-nonleader risk; this run "
                    "uses catalyst-depth and source profile instead of peer state."
                ),
                "exp-20260513-025": (
                    "Rejected peer-leader breakout risk; this run avoids another "
                    "breakout or peer-slice retune."
                ),
                "exp-20260513-026": (
                    "Rejected IWM+peer-leader trend target width despite aggregate "
                    "EV lift because PnL and old_thin regressed; this run leaves "
                    "lifecycle/targets fixed."
                ),
            },
            "3_single_causal_variable": (
                "space_single_event_defense_risk_scalar. Candidate pool, accepted "
                "Space stack, targets, stops, ranking, add-ons, LLM/news, and live "
                "slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp-020 accepted stack, at least 2/3 improved EV "
                "windows, no EV-regressed window, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, >=50 total trades, nonzero adjusted signals, and "
                "non-1.0 scalar."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_028_space_single_event_defense_haircut.py"
            ),
        },
        "parameters": {
            "target_tickers": single_event_gate["target_tickers"],
            "tested_single_event_defense_scalars": list(SINGLE_EVENT_DEFENSE_RISK_SCALARS),
            "target_event_field": TARGET_EVENT_FIELD,
            "excluded_event_field": EXCLUDED_EVENT_FIELD,
            "target_semantic_bucket": TARGET_SEMANTIC_BUCKET,
            "target_source_types": list(OFFICIAL_NON_ATTENTION_SOURCE_TYPES),
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
                "from a 2026-05-10 research universe. The tested profile fields are "
                "production-visible event-seed metadata, but accepted positive changes "
                "must be promoted through shared default-off Space policy before use."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "official_customer_source_profile": source_gate,
            "single_event_defense_profile": single_event_gate,
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
                "data/space_catalyst_event_seeds.jsonl event_id",
                "data/space_catalyst_event_seeds.jsonl event_fields",
                "data/space_catalyst_event_seeds.jsonl semantic_bucket",
                "data/space_catalyst_event_seeds.jsonl source_type",
                "data/space_catalyst_event_seeds.jsonl tickers",
                "sizing.shares_to_buy from shared sizing engine",
            ],
            "passed": (
                gate2_open["passed"]
                and source_gate["passed"]
                and single_event_gate["passed"]
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
                "production-visible official event-seed profile metadata."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "promotion_required_if_accepted": False,
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
            "Do not retest nearby single-event defense-only scalars on the same frozen "
            "snapshots if rejected. Next Space alpha should close forward "
            "replacement-value labels by catalyst family/source/peer bucket, or add "
            "production-visible official-catalyst coverage for genuinely new issuers "
            "instead of noisy ticker expansion."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_028_space_single_event_defense_haircut.py",
            "data/experiments/exp-20260513-028/space_single_event_defense_haircut.json",
            "docs/experiments/logs/exp-20260513-028.json",
            "docs/experiments/tickets/exp-20260513-028.json",
            "docs/experiments/artifacts/exp-20260513-028_space_single_event_defense_haircut.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is label-limited; noisy ticker additions, mature satcom "
            "breadth, watch-liquidity peer/TQS/strategy scopes, broad defense-budget "
            "source scalars, primary-authority source scalars, customer-source "
            "peer-nonleader scaling, government-contract peer-nonleader scaling, "
            "peer-leader breakout risk, and adjacent trend target width were already "
            "rejected, accepted, or underpowered."
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
