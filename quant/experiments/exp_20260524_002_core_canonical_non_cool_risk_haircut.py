"""exp-20260524-002: core canonical non-cool risk-heat haircut scout.

Alpha search. Tests whether already-qualified non-ETF/non-Commodity core stock
signals whose canonical risk heat is normal/hot, rather than cool, should
receive a bounded post-sizing haircut.

This is experiment-only. If a variant passes Gate 4, the vector exposure and
sizing rule must move into shared production/backtest modules before any order
path changes.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260523_013_core_canonical_leadership_risk_topup as base


EXPERIMENT_ID = "exp-20260524-002"
STEM = "core_canonical_non_cool_risk_haircut"
MULTIPLIER_KEY = "canonical_non_cool_risk_heat_haircut_applied"
TARGET_RISK_HEAT_STATES = {"normal", "hot"}

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"

VARIANTS = OrderedDict(
    [
        ("non_cool_risk_heat_haircut_090", {"multiplier": 0.90}),
        ("non_cool_risk_heat_haircut_075", {"multiplier": 0.75}),
        ("non_cool_risk_heat_haircut_050", {"multiplier": 0.50}),
    ]
)


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        vectors = base._state_vectors(features_dict or {})
        ticker_vectors = vectors.get("ticker_vectors") or {}
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            vector_row = ticker_vectors.get(ticker) or {}
            leadership = vector_row.get("leadership_vector") or {}
            risk_heat = vector_row.get("risk_heat_vector") or {}
            sector = sig.get("sector") or base.re.SECTOR_MAP.get(ticker, "Unknown")
            risk_state = risk_heat.get("state")
            sig["canonical_leadership_vector_state"] = leadership.get("state")
            sig["canonical_leadership_vector_score"] = leadership.get("score")
            sig["canonical_risk_heat_vector_state"] = risk_state
            sig["canonical_risk_heat_vector_score"] = risk_heat.get("score")
            sig["canonical_non_cool_risk_heat_state"] = (
                sig.get("strategy") in base.TARGET_STRATEGIES
                and sector not in base.EXCLUDED_SECTORS
                and risk_state in TARGET_RISK_HEAT_STATES
            )
        return enriched

    return wrapped


def _apply_haircut_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("canonical_non_cool_risk_heat_state") is not True:
        return sig, None

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 1:
        return sig, None

    entry = base._safe_float(sizing.get("entry_price") or sig.get("entry_price"))
    portfolio_value = base._safe_float(sizing.get("portfolio_value_usd"))
    net_risk_per_share = base._safe_float(sizing.get("net_risk_per_share"))
    if not entry or not portfolio_value or not net_risk_per_share:
        return sig, None

    new_shares = max(1, int(math.floor(old_shares * multiplier)))
    if new_shares >= old_shares:
        return sig, None

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    sizing["canonical_non_cool_risk_heat_state"] = True
    sizing["canonical_non_cool_risk_heat_baseline_shares"] = old_shares
    sizing["canonical_non_cool_risk_heat_new_shares"] = new_shares
    sizing["canonical_leadership_vector_state"] = sig.get(
        "canonical_leadership_vector_state"
    )
    sizing["canonical_leadership_vector_score"] = sig.get(
        "canonical_leadership_vector_score"
    )
    sizing["canonical_risk_heat_vector_state"] = sig.get(
        "canonical_risk_heat_vector_state"
    )
    sizing["canonical_risk_heat_vector_score"] = sig.get(
        "canonical_risk_heat_vector_score"
    )
    sizing[MULTIPLIER_KEY] = multiplier
    sig = {**sig, "sizing": sizing}

    record = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "baseline_shares": old_shares,
        "new_shares": new_shares,
        "multiplier": multiplier,
        "canonical_leadership_vector_state": sig.get(
            "canonical_leadership_vector_state"
        ),
        "canonical_leadership_vector_score": sig.get(
            "canonical_leadership_vector_score"
        ),
        "canonical_risk_heat_vector_state": sig.get(
            "canonical_risk_heat_vector_state"
        ),
        "canonical_risk_heat_vector_score": sig.get(
            "canonical_risk_heat_vector_score"
        ),
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
            "Best variant failed adjusted-signal sample guard; canonical "
            "normal/hot risk heat did not touch enough sized core signals."
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


def _artifact(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Trial accounting",
        f"- trial_family: {payload['trial_family']}",
        f"- changed_variable: {payload['changed_variable']}",
        f"- prior_trial_count: {payload['prior_trial_count']}",
        f"- multiple_testing_risk_bucket: {payload['multiple_testing_risk_bucket']}",
        f"- new_evidence_type: {payload['new_evidence_type']}",
        "",
        "## Three-window aggregate",
        f"- baseline EV: {payload['before_metrics']['aggregate']['expected_value_score_sum']}",
        f"- best EV: {payload['after_metrics']['aggregate']['expected_value_score_sum']}",
        f"- EV delta: {payload['delta_metrics']['aggregate']['expected_value_score_sum']}",
        f"- PnL delta: {payload['delta_metrics']['aggregate']['total_pnl_sum']}",
        f"- decision: {payload['decision']}",
        "",
        "## Sweep summary",
        "| variant | multiplier | EV delta | PnL delta | DD delta | adjusted | changed trades | max pos share | passed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["sweep_summary"]:
        gate = row["gate4"]
        lines.append(
            "| {variant} | {multiplier} | {ev_delta} | {pnl_delta} | {dd_delta} | {adjusted} | {changed} | {share} | {passed} |".format(
                variant=row["variant"],
                multiplier=row["multiplier"],
                ev_delta=gate["aggregate_delta"]["expected_value_score_sum"],
                pnl_delta=gate["aggregate_delta"]["total_pnl_sum"],
                dd_delta=gate["aggregate_delta"]["max_drawdown_pct_max"],
                adjusted=gate["adjusted_signal_count"],
                changed=gate["changed_trade_count"],
                share=gate["concentration"]["max_single_positive_ticker_share"],
                passed=gate["passed"],
            )
        )
    lines.extend(
        [
            "",
            "## Selected Window Deltas",
            "| window | EV | PnL | DD | survival | worst trade | tail loss share |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["delta_metrics"]["windows"].items():
        lines.append(
            f"| {label} | {row.get('expected_value_score')} | {row.get('total_pnl')} | {row.get('max_drawdown_pct')} | {row.get('survival_rate')} | {row.get('worst_trade_pct')} | {row.get('tail_loss_share')} |"
        )
    lines.extend(
        [
            "",
            "## Production impact",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "## Closeout",
            payload.get("rejection_reason") or "n/a",
            "",
        ]
    )
    return "\n".join(lines)


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
    base._apply_topup_to_sizing = _apply_haircut_to_sizing
    base._rejection_reason = _rejection_reason
    base._artifact = _artifact


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected_multiplier = payload["parameters"]["selected_multiplier"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "A compressed entry-day canonical risk-heat vector may identify "
                "already-qualified core stock signals where portfolio/theme/"
                "regime heat is not cool. A bounded non-cool risk haircut may "
                "improve expected_value_score or tail risk without changing "
                "entry, exit, ranking, universe, news, or LLM logic."
            ),
            "change_summary": (
                "Compute experiment-only canonical state vectors from existing "
                "replayable OHLCV context and sweep a post-sizing haircut for "
                "non-ETF/non-Commodity core signals whose risk_heat_vector is "
                "normal or hot."
            ),
            "mechanism_family": "core_canonical_state_vector_risk_heat",
            "trial_family": "core_canonical_non_cool_risk_heat_haircut",
            "changed_variable": "canonical_non_cool_risk_heat_haircut_multiplier",
            "prior_trial_count": 2,
            "nearby_prior_experiments": [
                "exp-20260523-013",
                "exp-20260523-014",
                "exp-20260522-025",
            ],
            "component": (
                "quant/canonical_state_vectors.py, quant/market_state_bundle.py, "
                "quant/risk_engine.py, quant/portfolio_engine.py"
            ),
            "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
        }
    )
    payload["parameters"] = {
        "risk_heat_states": sorted(TARGET_RISK_HEAT_STATES),
        "target_strategies": sorted(base.TARGET_STRATEGIES),
        "excluded_sectors": sorted(base.EXCLUDED_SECTORS),
        "baseline_multiplier": 1.0,
        "swept_multipliers": [row["multiplier"] for row in payload["sweep_summary"]],
        "selected_multiplier": selected_multiplier,
        "share_floor": 1,
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "risk allocation: canonical normal/hot risk heat may mark existing "
            "core entries that should be sized down."
        ),
        "2_history_check": (
            "exp-20260523-013 and exp-20260523-014 tested cool-risk top-ups and "
            "failed Gate 4; exp-20260522-025 tested a downside-path haircut but "
            "had zero touches. This is the first canonical non-cool risk-heat "
            "haircut scout found in the log review."
        ),
        "3_single_causal_variable": (
            "post-sizing share multiplier for canonical risk_heat_vector_state in normal/hot"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; require positive aggregate "
            "EV/PnL, no EV-regressed window, drawdown/survival/trade-count/"
            "sample/concentration guards."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260524_002_core_canonical_non_cool_risk_haircut.py"
        ),
    }
    payload["gate2"]["rule_dependencies"] = [
        "OHLCV features through signal day",
        "market_state_bundle",
        "canonical_state_vectors",
        "risk_heat_vector.state",
        "sector",
        "strategy",
        "sizing.shares_to_buy",
        "sizing.entry_price",
        "sizing.portfolio_value_usd",
        "sizing.net_risk_per_share",
    ]
    payload["gate3"]["adds_filter"] = False
    payload["gate3"]["filter_note"] = (
        "Haircut keeps at least one share for touched entries, so it is sizing "
        "risk allocation rather than an entry filter."
    )
    payload["production_impact"][
        "promotion_required_if_accepted"
    ] = (
        "Move canonical risk-heat state exposure and the haircut into shared "
        "daily context/risk/portfolio modules with parity tests, then rerun "
        "the same three-window protocol before production use."
    )
    payload["why_not_other_changes"] = (
        "Skipped adjacent cool-state top-ups because they just failed Gate 4. "
        "Skipped state-surface, broad-market, event, and execution scalar "
        "families because recent logs show high multiple-testing or rejected "
        "nearby variants. This tests the opposite risk-control side of the "
        "new canonical vector field."
    )
    payload["known_risks"] = [
        "Moderate multiple-testing risk because canonical vectors are a recent attribution surface.",
        "Haircuts can reduce winners if risk heat is not predictive.",
        "If accepted, production parity requires shared implementation before orders change.",
    ]
    if payload["status"] == "rejected":
        payload["next_retry_requires"] = [
            "Do not retry adjacent canonical non-cool risk-heat haircut multipliers on the same frozen windows without new forward rows or a distinct vector state.",
            "A valid retry needs forward outcome evidence or a materially different production-visible risk-heat discriminator.",
        ]
    else:
        payload["next_retry_requires"] = [
            "Promote the vector field and risk policy into shared modules.",
            "Add parity/unit tests for production-visible vector and sizing metadata.",
            "Rerun the same three-window protocol after promotion before accepting.",
        ]
    payload["related_files"] = [
        "quant/experiments/exp_20260524_002_core_canonical_non_cool_risk_haircut.py",
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
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
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
