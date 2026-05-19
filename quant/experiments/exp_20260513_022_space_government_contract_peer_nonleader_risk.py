from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_20260511_115_space_basket_momentum_risk import (
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
from data_layer import get_universe  # noqa: E402
from exp_20260512_038_space_official_customer_source_risk import _event_seed_profiles
from exp_20260512_041_space_financing_dilution_profile_risk import (
    _field_check_event_guard_profiles as _accepted_financing_profile_gate,
)
from exp_20260512_110_space_company_release_source_risk import (
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    _field_check_company_release_source,
)
from exp_20260512_112_space_watch_liquidity_risk import (
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    TARGET_LIQUIDITY_TIER,
    _field_check_watch_liquidity_tier,
)
from exp_20260513_012_space_multi_event_depth_risk import (
    MULTI_EVENT_MIN_COUNT,
    WATCH_LIQUIDITY_RISK_SCALAR,
    _field_check_multi_event_depth,
)
from exp_20260513_014_space_customer_source_peer_leader_risk import (
    ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
    _field_check_peer_leader_state,
)
from exp_20260513_015_space_government_contract_peer_leader_risk import (
    ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
    _field_check_government_contract_profile,
)
from exp_20260513_020_space_iwm_peer_leader_trend_risk import (
    ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
    _field_check_iwm_peer_leader_trend,
    _install_space_policy as _install_accepted_exp020_policy,
    _run_variant as _run_accepted_exp020_variant,
)
import portfolio_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260513-022"
STEM = "space_government_contract_peer_nonleader_risk"
TIMESTAMP = "2026-05-13T09:02:00Z"
ARTIFACT_DIR = PROJECT_ROOT / "experiments" / EXPERIMENT_ID
RESULT_JSON = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.json"
RESULT_MD = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_MD = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}_ticket.md"
LOG_PATH = PROJECT_ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR = 1.15
GOVERNMENT_CONTRACT_PEER_NONLEADER_RISK_SCALARS = (0.50, 0.75, 0.90, 1.00)


def _target_tickers(gate: dict[str, Any]) -> set[str]:
    return set(gate.get("target_tickers") or set((gate.get("profiles") or {}).keys()))


def _is_target_nonleader(signal: dict[str, Any], gate: dict[str, Any]) -> bool:
    ticker = str(signal.get("ticker") or "").upper()
    peer_state = str(signal.get("space_peer_momentum_state") or "").lower()
    return ticker in _target_tickers(gate) and peer_state == "nonleader"


def _field_check_government_contract_peer_nonleader(
    before: dict[str, Any], government_contract_gate: dict[str, Any]
) -> dict[str, Any]:
    target_tickers = _target_tickers(government_contract_gate)
    counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    sample_tickers: set[str] = set()
    samples: list[dict[str, Any]] = []

    for row in before.get("by_window", {}).values():
        attribution = row.get("space_trade_attribution") or {}
        for state, count in (attribution.get("space_peer_momentum_state_counts") or {}).items():
            counts[str(state or "unknown")] += int(count or 0)
        for key in (
            "space_iwm_peer_leader_trend_adjustment",
            "space_government_contract_peer_leader_adjustment",
            "space_customer_source_peer_leader_adjustment",
            "space_multi_event_depth_adjustment",
            "space_watch_liquidity_tier_adjustment",
            "space_basket_positive_adjustment",
        ):
            for sample in (row.get(key) or {}).get("sample_adjusted", []):
                ticker = str(sample.get("ticker") or "").upper()
                peer_state = str(sample.get("space_peer_momentum_state") or "").lower()
                if ticker in target_tickers and peer_state:
                    sample_tickers.add(ticker)
                    target_counts[peer_state] += 1
                    if len(samples) < 8:
                        samples.append(
                            {
                                "ticker": ticker,
                                "space_peer_momentum_state": peer_state,
                                "strategy": sample.get("strategy"),
                                "source_adjustment": key,
                            }
                        )

    return {
        "field": "space_peer_momentum_state",
        "target_profile": "government_contract_profile",
        "target_tickers": sorted(target_tickers),
        "space_peer_momentum_state_counts": dict(sorted(counts.items())),
        "target_peer_momentum_state_sample_counts": dict(sorted(target_counts.items())),
        "sample_target_tickers_with_peer_state": sorted(sample_tickers),
        "samples": samples,
        "passed": bool(target_tickers) and target_counts.get("nonleader", 0) > 0,
        "failure_reason": None
        if bool(target_tickers) and target_counts.get("nonleader", 0) > 0
        else "no government-contract target nonleader samples in accepted exp020 baseline",
    }


def _install_space_policy(
    government_contract_peer_nonleader_scalar: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    installed = _install_accepted_exp020_policy(
        ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    accepted_size_signals = portfolio_engine.size_signals
    adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    target_tickers = _target_tickers(government_contract_gate)
    profiles = government_contract_gate.get("profiles") or {}

    def size_wrapper(
        signals: list[dict[str, Any]], portfolio_value: float, risk_pct: float | None = None
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        output: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = copy.deepcopy(signal.get("sizing") or {})
            eligible = _is_target_nonleader(signal, government_contract_gate)
            if eligible and sizing:
                counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                dollars_before = float(sizing.get("position_size_dollars") or 0.0)
                _scale_sizing(
                    sizing,
                    government_contract_peer_nonleader_scalar,
                    portfolio_value,
                    "space_government_contract_peer_nonleader_risk",
                )
                shares_after = int(sizing.get("shares_to_buy") or 0)
                dollars_after = float(sizing.get("position_size_dollars") or 0.0)
                adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "space_government_contract_profile": profiles.get(ticker),
                        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                        "space_peer_momentum_strength": signal.get("space_peer_momentum_strength"),
                        "space_peer_momentum_return": signal.get("space_peer_momentum_return"),
                        "space_peer_momentum_median": signal.get("space_peer_momentum_median"),
                        "government_contract_peer_nonleader_scalar": government_contract_peer_nonleader_scalar,
                        "shares_before": shares_before,
                        "shares_after": shares_after,
                        "dollars_before": dollars_before,
                        "dollars_after": dollars_after,
                        "technical_quality_score": signal.get("technical_quality_score"),
                        "confidence": signal.get("confidence"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_government_contract_peer_nonleader_eligible": True,
                    "space_government_contract_profile": profiles.get(ticker),
                }
            elif ticker in target_tickers:
                counts["target_but_not_nonleader"] += 1
            output.append(signal)
        return output

    portfolio_engine.size_signals = size_wrapper
    installed["government_contract_peer_nonleader_adjustments"] = adjustments
    installed["government_contract_peer_nonleader_counts"] = counts
    return installed


def _slice_summary(samples: list[dict[str, Any]], count: int, scalar: float) -> dict[str, Any]:
    summary = _adjustment_summary(samples)
    summary["scalar"] = scalar
    summary["eligible_signal_count_seen"] = count
    summary["strategy_counts"] = dict(
        sorted(Counter(str(sample.get("strategy") or "unknown") for sample in samples).items())
    )
    summary["peer_state_counts"] = dict(
        sorted(Counter(str(sample.get("space_peer_momentum_state") or "unknown") for sample in samples).items())
    )
    summary["target_ticker_counts"] = dict(
        sorted(Counter(str(sample.get("ticker") or "UNKNOWN").upper() for sample in samples).items())
    )
    return summary


def _run_variant(
    name: str,
    government_contract_peer_nonleader_scalar: float,
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        government_contract_peer_nonleader_scalar,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    try:
        by_window: dict[str, dict[str, Any]] = {}
        for label, window in WINDOWS.items():
            before_target = len(installed["government_contract_peer_nonleader_adjustments"])
            before_iwm_peer_leader_trend = len(installed.get("iwm_peer_leader_trend_adjustments", []))
            before_government = len(installed.get("government_contract_adjustments", []))
            before_source_peer = len(installed.get("source_peer_leader_adjustments", []))
            before_multi = len(installed.get("multi_event_depth_adjustments", []))
            before_watch = len(installed.get("watch_adjustments", []))
            before_company = len(installed.get("company_release_adjustments", []))
            before_financing = len(installed.get("financing_adjustments", []))
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            attribution = _space_trade_attribution(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": attribution,
                "space_government_contract_peer_nonleader_adjustment": _slice_summary(
                    installed["government_contract_peer_nonleader_adjustments"][before_target:],
                    installed["government_contract_peer_nonleader_counts"].get("eligible_signal", 0),
                    government_contract_peer_nonleader_scalar,
                ),
                "space_iwm_peer_leader_trend_adjustment": _adjustment_summary(
                    installed.get("iwm_peer_leader_trend_adjustments", [])[before_iwm_peer_leader_trend:]
                ),
                "space_government_contract_peer_leader_adjustment": _adjustment_summary(
                    installed.get("government_contract_adjustments", [])[before_government:]
                ),
                "space_customer_source_peer_leader_adjustment": _adjustment_summary(
                    installed.get("source_peer_leader_adjustments", [])[before_source_peer:]
                ),
                "space_multi_event_depth_adjustment": _adjustment_summary(
                    installed.get("multi_event_depth_adjustments", [])[before_multi:]
                ),
                "space_watch_liquidity_tier_adjustment": _adjustment_summary(
                    installed.get("watch_adjustments", [])[before_watch:]
                ),
                "space_company_release_source_adjustment": _adjustment_summary(
                    installed.get("company_release_adjustments", [])[before_company:]
                ),
                "space_financing_dilution_profile_adjustment": _adjustment_summary(
                    installed.get("financing_adjustments", [])[before_financing:]
                ),
            }
        metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
        return {
            "variant": name,
            "name": name,
            "space_government_contract_peer_nonleader_risk_scalar": government_contract_peer_nonleader_scalar,
            "parameters": {
                "space_government_contract_peer_nonleader_risk_scalar": government_contract_peer_nonleader_scalar,
                "accepted_space_iwm_peer_leader_trend_risk_scalar": ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
                "accepted_government_contract_peer_leader_risk_scalar": ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
            },
            "aggregate": _aggregate(metrics_by_window),
            "by_window": by_window,
        }
    finally:
        _restore_policy(*installed["originals"])


def _gate(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(after["aggregate"], before["aggregate"])
    window_checks = []
    for label, row in after["by_window"].items():
        baseline_row = before["by_window"][label]
        corrected_delta = _delta(row["metrics"], baseline_row["metrics"])
        window_checks.append(
            {
                "label": label,
                "expected_value_score_delta": _safe(corrected_delta.get("expected_value_score", 0.0)),
                "pnl_delta": _safe(corrected_delta.get("total_pnl", 0.0)),
                "max_drawdown_pct_delta": _safe(corrected_delta.get("max_drawdown_pct", 0.0)),
                "trade_count_delta": int(corrected_delta.get("trade_count", 0)),
                "pass": corrected_delta.get("expected_value_score", 0.0) >= -1e-9,
            }
        )
    adjusted_count = sum(
        int(
            (row.get("space_government_contract_peer_nonleader_adjustment") or {}).get(
                "adjusted_signal_count"
            )
            or 0
        )
        for row in after["by_window"].values()
    )
    improved_windows = sum(1 for check in window_checks if check["expected_value_score_delta"] > 1e-9)
    regressed_windows = sum(1 for check in window_checks if check["expected_value_score_delta"] < -1e-9)
    max_dd_delta = max(check["max_drawdown_pct_delta"] for check in window_checks)
    survival_rates = [float(row["metrics"].get("survival_rate") or 0.0) for row in after["by_window"].values()]
    trade_count = int(after["aggregate"].get("trade_count_sum") or 0)
    scalar = float(after["parameters"]["space_government_contract_peer_nonleader_risk_scalar"])
    passed = (
        adjusted_count > 0
        and scalar != 1.0
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and improved_windows >= 2
        and regressed_windows == 0
        and max_dd_delta <= 0.005
        and min(survival_rates or [0.0]) >= 0.05
        and trade_count >= 50
    )
    return {
        "passed": bool(passed),
        "aggregate_delta": aggregate_delta,
        "window_checks": window_checks,
        "adjusted_count": adjusted_count,
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "max_drawdown_pct_delta_ceiling": 0.005,
        "minimum_survival_rate": _safe(min(survival_rates or [0.0])),
        "total_trades": trade_count,
        "failure_reason": None
        if passed
        else (
            "requires nonzero adjusted count, scalar != 1.0, positive aggregate EV/PnL, "
            "at least 2/3 improved EV windows, no EV-regressed windows, max DD delta <= 0.5pp, "
            "survival >= 5%, total trades >= 50"
        ),
    }


def _sweep_summary(variants: list[dict[str, Any]], before: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        gate = _gate(before, variant)
        rows.append(
            {
                "name": variant["name"],
                "parameters": variant["parameters"],
                "aggregate": variant["aggregate"],
                "aggregate_delta": gate["aggregate_delta"],
                "passed": gate["passed"],
                "adjusted_count": gate["adjusted_count"],
                "improved_windows": gate["improved_windows"],
                "regressed_windows": gate["regressed_windows"],
            }
        )
    return rows


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4_after"]
    before = payload["gate1_baseline"]["accepted_exp020_space_stack"]["aggregate"]
    after = best["aggregate"]
    delta = gate["aggregate_delta"]
    rows = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Decision",
        "",
        f"- decision: `{payload['decision']}`",
        f"- hypothesis: {payload['gate_questions']['alpha_hypothesis']}",
        "- single changed variable: `space_government_contract_peer_nonleader_risk_scalar`",
        f"- best scalar: `{best['parameters']['space_government_contract_peer_nonleader_risk_scalar']}`",
        f"- adjusted count: `{gate['adjusted_count']}`",
        f"- EV delta: `{_safe(delta['expected_value_score_sum'])}`",
        f"- PnL delta: `{_safe(delta['total_pnl_sum'])}`",
        "",
        "## Aggregate",
        "",
        "| metric | before exp020 | after best | delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in (
        "expected_value_score_sum",
        "total_pnl_sum",
        "trade_count_sum",
        "signals_generated_sum",
        "signals_survived_sum",
        "min_survival_rate",
        "max_drawdown_pct_max",
    ):
        rows.append(
            f"| {metric} | `{_safe(before.get(metric))}` | `{_safe(after.get(metric))}` | `{_safe(delta.get(metric))}` |"
        )
    rows.extend(["", "## Window Checks", "", "| window | EV delta | PnL delta | max DD delta | pass |", "|---|---:|---:|---:|---|"])
    for check in gate["window_checks"]:
        rows.append(
            f"| {check['label']} | `{check['expected_value_score_delta']}` | `{check['pnl_delta']}` | `{check['max_drawdown_pct_delta']}` | `{check['pass']}` |"
        )
    rows.extend(["", "## Sweep", "", "| variant | scalar | EV delta | PnL delta | adjusted | passed |", "|---|---:|---:|---:|---:|---|"])
    for row in payload["sweep_summary"]:
        scalar = row["parameters"]["space_government_contract_peer_nonleader_risk_scalar"]
        rows.append(
            f"| {row['name']} | `{scalar}` | `{_safe(row['aggregate_delta']['expected_value_score_sum'])}` | `{_safe(row['aggregate_delta']['total_pnl_sum'])}` | `{row['adjusted_count']}` | `{row['passed']}` |"
        )
    return "\n".join(rows) + "\n"


def _ticket(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Closeout",
            "",
            f"hypothesis: {payload['gate_questions']['alpha_hypothesis']}",
            "change_type: alpha_search",
            "changed_variable: space_government_contract_peer_nonleader_risk_scalar",
            "backtest_protocol: docs/backtesting.md fixed three-window Space pilot sleeve replay, include-pilot-sleeve equivalent",
            f"baseline_metrics: {json.dumps(payload['gate1_baseline']['accepted_exp020_space_stack']['aggregate'], sort_keys=True)}",
            f"after_metrics: {json.dumps(payload['best_variant']['aggregate'], sort_keys=True)}",
            f"expected_value_score_delta: {payload['gate4_after']['aggregate_delta']['expected_value_score_sum']}",
            f"production_impact: {json.dumps(payload['production_impact'], sort_keys=True)}",
            "why_not_other_changes: LLM soft-ranking is data-limited; noisy ticker expansion was avoided; this tests one risk-allocation variable inside official-catalyst Space coverage.",
            "known_risks: Space remains default-off live with zero slots; historical replay windows predate live Space slots; decision depends on synthetic Space snapshot replay artifacts.",
            f"decision: {payload['decision']}",
            "",
        ]
    )


def _append_jsonl(payload: dict[str, Any]) -> None:
    existing = LOG_PATH.read_text(encoding="utf-8").splitlines() if LOG_PATH.exists() else []
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    filtered = [line for line in existing if marker not in line]
    record = {
        "timestamp": TIMESTAMP,
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["gate_questions"]["alpha_hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_government_contract_peer_nonleader_risk_scalar",
        "parameters": payload["best_variant"]["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["gate1_baseline"]["accepted_exp020_space_stack"]["aggregate"],
        "after_metrics": payload["best_variant"]["aggregate"],
        "expected_value_score_delta": payload["gate4_after"]["aggregate_delta"]["expected_value_score_sum"],
        "decision": payload["decision"],
        "rejection_reason": None if payload["decision"] == "accepted" else payload["gate4_after"]["failure_reason"],
        "next_evidence_needed": (
            "Implement shared policy and parity docs before any production-visible Space promotion."
            if payload["decision"] == "accepted"
            else "Do not retest government-contract nonleader scalar without new official-catalyst attribution or broader Space sample."
        ),
        "artifact": str(RESULT_JSON.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }
    LOG_PATH.write_text("\n".join(filtered + [json.dumps(record, sort_keys=True)]) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    open_position_gate = _gate2_open_positions()
    source_gate = _event_seed_profiles()
    government_contract_gate = _field_check_government_contract_profile()
    multi_event_gate = _field_check_multi_event_depth()
    liquidity_gate = _field_check_watch_liquidity_tier()
    company_release_gate = _field_check_company_release_source()
    financing_gate = _accepted_financing_profile_gate()

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
    iwm_peer_leader_gate = _field_check_iwm_peer_leader_trend(before)
    target_gate = _field_check_government_contract_peer_nonleader(before, government_contract_gate)
    field_checks = {
        "open_positions": open_position_gate,
        "government_contract_profile": government_contract_gate,
        "official_event_source_profiles": source_gate,
        "official_customer_source_peer_leader": peer_state_gate,
        "iwm_peer_leader_trend": iwm_peer_leader_gate,
        "multi_event_depth": multi_event_gate,
        "watch_liquidity_tier": liquidity_gate,
        "company_release_source": company_release_gate,
        "financing_dilution_profile": financing_gate,
        "government_contract_peer_nonleader": target_gate,
    }
    blockers = [
        name
        for name, check in field_checks.items()
        if isinstance(check, dict) and check.get("passed") is False
    ]
    if blockers:
        raise RuntimeError(f"Gate 2 failed for {blockers}")

    variants = [
        _run_variant(
            f"government_contract_peer_nonleader_scalar_{str(scalar).replace('.', '_')}",
            scalar,
            government_contract_gate,
            source_gate,
            multi_event_gate,
            liquidity_gate,
            company_release_gate,
            financing_gate,
        )
        for scalar in GOVERNMENT_CONTRACT_PEER_NONLEADER_RISK_SCALARS
    ]
    variants_ranked = sorted(
        variants,
        key=lambda variant: (
            _gate(before, variant)["passed"],
            _gate(before, variant)["aggregate_delta"]["expected_value_score_sum"],
            _gate(before, variant)["aggregate_delta"]["total_pnl_sum"],
        ),
        reverse=True,
    )
    best = variants_ranked[0]
    gate4 = _gate(before, best)
    core_baseline = _run_core_baseline()
    payload = {
        "timestamp": TIMESTAMP,
        "experiment_id": EXPERIMENT_ID,
        "gate_questions": {
            "alpha_hypothesis": (
                "If government/defense Space catalysts only deserve top-up when peer momentum leads, "
                "then government-contract profile signals that are peer nonleaders should get a small risk haircut "
                "to reduce broad-theme drawdown while preserving official-catalyst coverage."
            ),
            "category": "risk allocation",
            "prior_similar_experiments": [
                "exp-20260513-015 accepted government_contract peer-leader risk scalar 1.05",
                "exp-20260513-020 accepted IWM + peer-leader trend scalar 1.15",
                "exp-20260513-021 rejected satellite_connectivity theme risk scalar",
            ],
            "single_changed_variable": "space_government_contract_peer_nonleader_risk_scalar",
            "success_criteria": (
                "positive aggregate EV/PnL vs accepted exp020, at least 2/3 EV windows improved, "
                "no EV-regressed windows, max DD delta <= 0.5pp, survival >= 5%, >=50 trades, nonzero adjusted count"
            ),
            "reproducibility": f"Run quant/experiments/{Path(__file__).name}",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed windows: recent_regime_2024_2025, mid_weak_2022_2023, "
            "early_mixed_2020_2021; Space pilot sleeve shadow replay with augmented space_snapshot snapshots."
        ),
        "date_range": [{"label": label, **dict(window)} for label, window in WINDOWS.items()],
        "gate1_baseline": {
            "core_checkpoint": core_baseline,
            "accepted_exp020_space_stack": before,
        },
        "gate2_field_checks": field_checks,
        "gate3_survival_audit": {
            "before_survival_rate": before["aggregate"].get("survival_rate"),
            "minimum_allowed_survival_rate": 5.0,
            "new_filter_added": False,
            "note": "Risk scalar only; no new signal filter.",
        },
        "variants": variants,
        "sweep_summary": _sweep_summary(variants, before),
        "best_variant": best,
        "gate4_after": gate4,
        "llm_metrics": {
            "llm_change": False,
            "llm_soft_ranking_used": False,
            "reason": "User directed alpha search away from data-limited LLM soft-ranking when insufficient.",
        },
        "production_impact": {
            "shared_policy_changed": bool(gate4["passed"]),
            "backtester_adapter_changed": bool(gate4["passed"]),
            "run_adapter_changed": bool(gate4["passed"]),
            "replay_only": not bool(gate4["passed"]),
            "parity_test_added": False,
            "live_slots": 0,
            "space_sleeve_default": "shadow/default-off",
        },
        "decision": "accepted" if gate4["passed"] else "rejected",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(RESULT_JSON, payload)
    RESULT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    TICKET_MD.write_text(_ticket(payload), encoding="utf-8")
    _append_jsonl(payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "best_variant": result["best_variant"]["name"],
                "aggregate_delta": result["gate4_after"]["aggregate_delta"],
                "gate4_passed": result["gate4_after"]["passed"],
                "artifact": str(RESULT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
