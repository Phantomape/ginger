from __future__ import annotations

import json
import sys
from collections import Counter
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

import portfolio_engine
from data_layer import get_universe
from exp_20260513_032_space_attention_overlay_risk import (
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
    ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
    ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
    ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
    EXPERIMENT_ID as BEFORE_EXPERIMENT_ID,
    MULTI_EVENT_MIN_COUNT,
    OFFICIAL_SPACE_TICKERS,
    TARGET_LIQUIDITY_TIER,
    WATCH_LIQUIDITY_RISK_SCALAR,
    WINDOWS,
    _accepted_financing_profile_gate,
    _adjustment_summary,
    _aggregate,
    _aggregate_delta,
    _delta,
    _event_seed_profiles,
    _field_check_attention_overlay_profile,
    _field_check_company_release_source,
    _field_check_government_contract_profile,
    _field_check_iwm_peer_leader_trend,
    _field_check_multi_event_depth,
    _field_check_peer_leader_state,
    _field_check_single_event_defense_profile,
    _field_check_watch_liquidity_tier,
    _gate2_open_positions,
    _install_space_policy,
    _metrics,
    _restore_policy,
    _run_core_baseline,
    _run_variant as _run_exp032_variant,
    _run_window,
    _safe,
    _scale_sizing,
    _space_trade_attribution,
    _write_json,
)

EXPERIMENT_ID = "exp-20260513-037"
STEM = "space_non_dilutive_contract_profile_risk"
ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR = 1.25
TARGET_PROFILE_TERMS = ("contract", "revenue_quality")
EXCLUDED_PROFILE_TERMS = ("financing", "dilution")
PROFILE_RISK_SCALARS = (0.75, 0.90, 1.00, 1.025, 1.05, 1.075, 1.10, 1.15)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


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


def _official_space_registry() -> dict[str, dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "universe_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("tickers") or {}
    return {ticker: records.get(ticker) or {} for ticker in OFFICIAL_SPACE_TICKERS}


def _field_check_non_dilutive_contract_profiles() -> dict[str, Any]:
    records = _official_space_registry()
    missing: list[str] = []
    profiles: dict[str, str] = {}
    target_tickers: list[str] = []
    excluded_tickers: dict[str, str] = {}

    for ticker, record in records.items():
        profile = str(record.get("event_guard_profile") or "")
        if not profile:
            missing.append(ticker)
            continue
        profile_lower = profile.lower()
        profiles[ticker] = profile
        has_target_term = any(term in profile_lower for term in TARGET_PROFILE_TERMS)
        has_excluded_term = any(term in profile_lower for term in EXCLUDED_PROFILE_TERMS)
        if has_target_term and has_excluded_term:
            excluded_tickers[ticker] = profile
        elif has_target_term:
            target_tickers.append(ticker)

    return {
        "passed": not missing and bool(target_tickers),
        "path": "data/universe_registry.json",
        "field": "event_guard_profile",
        "target_profile_terms": list(TARGET_PROFILE_TERMS),
        "excluded_profile_terms": list(EXCLUDED_PROFILE_TERMS),
        "target_tickers": sorted(target_tickers),
        "excluded_tickers": dict(sorted(excluded_tickers.items())),
        "profiles": dict(sorted(profiles.items())),
        "missing_event_guard_profile": sorted(missing),
    }


def _run_profile_variant(
    label: str,
    profile_scalar: float,
    *,
    profile_gate: dict[str, Any],
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
        ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
        attention_gate=attention_gate,
        single_event_gate=single_event_gate,
        government_contract_gate=government_contract_gate,
        source_gate=source_gate,
        multi_event_gate=multi_event_gate,
        liquidity_gate=liquidity_gate,
        company_release_gate=company_release_gate,
        financing_gate=financing_gate,
    )
    accepted_size_signals = portfolio_engine.size_signals
    target_tickers = set(profile_gate["target_tickers"])
    profiles = profile_gate["profiles"]
    profile_adjustments: list[dict[str, Any]] = []
    profile_counts: Counter[str] = Counter()

    def size_with_profile_scalar(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        adjusted: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                profile_counts["eligible_signal"] += 1
                profile_counts[f"eligible_{ticker}"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                dollars_before = float(sizing.get("position_size_dollars") or 0.0)
                _scale_sizing(
                    sizing,
                    profile_scalar,
                    portfolio_value,
                    "space_non_dilutive_contract_profile_risk",
                )
                shares_after = int(sizing.get("shares_to_buy") or 0)
                dollars_after = float(sizing.get("position_size_dollars") or 0.0)
                if shares_after != shares_before:
                    profile_counts["changed_signal"] += 1
                    profile_counts[f"changed_{ticker}"] += 1
                profile_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_non_dilutive_contract_profile_risk",
                        "event_guard_profile": profiles.get(ticker),
                        "scalar": profile_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": shares_after,
                        "dollars_before_scalar": dollars_before,
                        "dollars_after_scalar": dollars_after,
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                        "space_basket_momentum_state": signal.get("space_basket_momentum_state"),
                        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_event_guard_profile": profiles.get(ticker),
                    "space_non_dilutive_contract_profile_eligible": True,
                    "space_non_dilutive_contract_profile_scalar": profile_scalar,
                }
            adjusted.append(signal)
        return adjusted

    portfolio_engine.size_signals = size_with_profile_scalar
    try:
        by_window: dict[str, Any] = {}
        for name, window in WINDOWS.items():
            before_profile = len(profile_adjustments)
            before_counts = Counter(profile_counts)
            result = _run_window(window, universe, "space_snapshot")
            window_adjustments = profile_adjustments[before_profile:]
            count_delta = dict(sorted((profile_counts - before_counts).items()))
            by_window[name] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_non_dilutive_contract_profile_adjustment": _adjustment_summary(
                    window_adjustments
                ),
                "space_non_dilutive_contract_profile_counts": count_delta,
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": label,
            "parameters": {
                "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
                "accepted_attention_overlay_risk_scalar": ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
                "space_non_dilutive_contract_profile_scalar": profile_scalar,
                "target_profile_terms": list(TARGET_PROFILE_TERMS),
                "excluded_profile_terms": list(EXCLUDED_PROFILE_TERMS),
                "target_tickers": profile_gate["target_tickers"],
            },
            "by_window": by_window,
            "aggregate": _aggregate(metrics_by_window),
            "profile_adjustment_summary": _adjustment_summary(profile_adjustments),
            "profile_adjustment_counts": dict(sorted(profile_counts.items())),
            "profile_adjustment_sample": profile_adjustments[:25],
        }
    finally:
        _restore_policy(*installed["originals"])


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
    before_by_window = before["by_window"]
    by_window_delta = {
        name: _delta(payload["metrics"], before_by_window[name]["metrics"])
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
    max_drawdown_damage = aggregate_delta["max_drawdown_pct_max"]
    min_survival_rate = variant["aggregate"]["min_survival_rate"]
    trade_count = variant["aggregate"]["trade_count_sum"]
    changed_count = int(variant["profile_adjustment_counts"].get("changed_signal", 0))
    eligible_count = int(variant["profile_adjustment_counts"].get("eligible_signal", 0))
    scalar = float(variant["parameters"]["space_non_dilutive_contract_profile_scalar"])
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improvements": ev_improvements,
        "ev_regressions": ev_regressions,
        "max_drawdown_damage_vs_before": max_drawdown_damage,
        "min_survival_rate": min_survival_rate,
        "trade_count": trade_count,
        "eligible_profile_signal_count": eligible_count,
        "changed_profile_signal_count": changed_count,
        "accepted": bool(
            scalar != 1.0
            and changed_count > 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and max_drawdown_damage <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and min_survival_rate >= MIN_SURVIVAL_RATE
            and trade_count >= MIN_TRADE_COUNT
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space non-dilutive contract profile risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_non_dilutive_contract_profile_scalar` applied after the accepted "
            "exp-032 attention-overlay stack."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        (
            "- Best scalar: "
            f"`{best['parameters']['space_non_dilutive_contract_profile_scalar']}`"
        ),
        (
            "- Aggregate delta vs exp-032: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Profile signals changed: "
            f"`{gate['changed_profile_signal_count']}` of "
            f"`{gate['eligible_profile_signal_count']}` eligible"
        ),
        "",
        "## Three-Window Deltas vs Exp-032",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | profile signals |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        adjusted = best["by_window"][name][
            "space_non_dilutive_contract_profile_adjustment"
        ]["adjusted_signal_count"]
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
            "## Sweep",
            "| scalar | gate | dEV | dPnL | EV-improved windows | EV-regressed windows | changed signals |",
            "|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    for variant in payload["variants"]:
        variant_gate = variant["gate"]
        delta = variant_gate["aggregate_delta_vs_before"]
        lines.append(
            "| {scalar:.3f} | {gate_status} | {ev:+.6f} | {pnl:+.2f} | {wins} | {losses} | {changed} |".format(
                scalar=variant["parameters"]["space_non_dilutive_contract_profile_scalar"],
                gate_status="pass" if variant_gate["accepted"] else "fail",
                ev=delta["expected_value_score_sum"],
                pnl=delta["total_pnl_sum"],
                wins=len(variant_gate["ev_improvements"]),
                losses=len(variant_gate["ev_regressions"]),
                changed=variant_gate["changed_profile_signal_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            (
                "No shared production policy was changed by this experiment artifact. "
                "If accepted, the scalar must be promoted into `quant/space_catalyst_sleeve.py` "
                "and covered by parity tests before live use."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "title": "Space non-dilutive contract profile risk",
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "best_parameters": payload["best_variant"]["parameters"],
        "aggregate_delta_vs_before": payload["best_variant_gate"]["aggregate_delta_vs_before"],
        "next_action": payload["next_evidence_needed"],
    }


def run() -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc).isoformat()
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
    profile_gate = _field_check_non_dilutive_contract_profiles()
    if not profile_gate["passed"]:
        raise RuntimeError(f"Non-dilutive contract profile field check failed: {profile_gate}")

    core = _run_core_baseline()
    before = _run_exp032_variant(
        "accepted_exp032_attention_overlay_stack",
        ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
        attention_gate,
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

    gate2 = {
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
        "non_dilutive_contract_profiles": profile_gate,
        "runtime_fields": [
            "operator_inputs/open_positions.json entry_date",
            "operator_inputs/open_positions.json target_price",
            "data/universe_registry.json event_guard_profile",
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
            and profile_gate["passed"]
        ),
    }

    variants = [
        _run_profile_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            scalar,
            profile_gate=profile_gate,
            attention_gate=attention_gate,
            single_event_gate=single_event_gate,
            government_contract_gate=government_contract_gate,
            source_gate=source_gate,
            multi_event_gate=multi_event_gate,
            liquidity_gate=liquidity_gate,
            company_release_gate=company_release_gate,
            financing_gate=financing_gate,
        )
        for scalar in PROFILE_RISK_SCALARS
    ]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

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
            "No tested non-dilutive contract/revenue profile scalar improved aggregate "
            "EV/PnL across the three standard windows without a window-level EV regression."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "On top of accepted exp-032 Space attention overlay stack, official Space "
            "signals with production registry profiles tied to contracts or revenue quality "
            "but not financing/dilution sensitivity may have cleaner catalyst duration. "
            "A single risk scalar can test whether that profile deserves more or less "
            "capital without changing the Space pool, ranking, events, targets, stops, "
            "LLM boundary, or live slots."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_non_dilutive_contract_profile_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose production registry event_guard_profile "
            "contains contract or revenue_quality and excludes financing/dilution"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol",
            "windows": WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"] for label, window in WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "risk allocation: scale only official Space signals with non-dilutive "
                "contract/revenue-quality event_guard_profile metadata."
            ),
            "q2_prior_experiments": [
                "exp-20260512-041 accepted financing/dilution profile scalar; excluded here.",
                "exp-20260513-015 accepted government-contract peer-leader scalar; peer state is locked here.",
                "exp-20260513-022 rejected government-contract peer-nonleader scalar; not retested here.",
                "exp-20260513-035 rejected broad breakout scalar; strategy is not the tested axis here.",
            ],
            "q3_single_causal_variable": (
                "Only space_non_dilutive_contract_profile_risk_scalar changes; candidate pool, "
                "event labels, ranking, targets, stops, LLM/news, accepted exp-032 stack, and live slots stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate EV/PnL, "
                "at least two EV-improved windows, no EV-regressed window, max drawdown damage <= 0.5pp, "
                "survival >= 5%, >=50 aggregate trades, and real adjusted profile-qualified signals."
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
                "Space candidate snapshots are frozen historical replay copies built from a "
                "2026-05-10 research universe. Registry event_guard_profile metadata is "
                "production-observable, but accepted Space helper policy remains default-off "
                "with live Space slots at zero until forward evidence supports promotion."
            ),
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_profile_scalar_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_profile_terms": list(TARGET_PROFILE_TERMS),
            "excluded_profile_terms": list(EXCLUDED_PROFILE_TERMS),
            "target_tickers": profile_gate["target_tickers"],
            "excluded_tickers": profile_gate["excluded_tickers"],
            "event_guard_profiles": profile_gate["profiles"],
            "tested_profile_scalars": list(PROFILE_RISK_SCALARS),
            "accepted_exp032_attention_overlay_risk_scalar": ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
            "accepted_stack_scalars": {
                "multi_event_depth": ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
                "customer_source_peer_leader": ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
                "government_contract_peer_leader": ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
                "iwm_peer_leader_trend": ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
                "single_event_defense": ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
                "watch_liquidity": WATCH_LIQUIDITY_RISK_SCALAR,
                "company_release_source": ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
                "financing_dilution_profile": ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
            },
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
                "accepted liquidity_tier=ok/watch scalars",
                "accepted official source scalars",
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
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "status": (
            "accepted_default_off_space_non_dilutive_contract_profile_risk"
            if decision == "accepted"
            else "rejected_space_non_dilutive_contract_profile_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote scalar into the shared Space policy and add parity tests before enabling in live routing."
            if decision == "accepted"
            else (
                "Do not keep tuning non-dilutive contract/revenue registry scalars on these frozen snapshots. "
                "Prefer a different Space alpha axis with production-visible metadata or better official-catalyst coverage."
            )
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": decision == "accepted",
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains label-thin, naive ticker expansion recently failed, and "
            "broad breakout retuning was rejected. This run isolates one production-visible "
            "registry-quality axis complementary to accepted financing/dilution risk."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and based on frozen historical replay snapshots.",
            "Registry-profile samples are small; accepted evidence still needs forward validation before live slots.",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    exp_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = PROJECT_ROOT / "docs" / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "docs" / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "docs" / "experiments" / "artifacts"
    for directory in (logs_dir, tickets_dir, artifacts_dir):
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
                for label, window in WINDOWS.items()
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
            "space_non_dilutive_contract_profile_scalar"
        ],
        "target_tickers": result["parameters"]["target_tickers"],
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "by_window_delta_vs_before": result["best_variant_gate"][
            "by_window_delta_vs_before"
        ],
        "changed_profile_signal_count": result["best_variant_gate"][
            "changed_profile_signal_count"
        ],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
