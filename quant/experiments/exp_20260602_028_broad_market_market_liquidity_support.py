"""exp-20260602-028: broad-market market-liquidity support scout.

Alpha search. Replays the accepted exp-20260520-004 broad-market default-off
paper sleeve and tests one causal variable: a free-OHLCV market-liquidity
regime support scalar for already-selected paper trades.

The accepted broad-market candidate definition, rank profile, low-extension,
high-volatility, trend-persistence support, hold period, entry slots, and
universe remain fixed. This run changes no shared production/backtest adapter;
positive evidence would still require a shared helper before retention.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260602-028"
EXPERIMENT_SLUG = "broad_market_market_liquidity_support"
SOURCE_EXPERIMENT_ID = "exp-20260520-004"
SOURCE_SLUG = "broad_market_trend_persistence_notional"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
RULE_VERSION = "broad_market_orderly_market_liquidity_support_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
import exp_20260520_004_broad_market_trend_persistence_notional as e004  # noqa: E402
import exp_20260527_901_broad_market_sector_open_crowding_haircut as prior  # noqa: E402


WINDOWS = e004.WINDOWS
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / f"{SOURCE_SLUG}.json"
)
CONTROL_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / CONTROL_EXPERIMENT_ID
    / "broad_market_shared_paper_adapter.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
BEFORE_AGG_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}_before_aggregate.json"
AFTER_AGG_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "baseline_no_market_liquidity_support"
MARKET_LIQUIDITY_SWEEP: OrderedDict[str, dict[str, float]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "min_liquidity_ratio_20_60": 0.0,
                "avg_range20_max": 99.0,
                "current_max_range_max": 99.0,
                "scalar": 1.0,
            },
        ),
        (
            "minliq0p90_range20lte0p022_currlte0p030_scalar1p05",
            {
                "min_liquidity_ratio_20_60": 0.90,
                "avg_range20_max": 0.022,
                "current_max_range_max": 0.030,
                "scalar": 1.05,
            },
        ),
        (
            "minliq1p00_range20lte0p022_currlte0p030_scalar1p05",
            {
                "min_liquidity_ratio_20_60": 1.00,
                "avg_range20_max": 0.022,
                "current_max_range_max": 0.030,
                "scalar": 1.05,
            },
        ),
        (
            "minliq0p90_range20lte0p026_currlte0p035_scalar1p05",
            {
                "min_liquidity_ratio_20_60": 0.90,
                "avg_range20_max": 0.026,
                "current_max_range_max": 0.035,
                "scalar": 1.05,
            },
        ),
        (
            "minliq1p00_range20lte0p026_currlte0p035_scalar1p05",
            {
                "min_liquidity_ratio_20_60": 1.00,
                "avg_range20_max": 0.026,
                "current_max_range_max": 0.035,
                "scalar": 1.05,
            },
        ),
        (
            "minliq0p90_range20lte0p030_currlte0p040_scalar1p05",
            {
                "min_liquidity_ratio_20_60": 0.90,
                "avg_range20_max": 0.030,
                "current_max_range_max": 0.040,
                "scalar": 1.05,
            },
        ),
        (
            "minliq1p00_range20lte0p030_currlte0p040_scalar1p05",
            {
                "min_liquidity_ratio_20_60": 1.00,
                "avg_range20_max": 0.030,
                "current_max_range_max": 0.040,
                "scalar": 1.05,
            },
        ),
    ]
)

MIN_ADJUSTED_TRADES = 8
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_snapshot_benchmark_rows(prices: dict[str, list[dict[str, Any]]]) -> None:
    by_ticker: dict[str, dict[str, dict[str, Any]]] = {
        ticker: {str(row.get("date") or ""): dict(row) for row in rows}
        for ticker, rows in prices.items()
    }
    for spec in WINDOWS.values():
        snapshot_path = REPO_ROOT / str(spec["snapshot"])
        snapshot = _json_load(snapshot_path)
        ohlcv = snapshot.get("ohlcv") or {}
        for ticker in ("SPY", "QQQ", "IWM"):
            rows = ohlcv.get(ticker) or []
            ticker_rows = by_ticker.setdefault(ticker, {})
            for row in rows:
                day = str(row.get("date") or row.get("Date") or "")[:10]
                if not day:
                    continue
                ticker_rows[day] = {
                    "date": day,
                    "open": float(row.get("open", row.get("Open"))),
                    "high": float(row.get("high", row.get("High"))),
                    "low": float(row.get("low", row.get("Low"))),
                    "close": float(row.get("close", row.get("Close"))),
                    "volume": float(row.get("volume", row.get("Volume"))),
                }
    for ticker, rows_by_date in by_ticker.items():
        prices[ticker] = [
            rows_by_date[day]
            for day in sorted(rows_by_date)
            if day
        ]


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _judge_aggregate(row: dict[str, Any]) -> dict[str, Any]:
    total_pnl = float(row.get("total_pnl_sum") or 0.0)
    return {
        "benchmarks": {
            "strategy_total_return_pct": round(total_pnl / 100_000.0, 4),
        },
        "expected_value_score": row.get("expected_value_score_sum"),
        "max_drawdown_pct": row.get("max_drawdown_pct_max"),
        "sharpe_daily": None,
        "survival_rate": row.get("survival_rate_min"),
        "total_pnl": row.get("total_pnl_sum"),
        "total_trades": row.get("trade_count_sum"),
        "win_rate": None,
    }


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0.0 or not math.isfinite(parsed):
        return None
    return parsed


def _rolling_values(
    rows: list[dict[str, Any]],
    idx: int,
    *,
    lookback: int,
    field: str,
) -> list[float] | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for cursor in range(idx - lookback + 1, idx + 1):
        if field == "dollar_volume":
            close = _positive_float(rows[cursor].get("close"))
            volume = _positive_float(rows[cursor].get("volume"))
            if close is None or volume is None:
                return None
            values.append(close * volume)
        elif field == "range_pct":
            high = _positive_float(rows[cursor].get("high"))
            low = _positive_float(rows[cursor].get("low"))
            close = _positive_float(rows[cursor].get("close"))
            if high is None or low is None or close is None:
                return None
            values.append(max(0.0, (high - low) / close))
        else:
            raise ValueError(f"unsupported field: {field}")
    return values if len(values) == lookback else None


def _market_liquidity_state(
    *,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    decision_date: str,
) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    liquidity_ratios: list[float] = []
    range20_values: list[float] = []
    current_ranges: list[float] = []
    missing: list[str] = []

    for ticker in ("SPY", "QQQ", "IWM"):
        rows = prices.get(ticker) or []
        idx = (indexes.get(ticker) or {}).get(decision_date)
        if idx is None:
            missing.append(ticker)
            continue
        dv20 = _rolling_values(rows, idx, lookback=20, field="dollar_volume")
        dv60 = _rolling_values(rows, idx, lookback=60, field="dollar_volume")
        range20 = _rolling_values(rows, idx, lookback=20, field="range_pct")
        current_range = _rolling_values(rows, idx, lookback=1, field="range_pct")
        if not dv20 or not dv60 or not range20 or not current_range:
            missing.append(ticker)
            continue
        avg_dv20 = sum(dv20) / len(dv20)
        avg_dv60 = sum(dv60) / len(dv60)
        ratio = avg_dv20 / avg_dv60 if avg_dv60 > 0.0 else None
        if ratio is None:
            missing.append(ticker)
            continue
        avg_range20 = sum(range20) / len(range20)
        current = current_range[-1]
        components[ticker] = {
            "avg_dollar_volume_20": round(avg_dv20, 2),
            "avg_dollar_volume_60": round(avg_dv60, 2),
            "liquidity_ratio_20_60": round(ratio, 6),
            "avg_range20_pct": round(avg_range20, 6),
            "current_range_pct": round(current, 6),
        }
        liquidity_ratios.append(ratio)
        range20_values.append(avg_range20)
        current_ranges.append(current)

    if missing:
        return {
            "available": False,
            "decision_date": decision_date,
            "missing": sorted(missing),
            "components": components,
        }
    return {
        "available": True,
        "decision_date": decision_date,
        "components": components,
        "min_liquidity_ratio_20_60": round(min(liquidity_ratios), 6),
        "avg_range20_pct": round(sum(range20_values) / len(range20_values), 6),
        "current_max_range_pct": round(max(current_ranges), 6),
    }


def _passes_market_liquidity(
    state: dict[str, Any],
    *,
    min_liquidity_ratio_20_60: float,
    avg_range20_max: float,
    current_max_range_max: float,
) -> bool:
    if not state.get("available"):
        return False
    return bool(
        float(state["min_liquidity_ratio_20_60"]) >= min_liquidity_ratio_20_60
        and float(state["avg_range20_pct"]) <= avg_range20_max
        and float(state["current_max_range_pct"]) <= current_max_range_max
    )


def _scale_trade_notional(
    trade: dict[str, Any],
    *,
    scalar: float,
    applied: bool,
    market_state: dict[str, Any],
    variant: dict[str, float],
) -> dict[str, Any]:
    out = dict(trade)
    original_notional = float(out.get("notional") or 0.0)
    original_shares = float(out.get("shares") or 0.0)
    original_pnl = float(out.get("pnl") or 0.0)
    effective_scalar = float(scalar) if applied else 1.0
    out["pre_market_liquidity_notional"] = round(original_notional, 2)
    out["pre_market_liquidity_shares"] = round(original_shares, 8)
    out["pre_market_liquidity_pnl"] = round(original_pnl, 2)
    out["market_liquidity_support_rule_version"] = RULE_VERSION
    out["market_liquidity_support_applied"] = bool(applied)
    out["market_liquidity_support_scalar"] = round(effective_scalar, 6)
    out["market_liquidity_state"] = market_state
    out["market_liquidity_thresholds"] = {
        "min_liquidity_ratio_20_60": variant["min_liquidity_ratio_20_60"],
        "avg_range20_max": variant["avg_range20_max"],
        "current_max_range_max": variant["current_max_range_max"],
    }
    out["notional"] = round(original_notional * effective_scalar, 2)
    out["shares"] = round(original_shares * effective_scalar, 8)
    out["pnl"] = round(original_pnl * effective_scalar, 2)
    return out


def _apply_market_liquidity_support(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    variant: dict[str, float],
) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for raw in trades:
        state = _market_liquidity_state(
            prices=prices,
            indexes=indexes,
            decision_date=str(raw.get("decision_date") or ""),
        )
        applied = bool(
            float(variant["scalar"]) > 1.0
            and _passes_market_liquidity(
                state,
                min_liquidity_ratio_20_60=float(variant["min_liquidity_ratio_20_60"]),
                avg_range20_max=float(variant["avg_range20_max"]),
                current_max_range_max=float(variant["current_max_range_max"]),
            )
        )
        adjusted.append(
            _scale_trade_notional(
                raw,
                scalar=float(variant["scalar"]),
                applied=applied,
                market_state=state,
                variant=variant,
            )
        )
    return adjusted


def _trade_rows(trades: list[dict[str, Any]], *, limit: int = 40) -> list[dict[str, Any]]:
    rows = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        state = trade.get("market_liquidity_state") or {}
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade.get("window"),
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "notional": trade.get("notional"),
                "pre_market_liquidity_notional": trade.get("pre_market_liquidity_notional"),
                "pnl": trade.get("pnl"),
                "pre_market_liquidity_pnl": trade.get("pre_market_liquidity_pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "market_liquidity_support_applied": trade.get("market_liquidity_support_applied"),
                "market_liquidity_support_scalar": trade.get("market_liquidity_support_scalar"),
                "min_liquidity_ratio_20_60": state.get("min_liquidity_ratio_20_60"),
                "avg_range20_pct": state.get("avg_range20_pct"),
                "current_max_range_pct": state.get("current_max_range_pct"),
                "ret20_excess_spy": trade.get("ret20_excess_spy"),
                "ret60": trade.get("ret60"),
                "ret5": trade.get("ret5"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "realized_volatility_20": trade.get("realized_volatility_20"),
            }
        )
    return rows


def _state_bucket(trade: dict[str, Any]) -> str:
    state = trade.get("market_liquidity_state") or {}
    if not state.get("available"):
        return "missing"
    ratio = float(state.get("min_liquidity_ratio_20_60") or 0.0)
    avg_range = float(state.get("avg_range20_pct") or 0.0)
    if ratio >= 1.0 and avg_range <= 0.022:
        return "strong_liquid_orderly"
    if ratio >= 0.9 and avg_range <= 0.026:
        return "liquid_orderly"
    if avg_range <= 0.030:
        return "orderly"
    return "noisy_or_illiquid"


def _bucket_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(_state_bucket(row) for row in trades)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _bucket_pnl(trades: list[dict[str, Any]]) -> dict[str, float]:
    pnl: dict[str, float] = {}
    for trade in trades:
        bucket = _state_bucket(trade)
        pnl[bucket] = pnl.get(bucket, 0.0) + float(trade.get("pnl") or 0.0)
    return {
        bucket: round(value, 2)
        for bucket, value in sorted(pnl.items(), key=lambda item: (-item[1], item[0]))
    }


def _window_sleeve_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    adjusted = [row for row in trades if row.get("market_liquidity_support_applied")]
    pre_adjusted_pnl = sum(float(row.get("pre_market_liquidity_pnl") or 0.0) for row in adjusted)
    adjusted_pnl = sum(float(row.get("pnl") or 0.0) for row in adjusted)
    pre_notional = sum(float(row.get("pre_market_liquidity_notional") or 0.0) for row in adjusted)
    post_notional = sum(float(row.get("notional") or 0.0) for row in adjusted)
    wins = sum(1 for row in trades if float(row.get("pnl") or 0.0) > 0.0)
    return {
        "trade_count": len(trades),
        "pnl": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "market_liquidity_adjusted_trade_count": len(adjusted),
        "market_liquidity_pre_adjusted_pnl": round(pre_adjusted_pnl, 2),
        "market_liquidity_adjusted_pnl": round(adjusted_pnl, 2),
        "market_liquidity_incremental_pnl": round(adjusted_pnl - pre_adjusted_pnl, 2),
        "market_liquidity_notional_added": round(post_notional - pre_notional, 2),
        "state_bucket_counts": _bucket_counts(trades),
        "state_bucket_pnl": _bucket_pnl(trades),
        "adjusted_state_bucket_counts": _bucket_counts(adjusted),
        "sample_trades": _trade_rows(trades, limit=25),
        "adjusted_trades_sample": _trade_rows(adjusted, limit=25),
    }


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, float],
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    baseline_replay_parity_passed: bool,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        adjusted_trades = _apply_market_liquidity_support(
            baseline_trades_by_window[label],
            prices=prices,
            indexes=indexes,
            variant=variant,
        )
        for trade in adjusted_trades:
            trade["window"] = label
        all_trades.extend(adjusted_trades)
        curve = p35._event_equity_curve(
            trades=adjusted_trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = p35._metrics_from_overlay(
            baseline_metrics=control_metrics[label],
            event_curve=curve,
            event_trades=adjusted_trades,
        )
        sleeve[label] = _window_sleeve_summary(adjusted_trades)

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    adjusted = [row for row in all_trades if row.get("market_liquidity_support_applied")]
    adjusted_windows = sorted({row["window"] for row in adjusted})
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    sample_guard_passed = len(all_trades) >= p35.MIN_SELECTED_TRADES
    adjusted_guard_passed = len(adjusted) >= MIN_ADJUSTED_TRADES and len(adjusted_windows) >= MIN_ADJUSTED_WINDOWS
    window_guard_passed = selected_windows >= p35.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= p35.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= p35.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= p35.MAX_DRAWDOWN_WORSE
    gate4_passed = bool(
        variant_name != BASELINE_VARIANT
        and baseline_replay_parity_passed
        and delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    return {
        "variant_name": variant_name,
        "variant": variant,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
        "pre_adjusted_pnl": round(
            sum(float(row.get("pre_market_liquidity_pnl") or 0.0) for row in adjusted),
            2,
        ),
        "adjusted_pnl": round(sum(float(row.get("pnl") or 0.0) for row in adjusted), 2),
        "notional_added": round(
            sum(
                float(row.get("notional") or 0.0)
                - float(row.get("pre_market_liquidity_notional") or 0.0)
                for row in adjusted
            ),
            2,
        ),
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "state_bucket_counts": _bucket_counts(all_trades),
        "state_bucket_pnl": _bucket_pnl(all_trades),
        "adjusted_state_bucket_counts": _bucket_counts(adjusted),
        "selected_trades_sample": _trade_rows(all_trades, limit=60),
        "adjusted_trades_sample": _trade_rows(adjusted, limit=40),
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "windows_ev_improved": delta["windows_ev_improved"],
            "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
            "windows_ev_regressed": delta["windows_ev_regressed"],
            "windows_pnl_improved": delta["windows_pnl_improved"],
            "windows_pnl_regressed": delta["windows_pnl_regressed"],
            "selected_trade_count": len(all_trades),
            "minimum_selected_trades": p35.MIN_SELECTED_TRADES,
            "sample_guard_passed": sample_guard_passed,
            "adjusted_trade_count": len(adjusted),
            "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
            "adjusted_windows": adjusted_windows,
            "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
            "adjusted_guard_passed": adjusted_guard_passed,
            "selected_windows": selected_windows,
            "minimum_selected_windows": p35.MIN_SELECTED_WINDOWS,
            "window_guard_passed": window_guard_passed,
            "single_ticker_positive_share": single_share,
            "max_single_ticker_positive_share": p35.MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "top5_positive_share": top5_share,
            "max_top5_positive_share": p35.MAX_TOP5_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
            "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": p35.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
            "baseline_replay_parity_passed": baseline_replay_parity_passed,
        },
    }


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or [row for row in variants if row["variant_name"] != BASELINE_VARIANT]
    return sorted(
        pool,
        key=lambda row: (
            bool(row["gate4"]["passed"]),
            float(row["delta_metrics"]["aggregate_ev_delta"]),
            float(row["delta_metrics"]["aggregate_pnl_delta"]),
            -float(row["gate4"]["max_drawdown_worse_max"]),
        ),
        reverse=True,
    )[0]


def _sweep_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": row["variant_name"],
            "variant": row["variant"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "adjusted_trade_count": row["adjusted_trade_count"],
            "adjusted_windows": row["adjusted_windows"],
            "pre_adjusted_pnl": row["pre_adjusted_pnl"],
            "adjusted_pnl": row["adjusted_pnl"],
            "notional_added": row["notional_added"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "state_bucket_counts": row["state_bucket_counts"],
            "adjusted_state_bucket_counts": row["adjusted_state_bucket_counts"],
            "event_risk": row["event_risk"],
        }
        for row in variants
    ]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Market-Liquidity Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: default-off paper-notional support for already-selected",
        "broad-market paper entries when SPY/QQQ/IWM show adequate 20d/60d",
        "liquidity participation and orderly 20d/current range.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Max DD Worse |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {gate} | {adjusted} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {pr} | {dd:+.4%} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                adjusted=row["adjusted_trade_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                pr=row["windows_pnl_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Evidence",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted Trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["broad_market_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {adj} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
                adj=sleeve["market_liquidity_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Baseline Replay Parity",
            "",
            "```json",
            json.dumps(payload["baseline_replay_parity"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    if not SOURCE_JSON.exists():
        raise RuntimeError(f"Missing source artifact: {_repo_rel(SOURCE_JSON)}")
    if not CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {_repo_rel(CONTROL_JSON)}")
    gate2 = p35._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_payload = _json_load(SOURCE_JSON)
    control_payload = _json_load(CONTROL_JSON)
    if source_payload.get("decision") != "accepted_default_off_broad_market_trend_persistence_notional":
        raise RuntimeError(f"Unexpected source decision: {source_payload.get('decision')}")

    before_metrics = source_payload["after_metrics"]
    control_metrics = control_payload["before_metrics"]
    baseline = prior._resimulate_source_baseline(source_payload)
    benchmark_tickers = sorted(set(baseline["candidate_tickers"]) | {"SPY", "QQQ", "IWM"})
    prices = p35._load_price_rows(benchmark_tickers)
    for ticker in baseline["candidate_tickers"]:
        if ticker in baseline["prices"]:
            prices[ticker] = baseline["prices"][ticker]
    _merge_snapshot_benchmark_rows(prices)
    indexes = p35._index_by_date(prices)
    variants = [
        _variant_payload(
            variant_name=name,
            variant=values,
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            baseline_trades_by_window=baseline["trades_by_window"],
            prices=prices,
            indexes=indexes,
            baseline_replay_parity_passed=baseline["parity_passed"],
        )
        for name, values in MARKET_LIQUIDITY_SWEEP.items()
    ]
    selected = _choose_selected(variants)
    gate4_passed = bool(selected["gate4"]["passed"])
    status = "observed_only" if gate4_passed else "rejected"
    decision = (
        "observed_positive_broad_market_market_liquidity_support_requires_shared_adapter"
        if gate4_passed
        else "rejected_broad_market_market_liquidity_support"
    )

    aggregate_before = p35._aggregate(before_metrics)
    aggregate_after = p35._aggregate(selected["after_metrics"])
    gate3 = {
        "signals_generated": {
            label: before_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: before_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: before_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; selected broad-market paper trades stay unchanged.",
    }
    baseline_replay_parity = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "passed": baseline["parity_passed"],
        "source_pnl_by_window": baseline["source_pnl_by_window"],
        "replayed_pnl_by_window": baseline["baseline_pnl_by_window"],
        "pnl_drift": baseline["pnl_drift"],
        "source_trade_count_by_window": baseline["source_trade_count_by_window"],
        "replayed_trade_count_by_window": baseline["baseline_trade_count_by_window"],
        "trade_count_drift": baseline["trade_count_drift"],
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "default_off_paper_only": True,
        "research_replay_alters_paper_notional": True,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "promotion_blocker": (
            "If positive, implement the same market-liquidity regime through a shared "
            "default-off broad-market paper helper before retention. This run does not "
            "create production/backtest behavior divergence because it does not promote "
            "the support scalar."
        ),
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Already-selected broad-market default-off paper candidates may have "
            "better replacement value when the broad tape is liquid and orderly. "
            "A bounded support scalar using only SPY/QQQ/IWM decision-date OHLCV "
            "can improve allocation without adding noisy tickers."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / risk allocation",
            "playbook_alignment": (
                "Directly tests the playbook backlog field market_liquidity_regime_bucket "
                "with free production-visible OHLCV. It avoids LLM soft-ranking, "
                "Companyfacts/post-earnings retunes, and broad OHLCV ticker-pattern renames."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                "exp-20260524-030 rejected candidate-level avg-dollar-volume liquidity quality",
                "exp-20260527-024 rejected candidate-level cost/liquidity haircut",
                "No logged run found for SPY/QQQ/IWM market-liquidity regime support on this sleeve",
            ],
            "anti_repeat": (
                "Keeps accepted broad-market candidate set, rank profile, low-extension, "
                "high-volatility, trend-persistence support, hold days, entry slots, and "
                "universe fixed. Only the market-level liquidity-regime notional support "
                "field changes."
            ),
        },
        "change_type": "default_off_paper_capital_allocation_scout",
        "changed_variable": "broad_market_orderly_market_liquidity_regime_support_v1",
        "single_causal_variable": "SPY/QQQ/IWM orderly market-liquidity regime paper-notional support scalar",
        "component": "quant/experiments/exp_20260602_028_broad_market_market_liquidity_support.py",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "rule_version": RULE_VERSION,
            "market_liquidity_inputs": [
                "SPY decision-date 20d/60d average dollar-volume ratio",
                "QQQ decision-date 20d/60d average dollar-volume ratio",
                "IWM decision-date 20d/60d average dollar-volume ratio",
                "SPY/QQQ/IWM 20d average high-low-close range pct",
                "SPY/QQQ/IWM current-day high-low-close range pct",
            ],
            "lookahead_policy": "Uses OHLCV up to the paper trade decision date only.",
            "sweep": MARKET_LIQUIDITY_SWEEP,
            "selected_variant": selected["variant_name"],
            "selected_thresholds": selected["variant"],
            "candidate_count": len(baseline["candidate_tickers"]),
            "locked_variables": [
                "core signal generation",
                "core entry filters",
                "core ranking",
                "core exits",
                "core sizing",
                "portfolio heat",
                "LLM/news decisions",
                "live/default orders",
                "broad-market candidate thresholds",
                "broad-market rank-notional profile",
                "broad-market low-extension scalar",
                "broad-market high-volatility scalar",
                "broad-market trend-persistence scalar",
                "broad-market hold days",
                "broad-market active position cap",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "minimum_selected_trades": p35.MIN_SELECTED_TRADES,
                "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
                "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
                "max_drawdown_worse": p35.MAX_DRAWDOWN_WORSE,
                "requires_baseline_replay_parity": True,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"], "snapshot": row["snapshot"]}
            for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-004 after_metrics are the before state; after state "
            "replays identical selected broad-market paper trades with one "
            "decision-date market-liquidity support variable."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": SOURCE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(SOURCE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
            "baseline_replay_parity": baseline_replay_parity,
            "known_measurement_boundary": (
                "Historical replay uses the frozen exp-20260520-004 candidate universe. "
                "The tested support field is not promoted into production or default-off "
                "paper behavior in this commit."
            ),
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": selected["gate4"],
        "baseline_replay_parity": baseline_replay_parity,
        "before_metrics": before_metrics,
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "expected_value_score_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_ev_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_pnl_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["total_pnl"]
                for label in WINDOWS
            },
        },
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": {
            "variant_name": selected["variant_name"],
            "thresholds": selected["variant"],
            "selected_trade_count": selected["selected_trade_count"],
            "adjusted_trade_count": selected["adjusted_trade_count"],
            "adjusted_windows": selected["adjusted_windows"],
            "pre_adjusted_pnl": selected["pre_adjusted_pnl"],
            "adjusted_pnl": selected["adjusted_pnl"],
            "notional_added": selected["notional_added"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "event_risk": selected["event_risk"],
            "state_bucket_counts": selected["state_bucket_counts"],
            "state_bucket_pnl": selected["state_bucket_pnl"],
            "adjusted_state_bucket_counts": selected["adjusted_state_bucket_counts"],
            "adjusted_trades_sample": selected["adjusted_trades_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: already-selected broad-market paper "
                "candidates may deserve support when the broad tape is liquid and orderly."
            ),
            "2_past_similar_experiments": (
                "Candidate-level liquidity-quality and cost-liquidity broad-market tests "
                "were rejected; no prior SPY/QQQ/IWM market-liquidity regime support test "
                "was found."
            ),
            "3_single_variable": (
                "Only the market-liquidity support scalar changes; candidate eligibility, "
                "ranking, existing support scalars, hold, slots, and universe remain fixed."
            ),
            "4_acceptance": (
                "Gate 4 requires positive aggregate EV/PnL, all 3 windows EV-positive, "
                "no EV/PnL regression windows, >=8 adjusted trades across all 3 windows, "
                "concentration guard, <=0.5pp drawdown worsening, and baseline replay parity."
            ),
            "5_reproducibility": (
                "Script, JSON artifact, ticket, markdown artifact, and docs JSONL record "
                "windows, source artifact, sweep parameters, Gate 1-4, and selected result."
            ),
        },
        "interpretation": (
            "Market-liquidity regime is tested as a capital allocation layer on the "
            "accepted broad-market paper sleeve. Because this run does not promote a "
            "shared adapter, positive evidence would be observed-only and cannot affect production."
        ),
        "rejection_reason": None if gate4_passed else "Best market-liquidity support variant failed Gate 4.",
        "next_evidence_needed": (
            "If revisited, require a materially different market-liquidity field or forward "
            "replacement-value rows; do not retune nearby SPY/QQQ/IWM range/liquidity thresholds "
            "on the same frozen sample."
        ),
        "why_not_other_changes": [
            "No price-floor, ret20, ret60, near-high, volume, ret5, or positive-day threshold changed.",
            "No rank-notional profile retune.",
            "No LLM soft-ranking; attribution remains sparse.",
            "No live/core universe expansion; this stays default-off paper.",
        ],
        "known_risks": [
            "Historical replay depends on the local exp-20260520-004 broad-market candidate universe.",
            "A market regime field can be correlated with existing benchmark momentum gates.",
            "Positive replay evidence would require a shared helper before any retention.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "source_baseline": _repo_rel(SOURCE_JSON),
            "control": _repo_rel(CONTROL_JSON),
            "output": _repo_rel(OUT_JSON),
            "before_aggregate": _repo_rel(BEFORE_AGG_JSON),
            "after_aggregate": _repo_rel(AFTER_AGG_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
        },
    }
    return payload


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "baseline_replay_parity": payload["baseline_replay_parity"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def _ticket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    existing = _json_load(TICKET_JSON) if TICKET_JSON.exists() else {}
    existing.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4": payload["gate4"],
                "baseline_replay_parity": payload["baseline_replay_parity"],
                "production_impact": payload["production_impact"],
                "next_evidence_needed": payload["next_evidence_needed"],
                "related_files": payload["related_files"],
            },
        }
    )
    return existing


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_AGG_JSON, _judge_aggregate(payload["aggregate_before"]))
    _write_json(AFTER_AGG_JSON, _judge_aggregate(payload["aggregate_after"]))
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, _ticket_payload(payload))
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["selected_variant"]["variant_name"],
                    "gate4": payload["gate4"],
                    "baseline_replay_parity": payload["baseline_replay_parity"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "output": payload["related_files"]["output"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
