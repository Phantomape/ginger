"""exp-20260522-027: core overnight-gap-share haircut scout.

Alpha search. Tests whether already-qualified non-ETF/non-Commodity core stock
signals whose prior 20 trading days have top-quartile overnight-gap share should
receive a risk haircut. The field is production-visible from OHLCV only:

    overnight_gap_share_20 =
        sum(abs(open_t / close_t-1 - 1)) / sum(abs(close_t / close_t-1 - 1))

This is not a retry of downside-path share. It asks whether recent path movement
that is disproportionately overnight-driven is a sizing risk for existing core
entries.

This runner is experiment-only. If a variant passes Gate 4, promotion must move
the feature and sizing rule into shared production/backtest modules before any
production behavior changes.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260522_025_core_downside_path_haircut as base


EXPERIMENT_ID = "exp-20260522-027"
STEM = "core_overnight_gap_share_haircut"
MULTIPLIER_KEY = "overnight_gap_share20_top_quartile_risk_multiplier_applied"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = base.WINDOWS
VARIANTS = OrderedDict(
    [
        ("overnight_gap_share20_haircut_000", {"multiplier": 0.0}),
        ("overnight_gap_share20_haircut_025", {"multiplier": 0.25}),
        ("overnight_gap_share20_haircut_050", {"multiplier": 0.50}),
        ("overnight_gap_share20_haircut_075", {"multiplier": 0.75}),
    ]
)

TOP_QUARTILE_FRACTION = 0.25
EXCLUDED_SECTORS = {"ETF", "Commodities"}
ADJUSTMENTS: list[dict[str, Any]] = []


def _overnight_gap_share20_features(data) -> dict[str, Any]:
    if data is None or len(data) < 22 or "Open" not in data or "Close" not in data:
        return {
            "overnight_gap_share_20": None,
            "overnight_gap_share_20_available": False,
        }
    rows = data[["Open", "Close"]].dropna().tail(21)
    if len(rows) < 21:
        return {
            "overnight_gap_share_20": None,
            "overnight_gap_share_20_available": False,
        }
    prev_close = rows["Close"].shift(1).iloc[1:]
    opens = rows["Open"].iloc[1:]
    closes = rows["Close"].iloc[1:]
    close_to_close = (closes / prev_close) - 1.0
    overnight = (opens / prev_close) - 1.0
    total_path = float(close_to_close.abs().sum())
    if total_path <= 0.0:
        share = None
    else:
        share = float(overnight.abs().sum()) / total_path
    return {
        "overnight_gap_share_20": round(share, 6) if share is not None else None,
        "overnight_gap_share_20_available": share is not None,
    }


def _make_trend_feature_wrapper(original: Callable[..., dict[str, Any] | None]):
    def wrapped(data):
        features = original(data)
        if features is None:
            return None
        return {**features, **_overnight_gap_share20_features(data)}

    return wrapped


def _top_quartile_cutoff(features_dict: dict[str, Any]) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        if not isinstance(features, dict):
            continue
        sector = base.re.SECTOR_MAP.get(str(ticker).upper(), "Unknown")
        if sector in EXCLUDED_SECTORS:
            continue
        value = features.get("overnight_gap_share_20")
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return None
    values.sort()
    index = max(0, math.ceil(len(values) * (1.0 - TOP_QUARTILE_FRACTION)) - 1)
    return values[index]


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = _top_quartile_cutoff(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            features = (features_dict or {}).get(ticker) or {}
            value = features.get("overnight_gap_share_20")
            sector = sig.get("sector") or base.re.SECTOR_MAP.get(ticker, "Unknown")
            sig["overnight_gap_share_20"] = value
            sig["overnight_gap_share_20_top_quartile_cutoff"] = (
                round(float(cutoff), 6) if isinstance(cutoff, (int, float)) else None
            )
            sig["overnight_gap_share_20_top_quartile_state"] = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and isinstance(value, (int, float))
                and isinstance(cutoff, (int, float))
                and float(value) >= float(cutoff)
            )
        return enriched

    return wrapped


def _apply_haircut_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("overnight_gap_share_20_top_quartile_state") is not True:
        return sig, None

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return sig, None

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0 or portfolio_value <= 0 or net_risk_per_share <= 0:
        return sig, None

    new_shares = int(math.floor(old_shares * multiplier))
    if new_shares >= old_shares:
        return sig, None

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    sizing["overnight_gap_share20_top_quartile_state"] = True
    sizing["overnight_gap_share20_top_quartile_baseline_shares"] = old_shares
    sizing["overnight_gap_share20_top_quartile_new_shares"] = new_shares
    sizing["overnight_gap_share20_top_quartile_value"] = sig.get(
        "overnight_gap_share_20"
    )
    sizing["overnight_gap_share20_top_quartile_cutoff"] = sig.get(
        "overnight_gap_share_20_top_quartile_cutoff"
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
        "overnight_gap_share_20": sig.get("overnight_gap_share_20"),
        "cutoff": sig.get("overnight_gap_share_20_top_quartile_cutoff"),
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
        "days_to_earnings": sig.get("days_to_earnings"),
        "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
    }
    return sig, record


def _make_size_wrapper(original: Callable[..., list[dict[str, Any]]], multiplier: float):
    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        adjusted = []
        for sig in sized:
            new_sig, record = _apply_haircut_to_sizing(dict(sig), multiplier)
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
    original_trend_features = base.fl.compute_trend_features
    original_enrich = base.re.enrich_signals
    original_size = base.pe.size_signals
    original_keys = base.bt.SIZING_MULTIPLIER_KEYS
    ADJUSTMENTS.clear()
    if MULTIPLIER_KEY not in base.bt.SIZING_MULTIPLIER_KEYS:
        base.bt.SIZING_MULTIPLIER_KEYS = (
            *base.bt.SIZING_MULTIPLIER_KEYS,
            MULTIPLIER_KEY,
        )
    if multiplier is not None:
        base.fl.compute_trend_features = _make_trend_feature_wrapper(
            original_trend_features
        )
        base.re.enrich_signals = _make_enrich_wrapper(original_enrich)
        base.pe.size_signals = _make_size_wrapper(original_size, multiplier)
    try:
        engine = base.BacktestEngine(
            sorted(base.get_universe()),
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
        base.fl.compute_trend_features = original_trend_features
        base.re.enrich_signals = original_enrich
        base.pe.size_signals = original_size
        base.bt.SIZING_MULTIPLIER_KEYS = original_keys
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


def _rejection_reason(gate: dict[str, Any]) -> str:
    if gate["adjusted_signal_count"] < gate["guardrails"]["min_adjusted_signal_count"]:
        return (
            "Best variant failed adjusted-signal sample guard; the top-quartile "
            "overnight-gap-share state did not touch enough sized core signals."
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
    field_check = base._open_position_field_check()
    baseline_results = _run_baseline()
    before_metrics = {
        label: base.core_helper._metrics(result)
        for label, result in baseline_results.items()
    }

    sweep_summary = []
    variant_payloads: dict[str, dict[str, Any]] = {}
    for variant, params in VARIANTS.items():
        after_results, adjustments = _run_variant(params["multiplier"])
        after_metrics = {
            label: base.core_helper._metrics(result)
            for label, result in after_results.items()
        }
        gate4 = base.gate_helper._gate4(baseline_results, after_results, adjustments)
        payload = {
            "variant": variant,
            "multiplier": params["multiplier"],
            "after_results": after_results,
            "after_metrics": after_metrics,
            "delta_metrics": {
                label: base.core_helper._delta(
                    after_metrics[label],
                    before_metrics[label],
                )
                for label in WINDOWS
            },
            "gate4": gate4,
            "adjustment_summary": base.gate_helper._adjustment_summary(adjustments),
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
            "Already-qualified core stock signals with top-quartile prior-20-day "
            "overnight-gap share are more event-driven and gap-risk exposed. A "
            "risk haircut should improve expected_value_score and tail risk "
            "without changing entry, exit, ranking, universe, news, or LLM logic."
        ),
        "change_summary": (
            "Add an experiment-only overnight_gap_share_20 OHLCV field and sweep "
            "a risk multiplier for non-ETF/non-Commodity core signals in the "
            "same-day top quartile of that field."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_daily_return_path",
        "trial_family": "core_overnight_gap_share20_risk",
        "trial_variant_id": selected["variant"],
        "changed_variable": "high_overnight_gap_share20_risk_multiplier",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260421-013",
            "exp-20260421-020",
            "exp-20260522-013",
            "exp-20260522-014",
            "exp-20260522-025",
            "exp-20260522-026",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_field",
        "component": "quant/feature_layer.py, quant/risk_engine.py, quant/portfolio_engine.py",
        "parameters": {
            "field": "overnight_gap_share_20",
            "field_definition": (
                "sum(abs(open_t / close_t-1 - 1)) divided by "
                "sum(abs(close_t / close_t-1 - 1)) over the last 20 "
                "signal-known trading days"
            ),
            "top_quartile_fraction": TOP_QUARTILE_FRACTION,
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
            "aggregate": base.core_helper._aggregate(before_metrics),
        },
        "after_metrics": {
            "windows": selected_after_metrics,
            "aggregate": base.core_helper._aggregate(selected_after_metrics),
        },
        "delta_metrics": {
            "windows": selected["delta_metrics"],
            "aggregate": base.core_helper._aggregate_delta(
                selected_after_metrics,
                before_metrics,
            ),
        },
        "sweep_summary": sweep_summary,
        "selected_adjustment_summary": selected["adjustment_summary"],
        "gate1": {
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "field_check": field_check,
            "rule_dependencies": [
                "OHLCV Open/Close series through signal day",
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
            "survival_rate_min_before": base.core_helper._aggregate(before_metrics)[
                "survival_rate_min"
            ],
            "survival_rate_min_after": base.core_helper._aggregate(
                selected_after_metrics
            )["survival_rate_min"],
            "signals_generated_sum_before": base.core_helper._aggregate(
                before_metrics
            )["signals_generated_sum"],
            "signals_survived_sum_before": base.core_helper._aggregate(
                before_metrics
            )["signals_survived_sum"],
            "signals_generated_sum_after": base.core_helper._aggregate(
                selected_after_metrics
            )["signals_generated_sum"],
            "signals_survived_sum_after": base.core_helper._aggregate(
                selected_after_metrics
            )["signals_survived_sum"],
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
                "Move overnight_gap_share_20 feature, top-quartile state, and "
                "risk haircut into shared feature_layer/risk_engine/portfolio_engine "
                "with tests, then rerun the same three-window protocol."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because attribution rows remain sparse; "
            "skipped SEC/event/source, broad-market, clean-SPY-cap, Commodity-cap, "
            "DTE, and state-surface scalar/profile retunes because recent logs "
            "show repeated drawdown/sample failures or same-family gates. This "
            "tests a new production-visible OHLCV gap-share field instead of "
            "repeating downside-path, max20, or path-efficiency variables."
        ),
        "known_risks": [
            "Moderate multiple-testing risk because this is adjacent to recent OHLCV daily-return-path scouts.",
            "Older gap-vulnerability experiments used stop-distance, not historical overnight-gap path share.",
            "If accepted, production parity requires shared feature and sizing implementation before use.",
            "The 0x variant is effectively no-trade alpha and must clear trade-count and concentration guards.",
        ],
        "rejection_reason": None if passed else _rejection_reason(selected["gate4"]),
        "next_retry_requires": (
            [
                "Do not retry adjacent overnight_gap_share20 cutoffs or scalars on the same frozen windows without forward rows or a stronger replacement-value cohort.",
                "Prefer candidate-pool/replacement-value evidence over more local price-path threshold sweeps.",
            ]
            if not passed
            else [
                "Promote the field and risk policy into shared modules.",
                "Add parity/unit tests for production-visible feature and sizing metadata.",
                "Rerun the same three-window protocol after promotion before accepting.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260522_027_core_overnight_gap_share_haircut.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
    }

    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, payload)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    artifact = base._artifact(payload).replace(
        f"# {base.EXPERIMENT_ID} {base.STEM}",
        f"# {EXPERIMENT_ID} {STEM}",
        1,
    )
    ARTIFACT_MD.write_text(artifact, encoding="utf-8")
    base._append_jsonl(EXPERIMENT_LOG_JSONL, payload)
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
