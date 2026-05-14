"""exp-20260514-024: Space forward replacement IWM-leader trend risk.

Tests one causal variable on top of accepted exp-20260514-009: whether the
already accepted forward same-theme replacement-strength trend bucket deserves
an additional small top-up only when IWM 20d momentum leads SPY.

This stays inside the default-off Space sleeve. It does not change live slots,
candidate ranking, entries, exits, targets, LLM/news, or broad ticker breadth.
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
from data_layer import get_universe
import exp_20260513_038_space_source_diversity_risk as source_diversity_exp
import exp_20260514_002_space_forward_replacement_same_theme_strength_risk as same_theme_exp
import space_catalyst_sleeve


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-024"
STEM = "space_forward_replacement_iwm_leader_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-009"

ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR = 1.25
ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR = 1.075
ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR = 1.15
ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR = 1.05
ACCEPTED_SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALAR = 1.05
ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR = 1.05
ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR = 500.0
ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR = 1.05
ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR = 1.05

IWM_LEADER_TREND_RISK_SCALARS = (1.00, 1.025, 1.05, 1.075, 1.10)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
PEER_LEADER_STATE = "leader"
IWM_LEADER_STATE = "smallcap_leader"


def _neutralize_promoted_iwm_helper_for_replay_base() -> None:
    """Keep the replay baseline at the accepted exp-009 stack after promotion."""
    space_catalyst_sleeve.SPACE_CATALYST_FORWARD_REPLACEMENT_IWM_LEADER_TREND_RISK_SCALAR = (
        1.0
    )
    space_catalyst_sleeve.SPACE_CATALYST_FORWARD_HYPOTHESIS[
        "space_forward_replacement_iwm_leader_trend_risk_scalar"
    ] = 1.0


def _safe(payload: Any) -> Any:
    return source_diversity_exp._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source_diversity_exp._write_json(path, payload)


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> Any:
    number = _as_float(value)
    if number is None:
        return None
    return round(number, digits)


def _rounded_bucket(bucket: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, row in bucket.items():
        out[key] = {**row, "pnl": _round(row.get("pnl"), 2)}
    return out


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


def _scale_and_count(
    *,
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    marker: str,
    counts: Counter[str],
    ticker: str,
) -> tuple[int, int]:
    shares_before = int(sizing.get("shares_to_buy") or 0)
    source_diversity_exp._scale_sizing(sizing, scalar, portfolio_value, marker)
    shares_after = int(sizing.get("shares_to_buy") or 0)
    if shares_after != shares_before:
        counts[f"{marker}_changed_signal"] += 1
        counts[f"{marker}_changed_{ticker}"] += 1
    return shares_before, shares_after


def _space_trade_attribution_for(result: dict[str, Any], tickers: set[str]) -> dict[str, Any]:
    trades = [
        trade
        for trade in result.get("trades") or []
        if str(trade.get("ticker") or "").upper() in tickers
    ]
    by_ticker: dict[str, dict[str, Any]] = {}
    by_strategy: dict[str, dict[str, Any]] = {}
    by_exit_reason: dict[str, dict[str, Any]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        strategy = str(trade.get("strategy") or "unknown")
        exit_reason = str(trade.get("exit_reason") or "unknown")
        pnl = float(trade.get("pnl") or 0.0)
        for bucket, key in (
            (by_ticker, ticker),
            (by_strategy, strategy),
            (by_exit_reason, exit_reason),
        ):
            row = bucket.setdefault(
                key,
                {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
            )
            row["trade_count"] += 1
            row["wins"] += int(pnl > 0)
            row["losses"] += int(pnl <= 0)
            row["pnl"] += pnl
    positive = [row["pnl"] for row in by_ticker.values() if row["pnl"] > 0]
    total_positive = sum(positive)
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    return {
        "trade_count": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": _round(wins / len(trades), 4) if trades else None,
        "total_pnl": _round(
            sum(float(trade.get("pnl") or 0.0) for trade in trades),
            2,
        ),
        "single_ticker_positive_share": _round(
            max(positive) / total_positive if total_positive else 0.0,
            4,
        ),
        "by_ticker": _rounded_bucket(by_ticker),
        "by_strategy": _rounded_bucket(by_strategy),
        "by_exit_reason": _rounded_bucket(by_exit_reason),
    }


def _run_variant(
    label: str,
    *,
    iwm_leader_trend_scalar: float,
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
    _neutralize_promoted_iwm_helper_for_replay_base()
    universe = sorted(
        set(get_universe()) | set(source_diversity_exp.OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"}
    )
    installed = source_diversity_exp._install_space_policy(
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
    source_diverse_tickers = set(source_diversity_gate["target_tickers"])
    source_diversity_profiles = source_diversity_gate["profiles"]
    forward_tickers = set(forward_gate["base_target_tickers"])
    forward_profiles = forward_gate["profiles"]
    strength_tickers = same_theme_exp._target_tickers_for_floor(
        forward_gate,
        ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR,
    )

    adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def size_with_iwm_leader_trend_scalar(
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
                    ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR,
                    portfolio_value,
                    "space_source_diversity_risk",
                )
                is_peer_leader = signal.get("space_peer_momentum_state") == PEER_LEADER_STATE
                is_iwm_leader = signal.get("space_iwm_relative_state") == IWM_LEADER_STATE
                if is_peer_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_peer_leader_risk",
                    )
                if is_iwm_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_iwm_leader_risk",
                    )
                if is_peer_leader and is_iwm_leader:
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALAR,
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
                    ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_positive_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_positive_bucket": True,
                    "space_forward_replacement_positive_scalar": (
                        ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
                    ),
                    "space_forward_replacement_positive_profile": forward_profiles.get(ticker),
                }

            if ticker in strength_tickers and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_same_theme_strength_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_same_theme_strength_bucket": True,
                    "space_forward_replacement_same_theme_strength_scalar": (
                        ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
                    ),
                    "space_forward_replacement_same_theme_strength_floor": (
                        ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
                    ),
                }

            is_strength_trend = ticker in strength_tickers and strategy == "trend_long"
            if is_strength_trend and sizing:
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR,
                    portfolio_value,
                    "space_forward_replacement_trend_strength_risk",
                )
                signal = {
                    **signal,
                    "space_forward_replacement_trend_strength_bucket": True,
                    "space_forward_replacement_trend_strength_scalar": (
                        ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
                    ),
                }

            is_iwm_leader_trend = (
                is_strength_trend
                and signal.get("space_iwm_relative_state") == IWM_LEADER_STATE
            )
            if is_iwm_leader_trend and sizing:
                counts["eligible_signal"] += 1
                counts[f"eligible_{ticker}"] += 1
                shares_before, shares_after = _scale_and_count(
                    sizing=sizing,
                    scalar=iwm_leader_trend_scalar,
                    portfolio_value=portfolio_value,
                    marker="space_forward_replacement_iwm_leader_trend_risk",
                    counts=counts,
                    ticker=ticker,
                )
                profile = forward_profiles.get(ticker)
                adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "scalar": iwm_leader_trend_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": shares_after,
                        "forward_replacement_profile": profile,
                        "same_theme_floor": (
                            ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
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
                    "space_forward_replacement_iwm_leader_trend_bucket": True,
                    "space_forward_replacement_iwm_leader_trend_scalar": (
                        iwm_leader_trend_scalar
                    ),
                }

            if sizing:
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_with_iwm_leader_trend_scalar
    try:
        by_window: dict[str, Any] = {}
        for name, window in source_diversity_exp.WINDOWS.items():
            before_adjustments = len(adjustments)
            before_counts = Counter(counts)
            result = source_diversity_exp._run_window(window, universe, "space_snapshot")
            by_window[name] = {
                "metrics": source_diversity_exp._metrics(result),
                "official_space_trade_attribution": (
                    source_diversity_exp._space_trade_attribution(result)
                ),
                "iwm_leader_trend_trade_attribution": _space_trade_attribution_for(
                    result,
                    set(str(row.get("ticker") or "").upper() for row in adjustments[before_adjustments:]),
                ),
                "iwm_leader_trend_adjustment": source_diversity_exp._adjustment_summary(
                    adjustments[before_adjustments:]
                ),
                "iwm_leader_trend_counts": dict(sorted((counts - before_counts).items())),
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": label,
            "parameters": {
                "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
                "accepted_forward_replacement_positive_scalar": (
                    ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
                ),
                "accepted_forward_replacement_same_theme_strength_floor": (
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
                ),
                "accepted_forward_replacement_same_theme_strength_scalar": (
                    ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
                ),
                "accepted_forward_replacement_trend_strength_scalar": (
                    ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
                ),
                "shared_iwm_leader_trend_helper_neutralized_in_replay_base": True,
                "space_forward_replacement_iwm_leader_trend_scalar": (
                    iwm_leader_trend_scalar
                ),
                "target_tickers": sorted(
                    {
                        str(row.get("ticker") or "").upper()
                        for row in adjustments
                        if row.get("ticker")
                    }
                ),
                "base_forward_replacement_target_tickers": (
                    forward_gate["base_target_tickers"]
                ),
                "same_theme_strength_target_tickers": sorted(strength_tickers),
                "target_strategy": "trend_long",
                "target_iwm_state": IWM_LEADER_STATE,
            },
            "by_window": by_window,
            "aggregate": source_diversity_exp._aggregate(metrics_by_window),
            "iwm_leader_trend_adjustment_summary": (
                source_diversity_exp._adjustment_summary(adjustments)
            ),
            "iwm_leader_trend_counts": dict(sorted(counts.items())),
            "iwm_leader_trend_adjustment_sample": adjustments[:25],
        }
    finally:
        source_diversity_exp._restore_policy(*installed["originals"])


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        name: source_diversity_exp._delta(payload["metrics"], before["by_window"][name]["metrics"])
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
    changed_count = int(
        variant["iwm_leader_trend_counts"].get(
            "space_forward_replacement_iwm_leader_trend_risk_changed_signal",
            0,
        )
    )
    eligible_count = int(variant["iwm_leader_trend_counts"].get("eligible_signal", 0))
    scalar = float(
        variant["parameters"]["space_forward_replacement_iwm_leader_trend_scalar"]
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "eligible_iwm_leader_trend_signal_count": eligible_count,
        "changed_iwm_leader_trend_signal_count": changed_count,
        "accepted": bool(
            scalar != 1.0
            and changed_count > 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE
            and variant["aggregate"]["trade_count_sum"] >= MIN_TRADE_COUNT
        ),
    }


def _gate2_runtime_state(before: dict[str, Any]) -> dict[str, Any]:
    eligible = 0
    samples = []
    for window_name, payload in before.get("by_window", {}).items():
        counts = payload.get("iwm_leader_trend_counts") or {}
        eligible += int(counts.get("eligible_signal", 0) or 0)
        summary = payload.get("iwm_leader_trend_adjustment") or {}
        for row in summary.get("sample") or []:
            samples.append(
                {
                    "window": window_name,
                    "ticker": row.get("ticker"),
                    "strategy": row.get("strategy"),
                    "iwm_state": row.get("space_iwm_relative_state"),
                    "peer_state": row.get("space_peer_momentum_state"),
                    "same_theme_floor": row.get("same_theme_floor"),
                    "profile": row.get("forward_replacement_profile"),
                }
            )
    return {
        "passed": eligible > 0,
        "required_runtime_fields": [
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d.cash_relative_pnl",
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d.same_theme_replacement_value",
            "signal.strategy",
            "signal.space_iwm_relative_state",
            "sizing.shares_to_buy",
        ],
        "eligible_signal_count_at_neutral_before": eligible,
        "sample_rows": samples[:10],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space forward replacement IWM-leader trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_forward_replacement_iwm_leader_trend_scalar` for `trend_long` "
            "signals already in the accepted forward same-theme replacement-strength "
            "bucket and whose IWM relative momentum state is `smallcap_leader`. Candidate pool, "
            "ranking, targets, stops, LLM/news, accepted exp-009 stack, and live "
            "Space slots stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        (
            "- Best scalar: "
            f"`{best['parameters']['space_forward_replacement_iwm_leader_trend_scalar']}`"
        ),
        (
            "- Aggregate delta vs exp-009: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- IWM-leader trend signals changed: "
            f"`{gate['changed_iwm_leader_trend_signal_count']}` of "
            f"`{gate['eligible_iwm_leader_trend_signal_count']}` eligible"
        ),
        f"- Target tickers: `{', '.join(best['parameters']['target_tickers'])}`",
        "",
        "## Three-Window Deltas vs Exp-009",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        adjusted = best["by_window"][name]["iwm_leader_trend_adjustment"][
            "adjusted_signal_count"
        ]
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
            "## Gate Checks",
            f"- Gate 2 passed: `{payload['gate2_field_checks']['passed']}`",
            f"- Gate 3 survival passed: `{payload['gate3']['passed']}`",
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

    before = _run_variant(
        "accepted_exp009_iwm_leader_neutral",
        iwm_leader_trend_scalar=1.0,
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
    runtime_state_gate = _gate2_runtime_state(before)

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
        "iwm_leader_trend_runtime_state": runtime_state_gate,
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
            runtime_state_gate["passed"],
        ]
    )

    variants = [
        _run_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            iwm_leader_trend_scalar=scalar,
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
        for scalar in IWM_LEADER_TREND_RISK_SCALARS
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
            "No tested IWM-leader trend replacement-strength scalar improved "
            "aggregate EV/PnL across the three windows without a window-level EV "
            "regression, drawdown/survival violation, or zero-adjustment result."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "Space replacement-strength allocation may be strongest when forward "
            "same-theme cash evidence, trend continuation, and smallcap tape leadership "
            "agree. On top of accepted exp-20260514-009, a single extra IWM-leader "
            "trend scalar tests the playbook's catalyst/source/tape interaction direction "
            "without adding noisy tickers, broad filters, LLM authority, lifecycle "
            "rules, or live Space slots."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_forward_replacement_iwm_leader_trend_risk_scalar",
        "single_causal_variable": (
            "extra risk scalar for trend_long signals in the accepted forward "
            "same-theme replacement-strength bucket when space_iwm_relative_state "
            "is smallcap_leader"
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
                "risk allocation: add a small incremental scalar only to Space "
                "trend_long signals whose closed 10d forward profile passes the "
                "same-theme replacement-strength bucket and whose IWM 20d momentum "
                "leads SPY."
            ),
            "q2_prior_experiments": [
                "exp-20260513-039 accepted source-diversity peer-leader interaction at 1.15x.",
                "exp-20260513-110 accepted source-diversity peer+IWM interaction at 1.05x.",
                "exp-20260514-002 accepted same-theme replacement-strength risk at $500 / 1.05x.",
                "exp-20260514-009 accepted same-theme replacement-strength trend-only risk at 1.05x.",
                "exp-20260514-016 rejected same-theme replacement-strength trend plus peer-leader interaction.",
                "No prior record found for same-theme replacement-strength trend plus IWM-leader interaction.",
            ],
            "q3_single_causal_variable": (
                "Only the additional IWM-leader trend risk scalar changes; accepted "
                "exp-009 stack and all entries/exits/ranking/targets stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least two EV-improved windows, no EV-regressed window, "
                "max drawdown damage <= 0.5pp, survival >= 5%, >=50 aggregate trades, "
                "and real adjusted signals."
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
                "Space candidate snapshots are frozen historical replay copies; "
                "forward replacement profiles come from closed 2026 event-state "
                "ledger rows, so any helper remains default-off metadata and live "
                "Space slots stay zero."
            ),
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "accepted_forward_replacement_positive_scalar": (
                ACCEPTED_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
            ),
            "accepted_same_theme_strength_floor": (
                ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR
            ),
            "accepted_same_theme_strength_scalar": (
                ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
            ),
            "accepted_trend_strength_scalar": (
                ACCEPTED_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
            ),
            "tested_iwm_leader_trend_scalars": list(IWM_LEADER_TREND_RISK_SCALARS),
            "base_forward_replacement_target_tickers": forward_gate[
                "base_target_tickers"
            ],
            "same_theme_strength_target_tickers": same_theme_exp._target_tickers_for_floor(
                forward_gate,
                ACCEPTED_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_FLOOR,
            ),
            "target_strategy": "trend_long",
            "target_iwm_state": IWM_LEADER_STATE,
            "locked_variables": [
                "official Space candidate pool",
                "accepted exp-113 forward replacement-positive scalar",
                "accepted exp-20260514-002 same-theme strength scalar",
                "accepted exp-20260514-009 trend strength scalar",
                "accepted exp-110 source-diversity stack",
                "all prior accepted Space risk helpers",
                "Space trend targets",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "status": (
            "accepted_default_off_space_forward_replacement_iwm_leader_trend_risk"
            if decision == "accepted"
            else "rejected_space_forward_replacement_iwm_leader_trend_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only as shared default-off Space metadata/helper; keep live "
            "Space slots at zero until forward replacement evidence broadens."
            if decision == "accepted"
            else (
                "Do not promote IWM-leader trend replacement-strength risk from "
                "this frozen replay. Use more closed forward rows or a different "
                "catalyst-quality axis."
            )
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
            "LLM soft-ranking remains label-thin; VSAT and broad satcom expansion "
            "failed the three-window gate; 5d confirmation and negative-profile "
            "forward variants were rejected. This keeps the candidate pool fixed "
            "and tests a stronger replacement-value plus smallcap tape interaction."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and historical Space snapshots are frozen research copies.",
            "Forward replacement profiles are closed 2026 outcomes and should not be treated as proof for live routing.",
            "The interaction is same-sample and should stay conservative even if accepted.",
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
        "best_scalar": result["best_variant"]["parameters"][
            "space_forward_replacement_iwm_leader_trend_scalar"
        ],
        "target_tickers": result["best_variant"]["parameters"]["target_tickers"],
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "by_window_delta_vs_before": result["best_variant_gate"][
            "by_window_delta_vs_before"
        ],
        "changed_iwm_leader_trend_signal_count": result["best_variant_gate"][
            "changed_iwm_leader_trend_signal_count"
        ],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))


