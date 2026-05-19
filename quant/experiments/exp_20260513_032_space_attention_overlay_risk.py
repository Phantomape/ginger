"""exp-20260513-032: Space attention-overlay risk.

Tests one causal variable on top of the accepted exp-20260513-028 default-off
Space stack: a risk scalar for official Space tickers whose event-seed profile
contains both a production-visible non-attention catalyst and an attention-only
Space catalyst. This deliberately avoids trading UAP/ETF attention by itself;
it only asks whether attention overlays add replacement value to already
qualified official Space catalysts.
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
)
from exp_20260513_028_space_single_event_defense_haircut import (  # noqa: E402
    ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
    _field_check_single_event_defense_profile,
    _install_space_policy as _install_accepted_exp028_policy,
    _run_variant as _run_accepted_exp028_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-032"
STEM = "space_attention_overlay_risk"
ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR = 1.05
ATTENTION_SEMANTIC_BUCKET = "attention_only"
ATTENTION_EVENT_FIELDS = ("spacex_ipo_proxy", "uap_attention_spike")
ATTENTION_OVERLAY_RISK_SCALARS = (
    0.50,
    0.75,
    0.90,
    1.00,
    1.025,
    1.05,
    1.075,
    1.10,
    1.15,
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


def _is_attention_event(row: dict[str, Any]) -> bool:
    semantic_bucket = str(row.get("semantic_bucket") or "")
    fields = {str(item) for item in row.get("event_fields") or []}
    return semantic_bucket == ATTENTION_SEMANTIC_BUCKET or bool(
        fields.intersection(ATTENTION_EVENT_FIELDS)
    )


def _is_non_attention_official_event(row: dict[str, Any]) -> bool:
    source_type = str(row.get("source_type") or "")
    semantic_bucket = str(row.get("semantic_bucket") or "")
    return (
        source_type in OFFICIAL_NON_ATTENTION_SOURCE_TYPES
        and semantic_bucket not in EXCLUDED_SEMANTIC_BUCKETS
    )


def _field_check_attention_overlay_profile() -> dict[str, Any]:
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
    attention_source_counts = Counter()
    attention_field_counts = Counter()
    non_attention_source_counts = Counter()

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

        is_attention = _is_attention_event(row)
        is_non_attention = _is_non_attention_official_event(row)
        if is_attention:
            attention_source_counts[source_type] += 1
            for field in fields:
                attention_field_counts[field] += 1
        if is_non_attention:
            non_attention_source_counts[source_type] += 1
        if not is_attention and not is_non_attention:
            continue

        for raw_ticker in row.get("tickers") or []:
            ticker = str(raw_ticker or "").upper()
            if ticker not in OFFICIAL_SPACE_TICKERS:
                continue
            profile = profiles.setdefault(
                ticker,
                {
                    "all_event_ids": set(),
                    "attention_event_ids": set(),
                    "attention_event_fields": set(),
                    "attention_semantic_buckets": set(),
                    "attention_source_types": set(),
                    "non_attention_event_ids": set(),
                    "non_attention_event_fields": set(),
                    "non_attention_semantic_buckets": set(),
                    "non_attention_source_types": set(),
                },
            )
            profile["all_event_ids"].add(str(row.get("event_id")))
            if is_attention:
                profile["attention_event_ids"].add(str(row.get("event_id")))
                profile["attention_event_fields"].update(fields)
                profile["attention_semantic_buckets"].add(semantic_bucket)
                profile["attention_source_types"].add(source_type)
            if is_non_attention:
                profile["non_attention_event_ids"].add(str(row.get("event_id")))
                profile["non_attention_event_fields"].update(fields)
                profile["non_attention_semantic_buckets"].add(semantic_bucket)
                profile["non_attention_source_types"].add(source_type)

    serialized_profiles = {}
    for ticker, profile in profiles.items():
        attention_ids = sorted(profile["attention_event_ids"])
        non_attention_ids = sorted(profile["non_attention_event_ids"])
        serialized_profiles[ticker] = {
            "event_count": len(profile["all_event_ids"]),
            "attention_event_count": len(attention_ids),
            "attention_event_ids": attention_ids,
            "attention_event_fields": sorted(profile["attention_event_fields"]),
            "attention_semantic_buckets": sorted(profile["attention_semantic_buckets"]),
            "attention_source_types": sorted(profile["attention_source_types"]),
            "non_attention_event_count": len(non_attention_ids),
            "non_attention_event_ids": non_attention_ids,
            "non_attention_event_fields": sorted(
                profile["non_attention_event_fields"]
            ),
            "non_attention_semantic_buckets": sorted(
                profile["non_attention_semantic_buckets"]
            ),
            "non_attention_source_types": sorted(
                profile["non_attention_source_types"]
            ),
        }

    target_tickers = sorted(
        ticker
        for ticker, profile in serialized_profiles.items()
        if int(profile["attention_event_count"]) > 0
        and int(profile["non_attention_event_count"]) > 0
    )
    return {
        "passed": not missing_fields and bool(target_tickers),
        "path": str(path.relative_to(PROJECT_ROOT)),
        "event_seed_count": len(rows),
        "target_definition": (
            "official Space ticker with at least one attention-only event seed "
            "and at least one official non-attention event seed"
        ),
        "target_tickers": target_tickers,
        "attention_semantic_bucket": ATTENTION_SEMANTIC_BUCKET,
        "attention_event_fields": list(ATTENTION_EVENT_FIELDS),
        "official_non_attention_source_types": list(OFFICIAL_NON_ATTENTION_SOURCE_TYPES),
        "excluded_semantic_buckets": list(EXCLUDED_SEMANTIC_BUCKETS),
        "profiles": serialized_profiles,
        "source_type_counts": dict(sorted(source_counts.items())),
        "semantic_bucket_counts": dict(sorted(semantic_counts.items())),
        "event_field_counts": dict(sorted(event_field_counts.items())),
        "attention_source_type_counts": dict(sorted(attention_source_counts.items())),
        "attention_event_field_counts": dict(sorted(attention_field_counts.items())),
        "non_attention_source_type_counts": dict(
            sorted(non_attention_source_counts.items())
        ),
        "missing_required_fields": missing_fields,
    }


def _install_space_policy(
    attention_overlay_scalar: float,
    attention_gate: dict[str, Any],
    single_event_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    accepted = _install_accepted_exp028_policy(
        ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
        single_event_gate,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    accepted_size = portfolio_engine.size_signals
    profiles = attention_gate["profiles"]
    target_tickers = set(attention_gate["target_tickers"])
    attention_adjustments: list[dict[str, Any]] = []
    attention_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                attention_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                profile = profiles.get(ticker, {})
                _scale_sizing(
                    sizing,
                    attention_overlay_scalar,
                    portfolio_value,
                    "space_attention_overlay_risk",
                )
                attention_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_attention_overlay_risk",
                        "scalar": attention_overlay_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "attention_event_count": profile.get(
                            "attention_event_count"
                        ),
                        "attention_event_ids": profile.get("attention_event_ids"),
                        "attention_event_fields": profile.get(
                            "attention_event_fields"
                        ),
                        "non_attention_event_count": profile.get(
                            "non_attention_event_count"
                        ),
                        "non_attention_event_ids": profile.get(
                            "non_attention_event_ids"
                        ),
                        "non_attention_event_fields": profile.get(
                            "non_attention_event_fields"
                        ),
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_attention_overlay_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return {
        "originals": accepted["originals"],
        "accepted_exp028": accepted,
        "attention_adjustments": attention_adjustments,
        "attention_counts": attention_counts,
    }


def _slice_exp020_summary(
    installed: dict[str, Any],
    key: str,
    before_count: int,
) -> dict[str, Any]:
    return _adjustment_summary(
        installed["accepted_exp028"]["accepted"][key][before_count:]
    )


def _run_variant(
    name: str,
    attention_overlay_scalar: float,
    attention_gate: dict[str, Any],
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
        attention_overlay_scalar,
        attention_gate,
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
            accepted028 = installed["accepted_exp028"]
            accepted020 = accepted028["accepted"]
            before_target = len(installed["attention_adjustments"])
            before_single = len(accepted028["single_event_adjustments"])
            before_iwm_trend = len(accepted020["iwm_peer_leader_trend_adjustments"])
            before_government = len(accepted020["government_contract_adjustments"])
            before_source_peer = len(accepted020["source_peer_leader_adjustments"])
            before_multi = len(accepted020["multi_event_adjustments"])
            before_watch = len(accepted020["watch_adjustments"])
            before_company = len(accepted020["company_release_adjustments"])
            before_financing = len(accepted020["financing_adjustments"])
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_attention_overlay_adjustment": _adjustment_summary(
                    installed["attention_adjustments"][before_target:]
                ),
                "space_single_event_defense_adjustment": _adjustment_summary(
                    accepted028["single_event_adjustments"][before_single:]
                ),
                "space_iwm_peer_leader_trend_adjustment": _slice_exp020_summary(
                    installed, "iwm_peer_leader_trend_adjustments", before_iwm_trend
                ),
                "space_government_contract_peer_leader_adjustment": _slice_exp020_summary(
                    installed, "government_contract_adjustments", before_government
                ),
                "space_customer_source_peer_leader_adjustment": _slice_exp020_summary(
                    installed, "source_peer_leader_adjustments", before_source_peer
                ),
                "space_multi_event_depth_adjustment": _slice_exp020_summary(
                    installed, "multi_event_adjustments", before_multi
                ),
                "space_watch_liquidity_tier_adjustment": _slice_exp020_summary(
                    installed, "watch_adjustments", before_watch
                ),
                "space_company_release_source_adjustment": _slice_exp020_summary(
                    installed, "company_release_adjustments", before_company
                ),
                "space_financing_dilution_profile_adjustment": _slice_exp020_summary(
                    installed, "financing_adjustments", before_financing
                ),
                "space_attention_overlay_signal_counts": dict(
                    sorted(installed["attention_counts"].items())
                ),
                "space_single_event_defense_signal_counts": dict(
                    sorted(accepted028["single_event_counts"].items())
                ),
                "space_iwm_peer_leader_trend_signal_counts": dict(
                    sorted(accepted020["iwm_peer_leader_trend_counts"].items())
                ),
                "space_iwm_relative_state_counts": dict(
                    sorted(accepted020["iwm_state_counts"].items())
                ),
                "space_peer_momentum_state_counts": dict(
                    sorted(accepted020["peer_counts"].items())
                ),
                "space_theme_segment_signal_counts": dict(
                    sorted(accepted020["theme_counts"].items())
                ),
                "space_basket_signal_state_counts": dict(
                    sorted(accepted020["basket_counts"].items())
                ),
                "space_iwm_relative_day_counts": dict(
                    sorted(accepted020["day_counts"].items())
                ),
            }
    finally:
        _restore_policy(*installed["originals"])

    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "target_definition": attention_gate["target_definition"],
        "target_tickers": attention_gate["target_tickers"],
        "space_attention_overlay_risk_scalar": attention_overlay_scalar,
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
        row["space_attention_overlay_adjustment"]["adjusted_signal_count"]
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
        and variant["space_attention_overlay_risk_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_attention_overlay_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space attention-overlay risk",
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
            "space_attention_overlay_adjustment"
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
                payload["gate2"]["attention_overlay_profile"],
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
    attention_gate = _field_check_attention_overlay_profile()
    if not attention_gate["passed"]:
        raise RuntimeError(f"Attention-overlay field check failed: {attention_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp028_variant(
        "accepted_exp028_single_event_defense_stack",
        ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
        single_event_gate,
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
    for scalar in ATTENTION_OVERLAY_RISK_SCALARS:
        name = f"attention_overlay_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(
            name,
            scalar,
            attention_gate,
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
        "accepted_default_off_space_attention_overlay_risk"
        if accepted
        else "rejected_space_attention_overlay_risk"
    )
    interpretation = (
        "The attention-overlay scalar cleared the three-window gate on top of the "
        "exp-028 accepted default-off Space stack. Because it uses event-seed "
        "metadata already visible to production, it is promoted through the shared "
        "default-off Space policy with live Space slots still zero."
        if accepted
        else (
            "The attention-overlay scalar did not clear the three-window gate on top "
            "of exp-028. Attention-only Space catalysts should remain audit context "
            "instead of becoming a separate risk-allocation input on these frozen "
            "snapshots."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_attention_overlay_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose event-seed profile has at "
            "least one attention-only seed and at least one official non-attention seed"
        ),
        "hypothesis": (
            "SpaceX IPO proxy or other attention-only events may amplify replacement "
            "value only when attached to a ticker that already has an official "
            "non-attention catalyst. The test avoids noisy ticker expansion and "
            "does not trade attention-only UAP/ETF seeds by themselves."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale only official Space signals for tickers with "
                "both attention-only and official non-attention event-seed support."
            ),
            "2_history_check": {
                "exp-20260512-103": (
                    "Rejected static Space candidate-pool expansion; this run keeps "
                    "the official operating Space basket fixed."
                ),
                "exp-20260512-944": (
                    "Rejected primary-authority customer-source scalar despite "
                    "aggregate EV lift because only one window improved."
                ),
                "exp-20260513-012": (
                    "Accepted multi-event non-attention depth at 1.075x; this run "
                    "does not retune non-attention depth."
                ),
                "exp-20260513-021": (
                    "Rejected satellite-connectivity theme scalar despite aggregate "
                    "EV lift because 3-window distribution failed."
                ),
                "exp-20260513-028": (
                    "Accepted single-event defense-only 1.05x scalar; this is the "
                    "fixed before stack for this run."
                ),
            },
            "3_single_causal_variable": (
                "space_attention_overlay_risk_scalar. Candidate pool, accepted "
                "Space stack, targets, stops, ranking, add-ons, LLM/news, and live "
                "slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp-028 accepted stack, at least 2/3 improved EV "
                "windows, no EV-regressed window, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, >=50 total trades, nonzero adjusted signals, and "
                "non-1.0 scalar."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_032_space_attention_overlay_risk.py"
            ),
        },
        "parameters": {
            "target_tickers": attention_gate["target_tickers"],
            "tested_attention_overlay_scalars": list(ATTENTION_OVERLAY_RISK_SCALARS),
            "attention_semantic_bucket": ATTENTION_SEMANTIC_BUCKET,
            "attention_event_fields": list(ATTENTION_EVENT_FIELDS),
            "official_non_attention_source_types": list(OFFICIAL_NON_ATTENTION_SOURCE_TYPES),
            "accepted_before_experiment": "exp-20260513-028",
            "accepted_single_event_defense_risk_scalar": (
                ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR
            ),
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
                "accepted single-event defense scalar",
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
            "The accepted_before variant reproduces exp-20260513-028 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. The tested attention profile is "
                "production-visible event-seed metadata, but accepted positive changes "
                "must be promoted through shared default-off Space policy before use."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "official_customer_source_profile": source_gate,
            "attention_overlay_profile": attention_gate,
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
                and attention_gate["passed"]
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
            "alters_sizing": accepted,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not promote attention-only catalyst metadata into a "
            "separate Space risk-allocation scalar on these frozen snapshots. Next "
            "Space alpha should use closed forward replacement value by catalyst "
            "family/source/peer bucket or add production-visible official catalyst "
            "coverage for genuinely new issuers."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_032_space_attention_overlay_risk.py",
            "data/experiments/exp-20260513-032/space_attention_overlay_risk.json",
            "experiments/logs/exp-20260513-032.json",
            "experiments/tickets/exp-20260513-032.json",
            "experiments/artifacts/exp-20260513-032_space_attention_overlay_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is label-limited; noisy ticker additions, mature "
            "satcom breadth, watch-liquidity peer/TQS/strategy scopes, broad "
            "defense-budget source scalars, primary-authority source scalars, "
            "customer-source peer-nonleader scaling, government-contract peer-nonleader "
            "scaling, peer-leader breakout risk, satellite-connectivity theme scalar, "
            "and adjacent trend target width were already rejected, accepted, or "
            "underpowered. This tests a different production-visible catalyst "
            "overlay without adding noise tickers."
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
