"""exp-20260712-019: prior-month MAX-residual core entry gate.

Private full-replay scout.  The one decision variable is a pre-slot hard
exclusion for stock candidates in the highest cross-sectional quintile of
their maximum daily ticker-minus-SPY return over the prior 20 sessions.  The
lookback excludes the signal day.  Ranking, sizing, exits, costs, production,
and live orders are unchanged; a positive result is only a lead.
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

import exp_20260712_017_broker_fee_aware_minimum_notional as replay  # noqa: E402
import feature_layer  # noqa: E402
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260712-019"
OWNER = "alpha-explore"
SLUG = "prior_month_max_residual_entry_gate"
RUNNER = f"quant/experiments/exp_20260712_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = EXP_DIR / f"exp_20260712_019_{SLUG}.json"
BEFORE_DIR = EXP_DIR / "before"
AFTER_DIR = EXP_DIR / "after"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

LOOKBACK_SESSIONS = 20
TOP_FRACTION = 0.20
MIN_OVERLAP = 20
EXCLUDED_SECTORS = {"ETF", "Commodities"}

HYPOTHESIS = (
    "Entry-exclusion private replay scout: among current core trend/breakout "
    "candidates, exclude candidates in the highest cross-sectional quintile "
    "of prior-20-session maximum ticker-minus-SPY daily return; lottery-demand "
    "spikes should mean-revert and improve active post-MTM EV and PnL without "
    "any canonical-window regression."
)
CHANGED_VARIABLE = (
    "prior_20_session_max_residual_return_top_quintile_entry_exclusion_v1"
)
TRIAL_FAMILY = "ohlcv_lottery_max_residual_entry_exclusion"
TRIAL_VARIANT_ID = "prior20_max_residual_top_quintile_v1"
MECHANISM_FAMILY = "lottery_demand_max_effect_entry_admission"
NEARBY = ["exp-20260708-021", "exp-20260708-026", "exp-20260709-013"]
NEW_AXIS = (
    "Unprecedented field on an unsaturated real surface: prior-20-session "
    "maximum ticker-minus-SPY daily return has zero historical matches, and "
    "the real OHLCV-relation x entry-admission cell had zero trials at reserve."
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
    "scope": "experiment_local_private_replay_scout",
    "positive_result_requires": "shared-paper-first helper plus production/backtest parity",
}


def _date10(value: Any) -> str:
    return str(value)[:10]


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _stock_feature(ticker: str) -> bool:
    return risk_engine.SECTOR_MAP.get(str(ticker).upper(), "Unknown") not in EXCLUDED_SECTORS


def _residual_scores(
    features_dict: dict[str, dict[str, Any] | None],
) -> tuple[dict[str, float], float | None, str | None]:
    spy = (features_dict.get("SPY") or {}).get("_max_gate_prior_returns") or {}
    signal_date = (features_dict.get("SPY") or {}).get("_max_gate_signal_date")
    scores: dict[str, float] = {}
    if len(spy) < MIN_OVERLAP:
        return scores, None, signal_date

    for ticker, features in features_dict.items():
        if not features or not _stock_feature(ticker):
            continue
        own = features.get("_max_gate_prior_returns") or {}
        common = sorted(set(own) & set(spy))
        if len(common) < MIN_OVERLAP:
            continue
        residuals = [
            float(own[day]) - float(spy[day])
            for day in common[-LOOKBACK_SESSIONS:]
            if _finite(own[day]) is not None and _finite(spy[day]) is not None
        ]
        if len(residuals) == LOOKBACK_SESSIONS:
            scores[str(ticker).upper()] = max(residuals)

    if not scores:
        return scores, None, signal_date
    ordered = sorted(scores.values())
    cutoff_index = max(0, math.ceil(len(ordered) * (1.0 - TOP_FRACTION)) - 1)
    return scores, ordered[cutoff_index], signal_date


@contextlib.contextmanager
def _lottery_max_gate():
    original_compute = feature_layer.compute_features
    original_enrich = risk_engine.enrich_signals
    audit: dict[str, Any] = {
        "rule": "exclude stock candidates at or above signal-day universe p80 of prior20 MAX(ticker return - SPY return)",
        "lookback_sessions": LOOKBACK_SESSIONS,
        "lookback_excludes_signal_day": True,
        "top_fraction": TOP_FRACTION,
        "calls": 0,
        "candidate_count": 0,
        "target_price_present_count": 0,
        "feature_days": 0,
        "cutoff_days": [],
        "dropped_events": [],
    }

    def compute_with_prior_returns(ticker, ohlcv_data, earnings_data):
        features = original_compute(ticker, ohlcv_data, earnings_data)
        if not features:
            return features
        returns = ohlcv_data["Close"].astype(float).pct_change().iloc[-21:-1]
        rows: dict[str, float] = {}
        for stamp, value in returns.items():
            number = _finite(value)
            if number is not None:
                rows[_date10(stamp)] = number
        features["_max_gate_prior_returns"] = rows
        features["_max_gate_signal_date"] = _date10(ohlcv_data.index[-1])
        return features

    def enrich_with_gate(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        audit["calls"] += 1
        audit["candidate_count"] += len(enriched)
        audit["target_price_present_count"] += sum(
            1 for signal in enriched if signal.get("target_price") is not None
        )
        scores, cutoff, signal_date = _residual_scores(features_dict or {})
        if cutoff is not None:
            audit["feature_days"] += 1

        kept = []
        dropped = []
        for signal in enriched:
            ticker = str(signal.get("ticker") or "").upper()
            score = scores.get(ticker)
            applies = _stock_feature(ticker) and score is not None and cutoff is not None
            if applies and float(score) >= float(cutoff):
                row = {
                    "ticker": ticker,
                    "strategy": signal.get("strategy"),
                    "sector": signal.get("sector"),
                    "signal_date": signal_date,
                    "prior20_max_residual_return": round(float(score), 8),
                    "cross_section_p80_cutoff": round(float(cutoff), 8),
                    "cross_section_stock_count": len(scores),
                    "entry_price": signal.get("entry_price"),
                    "target_price": signal.get("target_price"),
                    "stop_price": signal.get("stop_price"),
                }
                dropped.append(row)
                audit["dropped_events"].append(row)
                continue
            kept.append(signal)

        if enriched:
            audit["cutoff_days"].append(
                {
                    "signal_date": signal_date,
                    "candidate_count": len(enriched),
                    "stock_feature_count": len(scores),
                    "p80_cutoff": round(float(cutoff), 8) if cutoff is not None else None,
                    "dropped_count": len(dropped),
                }
            )
        return kept

    feature_layer.compute_features = compute_with_prior_returns
    risk_engine.enrich_signals = enrich_with_gate
    try:
        yield audit
    finally:
        feature_layer.compute_features = original_compute
        risk_engine.enrich_signals = original_enrich


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
        "_minimum_notional_gate": _lottery_max_gate,
        "_fee_provenance": lambda: {
            "source": "PIT frozen OHLCV from exp-20260712-015",
            "formula": "max over 20 prior sessions of ticker close return minus same-date SPY close return",
            "signal_day_excluded": True,
            "threshold": "same-day stock-universe empirical 80th percentile",
        },
        "_card": _card,
    }
    for name, value in values.items():
        setattr(replay, name, value)


def _interpret(payload: dict[str, Any]) -> dict[str, Any]:
    lead = bool(payload["gate4"]["passed"])
    # The structural replay template predates the explicit return projection
    # and therefore emits 0.0 for this presentation field.  The canonical
    # backtester starts each window with $100,000, so recover the exact decimal
    # return from PnL.  EV, PnL, Sharpe, drawdown, and the verdict were already
    # computed by the current-schema backtester and are unchanged here.
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
        "positive_replay_lead_not_promoted_prior_month_max_residual_entry_gate"
        if lead
        else "rejected_prior_month_max_residual_entry_gate"
    )
    why = (
        "The fixed prior-month MAX-residual gate improved the current-schema "
        "replay without a window regression; it remains a private lead and "
        "cannot affect production until a shared-paper-first promotion passes."
        if lead
        else "The prior-month MAX-residual exclusion did not add robust "
        "multi-window value; the removed lottery-like breakouts were not "
        "consistently worse than their replacements or empty slots."
    )
    audit = payload.pop("minimum_notional_gate_audit")
    provenance = payload.pop("fee_provenance")
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
                "reservation_fingerprint": "core_entry_admission|entry_admission",
                "real_data_source": "ohlcv_relation",
                "real_gate_shape": "entry_admission",
                "real_surface_prior_trials": 0,
                "reason": "entry-exclusion wording is classified before OHLCV relation keywords",
            },
            "parameters": {
                "lookback_sessions": LOOKBACK_SESSIONS,
                "lookback_excludes_signal_day": True,
                "residual_benchmark": "SPY same-date close return",
                "cross_section": "stocks only; ETF and Commodities excluded",
                "exclusion_cutoff": "empirical p80",
                "threshold_sweep": False,
                "baseline_protocol": "exp-20260712-015_post_mtm_frozen_inputs_v1",
            },
            "feature_provenance": provenance,
            "lottery_max_gate_audit": audit,
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
                    "Do not retry 10/40/60-session lookbacks, p70/p90 cutoffs, "
                    "raw instead of SPY-residual MAX, soft scalars, ticker/sector/"
                    "strategy/window slices, or signal-day inclusion on these rows."
                ),
                "new_evidence_required": (
                    "After rejection, move to a genuinely different source or "
                    "gate shape. After a positive lead, the only next step is a "
                    "shared production/backtest helper with daily default-off "
                    "snapshot and the same full Gate 1-4 replay."
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
                "quant/experiments/exp_20260712_017_broker_fee_aware_minimum_notional.py",
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
        "entry: exclude prior-month lottery-demand MAX-residual tail"
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
            f"# {EXPERIMENT_ID} prior-month MAX-residual entry gate",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.6f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Dropped gate events: `{aggregate['dropped_event_count']}`",
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
                "dropped_event_count": aggregate["dropped_event_count"],
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
