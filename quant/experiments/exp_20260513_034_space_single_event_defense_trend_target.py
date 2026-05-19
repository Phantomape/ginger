"""exp-20260513-034: Space single-event defense trend target width.

Tests one exit/lifecycle variable on top of the accepted exp-20260513-032
default-off Space stack: a wider target ATR floor for official Space trend_long
signals whose event-seed profile is a single official defense-budget catalyst.
This uses the current forward clue that defense-budget events have poor 1d but
stronger 10d follow-through, without retuning the accepted defense risk scalar.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = PROJECT_ROOT / "quant" / "experiments"
QUANT_DIR = PROJECT_ROOT / "quant"
for path in (str(EXPERIMENTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data_layer import get_universe  # noqa: E402
import risk_engine  # noqa: E402
from risk_engine import _retarget_signal_with_atr_mult  # noqa: E402

from exp_20260513_032_space_attention_overlay_risk import (  # noqa: E402
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
    ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
    ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
    ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
    ATTENTION_SEMANTIC_BUCKET,
    EXPERIMENT_ID as BEFORE_EXPERIMENT_ID,
    MULTI_EVENT_MIN_COUNT,
    OFFICIAL_NON_ATTENTION_SOURCE_TYPES,
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
    _space_trade_attribution,
    _write_json,
)


EXPERIMENT_ID = "exp-20260513-034"
STEM = "space_single_event_defense_trend_target"
ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR = 1.25
TARGET_ATR_FLOORS = (5.0, 6.0, 7.0, 8.0)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005


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
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _round(value: Any, digits: int = 6) -> Any:
    numeric = _as_float(value)
    return round(numeric, digits) if numeric is not None else None


def _target_adjustment_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, int] = {}
    by_previous_mult: dict[str, int] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "")
        previous = str(row.get("previous_target_mult"))
        by_ticker[ticker] = by_ticker.get(ticker, 0) + 1
        by_previous_mult[previous] = by_previous_mult.get(previous, 0) + 1
    return {
        "adjusted_signal_count": len(rows),
        "by_ticker": dict(sorted(by_ticker.items())),
        "by_previous_target_mult": dict(sorted(by_previous_mult.items())),
        "sample_adjusted": rows[:12],
    }


def _install_target_policy(
    target_floor: float,
    attention_gate: dict[str, Any],
    single_event_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    installed = _install_space_policy(
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
    original_enrich = risk_engine.enrich_signals
    target_tickers = {str(ticker).upper() for ticker in single_event_gate["target_tickers"]}
    adjustments: list[dict[str, Any]] = []

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            if ticker not in target_tickers or strategy != "trend_long":
                continue
            atr = _as_float((features_dict.get(ticker) or {}).get("atr"))
            if atr is None or atr <= 0:
                continue
            previous_mult = _as_float(signal.get("target_mult_used"))
            if previous_mult is None:
                previous_mult = _as_float(atr_target_mult) or 0.0
            applied_mult = max(previous_mult, target_floor)
            if applied_mult <= previous_mult:
                continue
            previous_target = signal.get("target_price")
            retargeted = _retarget_signal_with_atr_mult(signal, atr, applied_mult)
            retargeted["space_single_event_defense_trend_target_floor_applied"] = (
                target_floor
            )
            retargeted["space_single_event_defense_trend_target_previous_mult"] = (
                previous_mult
            )
            retargeted["space_single_event_defense_trend_target_previous_price"] = (
                previous_target
            )
            signal.clear()
            signal.update(retargeted)
            adjustments.append(
                {
                    "ticker": ticker,
                    "strategy": strategy,
                    "target_floor": target_floor,
                    "applied_target_mult": _round(applied_mult, 4),
                    "previous_target_mult": _round(previous_mult, 4),
                    "previous_target_price": _round(previous_target, 4),
                    "target_price": _round(signal.get("target_price"), 4),
                    "atr": _round(atr, 4),
                    "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
                    "confidence_score": _round(signal.get("confidence_score"), 4),
                    "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                    "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                }
            )
        return enriched

    risk_engine.enrich_signals = enrich_wrapper
    installed["target_original_enrich"] = original_enrich
    installed["target_adjustments"] = adjustments
    return installed


def _restore_target_policy(installed: dict[str, Any]) -> None:
    risk_engine.enrich_signals = installed["target_original_enrich"]
    _restore_policy(*installed["originals"])


def _run_target_variant(
    name: str,
    target_floor: float,
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
    installed = _install_target_policy(
        target_floor,
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
            before_target = len(installed["target_adjustments"])
            result = _run_window(window, universe, "space_snapshot")
            window_adjustments = installed["target_adjustments"][before_target:]
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_single_event_defense_trend_target_adjustment": (
                    _target_adjustment_summary(window_adjustments)
                ),
            }
    finally:
        _restore_target_policy(installed)

    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "target_definition": (
            "official Space single-event defense-budget trend_long signals get "
            "target ATR multiple floored at the tested value"
        ),
        "target_tickers": single_event_gate["target_tickers"],
        "space_single_event_defense_trend_target_atr_floor": target_floor,
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
        row["space_single_event_defense_trend_target_adjustment"]["adjusted_signal_count"]
        for row in variant["by_window"].values()
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
        and adjusted_count > 0
        and variant["space_single_event_defense_trend_target_atr_floor"] != 5.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_single_event_defense_trend_target_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space single-event defense trend target",
        "",
        f"- decision: `{payload['decision']}`",
        f"- best variant: `{best['variant']}`",
        f"- aggregate EV delta: `{payload['expected_value_score_delta']:+.4f}`",
        f"- aggregate PnL delta: `${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Target adjustments |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_single_event_defense_trend_target_adjustment"
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
            json.dumps(payload["gate2"], sort_keys=True),
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
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": payload["best_variant"]["variant"],
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
    financing_gate = _accepted_financing_profile_gate()
    company_release_gate = _field_check_company_release_source()
    liquidity_gate = _field_check_watch_liquidity_tier()
    multi_event_gate = _field_check_multi_event_depth()
    government_contract_gate = _field_check_government_contract_profile()
    single_event_gate = _field_check_single_event_defense_profile()
    attention_gate = _field_check_attention_overlay_profile()
    required_gates = {
        "official_customer_source_profile": source_gate,
        "accepted_financing_dilution_profiles": financing_gate,
        "accepted_company_release_source_profile": company_release_gate,
        "watch_liquidity_tier_registry": liquidity_gate,
        "accepted_multi_event_depth": multi_event_gate,
        "government_contract_profile": government_contract_gate,
        "single_event_defense_profile": single_event_gate,
        "attention_overlay_profile": attention_gate,
    }
    failed = {key: value for key, value in required_gates.items() if not value["passed"]}
    if failed:
        raise RuntimeError(f"Gate 2 field checks failed: {failed}")

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
    iwm_peer_leader_gate = _field_check_iwm_peer_leader_trend(before)
    if not peer_state_gate["passed"] or not iwm_peer_leader_gate["passed"]:
        raise RuntimeError(
            "Gate 2 accepted peer/IWM fields failed: "
            f"{peer_state_gate} {iwm_peer_leader_gate}"
        )

    variants = {}
    for floor in TARGET_ATR_FLOORS:
        name = f"target_floor_{str(floor).replace('.', '_')}atr"
        variants[name] = _run_target_variant(
            name,
            floor,
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
        "accepted_default_off_space_single_event_defense_trend_target"
        if accepted
        else "rejected_space_single_event_defense_trend_target"
    )
    interpretation = (
        "The single-event defense trend target floor cleared the three-window gate "
        "on top of exp-032 and would require a shared default-off target helper plus "
        "production/backtest parity tests before promotion."
        if accepted
        else (
            "The single-event defense trend target floor did not clear the "
            "three-window gate on top of exp-032. Forward evidence still points to "
            "defense-event lifecycle as interesting, but this frozen-snapshot exit "
            "geometry is not strong enough to promote."
        )
    )

    target_input_variant = next(
        (
            variant
            for variant in variants.values()
            if variant["space_single_event_defense_trend_target_atr_floor"] != 5.0
            and sum(
                row["space_single_event_defense_trend_target_adjustment"][
                    "adjusted_signal_count"
                ]
                for row in variant["by_window"].values()
            )
            > 0
        ),
        best_variant,
    )
    target_input_counts = {
        label: row["space_single_event_defense_trend_target_adjustment"][
            "adjusted_signal_count"
        ]
        for label, row in target_input_variant["by_window"].items()
    }
    target_input_samples = []
    for row in target_input_variant["by_window"].values():
        target_input_samples.extend(
            row["space_single_event_defense_trend_target_adjustment"]["sample_adjusted"]
        )
    target_input_gate = {
        "passed": sum(target_input_counts.values()) > 0,
        "fields": [
            "signal.ticker",
            "signal.strategy",
            "signal.target_price",
            "signal.target_mult_used",
            "features_by_ticker[ticker].atr",
            "data/space_catalyst_event_seeds.jsonl event_fields",
            "data/space_catalyst_event_seeds.jsonl semantic_bucket",
            "data/space_catalyst_event_seeds.jsonl source_type",
        ],
        "target_adjustment_counts_by_window": target_input_counts,
        "sample_runtime_values": target_input_samples[:12],
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "exit_target_shadow_sweep",
        "changed_variable": "space_single_event_defense_trend_target_atr_floor",
        "single_causal_variable": (
            "target ATR floor for official Space trend_long signals whose "
            "event-seed profile is a single official defense-budget catalyst"
        ),
        "hypothesis": (
            "Forward event-state evidence shows defense_budget_theme has weak 1d "
            "but stronger 10d follow-through. A wider target on the existing "
            "single-event defense trend subset may capture that lifecycle without "
            "adding candidate tickers or retuning the accepted risk scalar."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/lifecycle: widen target only for single-event official "
                "defense-budget Space trend_long signals."
            ),
            "2_history_check": {
                "exp-20260513-028": (
                    "Accepted 1.05x risk scalar for single-event defense-only. "
                    "This run changes target geometry, not that scalar."
                ),
                "exp-20260513-026": (
                    "Rejected IWM+peer-leader trend target width; this run tests "
                    "a different catalyst-family lifecycle."
                ),
                "exp-20260513-032": (
                    "Accepted attention-overlay risk and is the fixed before stack."
                ),
            },
            "3_single_causal_variable": (
                "space_single_event_defense_trend_target_atr_floor. Candidate pool, "
                "accepted Space risk scalars, ranking, filters, add-ons, LLM/news, "
                "and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp-032 accepted stack, at least 2/3 improved EV "
                "windows, no EV-regressed window, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, >=50 total trades, nonzero target adjustments, "
                "and non-5.0 target floor."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_034_space_single_event_defense_trend_target.py"
            ),
        },
        "parameters": {
            "target_tickers": single_event_gate["target_tickers"],
            "tested_target_atr_floors": list(TARGET_ATR_FLOORS),
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_attention_overlay_risk_scalar": ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
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
            "attention_semantic_bucket": ATTENTION_SEMANTIC_BUCKET,
            "official_non_attention_source_types": list(OFFICIAL_NON_ATTENTION_SOURCE_TYPES),
            "locked_variables": [
                "official Space candidate pool",
                "all accepted exp-032 Space risk scalars",
                "accepted broad official Space trend target",
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
            "The before variant reproduces exp-20260513-032 accepted policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. The target subset is "
                "production-visible event-seed metadata, but accepted target changes "
                "must be implemented in a shared policy before use."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            **required_gates,
            "peer_momentum_state": peer_state_gate,
            "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
            "target_inputs": target_input_gate,
            "passed": (
                gate2_open["passed"]
                and all(value["passed"] for value in required_gates.values())
                and peer_state_gate["passed"]
                and iwm_peer_leader_gate["passed"]
                and target_input_gate["passed"]
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "new_exit_target_rule_tested": True,
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
                "production-visible event-seed profile metadata."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": True,
            "daily_report_metadata_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exit_targets": accepted,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not widen target geometry for single-event defense "
            "signals on these snapshots. Continue collecting forward target-touch "
            "and 10d replacement-value evidence by defense-event ticker/peer state."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_034_space_single_event_defense_trend_target.py",
            "data/experiments/exp-20260513-034/space_single_event_defense_trend_target.json",
            "experiments/logs/exp-20260513-034.json",
            "experiments/tickets/exp-20260513-034.json",
            "experiments/artifacts/exp-20260513-034_space_single_event_defense_trend_target.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is label-limited; mature satcom, GSAT, static ticker "
            "breadth, broad defense-budget scalars, source-authority scalars, "
            "government/customer peer-nonleader scalars, peer-leader breakout risk, "
            "satellite-connectivity theme risk, and adjacent IWM peer trend target "
            "width were already rejected, accepted, or underpowered. This run tests "
            "a distinct exit/lifecycle variable within an accepted catalyst family."
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
