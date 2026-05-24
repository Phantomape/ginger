"""exp-20260524-011: core perfect trend-component top-up scout.

Alpha search. Tests whether the entry-day cross-sectional ranking surface's
trend component has allocation value when it is fully saturated for already
qualified core stock signals. The only causal variable is a cap-aware
post-sizing multiplier for signals with alpha_score_components.trend >= 0.999.

This is experiment-only. If a variant passes Gate 4, the component exposure
and sizing rule must move into shared production/backtest modules before any
order path changes.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260524_003_core_relative_strength_component_band_topup as parent


base = parent.base

EXPERIMENT_ID = "exp-20260524-011"
STEM = "core_trend_component_perfect_topup"
MULTIPLIER_KEY = "trend_component_perfect_topup_applied"

TREND_COMPONENT_MIN = 0.999

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"

VARIANTS = OrderedDict(
    [
        ("trend_component_perfect_topup_1025", {"multiplier": 1.025}),
        ("trend_component_perfect_topup_1050", {"multiplier": 1.05}),
        ("trend_component_perfect_topup_1075", {"multiplier": 1.075}),
    ]
)


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        rank_map = parent._ranking_context(features_dict or {})
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            rank_row = rank_map.get(ticker) or {}
            components = rank_row.get("alpha_score_components") or {}
            trend_component = base._safe_float(components.get("trend"))
            sector = sig.get("sector") or base.re.SECTOR_MAP.get(ticker, "Unknown")
            sig["alpha_score"] = rank_row.get("alpha_score")
            sig["alpha_score_components"] = components
            sig["alpha_score_rank_pct"] = rank_row.get("alpha_score_rank_pct")
            sig["alpha_score_bucket"] = rank_row.get("alpha_score_bucket")
            sig["trend_component"] = trend_component
            sig["trend_component_perfect_state"] = (
                sig.get("strategy") in base.TARGET_STRATEGIES
                and sector not in base.EXCLUDED_SECTORS
                and trend_component is not None
                and trend_component >= TREND_COMPONENT_MIN
            )
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("trend_component_perfect_state") is not True:
        return sig, None

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return sig, None

    entry = base._safe_float(sizing.get("entry_price") or sig.get("entry_price"))
    portfolio_value = base._safe_float(sizing.get("portfolio_value_usd"))
    net_risk_per_share = base._safe_float(sizing.get("net_risk_per_share"))
    if not entry or not portfolio_value or not net_risk_per_share:
        return sig, None

    cap_pct = base._safe_float(
        sizing.get("max_position_pct_applied"),
        base.MAX_POSITION_PCT,
    )
    desired_shares = max(old_shares, int(math.floor(old_shares * multiplier)))
    cap_shares = int(math.floor((portfolio_value * cap_pct) / entry))
    new_shares = min(desired_shares, cap_shares)
    if new_shares <= old_shares:
        return sig, None

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    sizing["trend_component_perfect_state"] = True
    sizing["trend_component"] = sig.get("trend_component")
    sizing["trend_component_min"] = TREND_COMPONENT_MIN
    sizing["trend_component_baseline_shares"] = old_shares
    sizing["trend_component_desired_shares"] = desired_shares
    sizing["trend_component_cap_shares"] = cap_shares
    sizing["trend_component_new_shares"] = new_shares
    sizing[MULTIPLIER_KEY] = multiplier
    sig = {**sig, "sizing": sizing}

    record = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "baseline_shares": old_shares,
        "desired_shares": desired_shares,
        "cap_shares": cap_shares,
        "new_shares": new_shares,
        "multiplier": multiplier,
        "trend_component": sig.get("trend_component"),
        "alpha_score": sig.get("alpha_score"),
        "alpha_score_bucket": sig.get("alpha_score_bucket"),
        "alpha_score_rank_pct": sig.get("alpha_score_rank_pct"),
        "alpha_score_components": sig.get("alpha_score_components"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
        "signal_day_ticker_outperformed_spy": sig.get(
            "signal_day_ticker_outperformed_spy"
        ),
        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
        "existing_sizing_multipliers": {
            key: value
            for key, value in sizing.items()
            if key.endswith("_applied")
            and value not in (None, 1.0)
            and key != MULTIPLIER_KEY
        },
    }
    return sig, record


def _rejection_reason(gate: dict[str, Any]) -> str:
    if gate["adjusted_signal_count"] < gate["guardrails"]["min_adjusted_signal_count"]:
        return (
            "Best variant failed adjusted-signal sample guard; the perfect "
            "trend-component state did not touch enough sized core signals."
        )
    if gate["regressed_windows"]:
        return (
            "Best variant failed Gate 4 because at least one fixed window "
            "regressed in expected_value_score."
        )
    if not gate["concentration"]["passed"]:
        return (
            "Best variant failed concentration guard; positive incremental PnL "
            "was too ticker-concentrated."
        )
    return (
        "Best variant did not satisfy aggregate EV/PnL, risk, sample, and "
        "no-regression Gate 4 guardrails."
    )


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.VARIANTS = VARIANTS
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._apply_topup_to_sizing = _apply_topup_to_sizing
    base._rejection_reason = _rejection_reason
    base._artifact = parent._artifact


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected_multiplier = payload["parameters"]["selected_multiplier"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hypothesis": (
                "The top-level alpha_score mostly saturates inside filled core "
                "trades, but the ranking surface's trend component may still "
                "separate the cleanest continuation entries. Already-qualified "
                "non-ETF/non-Commodity core signals with trend component at "
                "1.0 may deserve a small cap-aware top-up without changing "
                "entries, exits, ranking, universe, news, or LLM logic."
            ),
            "change_summary": (
                "Compute the experiment-only entry-day ranking surface and "
                "sweep a cap-aware top-up for alpha_score_components.trend >= 0.999."
            ),
            "change_type": "capital_allocation",
            "mechanism_family": "core_cross_sectional_ranking_component_allocation",
            "trial_family": "core_trend_component_perfect_topup",
            "changed_variable": "trend_component_perfect_post_sizing_multiplier",
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260523-012",
                "exp-20260523-015",
                "exp-20260524-003",
                "exp-20260524-007",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "new_production_visible_ranking_component_field",
            "component": (
                "quant/cross_sectional_ranking_surface.py, "
                "quant/market_state_bundle.py, quant/risk_engine.py, "
                "quant/portfolio_engine.py"
            ),
            "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
        }
    )
    payload["parameters"] = {
        "trend_component_min": TREND_COMPONENT_MIN,
        "target_strategies": sorted(base.TARGET_STRATEGIES),
        "excluded_sectors": sorted(base.EXCLUDED_SECTORS),
        "baseline_multiplier": 1.0,
        "swept_multipliers": [row["multiplier"] for row in payload["sweep_summary"]],
        "selected_multiplier": selected_multiplier,
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "capital allocation: fully saturated ranking trend component may "
            "mark cleaner continuation candidates among already-qualified core entries."
        ),
        "2_history_check": (
            "exp-20260523-012 exposed PIT ranking-component context. "
            "exp-20260523-015 top-level alpha-score, exp-20260524-003 "
            "relative-strength component, and exp-20260524-007 breadth-alignment "
            "component top-ups were rejected. No exact prior log row tested the "
            "trend component at 1.0."
        ),
        "3_single_causal_variable": (
            "post-sizing multiplier for alpha_score_components.trend >= 0.999"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; require positive aggregate "
            "EV/PnL, no unacceptable drawdown/survival/trade-count/sample/"
            "concentration deterioration, and no production/backtest split "
            "before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260524_011_core_trend_component_perfect_topup.py"
        ),
    }
    payload["gate2"]["rule_dependencies"] = [
        "OHLCV features through signal day",
        "market_state_bundle",
        "cross_sectional_ranking_surface rows",
        "alpha_score_components.trend",
        "sector",
        "strategy",
        "sizing.shares_to_buy",
        "sizing.entry_price",
        "sizing.portfolio_value_usd",
        "sizing.net_risk_per_share",
    ]
    payload["gate3"]["adds_filter"] = False
    payload["production_impact"][
        "promotion_required_if_accepted"
    ] = (
        "Move the trend component field and risk policy into shared daily "
        "context/risk/portfolio modules with parity tests, then rerun the "
        "same three-window protocol before production use."
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because replay-safe attribution remains sparse. "
        "Skipped SEC/event/state-surface/broad-market/ETF/candidate-pool scalars "
        "due recent rejected or strict-gated lanes. This is a high-risk ranking "
        "component test, but it uses a different production-computable component "
        "than the recent relative-strength and breadth-alignment failures."
    )
    payload["known_risks"] = [
        "High multiple-testing risk because adjacent ranking-component scouts failed.",
        "The field is production-computable but not yet promoted as a strategy input.",
        "If accepted, production parity requires shared implementation before orders change.",
    ]
    if payload["status"] == "rejected":
        payload["next_retry_requires"] = [
            "Do not retry adjacent trend-component thresholds or multipliers on the same frozen windows without new forward rows or a materially different ranking-field interaction.",
            "A valid retry needs replacement-value evidence or a broader PIT component interaction.",
        ]
    else:
        payload["next_retry_requires"] = [
            "Promote the component field and risk policy into shared modules.",
            "Add parity/unit tests for production-visible component metadata and sizing.",
            "Rerun the same three-window protocol after promotion before accepting.",
        ]
    payload["related_files"] = [
        "quant/experiments/exp_20260524_011_core_trend_component_perfect_topup.py",
        str(OUT_JSON.relative_to(REPO_ROOT)),
        str(LOG_JSON.relative_to(REPO_ROOT)),
        str(TICKET_JSON.relative_to(REPO_ROOT)),
        str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        "docs/experiment_log.jsonl",
    ]
    return payload


def run() -> dict[str, Any]:
    _configure_base()
    payload = _retag_payload(base.run())
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(parent._artifact(payload), encoding="utf-8")
    base._append_jsonl(base.EXPERIMENT_LOG_JSONL, payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_variant": result["trial_variant_id"],
                "aggregate_delta": result["delta_metrics"]["aggregate"],
                "gate4_passed": result["gate4"]["passed"],
                "artifact": str(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
