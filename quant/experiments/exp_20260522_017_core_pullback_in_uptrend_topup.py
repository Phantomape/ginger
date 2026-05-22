"""exp-20260522-017: core pullback-in-uptrend top-up scout.

Alpha search. Tests whether already-qualified core stock signals in a
pullback_in_uptrend daily-return-path state deserve a small cap-aware risk
top-up. The state is built from signal-day-visible 20d and 5d close returns:
20d return > 0 and 5d return <= 0.

This runner uses experiment-only monkey patches. If a variant passes Gate 4,
promotion must move the feature and sizing rule into shared production/backtest
modules before any production behavior changes.
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
import feature_layer as fl  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260522-017"
STEM = "core_pullback_in_uptrend_topup"
MULTIPLIER_KEY = "pullback_in_uptrend_risk_multiplier_applied"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = core_helper.WINDOWS
VARIANTS = OrderedDict(
    [
        ("pullback_uptrend_topup_1025", {"multiplier": 1.025}),
        ("pullback_uptrend_topup_1050", {"multiplier": 1.05}),
        ("pullback_uptrend_topup_1075", {"multiplier": 1.075}),
        ("pullback_uptrend_topup_1100", {"multiplier": 1.10}),
    ]
)

EXCLUDED_SECTORS = {"ETF", "Commodities"}
TARGET_STATE = "pullback_in_uptrend"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_TRADE_COUNT_SUM = 58
MIN_SURVIVAL_RATE = 0.05
MIN_ADJUSTED_SIGNAL_COUNT = 4
MIN_CHANGED_TRADE_COUNT = 4
MIN_AFFECTED_WINDOW_COUNT = 2
MAX_SINGLE_POSITIVE_TICKER_SHARE = 0.50

ADJUSTMENTS: list[dict[str, Any]] = []


def _trade_key(trade: dict[str, Any]) -> str:
    return "|".join(
        str(trade.get(field) or "")
        for field in ("ticker", "entry_date", "strategy", "entry_price")
    )


def _json_write(path: Path, payload: dict[str, Any]) -> None:
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


def _open_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "checked_fields": ["entry_date", "target_price"],
            "missing_count": 0,
            "note": "No live open position file; this experiment does not add an exit rule.",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("positions", [])
    missing = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        absent = [
            field
            for field in ("entry_date", "target_price")
            if row.get(field) in (None, "")
        ]
        if absent:
            missing.append({"ticker": row.get("ticker"), "missing_fields": absent})
    return {
        "path": str(path),
        "exists": True,
        "checked_fields": ["entry_date", "target_price"],
        "position_count": len(rows or []),
        "missing_count": len(missing),
        "missing_examples": missing[:10],
        "note": "This allocation experiment does not depend on these fields.",
    }


def _daily_return_path_features(data) -> dict[str, Any]:
    if data is None or len(data) < 21:
        return {
            "ret5_pct_experiment": None,
            "ret20_pct_experiment": None,
            "reversal_vs_continuation_state": None,
            "reversal_vs_continuation_state_available": False,
        }
    close = data["Close"]
    latest = float(close.iloc[-1])
    close_5 = float(close.iloc[-6]) if len(close) >= 6 else None
    close_20 = float(close.iloc[-21]) if len(close) >= 21 else None
    ret5 = ((latest / close_5) - 1.0) if close_5 and close_5 > 0 else None
    ret20 = ((latest / close_20) - 1.0) if close_20 and close_20 > 0 else None
    state = None
    if ret5 is not None and ret20 is not None:
        if ret20 > 0.0 and ret5 <= 0.0:
            state = "pullback_in_uptrend"
        elif ret20 > 0.0 and ret5 > 0.0:
            state = "continuation"
        elif ret20 <= 0.0 and ret5 > 0.0:
            state = "countertrend_bounce"
        else:
            state = "downtrend_persistence"
    return {
        "ret5_pct_experiment": round(ret5, 6) if ret5 is not None else None,
        "ret20_pct_experiment": round(ret20, 6) if ret20 is not None else None,
        "reversal_vs_continuation_state": state,
        "reversal_vs_continuation_state_available": state is not None,
    }


def _make_trend_feature_wrapper(original: Callable[..., dict[str, Any] | None]):
    def wrapped(data):
        features = original(data)
        if features is None:
            return None
        return {**features, **_daily_return_path_features(data)}

    return wrapped


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            features = (features_dict or {}).get(ticker) or {}
            sector = sig.get("sector") or re.SECTOR_MAP.get(ticker, "Unknown")
            ret5 = features.get("ret5_pct_experiment")
            ret20 = features.get("ret20_pct_experiment")
            state = features.get("reversal_vs_continuation_state")
            sig["ret5_pct_experiment"] = ret5
            sig["ret20_pct_experiment"] = ret20
            sig["reversal_vs_continuation_state"] = state
            sig["pullback_in_uptrend_state"] = (
                sig.get("strategy") in {"trend_long", "breakout_long"}
                and sector not in EXCLUDED_SECTORS
                and state == TARGET_STATE
            )
        return enriched

    return wrapped


def _apply_topup_to_sizing(
    sig: dict[str, Any],
    multiplier: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if sig.get("pullback_in_uptrend_state") is not True:
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

    cap_shares = int(math.floor((portfolio_value * MAX_POSITION_PCT) / entry))
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
    sizing["pullback_in_uptrend_state"] = True
    sizing["pullback_in_uptrend_baseline_shares"] = old_shares
    sizing["pullback_in_uptrend_new_shares"] = new_shares
    sizing["pullback_in_uptrend_ret5_pct"] = sig.get("ret5_pct_experiment")
    sizing["pullback_in_uptrend_ret20_pct"] = sig.get("ret20_pct_experiment")
    sizing["reversal_vs_continuation_state"] = sig.get(
        "reversal_vs_continuation_state"
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
        "ret5_pct_experiment": sig.get("ret5_pct_experiment"),
        "ret20_pct_experiment": sig.get("ret20_pct_experiment"),
        "reversal_vs_continuation_state": sig.get("reversal_vs_continuation_state"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "regime_exit_score": sig.get("regime_exit_score"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
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


def _changed_trade_rows(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for label in WINDOWS:
        before_by_key = {_trade_key(row): row for row in before[label].get("trades") or []}
        after_by_key = {_trade_key(row): row for row in after[label].get("trades") or []}
        rows: list[dict[str, Any]] = []
        for key in sorted(set(before_by_key) | set(after_by_key)):
            old = before_by_key.get(key) or {}
            new = after_by_key.get(key) or {}
            old_shares = int(old.get("shares") or 0)
            new_shares = int(new.get("shares") or 0)
            old_pnl = float(old.get("pnl") or 0.0)
            new_pnl = float(new.get("pnl") or 0.0)
            delta = new_pnl - old_pnl
            if old_shares == new_shares and abs(delta) < 0.005:
                continue
            rows.append(
                {
                    "key": key,
                    "ticker": (new or old).get("ticker"),
                    "entry_date": (new or old).get("entry_date"),
                    "strategy": (new or old).get("strategy"),
                    "sector": (new or old).get("sector"),
                    "shares_before": old_shares,
                    "shares_after": new_shares,
                    "pnl_before": core_helper._round(old_pnl, 2),
                    "pnl_after": core_helper._round(new_pnl, 2),
                    "incremental_pnl": core_helper._round(delta, 2),
                }
            )
        out[label] = rows
    return out


def _concentration(changed: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = {}
    positive_total = 0.0
    for rows in changed.values():
        for row in rows:
            delta = float(row.get("incremental_pnl") or 0.0)
            if delta <= 0:
                continue
            ticker = str(row.get("ticker") or "UNKNOWN")
            positive_total += delta
            by_ticker[ticker] = by_ticker.get(ticker, 0.0) + delta
    if positive_total <= 0:
        return {
            "positive_incremental_pnl": 0.0,
            "max_single_positive_ticker_share": 0.0,
            "positive_incremental_pnl_by_ticker": {},
            "passed": True,
        }
    max_share = max(by_ticker.values()) / positive_total
    return {
        "positive_incremental_pnl": core_helper._round(positive_total, 2),
        "max_single_positive_ticker_share": core_helper._round(max_share, 6),
        "positive_incremental_pnl_by_ticker": {
            ticker: core_helper._round(value, 2)
            for ticker, value in sorted(by_ticker.items())
        },
        "passed": max_share <= MAX_SINGLE_POSITIVE_TICKER_SHARE,
    }


def _adjustment_summary(adjustments: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    tickers: set[str] = set()
    sectors: dict[str, int] = {}
    for rows in adjustments.values():
        for row in rows:
            if row.get("ticker"):
                tickers.add(str(row["ticker"]))
            sector = str(row.get("sector") or "Unknown")
            sectors[sector] = sectors.get(sector, 0) + 1
    return {
        "count": sum(len(rows) for rows in adjustments.values()),
        "window_counts": {label: len(rows) for label, rows in adjustments.items()},
        "unique_tickers": sorted(tickers),
        "sector_counts": dict(sorted(sectors.items())),
        "sample": {label: rows[:10] for label, rows in adjustments.items() if rows},
    }


def _gate4(
    before_results: dict[str, dict[str, Any]],
    after_results: dict[str, dict[str, Any]],
    adjustments: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    before_metrics = {
        label: core_helper._metrics(result) for label, result in before_results.items()
    }
    after_metrics = {
        label: core_helper._metrics(result) for label, result in after_results.items()
    }
    deltas = {
        label: core_helper._delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    agg_delta = core_helper._aggregate_delta(after_metrics, before_metrics)
    after_agg = core_helper._aggregate(after_metrics)
    improved_windows = [
        label
        for label, row in deltas.items()
        if float(row.get("expected_value_score") or 0.0) > 0.0
    ]
    regressed_windows = [
        label
        for label, row in deltas.items()
        if float(row.get("expected_value_score") or 0.0) < 0.0
    ]
    changed = _changed_trade_rows(before_results, after_results)
    changed_trade_count = sum(len(rows) for rows in changed.values())
    affected_window_count = sum(1 for rows in adjustments.values() if rows)
    adjusted_signal_count = sum(len(rows) for rows in adjustments.values())
    concentration = _concentration(changed)
    passed = (
        agg_delta["expected_value_score_sum"] > 0.0
        and agg_delta["total_pnl_sum"] > 0.0
        and len(improved_windows) >= 2
        and not regressed_windows
        and agg_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and after_agg["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and after_agg["survival_rate_min"] >= MIN_SURVIVAL_RATE
        and adjusted_signal_count >= MIN_ADJUSTED_SIGNAL_COUNT
        and changed_trade_count >= MIN_CHANGED_TRADE_COUNT
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
        and concentration["passed"]
    )
    return {
        "passed": bool(passed),
        "aggregate_delta": agg_delta,
        "window_deltas": deltas,
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "adjusted_signal_count": adjusted_signal_count,
        "changed_trade_count": changed_trade_count,
        "affected_window_count": affected_window_count,
        "changed_trades": {label: rows[:20] for label, rows in changed.items() if rows},
        "concentration": concentration,
        "guardrails": {
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "min_survival_rate": MIN_SURVIVAL_RATE,
            "min_adjusted_signal_count": MIN_ADJUSTED_SIGNAL_COUNT,
            "min_changed_trade_count": MIN_CHANGED_TRADE_COUNT,
            "min_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "max_single_positive_ticker_share": MAX_SINGLE_POSITIVE_TICKER_SHARE,
            "requires_no_ev_regression_windows": True,
        },
    }


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
            "## Selected window deltas",
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


def run() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    field_check = _open_position_field_check()
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
        gate4 = _gate4(baseline_results, after_results, adjustments)
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
            "adjustment_summary": _adjustment_summary(adjustments),
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
    rejection_reason = None
    if not passed:
        gate = selected["gate4"]
        if gate["adjusted_signal_count"] < MIN_ADJUSTED_SIGNAL_COUNT:
            rejection_reason = "Best variant failed adjusted-signal sample guard."
        elif gate["changed_trade_count"] < MIN_CHANGED_TRADE_COUNT:
            rejection_reason = "Best variant failed changed-trade materiality guard."
        elif gate["affected_window_count"] < MIN_AFFECTED_WINDOW_COUNT:
            rejection_reason = "Best variant failed affected-window sample guard."
        elif gate["regressed_windows"]:
            rejection_reason = (
                "Best variant failed Gate 4 because at least one fixed window "
                "regressed in expected_value_score."
            )
        elif not gate["concentration"]["passed"]:
            rejection_reason = (
                "Best variant failed concentration guard; positive incremental "
                "PnL was too ticker-concentrated."
            )
        else:
            rejection_reason = (
                "Best variant did not satisfy aggregate EV/PnL, risk, sample, "
                "and no-regression Gate 4 guardrails."
            )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Core stock signals that remain in a 20d uptrend but have stalled "
            "or pulled back over the last 5d may offer better follow-through "
            "than straight continuation entries. A small cap-aware risk top-up "
            "should improve EV without changing entry filters, ranking, exits, "
            "universe, LLM, or news logic."
        ),
        "change_summary": (
            "Add an experiment-only reversal_vs_continuation_state OHLCV field "
            "from signal-day 20d/5d returns and sweep a cap-aware risk "
            "multiplier for non-ETF/non-Commodity core signals in the "
            "pullback_in_uptrend state."
        ),
        "change_type": "capital_allocation",
        "mechanism_family": "core_daily_return_path",
        "trial_family": "core_reversal_vs_continuation_state_risk",
        "trial_variant_id": selected["variant"],
        "changed_variable": "pullback_in_uptrend_risk_multiplier",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260522-013",
            "exp-20260522-014",
            "exp-20260522-015",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_production_visible_field",
        "component": "quant/feature_layer.py, quant/risk_engine.py, quant/portfolio_engine.py",
        "parameters": {
            "field": "reversal_vs_continuation_state",
            "field_definition": (
                "signal-day state from ret20_pct_experiment > 0 and "
                "ret5_pct_experiment <= 0, alongside the other three 20d/5d "
                "path states"
            ),
            "target_state": TARGET_STATE,
            "state_definition_map": {
                "pullback_in_uptrend": "ret20 > 0 and ret5 <= 0",
                "continuation": "ret20 > 0 and ret5 > 0",
                "countertrend_bounce": "ret20 <= 0 and ret5 > 0",
                "downtrend_persistence": "ret20 <= 0 and ret5 <= 0",
            },
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
                "Move reversal_vs_continuation_state feature and pullback "
                "state-aware risk top-up into shared feature_layer/risk_engine/"
                "portfolio_engine plumbing with tests, then rerun the same "
                "three-window protocol."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking due sparse attribution, broad-market due "
            "identity drift, event/governance/source scalars due recent repeated "
            "drawdown/sample failures, state-surface profile/notional retunes due "
            "the strict same-family gate, and nearby max20/efficiency daily-return "
            "fields because they were already explored today."
        ),
        "known_risks": [
            "Even production-visible daily-return-path states can be too sparse after the current core filters and position caps.",
            "This replay-only field still needs shared implementation before any production sizing change is allowed.",
            "Cap-aware top-ups can be immaterial if existing core sizing is already at the default position cap.",
        ],
        "rejection_reason": rejection_reason,
        "next_retry_requires": (
            [
                "Do not retry adjacent pullback-in-uptrend multipliers on the same frozen windows without new rows or a broader return-path cohort definition.",
                "If reversal-vs-continuation remains interesting, try a different production-visible state family with enough qualified core signals first.",
            ]
            if not passed
            else [
                "Promote the state field and risk policy into shared modules.",
                "Add parity/unit tests for production-visible path-state metadata and sizing.",
                "Rerun the same three-window protocol after promotion before accepting.",
            ]
        ),
        "related_files": [
            "quant/experiments/exp_20260522_017_core_pullback_in_uptrend_topup.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
        ],
        "notes": "No JavaScript used. This is alpha_search, not measurement repair.",
    }

    _json_write(OUT_JSON, payload)
    _json_write(LOG_JSON, payload)
    _json_write(TICKET_JSON, payload)
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
