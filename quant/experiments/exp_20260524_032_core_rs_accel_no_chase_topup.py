"""exp-20260524-032: core RS-acceleration no-chase top-up scout.

Alpha search. Tests whether already-qualified core stock signals with improving
20-day SPY-relative strength versus the prior 20-day window, and without a
signal-day 3% upward gap chase, deserve a small cap-aware risk top-up.

The field is production-visible from OHLCV only. This runner is experiment-only:
if a variant passes Gate 4, promotion must move the feature/state/sizing rule
into shared production/backtest modules before any live/default behavior changes.

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
import feature_layer as fl  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as risk  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260524-032"
STEM = "core_rs_accel_no_chase_topup"
MULTIPLIER_KEY = "rs_accel_no_chase_risk_multiplier_applied"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = core_helper.WINDOWS
VARIANTS = OrderedDict(
    [
        ("rs_accel_no_chase_topup_10125", {"multiplier": 1.0125}),
        ("rs_accel_no_chase_topup_1025", {"multiplier": 1.025}),
        ("rs_accel_no_chase_topup_1050", {"multiplier": 1.05}),
        ("rs_accel_no_chase_topup_1075", {"multiplier": 1.075}),
    ]
)

RS_ACCEL_DELTA_MIN = 0.0
CURRENT_REL_SPY_MIN = 0.0
MAX_SIGNAL_DAY_GAP_UP_PCT = 0.03
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


def _pct_change(new: float, old: float) -> float | None:
    if old <= 0.0:
        return None
    return (new - old) / old


def _rs_accel_features(data) -> dict[str, Any]:
    if (
        data is None
        or len(data) < 41
        or "Open" not in data
        or "Close" not in data
    ):
        return {
            "momentum_prev20d_pct": None,
            "signal_day_open_gap_pct": None,
            "rs_accel_lookback_available": False,
        }

    close_now = float(data["Close"].iloc[-1])
    close_20d_ago = float(data["Close"].iloc[-21])
    close_40d_ago = float(data["Close"].iloc[-41])
    open_now = float(data["Open"].iloc[-1])
    close_prev = float(data["Close"].iloc[-2])

    prev20 = _pct_change(close_20d_ago, close_40d_ago)
    gap = _pct_change(open_now, close_prev)
    return {
        "momentum_prev20d_pct": round(prev20, 6) if prev20 is not None else None,
        "signal_day_open_gap_pct": round(gap, 6) if gap is not None else None,
        "rs_accel_lookback_available": prev20 is not None and gap is not None,
    }


def _make_trend_feature_wrapper(original: Callable[..., dict[str, Any] | None]):
    def wrapped(data):
        features = original(data)
        if features is None:
            return None
        return {**features, **_rs_accel_features(data)}

    return wrapped


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        spy_features = (features_dict or {}).get("SPY") or {}
        spy_cur20 = spy_features.get("momentum_20d_pct")
        spy_prev20 = spy_features.get("momentum_prev20d_pct")

        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            features = (features_dict or {}).get(ticker) or {}
            cur20 = features.get("momentum_20d_pct")
            prev20 = features.get("momentum_prev20d_pct")
            gap = features.get("signal_day_open_gap_pct")
            sector = sig.get("sector") or risk.SECTOR_MAP.get(ticker, "Unknown")

            current_rel_spy = None
            previous_rel_spy = None
            rs_accel_delta = None
            if all(
                isinstance(value, (int, float))
                for value in (cur20, prev20, spy_cur20, spy_prev20)
            ):
                current_rel_spy = float(cur20) - float(spy_cur20)
                previous_rel_spy = float(prev20) - float(spy_prev20)
                rs_accel_delta = current_rel_spy - previous_rel_spy

            no_gap_chase = isinstance(gap, (int, float)) and float(gap) < MAX_SIGNAL_DAY_GAP_UP_PCT
            state = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and isinstance(current_rel_spy, (int, float))
                and isinstance(rs_accel_delta, (int, float))
                and current_rel_spy > CURRENT_REL_SPY_MIN
                and rs_accel_delta > RS_ACCEL_DELTA_MIN
                and no_gap_chase
            )

            sig["rs_accel_no_chase_state"] = bool(state)
            sig["rs_accel_current_rel_spy_20d"] = (
                round(current_rel_spy, 6) if isinstance(current_rel_spy, (int, float)) else None
            )
            sig["rs_accel_previous_rel_spy_20d"] = (
                round(previous_rel_spy, 6) if isinstance(previous_rel_spy, (int, float)) else None
            )
            sig["rs_accel_delta_20d"] = (
                round(rs_accel_delta, 6) if isinstance(rs_accel_delta, (int, float)) else None
            )
            sig["rs_accel_delta_min"] = RS_ACCEL_DELTA_MIN
            sig["current_rel_spy_min"] = CURRENT_REL_SPY_MIN
            sig["signal_day_open_gap_pct"] = gap
            sig["max_signal_day_gap_up_pct"] = MAX_SIGNAL_DAY_GAP_UP_PCT
            sig["rs_accel_no_gap_chase"] = bool(no_gap_chase)
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("rs_accel_no_chase_state") is not True:
        return sig, None

    sizing = dict(sig.get("sizing") or {})
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return sig, None

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    portfolio_value = float(sizing.get("portfolio_value_usd") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    if entry <= 0.0 or portfolio_value <= 0.0 or net_risk_per_share <= 0.0:
        return sig, None

    cap_shares = int(math.floor((portfolio_value * gate_helper.MAX_POSITION_PCT) / entry))
    new_shares = min(int(math.floor(old_shares * multiplier)), cap_shares)
    if new_shares <= old_shares:
        return sig, None

    risk_amount = new_shares * net_risk_per_share
    position_value = new_shares * entry
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = round(position_value / portfolio_value, 4)
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    sizing["rs_accel_no_chase_state"] = True
    sizing["rs_accel_no_chase_baseline_shares"] = old_shares
    sizing["rs_accel_no_chase_new_shares"] = new_shares
    sizing["rs_accel_delta_20d"] = sig.get("rs_accel_delta_20d")
    sizing["rs_accel_current_rel_spy_20d"] = sig.get("rs_accel_current_rel_spy_20d")
    sizing["signal_day_open_gap_pct"] = sig.get("signal_day_open_gap_pct")
    sizing[MULTIPLIER_KEY] = multiplier
    sig = {**sig, "sizing": sizing}

    record = {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "baseline_shares": old_shares,
        "new_shares": new_shares,
        "multiplier": multiplier,
        "rs_accel_delta_20d": sig.get("rs_accel_delta_20d"),
        "current_rel_spy_20d": sig.get("rs_accel_current_rel_spy_20d"),
        "previous_rel_spy_20d": sig.get("rs_accel_previous_rel_spy_20d"),
        "signal_day_open_gap_pct": sig.get("signal_day_open_gap_pct"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "spy_relative_leader": sig.get("spy_relative_leader"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
        "signal_day_ticker_outperformed_spy": sig.get("signal_day_ticker_outperformed_spy"),
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
    original_enrich = risk.enrich_signals
    original_size = pe.size_signals
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    ADJUSTMENTS.clear()
    if MULTIPLIER_KEY not in bt.SIZING_MULTIPLIER_KEYS:
        bt.SIZING_MULTIPLIER_KEYS = (*bt.SIZING_MULTIPLIER_KEYS, MULTIPLIER_KEY)
    if multiplier is not None:
        fl.compute_trend_features = _make_trend_feature_wrapper(original_trend_features)
        risk.enrich_signals = _make_enrich_wrapper(original_enrich)
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
        risk.enrich_signals = original_enrich
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


def _rejection_reason(gate: dict[str, Any]) -> str:
    if gate["adjusted_signal_count"] < gate["guardrails"]["min_adjusted_signal_count"]:
        return "Best variant failed sample guard; rs_accel_no_chase touched too few sized signals."
    if gate["changed_trade_count"] < gate["guardrails"]["min_changed_trade_count"]:
        return "Best variant failed changed-trade guard; top-up did not materially alter enough fills."
    if gate["regressed_windows"]:
        return "Best variant failed Gate 4 because at least one fixed window regressed in EV."
    if not gate["concentration"]["passed"]:
        return "Best variant failed concentration guard; positive incremental PnL was too ticker-concentrated."
    return "Best variant did not satisfy aggregate EV/PnL, risk, sample, and no-regression Gate 4 guardrails."


def _artifact(payload: dict[str, Any]) -> str:
    agg_delta = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Decision",
        f"- decision: {payload['decision']}",
        f"- selected_variant: {payload['trial_variant_id']}",
        f"- gate4_passed: {gate4['passed']}",
        f"- aggregate_ev_delta: {agg_delta['expected_value_score_sum']}",
        f"- aggregate_pnl_delta: {agg_delta['total_pnl_sum']}",
        f"- improved_windows: {', '.join(gate4['improved_windows']) or 'none'}",
        f"- regressed_windows: {', '.join(gate4['regressed_windows']) or 'none'}",
        "",
        "## Production Impact",
        json.dumps(payload["production_impact"], indent=2, sort_keys=True),
        "",
        "## Gate Questions",
        json.dumps(payload["gate_questions"], indent=2, sort_keys=True),
        "",
        "## Gate 4",
        json.dumps(gate4, indent=2, sort_keys=True),
        "",
        "## Sweep Summary",
        json.dumps(payload["sweep_summary"], indent=2, sort_keys=True),
        "",
    ]
    return "\n".join(lines)


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    field_check = field_helper._open_position_field_check()
    baseline_results = _run_baseline()
    before_metrics = {
        label: core_helper._metrics(result)
        for label, result in baseline_results.items()
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
            "after_results": after_results,
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
            "Already-qualified core stock signals with improving 20-day "
            "SPY-relative strength versus the prior 20-day window, while not "
            "opening with a 3% signal-day gap chase, may be cleaner continuation "
            "setups. A small cap-aware post-sizing top-up could improve EV "
            "without changing entries, exits, ranking, universe, news, or LLM."
        ),
        "change_summary": (
            "Add an experiment-only OHLCV field rs_accel_no_chase and sweep a "
            "cap-aware risk multiplier for non-ETF/non-Commodity core "
            "trend_long/breakout_long signals matching that state."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_relative_strength_acceleration",
        "trial_family": "core_rs_accel_no_chase_risk",
        "trial_variant_id": selected["variant"],
        "changed_variable": "rs_accel_no_chase_risk_multiplier",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260508-029",
            "exp-20260524-003",
            "exp-20260524-011",
            "exp-20260524-018",
            "exp-20260524-019",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_relative_strength_acceleration_field",
        "component": "quant/feature_layer.py, quant/risk_engine.py, quant/portfolio_engine.py",
        "parameters": {
            "field": "rs_accel_no_chase",
            "field_definition": (
                "(ticker_ret20 - spy_ret20) > (ticker_prev20 - spy_prev20), "
                "current ticker_ret20_minus_spy > 0, and signal-day open gap < 3%"
            ),
            "rs_accel_delta_min": RS_ACCEL_DELTA_MIN,
            "current_rel_spy_min": CURRENT_REL_SPY_MIN,
            "max_signal_day_gap_up_pct": MAX_SIGNAL_DAY_GAP_UP_PCT,
            "excluded_sectors": sorted(EXCLUDED_SECTORS),
            "baseline_multiplier": 1.0,
            "swept_multipliers": [params["multiplier"] for params in VARIANTS.values()],
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
            "aggregate": core_helper._aggregate_delta(selected_after_metrics, before_metrics),
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
                "OHLCV Open/Close through signal day",
                "SPY OHLCV through signal day",
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
            "survival_rate_min_before": core_helper._aggregate(before_metrics)["survival_rate_min"],
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
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Core allocation: RS acceleration versus SPY plus no 3% signal-day "
                "gap chase may identify cleaner continuation among already-qualified "
                "trend_long/breakout_long stock signals. This matches the playbook's "
                "new production-visible field preference."
            ),
            "2_history_check": {
                "exp-20260508-029": "Proposed shadow tag only; not yet completed.",
                "exp-20260524-003": "Relative-strength component band top-up was too sparse.",
                "exp-20260524-011": "Raw trend component top-up regressed and concentrated.",
                "exp-20260524-018": "Alpha/breadth midpoint top-up had too little changed sample.",
                "exp-20260524-019": "Signal-day close-location top-up regressed aggregate EV.",
            },
            "3_single_causal_variable": (
                "Only the post-sizing multiplier for the fixed rs_accel_no_chase "
                "state changes; all entries, exits, ranking, slots, universe, LLM, "
                "and news logic stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md canonical three-window before/after, requiring "
                "positive aggregate EV/PnL, at least two EV-improved windows, no "
                "EV-regressed windows, drawdown/survival/trade-count/sample guards, "
                "and concentration guard pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260524_032_core_rs_accel_no_chase_topup.py"
            ),
        },
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
                "Move rs_accel_no_chase feature/state/sizing into shared "
                "feature_layer/risk_engine/portfolio_engine with parity tests, "
                "then rerun the same three-window protocol before live/default use."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because attribution remains sparse; skipped "
            "SEC/event/state-surface/broad-market scalar retunes due recent "
            "anti-repeat gates; skipped direct candidate-pool expansion because "
            "recent governed cohorts failed sample, concentration, or old_thin."
        ),
        "known_risks": [
            "Moderate multiple-testing risk because RS and entry-day OHLCV fields have nearby failed tests.",
            "The field may overlap with accepted SPY-relative and green-candle sizing helpers.",
            "A positive replay-only result still cannot be promoted without shared policy/parity work.",
        ],
        "rejection_reason": None if passed else _rejection_reason(selected["gate4"]),
        "next_retry_requires": (
            [
                "Do not retry adjacent RS-acceleration/no-chase cutoffs or scalars on these frozen windows without forward rows or replacement-value evidence.",
                "If revisiting RS acceleration, prefer a broader candidate-pool or displacement-value study rather than another local top-up.",
            ]
            if not passed
            else [
                "Promote the field and risk policy into shared modules.",
                "Add parity/unit tests for production-visible feature and sizing metadata.",
                "Rerun the same three-window protocol after promotion before accepting.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260524_032_core_rs_accel_no_chase_topup.py",
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
