"""exp-20260524-014: core low theme-participation top-up scout.

Alpha search. Tests whether already-qualified core stock signals with a low
cross-sectional ranking theme_participation component deserve a small cap-aware
post-sizing top-up. The causal variable is only the multiplier for
theme_participation <= 0.25.

This runner is experiment-only. If a variant passes Gate 4, the component
exposure and sizing rule must move into shared production/backtest modules and
the same three-window protocol must be rerun before any order path changes.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260523_013_core_canonical_leadership_risk_topup as base


EXPERIMENT_ID = "exp-20260524-014"
STEM = "core_theme_low_participation_topup"
MULTIPLIER_KEY = "theme_low_participation_topup_applied"

THEME_PARTICIPATION_MAX = 0.25

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"

VARIANTS = OrderedDict(
    [
        ("theme_low_participation_topup_1025", {"multiplier": 1.025}),
        ("theme_low_participation_topup_1050", {"multiplier": 1.05}),
        ("theme_low_participation_topup_1075", {"multiplier": 1.075}),
        ("theme_low_participation_topup_1100", {"multiplier": 1.10}),
    ]
)


def _rank_bucket(rank_pct: float | None) -> str:
    if rank_pct is None:
        return "unknown"
    if rank_pct <= 0.10:
        return "top_decile"
    if rank_pct <= 0.25:
        return "top_quartile"
    if rank_pct <= 0.50:
        return "upper_mid"
    if rank_pct <= 0.75:
        return "lower_mid"
    return "bottom_quartile"


def _ranking_context(features_dict: dict[str, Any]) -> dict[str, dict[str, Any]]:
    breadth = base.build_breadth_context(features_dict)
    theme_density = base.build_theme_density_context(features_dict)
    earnings_context = base.build_earnings_estimate_revision_context(features_dict)
    bundle = base.build_market_state_bundle(
        features_dict=features_dict,
        breadth_context=breadth,
        theme_density_context=theme_density,
        expectation_context=earnings_context,
    )
    rows = (bundle.get("cross_sectional_ranking_surface") or {}).get("rows") or []
    n = len(rows)
    out: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows):
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        rank_pct = (idx + 1) / n if n else None
        out[ticker] = {
            "alpha_score": row.get("alpha_score"),
            "alpha_score_components": row.get("components") or {},
            "alpha_score_rank_pct": round(rank_pct, 4) if rank_pct is not None else None,
            "alpha_score_bucket": _rank_bucket(rank_pct),
        }
    return out


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        rank_map = _ranking_context(features_dict or {})
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            rank_row = rank_map.get(ticker) or {}
            components = rank_row.get("alpha_score_components") or {}
            theme_participation = base._safe_float(components.get("theme_participation"))
            sector = sig.get("sector") or base.re.SECTOR_MAP.get(ticker, "Unknown")
            sig["alpha_score"] = rank_row.get("alpha_score")
            sig["alpha_score_components"] = components
            sig["alpha_score_rank_pct"] = rank_row.get("alpha_score_rank_pct")
            sig["alpha_score_bucket"] = rank_row.get("alpha_score_bucket")
            sig["theme_participation_component"] = theme_participation
            sig["theme_low_participation_state"] = (
                sig.get("strategy") in base.TARGET_STRATEGIES
                and sector not in base.EXCLUDED_SECTORS
                and theme_participation is not None
                and theme_participation <= THEME_PARTICIPATION_MAX
            )
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("theme_low_participation_state") is not True:
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
    sizing["theme_low_participation_state"] = True
    sizing["theme_participation_component"] = sig.get("theme_participation_component")
    sizing["theme_participation_max"] = THEME_PARTICIPATION_MAX
    sizing["theme_low_participation_baseline_shares"] = old_shares
    sizing["theme_low_participation_desired_shares"] = desired_shares
    sizing["theme_low_participation_cap_shares"] = cap_shares
    sizing["theme_low_participation_new_shares"] = new_shares
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
        "theme_participation_component": sig.get("theme_participation_component"),
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
            "Best variant failed adjusted-signal sample guard; the low "
            "theme-participation state did not touch enough sized core signals."
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
    base._apply_topup_to_sizing = _apply_topup_to_sizing
    base._rejection_reason = _rejection_reason
    base._artifact = _artifact


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected_multiplier = payload["parameters"]["selected_multiplier"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hypothesis": (
                "The entry-day ranking surface suggests low theme_participation "
                "core stock trades have strong average outcomes across the "
                "canonical windows. Low theme participation may mark less "
                "crowded, more idiosyncratic continuation entries, so already-"
                "qualified non-ETF/non-Commodity core signals with "
                "theme_participation <= 0.25 may deserve a small cap-aware "
                "top-up without changing entries, exits, ranking, universe, "
                "news, or LLM logic."
            ),
            "change_summary": (
                "Compute the experiment-only entry-day ranking surface and "
                "sweep a cap-aware top-up for alpha_score_components."
                "theme_participation <= 0.25."
            ),
            "change_type": "capital_allocation",
            "mechanism_family": "core_cross_sectional_ranking_component_allocation",
            "trial_family": "core_theme_low_participation_topup",
            "changed_variable": "theme_low_participation_post_sizing_multiplier",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260523-012",
                "exp-20260523-015",
                "exp-20260524-003",
                "exp-20260524-007",
                "exp-20260524-011",
                "exp-20260524-012",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_theme_crowding_component_field",
            "component": (
                "quant/cross_sectional_ranking_surface.py, "
                "quant/market_state_bundle.py, quant/risk_engine.py, "
                "quant/portfolio_engine.py"
            ),
            "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
        }
    )
    payload["parameters"] = {
        "theme_participation_max": THEME_PARTICIPATION_MAX,
        "target_strategies": sorted(base.TARGET_STRATEGIES),
        "excluded_sectors": sorted(base.EXCLUDED_SECTORS),
        "baseline_multiplier": 1.0,
        "swept_multipliers": [row["multiplier"] for row in payload["sweep_summary"]],
        "selected_multiplier": selected_multiplier,
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "capital allocation: low theme_participation may identify less "
            "crowded idiosyncratic continuation among already-qualified core entries."
        ),
        "2_history_check": (
            "exp-20260523-012 and exp-20260524-012 exposed PIT-safe component "
            "attribution. Nearby top-level alpha, relative_strength, "
            "breadth_alignment, and trend component scalars were rejected; no "
            "prior log entry tested low theme_participation."
        ),
        "3_single_causal_variable": (
            "post-sizing multiplier for theme_participation_component <= 0.25"
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; require positive aggregate "
            "EV/PnL, no unacceptable drawdown/survival/trade-count/sample/"
            "concentration deterioration, and no production/backtest split "
            "before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260524_014_core_theme_low_participation_topup.py"
        ),
    }
    payload["gate2"]["rule_dependencies"] = [
        "OHLCV features through signal day",
        "market_state_bundle",
        "cross_sectional_ranking_surface rows",
        "alpha_score_components.theme_participation",
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
        "Move the theme-participation component field and risk policy into "
        "shared daily context/risk/portfolio modules with parity tests, then "
        "rerun the same three-window protocol before production use."
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because replay-safe attribution remains sparse. "
        "Skipped SEC/event/state-surface/broad-market/ETF/candidate-pool near "
        "neighbors due recent rejected, concentration-blocked, or strict-gated "
        "lanes. This uses a production-computable crowding-themed component "
        "rather than another saturated top-level score or price-momentum scalar."
    )
    payload["known_risks"] = [
        "Moderate multiple-testing risk because ranking components were recently exposed.",
        "The field is production-computable but not yet promoted as a strategy input.",
        "If accepted, production parity requires shared implementation before orders change.",
    ]
    if payload["status"] == "rejected":
        payload["next_retry_requires"] = [
            "Do not retry adjacent theme-participation component multipliers on the same frozen windows without new forward rows or replacement-value evidence.",
            "A valid retry needs a broader PIT component interaction or explicit crowding/concentration attribution.",
        ]
    else:
        payload["next_retry_requires"] = [
            "Promote the component field and risk policy into shared modules.",
            "Add parity/unit tests for production-visible component metadata and sizing.",
            "Rerun the same three-window protocol after promotion before accepting.",
        ]
    payload["related_files"] = [
        "quant/experiments/exp_20260524_014_core_theme_low_participation_topup.py",
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
