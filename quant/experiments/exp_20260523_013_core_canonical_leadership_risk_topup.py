"""exp-20260523-013: core canonical leadership/risk top-up scout.

Alpha search. Tests whether already-qualified core stock signals with a
production-computable canonical state vector of strong leadership and cool
risk heat deserve a small cap-aware risk top-up.

The only causal variable is the post-sizing risk multiplier for this
entry-day canonical vector state. This runner is experiment-only; if a variant
passes Gate 4, promotion must move the state-vector field and sizing rule into
shared production/backtest modules and rerun the same three-window protocol.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
import exp_20260521_020_ample_slot_stock_rank2_topup as core_helper  # noqa: E402
import exp_20260522_013_core_max_daily_return20_haircut as gate_helper  # noqa: E402
import exp_20260522_025_core_downside_path_haircut as field_helper  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from canonical_state_vectors import build_canonical_state_vectors  # noqa: E402
from constants import MAX_POSITION_PCT  # noqa: E402
from daily_context_archive import (  # noqa: E402
    build_breadth_context,
    build_earnings_estimate_revision_context,
    build_post_earnings_drift_context,
    build_theme_density_context,
)
from data_layer import get_universe  # noqa: E402
from market_state_bundle import build_market_state_bundle  # noqa: E402


EXPERIMENT_ID = "exp-20260523-013"
STEM = "core_canonical_leadership_risk_topup"
MULTIPLIER_KEY = "canonical_strong_leadership_cool_risk_topup_applied"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = core_helper.WINDOWS
VARIANTS = OrderedDict(
    [
        ("canonical_leadership_cool_topup_1025", {"multiplier": 1.025}),
        ("canonical_leadership_cool_topup_1050", {"multiplier": 1.05}),
        ("canonical_leadership_cool_topup_1075", {"multiplier": 1.075}),
        ("canonical_leadership_cool_topup_1100", {"multiplier": 1.10}),
    ]
)

TARGET_LEADERSHIP_STATE = "strong"
TARGET_RISK_HEAT_STATE = "cool"
TARGET_STRATEGIES = {"trend_long", "breakout_long"}
EXCLUDED_SECTORS = {"ETF", "Commodities"}
ADJUSTMENTS: list[dict[str, Any]] = []


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                kept.append(line)
    kept.append(json.dumps(record, sort_keys=True, ensure_ascii=False))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _state_vectors(features_dict: dict[str, Any]) -> dict[str, Any]:
    breadth = build_breadth_context(features_dict)
    theme_density = build_theme_density_context(features_dict)
    earnings_context = build_earnings_estimate_revision_context(features_dict)
    post_earnings = build_post_earnings_drift_context(features_dict)
    bundle = build_market_state_bundle(
        features_dict=features_dict,
        breadth_context=breadth,
        theme_density_context=theme_density,
        expectation_context=earnings_context,
    )
    return build_canonical_state_vectors(
        market_state_bundle=bundle,
        breadth_context=breadth,
        earnings_context=earnings_context,
        post_earnings_context=post_earnings,
    )


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        vectors = _state_vectors(features_dict or {})
        ticker_vectors = vectors.get("ticker_vectors") or {}
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            vector_row = ticker_vectors.get(ticker) or {}
            leadership = vector_row.get("leadership_vector") or {}
            risk_heat = vector_row.get("risk_heat_vector") or {}
            sector = sig.get("sector") or re.SECTOR_MAP.get(ticker, "Unknown")
            sig["canonical_leadership_vector_state"] = leadership.get("state")
            sig["canonical_leadership_vector_score"] = leadership.get("score")
            sig["canonical_risk_heat_vector_state"] = risk_heat.get("state")
            sig["canonical_risk_heat_vector_score"] = risk_heat.get("score")
            sig["canonical_strong_leadership_cool_risk_state"] = (
                sig.get("strategy") in TARGET_STRATEGIES
                and sector not in EXCLUDED_SECTORS
                and leadership.get("state") == TARGET_LEADERSHIP_STATE
                and risk_heat.get("state") == TARGET_RISK_HEAT_STATE
            )
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("canonical_strong_leadership_cool_risk_state") is not True:
        return sig, None

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return sig, None

    entry = _safe_float(sizing.get("entry_price") or sig.get("entry_price"))
    portfolio_value = _safe_float(sizing.get("portfolio_value_usd"))
    net_risk_per_share = _safe_float(sizing.get("net_risk_per_share"))
    if not entry or not portfolio_value or not net_risk_per_share:
        return sig, None

    cap_pct = _safe_float(sizing.get("max_position_pct_applied"), MAX_POSITION_PCT)
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
    sizing["canonical_strong_leadership_cool_risk_state"] = True
    sizing["canonical_strong_leadership_baseline_shares"] = old_shares
    sizing["canonical_strong_leadership_desired_shares"] = desired_shares
    sizing["canonical_strong_leadership_cap_shares"] = cap_shares
    sizing["canonical_strong_leadership_new_shares"] = new_shares
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
        "desired_shares": desired_shares,
        "cap_shares": cap_shares,
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


def _make_size_wrapper(original: Callable[..., list[dict[str, Any]]], multiplier: float):
    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        adjusted = []
        for sig in sized:
            new_sig, record = _apply_topup_to_sizing(dict(sig), multiplier)
            adjusted.append(new_sig)
            if record:
                ADJUSTMENTS.append(record)
        return adjusted

    return wrapped


def _run_window(
    window: dict[str, Any],
    *,
    multiplier: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    original_enrich = re.enrich_signals
    original_size = pe.size_signals
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    ADJUSTMENTS.clear()
    if MULTIPLIER_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, MULTIPLIER_KEY)
    if multiplier is not None:
        re.enrich_signals = _make_enrich_wrapper(original_enrich)
        pe.size_signals = _make_size_wrapper(original_size, multiplier)
    try:
        engine = BacktestEngine(
            sorted(get_universe()),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        )
        result = engine.run()
        return result, list(ADJUSTMENTS)
    finally:
        re.enrich_signals = original_enrich
        pe.size_signals = original_size
        bt.SIZING_MULTIPLIER_KEYS = original_keys
        ADJUSTMENTS.clear()


def _run_baseline() -> dict[str, dict[str, Any]]:
    return {label: _run_window(window)[0] for label, window in WINDOWS.items()}


def _run_variant(
    multiplier: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    for label, window in WINDOWS.items():
        result, rows = _run_window(window, multiplier=multiplier)
        results[label] = result
        adjustments[label] = rows
    return results, adjustments


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


def _rejection_reason(gate: dict[str, Any]) -> str:
    if gate["adjusted_signal_count"] < gate["guardrails"]["min_adjusted_signal_count"]:
        return (
            "Best variant failed adjusted-signal sample guard; the canonical "
            "strong-leadership/cool-risk state did not touch enough sized core signals."
        )
    if gate["regressed_windows"]:
        return (
            "Best variant failed Gate 4 because at least one fixed window "
            "regressed in expected_value_score."
        )
    if not gate["concentration"]["passed"]:
        return (
            "Best variant failed concentration guard; positive incremental "
            "PnL was too ticker-concentrated."
        )
    return (
        "Best variant did not satisfy aggregate EV/PnL, risk, sample, "
        "and no-regression Gate 4 guardrails."
    )


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    field_check = field_helper._open_position_field_check()
    baseline_results = _run_baseline()
    before_metrics = {
        label: core_helper._metrics(result) for label, result in baseline_results.items()
    }

    sweep_summary = []
    variant_payloads: dict[str, dict[str, Any]] = {}
    for variant, params in VARIANTS.items():
        after_results, adjustments = _run_variant(params["multiplier"])
        after_metrics = {
            label: core_helper._metrics(result)
            for label, result in after_results.items()
        }
        gate4 = gate_helper._gate4(baseline_results, after_results, adjustments)
        payload = {
            "variant": variant,
            "multiplier": params["multiplier"],
            "after_metrics": after_metrics,
            "delta_metrics": {
                label: core_helper._delta(after_metrics[label], before_metrics[label])
                for label in WINDOWS
            },
            "gate4": gate4,
            "adjustment_summary": gate_helper._adjustment_summary(adjustments),
        }
        variant_payloads[variant] = payload
        sweep_summary.append(
            {
                "variant": variant,
                "multiplier": params["multiplier"],
                "gate4": gate4,
                "adjustment_summary": payload["adjustment_summary"],
            }
        )

    def sort_key(item: dict[str, Any]) -> tuple[int, float, float]:
        return (
            1 if item["gate4"]["passed"] else 0,
            float(item["gate4"]["aggregate_delta"]["expected_value_score_sum"]),
            float(item["gate4"]["aggregate_delta"]["total_pnl_sum"]),
        )

    selected_summary = max(sweep_summary, key=sort_key)
    selected = variant_payloads[selected_summary["variant"]]
    selected_after_metrics = selected["after_metrics"]
    passed = bool(selected["gate4"]["passed"])
    status = "accepted" if passed else "rejected"
    decision = (
        "candidate_passed_requires_shared_policy_promotion"
        if passed
        else "rejected_failed_gate4"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "hypothesis": (
            "A compressed entry-day canonical state vector may identify "
            "already-qualified core signals where leadership is strong while "
            "portfolio/theme/regime risk heat is still cool. Those signals may "
            "deserve a small cap-aware risk top-up without changing entry, exit, "
            "ranking, universe, news, or LLM logic."
        ),
        "change_summary": (
            "Compute experiment-only canonical state vectors from existing "
            "replayable OHLCV context and sweep a cap-aware top-up for non-ETF/"
            "non-Commodity core signals where leadership_vector=strong and "
            "risk_heat_vector=cool."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_canonical_state_vector_allocation",
        "trial_family": "core_canonical_leadership_risk_vector_topup",
        "trial_variant_id": selected["variant"],
        "changed_variable": "canonical_strong_leadership_cool_risk_topup_multiplier",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260523-012",
            "exp-20260522-025",
            "exp-20260522-026",
            "exp-20260522-024",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_compressed_context_field",
        "component": (
            "quant/canonical_state_vectors.py, quant/market_state_bundle.py, "
            "quant/risk_engine.py, quant/portfolio_engine.py"
        ),
        "parameters": {
            "leadership_state": TARGET_LEADERSHIP_STATE,
            "risk_heat_state": TARGET_RISK_HEAT_STATE,
            "target_strategies": sorted(TARGET_STRATEGIES),
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
            "baseline_multiplier": 1.0,
            "swept_multipliers": [
                params["multiplier"] for params in VARIANTS.values()
            ],
            "selected_multiplier": selected["multiplier"],
        },
        "date_range": {
            "protocol": "docs/backtesting.md standard_three_window",
            "windows": {
                label: {
                    "start": window["start"],
                    "end": window["end"],
                    "snapshot": window["snapshot"],
                    "state_note": window["state_note"],
                }
                for label, window in WINDOWS.items()
            },
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "before_metrics": {
            "windows": before_metrics,
            "aggregate": core_helper._aggregate(before_metrics),
        },
        "after_metrics": {
            "windows": selected_after_metrics,
            "aggregate": core_helper._aggregate(selected_after_metrics),
        },
        "delta_metrics": {
            "windows": selected["delta_metrics"],
            "aggregate": core_helper._aggregate_delta(
                selected_after_metrics,
                before_metrics,
            ),
        },
        "sweep_summary": sweep_summary,
        "selected_adjustment_summary": selected["adjustment_summary"],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk/capital allocation: strong leadership plus cool risk "
                "canonical state may mark safer top-up candidates among existing entries."
            ),
            "2_history_check": (
                "No prior trial used canonical_state_vectors as the sizing "
                "variable. Recent neighboring daily price-path, risk-on breakout, "
                "and core-misfit no-entry trials were rejected for window/sample/"
                "concentration failures."
            ),
            "3_single_causal_variable": (
                "post-sizing multiplier for canonical strong leadership + cool risk state"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV/PnL, no EV-regressed window, drawdown/survival/"
                "trade-count/sample/concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260523_013_core_canonical_leadership_risk_topup.py"
            ),
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "field_check": field_check,
            "rule_dependencies": [
                "OHLCV features through signal day",
                "market_state_bundle",
                "canonical_state_vectors",
                "sector",
                "strategy",
                "sizing.shares_to_buy",
                "sizing.entry_price",
                "sizing.portfolio_value_usd",
                "sizing.net_risk_per_share",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "survival_rate_min_before": core_helper._aggregate(before_metrics)[
                "survival_rate_min"
            ],
            "survival_rate_min_after": core_helper._aggregate(selected_after_metrics)[
                "survival_rate_min"
            ],
            "signals_generated_sum_before": core_helper._aggregate(before_metrics)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_before": core_helper._aggregate(before_metrics)[
                "signals_survived_sum"
            ],
            "signals_generated_sum_after": core_helper._aggregate(selected_after_metrics)[
                "signals_generated_sum"
            ],
            "signals_survived_sum_after": core_helper._aggregate(selected_after_metrics)[
                "signals_survived_sum"
            ],
        },
        "gate4": selected["gate4"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_metric": "not_applicable",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": (
                "Move canonical vector state exposure and top-up into shared "
                "daily context/risk/portfolio modules with parity tests, then "
                "rerun the same three-window protocol before production use."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because replay-safe attribution remains "
            "sparse. Skipped SEC/event/state-surface/broad-market/ETF nearby "
            "scalars due recent rejected or high-multiple-testing lanes. This "
            "tests a new compressed production-computable context field instead "
            "of another local threshold sweep."
        ),
        "known_risks": [
            "Moderate multiple-testing risk because the clue came from a fresh read-only attribution surface.",
            "The vector is production-computable but not yet promoted as a strategy input.",
            "If accepted, production parity requires shared implementation before orders change.",
        ],
        "rejection_reason": None if passed else _rejection_reason(selected["gate4"]),
        "next_retry_requires": (
            [
                "Do not retry adjacent canonical leadership/risk scalar values on the same frozen windows without new forward rows or a distinct vector state.",
                "Prefer promoting only if a shared parity-tested policy passes the same three-window protocol.",
            ]
            if not passed
            else [
                "Promote the vector field and risk policy into shared modules.",
                "Add parity/unit tests for production-visible vector and sizing metadata.",
                "Rerun the same three-window protocol after promotion before accepting.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260523_013_core_canonical_leadership_risk_topup.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
        "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
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
