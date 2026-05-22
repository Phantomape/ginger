"""exp-20260522-026: core low-downside-path top-up scout.

Alpha search. Tests whether already-qualified non-ETF/non-Commodity core stock
signals with bottom-quartile downside-path share over the prior 20 trading days
deserve a small cap-aware risk top-up.

This is the opposite economic side of exp-20260522-025's zero-touch scout: low
downside participation may indicate clean trend persistence rather than choppy
fragility. The only causal variable is the top-up multiplier.

This runner is experiment-only. If a variant passes Gate 4, promotion must move
the feature and sizing rule into shared production/backtest modules before any
production behavior changes.
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
import feature_layer as fl  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260522-026"
STEM = "core_low_downside_path_topup"
MULTIPLIER_KEY = "low_downside_path_share20_bottom_quartile_risk_multiplier_applied"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = core_helper.WINDOWS
VARIANTS = OrderedDict(
    [
        ("low_downside_share20_topup_1025", {"multiplier": 1.025}),
        ("low_downside_share20_topup_1050", {"multiplier": 1.05}),
        ("low_downside_share20_topup_1075", {"multiplier": 1.075}),
        ("low_downside_share20_topup_1100", {"multiplier": 1.10}),
    ]
)

BOTTOM_QUARTILE_FRACTION = 0.25
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


def _make_trend_feature_wrapper(original: Callable[..., dict[str, Any] | None]):
    def wrapped(data):
        features = original(data)
        if features is None:
            return None
        return {**features, **field_helper._downside_path_share20_features(data)}

    return wrapped


def _bottom_quartile_cutoff(features_dict: dict[str, Any]) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        if not isinstance(features, dict):
            continue
        sector = re.SECTOR_MAP.get(str(ticker).upper(), "Unknown")
        if sector in EXCLUDED_SECTORS:
            continue
        value = features.get("downside_path_share_20")
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return None
    values.sort()
    index = max(0, math.ceil(len(values) * BOTTOM_QUARTILE_FRACTION) - 1)
    return values[index]


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = _bottom_quartile_cutoff(features_dict)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            features = (features_dict or {}).get(ticker) or {}
            value = features.get("downside_path_share_20")
            sector = sig.get("sector") or re.SECTOR_MAP.get(ticker, "Unknown")
            sig["downside_path_share_20"] = value
            sig["downside_path_share_20_bottom_quartile_cutoff"] = (
                round(float(cutoff), 6) if isinstance(cutoff, (int, float)) else None
            )
            sig["low_downside_path_share_20_bottom_quartile_state"] = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and isinstance(value, (int, float))
                and isinstance(cutoff, (int, float))
                and float(value) <= float(cutoff)
            )
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("low_downside_path_share_20_bottom_quartile_state") is not True:
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

    cap_pct = float(sizing.get("max_position_pct_applied") or MAX_POSITION_PCT)
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
    sizing["low_downside_path_share20_bottom_quartile_state"] = True
    sizing["low_downside_path_share20_baseline_shares"] = old_shares
    sizing["low_downside_path_share20_desired_shares"] = desired_shares
    sizing["low_downside_path_share20_cap_shares"] = cap_shares
    sizing["low_downside_path_share20_new_shares"] = new_shares
    sizing["low_downside_path_share20_value"] = sig.get("downside_path_share_20")
    sizing["low_downside_path_share20_cutoff"] = sig.get(
        "downside_path_share_20_bottom_quartile_cutoff"
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
        "downside_path_share_20": sig.get("downside_path_share_20"),
        "cutoff": sig.get("downside_path_share_20_bottom_quartile_cutoff"),
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
    original_trend_features = fl.compute_trend_features
    original_enrich = re.enrich_signals
    original_size = pe.size_signals
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    ADJUSTMENTS.clear()
    if MULTIPLIER_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, MULTIPLIER_KEY)
    if multiplier is not None:
        fl.compute_trend_features = _make_trend_feature_wrapper(original_trend_features)
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
        fl.compute_trend_features = original_trend_features
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
        return "Best variant failed adjusted-signal sample guard."
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
            "Already-qualified core stock signals with bottom-quartile prior-20-day "
            "downside-path share have cleaner trend persistence. A small cap-aware "
            "risk top-up should improve expected_value_score without changing entry, "
            "exit, ranking, universe, news, or LLM logic."
        ),
        "change_summary": (
            "Add an experiment-only downside_path_share_20 OHLCV field and sweep "
            "a cap-aware top-up for non-ETF/non-Commodity core signals in the "
            "same-day bottom quartile of that field."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_daily_return_path",
        "trial_family": "core_low_downside_path_share20_risk",
        "trial_variant_id": selected["variant"],
        "changed_variable": "low_downside_path_share20_bottom_quartile_risk_multiplier",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260522-013",
            "exp-20260522-014",
            "exp-20260522-025",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "opposite_side_after_zero_touch",
        "component": "quant/feature_layer.py, quant/risk_engine.py, quant/portfolio_engine.py",
        "parameters": {
            "field": "downside_path_share_20",
            "field_definition": "sum(abs(negative close-to-close returns)) divided by sum(abs(all close-to-close returns)) over last 20 signal-known trading days",
            "bottom_quartile_fraction": BOTTOM_QUARTILE_FRACTION,
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
        "gate1": {
            "baseline_protocol": "docs/backtesting.md standard three non-overlapping windows",
            "baseline_artifact": str(OUT_JSON),
            "baseline_metrics_readable": True,
        },
        "gate2": {
            "field_check": field_check,
            "rule_dependencies": [
                "OHLCV Close series through signal day",
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
                "Move downside_path_share_20 feature, bottom-quartile state, and "
                "cap-aware top-up into shared feature_layer/risk_engine/portfolio_engine "
                "with tests, then rerun the same three-window protocol."
            ),
        },
        "why_not_other_changes": (
            "exp-20260522-025 showed high downside-path top quartile was a valid "
            "production-visible field but zero-touch. This run tests the opposite "
            "economic side instead of retrying LLM, SEC, broad-market, event, "
            "state-surface, clean-SPY, Commodity-cap, or DTE scalar lanes that "
            "recent logs mark as sparse or same-family high-risk."
        ),
        "known_risks": [
            "High multiple-testing risk because this is adjacent to recent OHLCV daily-return-path scouts.",
            "If accepted, production parity requires shared feature and sizing implementation before use.",
            "A small top-up can still be cap-bound and may not move executed shares.",
        ],
        "rejection_reason": None if passed else _rejection_reason(selected["gate4"]),
        "next_retry_requires": (
            [
                "Stop retrying daily-return-path allocation fields on the same frozen windows unless forward replacement-value rows arrive.",
                "Prefer candidate-pool or event replacement-value evidence over more local price-path threshold sweeps.",
            ]
            if not passed
            else [
                "Promote the field and risk policy into shared modules.",
                "Add parity/unit tests for production-visible feature and sizing metadata.",
                "Rerun the same three-window protocol after promotion before accepting.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260522_026_core_low_downside_path_topup.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
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
