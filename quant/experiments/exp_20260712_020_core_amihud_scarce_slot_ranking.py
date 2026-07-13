"""exp-20260712-020: Amihud price-impact scarce-slot ranking scout.

Private full replay.  When more current core candidates survive than there are
available slots, reorder only the stock candidates by ascending 20-session
Amihud illiquidity.  ETFs retain their baseline list positions.  Eligibility,
slot count, sizing, exits, costs, and production behavior remain unchanged.
"""

from __future__ import annotations

import contextlib
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for path in (QUANT, EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260712_019_prior_month_max_residual_entry_gate as prior  # noqa: E402


replay = prior.replay
feature_layer = prior.feature_layer
risk_engine = prior.risk_engine

EXPERIMENT_ID = "exp-20260712-020"
OWNER = "alpha-explore"
SLUG = "core_amihud_scarce_slot_ranking"
RUNNER = f"quant/experiments/exp_20260712_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = EXP_DIR / f"exp_20260712_020_{SLUG}.json"
BEFORE_DIR = EXP_DIR / "before"
AFTER_DIR = EXP_DIR / "after"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

LOOKBACK_SESSIONS = 20
ILLIQ_SCALE = 1_000_000_000.0
EXCLUDED_SECTORS = {"ETF", "Commodities"}

HYPOTHESIS = (
    "Ranking/private full replay: when multiple current core trend/breakout "
    "candidates compete for fewer available slots, rank lower 20-session "
    "Amihud illiquidity first; lower price impact should identify "
    "institutional-quality participation and improve active post-MTM EV and "
    "PnL without any canonical-window regression."
)
CHANGED_VARIABLE = "prior20_amihud_illiquidity_ascending_scarce_slot_rank_v1"
TRIAL_FAMILY = "core_amihud_illiquidity_scarce_slot_ranking"
TRIAL_VARIANT_ID = "prior20_amihud_ascending_conflict_rank_v1"
MECHANISM_FAMILY = "real_ohlcv_relation_price_impact_quality_ranking"
NEARBY = ["exp-20260712-019", "exp-20260709-019", "exp-20260507-023"]
NEW_AXIS = (
    "Unprecedented field on an unsaturated surface: 20-session Amihud "
    "illiquidity has no prior core-candidate ranking experiment, while the "
    "real ohlcv_relation x allocator_source cell is below saturation."
)
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exit_rules_changed": False,
    "orders_changed": False,
    "llm_decision_boundary_changed": False,
    "trade_enabled": False,
    "replay_only": True,
    "scope": "experiment_local_private_full_replay_scout",
    "positive_result_requires": "shared-paper-first ranking helper plus production/backtest parity",
}


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _stock_candidate(signal: dict[str, Any]) -> bool:
    ticker = str(signal.get("ticker") or "").upper()
    sector = signal.get("sector") or risk_engine.SECTOR_MAP.get(ticker, "Unknown")
    return str(sector) not in EXCLUDED_SECTORS


@contextlib.contextmanager
def _amihud_ranking_patch():
    original_compute = feature_layer.compute_features
    original_enrich = risk_engine.enrich_signals
    original_plan = replay.bt.plan_entry_candidates
    audit: dict[str, Any] = {
        "rule": "scarce-slot stock candidates ranked by ascending prior20 Amihud illiquidity",
        "lookback_sessions": LOOKBACK_SESSIONS,
        "lookback_includes_signal_day": True,
        "scale": ILLIQ_SCALE,
        "calls": 0,
        "candidate_count": 0,
        "target_price_present_count": 0,
        "feature_count": 0,
        "scarce_slot_calls": 0,
        "ranking_matches_baseline_calls": 0,
        # The structural replay template calls this field dropped_events.  Here
        # each row is a ranking-change event; candidate eligibility is unchanged.
        "dropped_events": [],
    }

    def compute_with_amihud(ticker, ohlcv_data, earnings_data):
        features = original_compute(ticker, ohlcv_data, earnings_data)
        if not features:
            return features
        close = ohlcv_data["Close"].astype(float)
        volume = ohlcv_data["Volume"].astype(float)
        returns = close.pct_change().iloc[-LOOKBACK_SESSIONS:]
        dollar_volume = (close * volume).iloc[-LOOKBACK_SESSIONS:]
        ratios = []
        for ret, dvol in zip(returns.tolist(), dollar_volume.tolist()):
            ret_value = _finite(ret)
            dvol_value = _finite(dvol)
            if ret_value is None or dvol_value is None or dvol_value <= 0:
                continue
            ratios.append(abs(ret_value) / dvol_value)
        features["_amihud_illiquidity_20d"] = (
            sum(ratios) / len(ratios) * ILLIQ_SCALE
            if len(ratios) == LOOKBACK_SESSIONS
            else None
        )
        features["_amihud_signal_date"] = str(ohlcv_data.index[-1])[:10]
        return features

    def enrich_with_amihud(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            features = (features_dict or {}).get(ticker) or {}
            value = _finite(features.get("_amihud_illiquidity_20d"))
            signal["amihud_illiquidity_20d"] = (
                round(value, 10) if value is not None else None
            )
            signal["amihud_lookback_sessions"] = LOOKBACK_SESSIONS
            signal["amihud_known_at"] = "signal_day_close_before_next_open"
            if value is not None:
                audit["feature_count"] += 1
        return enriched

    def plan_with_amihud_rank(
        signals,
        open_positions,
        market_context=None,
        max_positions=None,
        **kwargs,
    ):
        input_signals = list(signals or [])
        audit["calls"] += 1
        audit["candidate_count"] += len(input_signals)
        audit["target_price_present_count"] += sum(
            1 for signal in input_signals if signal.get("target_price") is not None
        )
        active_count = kwargs.get("active_positions_count")
        if active_count is None:
            active_count = len([row for row in (open_positions or []) if row])
        slots = max(0, int(max_positions or 0) - int(active_count))
        ranked = list(input_signals)
        if slots > 0 and len(input_signals) > slots:
            audit["scarce_slot_calls"] += 1
            stock_positions = [
                index
                for index, signal in enumerate(input_signals)
                if _stock_candidate(signal)
                and _finite(signal.get("amihud_illiquidity_20d")) is not None
            ]
            ranked_stocks = sorted(
                (input_signals[index] for index in stock_positions),
                key=lambda signal: float(signal["amihud_illiquidity_20d"]),
            )
            for index, signal in zip(stock_positions, ranked_stocks):
                ranked[index] = signal
            before_order = [str(row.get("ticker") or "") for row in input_signals]
            after_order = [str(row.get("ticker") or "") for row in ranked]
            if after_order != before_order:
                audit["dropped_events"].append(
                    {
                        "ticker": next(
                            (
                                after
                                for before, after in zip(before_order, after_order)
                                if before != after
                            ),
                            None,
                        ),
                        "available_slots": slots,
                        "before_order": before_order,
                        "after_order": after_order,
                        "stock_scores": {
                            str(row.get("ticker") or ""): row.get(
                                "amihud_illiquidity_20d"
                            )
                            for row in input_signals
                            if _stock_candidate(row)
                        },
                    }
                )
            else:
                audit["ranking_matches_baseline_calls"] += 1

        planned, entry_plan = original_plan(
            ranked,
            open_positions,
            market_context=market_context,
            max_positions=max_positions,
            **kwargs,
        )
        entry_plan = dict(entry_plan)
        entry_plan["amihud_scarce_slot_rank_applied"] = (
            slots > 0 and len(input_signals) > slots
        )
        entry_plan["amihud_rule_version"] = CHANGED_VARIABLE
        return planned, entry_plan

    feature_layer.compute_features = compute_with_amihud
    risk_engine.enrich_signals = enrich_with_amihud
    replay.bt.plan_entry_candidates = plan_with_amihud_rank
    try:
        yield audit
    finally:
        feature_layer.compute_features = original_compute
        risk_engine.enrich_signals = original_enrich
        replay.bt.plan_entry_candidates = original_plan


def _configure_template() -> None:
    values = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "OWNER": OWNER,
        "SLUG": SLUG,
        "RUNNER": RUNNER,
        "RUNNER_COMMAND": RUNNER_COMMAND,
        "EXP_DIR": EXP_DIR,
        "OUT_JSON": OUT_JSON,
        "BEFORE_DIR": BEFORE_DIR,
        "AFTER_DIR": AFTER_DIR,
        "TICKET_JSON": TICKET_JSON,
        "LOG_JSON": LOG_JSON,
        "CARD_MD": CARD_MD,
        "MANIFEST_JSON": MANIFEST_JSON,
        "HYPOTHESIS": HYPOTHESIS,
        "CHANGED_VARIABLE": CHANGED_VARIABLE,
        "TRIAL_FAMILY": TRIAL_FAMILY,
        "TRIAL_VARIANT_ID": TRIAL_VARIANT_ID,
        "MECHANISM_FAMILY": MECHANISM_FAMILY,
        "NEARBY": NEARBY,
        "NEW_AXIS": NEW_AXIS,
        "PRODUCTION_IMPACT": PRODUCTION_IMPACT,
        "_minimum_notional_gate": _amihud_ranking_patch,
        "_fee_provenance": lambda: {
            "source": "PIT frozen OHLCV from exp-20260712-015",
            "formula": "mean(abs(daily close return) / (same-day close * volume))",
            "lookback_sessions": LOOKBACK_SESSIONS,
            "lookback_includes_signal_day": True,
            "display_scale": ILLIQ_SCALE,
        },
        "_card": _card,
    }
    for name, value in values.items():
        setattr(replay, name, value)


def _interpret(payload: dict[str, Any]) -> dict[str, Any]:
    lead = bool(payload["gate4"]["passed"])
    for label in payload["before_metrics"]:
        before_return = float(payload["before_metrics"][label]["total_pnl"]) / 100_000.0
        after_return = float(payload["after_metrics"][label]["total_pnl"]) / 100_000.0
        payload["before_metrics"][label]["strategy_total_return_pct"] = round(
            before_return, 9
        )
        payload["after_metrics"][label]["strategy_total_return_pct"] = round(
            after_return, 9
        )
        payload["delta_metrics"]["by_window"][label][
            "strategy_total_return_pct"
        ] = round(after_return - before_return, 9)

    decision = (
        "positive_replay_lead_not_promoted_core_amihud_scarce_slot_ranking"
        if lead
        else "rejected_core_amihud_scarce_slot_ranking"
    )
    why = (
        "Ascending Amihud ranking improved actual scarce-slot choices across "
        "the current-schema windows; it remains a private lead pending a "
        "shared-paper-first ranking helper and daily parity."
        if lead
        else "Lower prior-20-session Amihud price impact did not improve "
        "scarce-slot choices robustly; baseline momentum/quality ordering was "
        "as good or better across the canonical windows."
    )
    audit = payload.pop("minimum_notional_gate_audit")
    provenance = payload.pop("fee_provenance")
    aggregate = payload["delta_metrics"]["aggregate"]
    aggregate["ranking_conflict_event_count"] = aggregate.pop("dropped_event_count")
    payload.update(
        {
            "status": "observed_only" if lead else "rejected",
            "decision": decision,
            "observed_only_lead": lead,
            "hypothesis": HYPOTHESIS,
            "implementation_mode": "private_full_replay_scout_early_low_cost",
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": NEARBY,
            "new_evidence_axis": NEW_AXIS,
            "fingerprint_caveat": {
                "reservation_fingerprint": "ohlcv_relation|allocator_source",
                "real_data_source": "ohlcv_relation",
                "real_gate_shape": "scarce_slot_ranking",
                "nearest_mismatch": "volume-breakout eligibility and VBB rank are not Amihud price impact",
            },
            "parameters": {
                "lookback_sessions": LOOKBACK_SESSIONS,
                "lookback_includes_signal_day": True,
                "amihud_formula": "mean(abs(return)/(close*volume))",
                "display_scale": ILLIQ_SCALE,
                "rank_direction": "ascending_lower_impact_first",
                "scope": "stock candidates only during actual scarce-slot conflicts",
                "threshold_sweep": False,
                "baseline_protocol": "exp-20260712-015_post_mtm_frozen_inputs_v1",
            },
            "feature_provenance": provenance,
            "amihud_ranking_audit": audit,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": why,
            "post_run_reflection": {
                "why_result_happened": why,
                "realized_failure_mode": (
                    payload["gate4"]["failed_reasons"][0]
                    if payload["gate4"]["failed_reasons"]
                    else "none"
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry 10/40/60-session Amihud, median/max impact, "
                    "reverse ranking, turnover or impact-CV composites, sector/"
                    "ticker/strategy/window slices, or soft score bonuses on "
                    "these frozen rows."
                ),
                "new_evidence_required": (
                    "After rejection, move to a genuinely different data source "
                    "or gate shape. After a positive lead, the only next step is "
                    "a shared production/backtest ranking helper with a daily "
                    "default-off snapshot and the same Gate 1-4 replay."
                ),
            },
            "next_retry_requires": [
                "genuinely different data source or gate shape after rejection",
                "shared-paper-first parity promotion after a positive lead",
            ],
            "changed_files": [
                RUNNER,
                replay._repo_rel(OUT_JSON),
                replay._repo_rel(LOG_JSON),
                replay._repo_rel(CARD_MD),
                replay._repo_rel(MANIFEST_JSON),
                replay._repo_rel(TICKET_JSON),
                "docs/experiment_registry.json",
                "docs/frozen_families.jsonl",
            ],
            "related_files": [
                RUNNER,
                replay._repo_rel(OUT_JSON),
                replay._repo_rel(replay.BASELINE_SUMMARY),
                "quant/experiments/exp_20260712_019_prior_month_max_residual_entry_gate.py",
            ],
            "reproduction_commands": [
                f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
                RUNNER_COMMAND,
                ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
        }
    )
    payload["gate4"]["decision"] = decision
    payload["pre_run_questions"]["1_alpha_hypothesis"] = (
        "ranking: lower Amihud impact may identify institutionally supported scarce-slot candidates"
    )
    payload["pre_run_questions"]["2_history_check"] = {
        "nearby": NEARBY,
        "new_axis": NEW_AXIS,
    }
    return payload


def _card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} core Amihud scarce-slot ranking",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.6f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Ranking-change conflicts: `{aggregate['ranking_conflict_event_count']}`",
            f"- Removed/added trades: `{aggregate['removed_trade_count']}/{aggregate['added_trade_count']}`",
            f"- Failed gates: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
            "",
        ]
    )


def main() -> int:
    _configure_template()
    payload = _interpret(replay.build_payload())
    # replay.persist delegates registry mutation to the prediction-enforcing
    # experiment_registry.persist_self_registered_result( helper.
    replay.persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        replay.json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "ranking_conflict_event_count": aggregate[
                    "ranking_conflict_event_count"
                ],
                "removed_trade_count": aggregate["removed_trade_count"],
                "added_trade_count": aggregate["added_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": replay._repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
