"""exp-20260514-031: Space delayed-absorption all-trend scope.

Tests one causal variable on top of the accepted exp-20260514-030 Space stack:
whether the delayed-absorption helper should apply to every official Space
`trend_long` signal with weak 5d but strong 10d replacement evidence, rather
than only the source-diverse trend subset that actually moved in exp030.

The experiment keeps the candidate pool, entries, exits, target widths, ranking,
LLM/news authority, live Space slots, and the 1.025x scalar fixed.
"""

from __future__ import annotations

import json
import logging
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
import exp_20260513_038_space_source_diversity_risk as source_diversity_exp
import exp_20260514_002_space_forward_replacement_same_theme_strength_risk as same_theme_exp
import exp_20260514_028_space_source_diversity_trend_risk as source_trend_exp
import exp_20260514_030_space_delayed_absorption_trend_risk as delayed_exp
from data_layer import get_universe


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-031"
STEM = "space_delayed_absorption_all_trend_scope"
BEFORE_EXPERIMENT_ID = "exp-20260514-030"

ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR = 1.025
ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR = 1.025
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


def _run_exp030_before(
    *,
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
    return delayed_exp._run_delayed_variant(
        "accepted_exp030_before",
        delayed_absorption_scalar=ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR,
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


def _run_all_trend_scope_variant(
    *,
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
    source_trend_exp.iwm_trend_exp._neutralize_promoted_iwm_helper_for_replay_base()
    source_trend_exp.company_exp._neutralize_promoted_company_source_helper_for_replay_base()
    universe = sorted(
        set(get_universe())
        | set(source_diversity_exp.OFFICIAL_SPACE_TICKERS)
        | {"IWM", "SPY"}
    )
    installed = source_diversity_exp._install_space_policy(
        source_trend_exp.ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
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
    source_diverse_tickers = set(
        source_trend_exp._target_tickers_for_source_diversity_trend(
            source_diversity_gate
        )
    )
    source_diversity_profiles = source_diversity_gate["profiles"]
    forward_tickers = set(forward_gate["base_target_tickers"])
    forward_profiles = forward_gate["profiles"]
    strength_tickers = set(
        same_theme_exp._target_tickers_for_floor(
            forward_gate,
            source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR,
        )
    )
    company_source_tickers = set(company_release_gate["target_tickers"])
    company_source_profiles = company_release_gate["profiles"]
    delayed_tickers = set(delayed_gate["target_tickers"])
    delayed_profiles = delayed_gate["profiles"]

    source_diversity_adjustments: list[dict[str, Any]] = []
    delayed_adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def size_with_all_trend_delayed_scope(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        out: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            sizing = deepcopy(signal.get("sizing") or {})

            if ticker in source_diverse_tickers and sizing:
                profile = source_diversity_profiles.get(ticker)
                source_diversity_exp._scale_sizing(
                    sizing,
                    source_trend_exp.ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR,
                    portfolio_value,
                    "space_source_diversity_risk",
                )
                is_peer_leader = signal.get("space_peer_momentum_state") == source_trend_exp.PEER_LEADER_STATE
                is_iwm_leader = signal.get("space_iwm_relative_state") == source_trend_exp.IWM_LEADER_STATE
                if is_peer_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        source_trend_exp.ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_peer_leader_risk",
                    )
                if is_iwm_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        source_trend_exp.ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_iwm_leader_risk",
                    )
                if is_peer_leader and is_iwm_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        source_trend_exp.ACCEPTED_SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_peer_iwm_leader_risk",
                    )
                signal = {
                    **signal,
                    "space_source_diversity_eligible": True,
                    "space_source_diversity_profile": profile,
                }

            if ticker in forward_tickers and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_positive_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_positive_bucket": True,
                    "space_forward_replacement_positive_scalar": (
                        source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
                    ),
                    "space_forward_replacement_positive_profile": forward_profiles.get(ticker),
                }

            if ticker in strength_tickers and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_same_theme_strength_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_same_theme_strength_bucket": True,
                    "space_forward_replacement_same_theme_strength_scalar": (
                        source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
                    ),
                    "space_forward_replacement_same_theme_strength_floor": (
                        source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
                    ),
                }

            is_strength_trend = ticker in strength_tickers and strategy == TARGET_STRATEGY
            if is_strength_trend and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_trend_strength_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_trend_strength_bucket": True,
                    "space_forward_replacement_trend_strength_scalar": (
                        source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
                    ),
                }

            is_iwm_leader_trend = (
                is_strength_trend
                and signal.get("space_iwm_relative_state") == source_trend_exp.IWM_LEADER_STATE
            )
            if is_iwm_leader_trend and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_IWM_LEADER_TREND_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_iwm_leader_trend_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_iwm_leader_trend_bucket": True,
                    "space_forward_replacement_iwm_leader_trend_scalar": (
                        source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_IWM_LEADER_TREND_RISK_SCALAR
                    ),
                }

            is_company_source_trend = (
                is_strength_trend
                and ticker in company_source_tickers
                and company_source_profiles.get(ticker)
            )
            if is_company_source_trend and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_COMPANY_SOURCE_TREND_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_company_source_trend_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_company_source_trend_bucket": True,
                    "space_forward_replacement_company_source_trend_scalar": (
                        source_trend_exp.ACCEPTED_FORWARD_REPLACEMENT_COMPANY_SOURCE_TREND_RISK_SCALAR
                    ),
                    "space_company_release_source_profile": company_source_profiles.get(ticker),
                }

            is_source_diversity_trend = (
                ticker in source_diverse_tickers and strategy == TARGET_STRATEGY
            )
            if is_source_diversity_trend and sizing:
                source_trend_exp._scale_and_record(
                    signal=signal,
                    sizing=sizing,
                    scalar=ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR,
                    portfolio_value=portfolio_value,
                    marker="space_source_diversity_trend_risk",
                    counts=counts,
                    adjustments=source_diversity_adjustments,
                    profile=source_diversity_profiles.get(ticker),
                )
                signal = {
                    **signal,
                    "space_source_diversity_trend_bucket": True,
                    "space_source_diversity_trend_scalar": (
                        ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR
                    ),
                }

            is_delayed_all_trend = ticker in delayed_tickers and strategy == TARGET_STRATEGY
            if is_delayed_all_trend and sizing:
                shares_before = int(sizing.get("shares_to_buy") or 0)
                dollars_before = float(sizing.get("position_size_dollars") or 0.0)
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR,
                    portfolio_value,
                    "space_delayed_absorption_all_trend_scope",
                )
                shares_after = int(sizing.get("shares_to_buy") or 0)
                dollars_after = float(sizing.get("position_size_dollars") or 0.0)
                is_new_scope = ticker not in source_diverse_tickers
                counts["delayed_absorption_all_scope_eligible_signal"] += 1
                counts[f"delayed_absorption_all_scope_eligible_{ticker}"] += 1
                if is_new_scope:
                    counts["delayed_absorption_new_scope_eligible_signal"] += 1
                    counts[f"delayed_absorption_new_scope_eligible_{ticker}"] += 1
                if shares_after != shares_before:
                    counts["space_delayed_absorption_all_scope_changed_signal"] += 1
                    counts[f"space_delayed_absorption_all_scope_changed_{ticker}"] += 1
                    if is_new_scope:
                        counts["space_delayed_absorption_new_scope_changed_signal"] += 1
                        counts[f"space_delayed_absorption_new_scope_changed_{ticker}"] += 1
                delayed_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "marker": "space_delayed_absorption_all_trend_scope",
                        "scalar": ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR,
                        "new_scope_vs_exp030": is_new_scope,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": shares_after,
                        "dollars_before_scalar": dollars_before,
                        "dollars_after_scalar": dollars_after,
                        "delayed_absorption_profile": delayed_profiles.get(ticker),
                        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "space_delayed_absorption_all_trend_bucket": True,
                    "space_delayed_absorption_all_trend_scalar": (
                        ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR
                    ),
                    "space_delayed_absorption_profile": delayed_profiles.get(ticker),
                }

            if sizing:
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_with_all_trend_delayed_scope
    try:
        by_window: dict[str, Any] = {}
        for name, window in source_diversity_exp.WINDOWS.items():
            before_source = len(source_diversity_adjustments)
            before_delayed = len(delayed_adjustments)
            before_counts = Counter(counts)
            result = source_diversity_exp._run_window(window, universe, "space_snapshot")
            window_source = source_diversity_adjustments[before_source:]
            window_delayed = delayed_adjustments[before_delayed:]
            by_window[name] = {
                "metrics": source_diversity_exp._metrics(result),
                "official_space_trade_attribution": (
                    source_diversity_exp._space_trade_attribution(result)
                ),
                "source_diversity_trend_adjustment": (
                    source_diversity_exp._adjustment_summary(window_source)
                ),
                "delayed_absorption_all_scope_adjustment": (
                    source_diversity_exp._adjustment_summary(window_delayed)
                ),
                "delayed_absorption_new_scope_adjustment": (
                    source_diversity_exp._adjustment_summary(
                        [row for row in window_delayed if row["new_scope_vs_exp030"]]
                    )
                ),
                "delayed_absorption_all_scope_counts": dict(
                    sorted((counts - before_counts).items())
                ),
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": STEM,
            "parameters": {
                "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
                "accepted_source_diversity_trend_scalar": (
                    ACCEPTED_SOURCE_DIVERSITY_TREND_RISK_SCALAR
                ),
                "accepted_delayed_absorption_trend_scalar": (
                    ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR
                ),
                "target_strategy": TARGET_STRATEGY,
                "delayed_absorption_target_tickers": sorted(delayed_tickers),
                "source_diversity_target_tickers": sorted(source_diverse_tickers),
                "new_scope_target_tickers": sorted(delayed_tickers - source_diverse_tickers),
                "scope_change": "apply delayed absorption to all delayed trend profiles",
            },
            "by_window": by_window,
            "aggregate": source_diversity_exp._aggregate(metrics_by_window),
            "source_diversity_trend_adjustment_summary": (
                source_diversity_exp._adjustment_summary(source_diversity_adjustments)
            ),
            "delayed_absorption_all_scope_adjustment_summary": (
                source_diversity_exp._adjustment_summary(delayed_adjustments)
            ),
            "delayed_absorption_new_scope_adjustment_summary": (
                source_diversity_exp._adjustment_summary(
                    [row for row in delayed_adjustments if row["new_scope_vs_exp030"]]
                )
            ),
            "delayed_absorption_all_scope_counts": dict(sorted(counts.items())),
            "delayed_absorption_all_scope_adjustment_sample": delayed_adjustments[:25],
        }
    finally:
        source_diversity_exp._restore_policy(*installed["originals"])


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
    counts = variant.get("delayed_absorption_all_scope_counts") or {}
    changed_count = int(
        counts.get("space_delayed_absorption_new_scope_changed_signal", 0)
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "changed_new_scope_signal_count": changed_count,
        "eligible_new_scope_signal_count": int(
            counts.get("delayed_absorption_new_scope_eligible_signal", 0)
        ),
        "accepted": bool(
            changed_count > 0
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


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["best_variant_gate"]
    variant = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space delayed-absorption all-trend scope",
        "",
        f"Decision: `{payload['status']}`.",
        "",
        "Single variable: broaden the delayed-absorption `trend_long` scope from "
        "the exp030 source-diverse moved subset to every delayed-profile Space "
        "`trend_long` candidate. The scalar remains 1.025x; entries, exits, "
        "ranking, targets, LLM/news, ticker breadth, and live slots stay fixed.",
        "",
        "## Three-Window Delta vs Exp030",
        "| window | EV delta | PnL delta | max DD delta | survival | new-scope adjusted |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = variant["by_window"][name]["metrics"]
        counts = variant["by_window"][name]["delayed_absorption_all_scope_counts"]
        adjusted = counts.get("space_delayed_absorption_new_scope_changed_signal", 0)
        lines.append(
            "| {name} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {survival:.6f} | {adjusted} |".format(
                name=name,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                survival=metrics["survival_rate"],
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            f"Aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`.",
            f"Aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`.",
            f"New-scope changed signals: `{gate['changed_new_scope_signal_count']}`.",
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
    delayed_gate = delayed_exp._delayed_absorption_profile_gate(forward_gate)

    before = _run_exp030_before(
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
    variant = _run_all_trend_scope_variant(
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
    variant["gate"] = _gate_variant(variant, before)

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
        "new_scope_runtime_state": {
            "passed": variant["gate"]["eligible_new_scope_signal_count"] > 0,
            "eligible_signal_count": variant["gate"][
                "eligible_new_scope_signal_count"
            ],
            "required_runtime_fields": [
                "space_catalyst_event_state_shadow_ledger horizons.5d",
                "space_catalyst_event_state_shadow_ledger horizons.10d",
                "signal.strategy",
                "signal.sizing.shares_to_buy",
            ],
        },
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
            gate2["new_scope_runtime_state"]["passed"],
        ]
    )

    decision = "accepted" if variant["gate"]["accepted"] else "rejected"
    status = (
        "accepted_default_off_space_delayed_absorption_all_trend_scope"
        if decision == "accepted"
        else "rejected_space_delayed_absorption_all_trend_scope"
    )
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "The all-trend delayed-absorption scope did not clear Gate 4 versus "
            "the accepted exp030 stack. It was positive only where the newly "
            "touched non-source-diverse delayed profile appeared, so the evidence "
            "is not broad enough for another promoted helper."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "The strongest current Space direction is closed forward replacement "
            "cohorts. If delayed absorption is a real semantic alpha, it should "
            "generalize beyond source-diverse trend signals to every official "
            "Space trend profile with weak 5d but strong 10d replacement value."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_delayed_absorption_scope",
        "single_causal_variable": (
            "scope of the accepted delayed-absorption trend helper; scalar fixed "
            "at 1.025x"
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
                "risk allocation: broaden delayed-absorption trend scope from "
                "source-diverse moved signals to all official delayed-profile "
                "Space trend signals."
            ),
            "q2_prior_experiments": [
                "exp-20260514-030 accepted 1.025x delayed absorption, but only the source-diverse RKLB slice moved.",
                "exp-20260514-011 rejected positive 5d confirmation, making delayed absorption the stronger horizon-shape branch.",
                "VSAT/IRDM candidate-pool expansion failed drawdown gates, so this keeps ticker breadth fixed.",
            ],
            "q3_single_causal_variable": (
                "Only the delayed-absorption helper scope changes; scalar, entries, "
                "exits, ranking, targets, and live slots are fixed."
            ),
            "q4_acceptance_standard": (
                "Same three Space windows; require positive aggregate EV/PnL, at "
                "least two EV-improved windows, no EV-regressed windows, max DD "
                "damage <= 0.5pp, survival >= 5%, >=50 trades, and nonzero "
                "new-scope adjusted signals."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": False,
            "scope_change": True,
            "min_survival_rate_after": variant["aggregate"]["min_survival_rate"],
            "passed": variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "accepted_delayed_absorption_scalar": (
                ACCEPTED_DELAYED_ABSORPTION_TREND_RISK_SCALAR
            ),
            "delayed_absorption_target_tickers": delayed_gate["target_tickers"],
            "new_scope_target_tickers": variant["parameters"]["new_scope_target_tickers"],
            "locked_variables": [
                "official Space candidate pool",
                "all accepted Space scalars through exp030",
                "entry filters",
                "candidate ranking",
                "targets/stops",
                "MAX_POSITIONS",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "core_baseline": core,
        "before": before,
        "best_variant": variant,
        "best_variant_gate": variant["gate"],
        "decision": decision,
        "status": status,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only with multi-window evidence from new closed Space forward rows; "
            "do not broaden delayed absorption from this frozen sample alone."
            if decision == "rejected"
            else "Keep live Space slots at zero; use shared metadata only."
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
            "LLM soft-ranking remains label-thin. Candidate expansion through "
            "VSAT/IRDM failed drawdown/survival gates. This tests the current "
            "highest-value Space mechanism, closed forward replacement cohorts, "
            "without adding noisy ticker breadth."
        ),
        "known_risks": [
            "Space remains default-off; this does not authorize live Space slots.",
            "The new scope mostly tests non-source-diverse delayed profiles, a small sample.",
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
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "by_window_delta_vs_before": result["best_variant_gate"][
            "by_window_delta_vs_before"
        ],
        "changed_new_scope_signal_count": result["best_variant_gate"][
            "changed_new_scope_signal_count"
        ],
        "new_scope_target_tickers": result["best_variant"]["parameters"][
            "new_scope_target_tickers"
        ],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
