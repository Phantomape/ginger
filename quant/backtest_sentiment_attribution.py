"""Read-only market-state and sentiment attribution for backtest results.

This module does not change trade generation, ranking, sizing, or exits. It
labels closed trades with replay-visible sentiment and market-state metadata so
strategy experiments can see where edge is concentrated before any policy is
changed.
"""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from pathlib import Path

from sentiment_surface import (
    SENTIMENT_BASELINE,
    build_sentiment_trade_attribution,
    classify_sentiment_surface,
)


MARKET_STATE_BASELINE = "unknown_or_unmapped"
MARKET_STATE_BROAD_RISK_ON = "broad_risk_on"
MARKET_STATE_NARROW_THEME = "narrow_theme_mania"
MARKET_STATE_ROTATION_HIGH_DISPERSION = "rotation_high_dispersion"
MARKET_STATE_CHOPPY_LOW_EDGE = "choppy_low_edge"
MARKET_STATE_RISK_OFF_HIGH_VOL = "risk_off_high_vol"
MARKET_STATE_VOLATILE_REBOUND = "volatile_rebound"

STATE_BUCKET_TO_MARKET_STATE = {
    "balanced_risk_on": MARKET_STATE_BROAD_RISK_ON,
    "broad_rotation": MARKET_STATE_ROTATION_HIGH_DISPERSION,
    "narrow_cap_weight_leadership": MARKET_STATE_NARROW_THEME,
    "weak_index": MARKET_STATE_RISK_OFF_HIGH_VOL,
}


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _nested_get(row, path, default=None):
    current = row
    for part in str(path).split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current.get(part)
    return current


def _first_present(row, paths):
    for path in paths:
        value = _nested_get(row, path)
        if value not in (None, ""):
            return value, path
    return None, None


def _normalise_label(value):
    return str(value or "").strip().lower()


def _trade_pnl(trade):
    pnl = trade.get("pnl")
    if pnl is None:
        pnl = trade.get("profit_loss")
    return _float(pnl, 0.0)


def _trade_key(trade):
    parts = [
        trade.get("ticker"),
        trade.get("entry_date"),
        trade.get("exit_date"),
        trade.get("strategy"),
    ]
    return "|".join(str(part or "") for part in parts)


def infer_trade_sentiment(trade):
    """Infer sentiment from replay-visible trade metadata.

    Current canonical backtests do not persist full daily market context per
    trade, so we infer a conservative sentiment approximation from replayed
    regime fields already stored in trade artifacts.
    """
    regime_bucket = str(trade.get("regime_exit_bucket") or "").lower()
    strategy = str(trade.get("strategy") or "").lower()

    breakout_count = 1 if "breakout" in strategy else 0
    ai_count = 1 if trade.get("sector") == "Technology" else 0

    if regime_bucket in {"aggressive", "risk_on", "strong_trend"}:
        ctx = {
            "spy_pct_from_ma": 0.03,
            "qqq_pct_from_ma": 0.05,
            "spy_20d_return": 0.05,
            "qqq_20d_return": 0.08,
            "vix": 16,
            "qqq_minus_spy_ret20": 0.04,
            "breakout_signal_count": breakout_count + 3,
            "ai_signal_count": ai_count + 2,
        }
    elif regime_bucket in {"defensive", "risk_off", "weak"}:
        ctx = {
            "spy_pct_from_ma": -0.03,
            "qqq_pct_from_ma": -0.05,
            "spy_20d_return": -0.06,
            "qqq_20d_return": -0.09,
            "vix": 31,
        }
    elif regime_bucket in {"balanced", "neutral"}:
        ctx = {
            "spy_20d_return": 0.01,
            "qqq_20d_return": 0.00,
            "vix": 20,
        }
    else:
        return {
            "sentiment": SENTIMENT_BASELINE,
            "confidence": 0.25,
            "why": ["no_regime_bucket_mapping"],
        }

    return classify_sentiment_surface(ctx)


def _explicit_market_state_context(trade):
    """Collect point-in-time state fields when artifacts already carry them."""
    state_bucket, state_bucket_source = _first_present(
        trade,
        [
            "entry_state_bucket",
            "state_bucket_at_entry",
            "market_state_bucket",
            "state_bucket",
            "state.state_bucket",
            "state_features.state_bucket",
            "sizing.state_bucket",
        ],
    )
    state_surface, state_surface_source = _first_present(
        trade,
        [
            "entry_state_surface",
            "state_surface_at_entry",
            "state_surface",
            "state.state_surface",
            "state_features.state_surface",
            "sizing.state_surface",
        ],
    )
    breadth_bucket, breadth_bucket_source = _first_present(
        trade,
        [
            "entry_breadth_bucket",
            "breadth_bucket_at_entry",
            "breadth_bucket",
            "state.breadth_bucket",
            "state_features.breadth_bucket",
            "sizing.breadth_bucket",
        ],
    )
    regime_bucket, regime_bucket_source = _first_present(
        trade,
        [
            "regime_entry_bucket",
            "regime_at_entry",
            "entry_regime_bucket",
        ],
    )

    sources = {
        "state_bucket": state_bucket_source,
        "state_surface": state_surface_source,
        "breadth_bucket": breadth_bucket_source,
        "regime_bucket": regime_bucket_source,
    }
    values = {
        "state_bucket": state_bucket,
        "state_surface": state_surface,
        "breadth_bucket": breadth_bucket,
        "regime_bucket": regime_bucket,
    }
    has_entry_context = any(value not in (None, "") for value in values.values())
    return values, sources, has_entry_context


def _classify_explicit_market_state(context):
    state_bucket = _normalise_label(context.get("state_bucket"))
    state_surface = _normalise_label(context.get("state_surface"))
    breadth_bucket = _normalise_label(context.get("breadth_bucket"))
    regime_bucket = _normalise_label(context.get("regime_bucket"))
    why = []

    if state_bucket in STATE_BUCKET_TO_MARKET_STATE:
        why.append(f"state_bucket:{state_bucket}")
        return STATE_BUCKET_TO_MARKET_STATE[state_bucket], why

    if "narrow" in state_surface or "cap_weight" in state_surface:
        why.append(f"state_surface:{state_surface}")
        return MARKET_STATE_NARROW_THEME, why
    if "rotation" in state_surface or "dispersion" in state_surface:
        why.append(f"state_surface:{state_surface}")
        return MARKET_STATE_ROTATION_HIGH_DISPERSION, why
    if "broad_breadth" in state_surface or "balanced" in state_surface:
        why.append(f"state_surface:{state_surface}")
        return MARKET_STATE_BROAD_RISK_ON, why

    if breadth_bucket == "broad_breadth":
        why.append("breadth_bucket:broad_breadth")
        return MARKET_STATE_BROAD_RISK_ON, why
    if breadth_bucket in {"mixed_breadth", "thin_breadth"}:
        why.append(f"breadth_bucket:{breadth_bucket}")
        return MARKET_STATE_CHOPPY_LOW_EDGE, why

    if regime_bucket in {"defensive", "risk_off", "weak", "bear"}:
        why.append(f"entry_regime_bucket:{regime_bucket}")
        return MARKET_STATE_RISK_OFF_HIGH_VOL, why
    if regime_bucket in {"balanced", "neutral"}:
        why.append(f"entry_regime_bucket:{regime_bucket}")
        return MARKET_STATE_CHOPPY_LOW_EDGE, why
    if regime_bucket in {"aggressive", "risk_on", "strong_trend", "bull"}:
        why.append(f"entry_regime_bucket:{regime_bucket}")
        return MARKET_STATE_BROAD_RISK_ON, why

    why.append("explicit_context_unmapped")
    return MARKET_STATE_BASELINE, why


def _proxy_market_state_from_sentiment(trade, sentiment):
    sentiment_label = _normalise_label(sentiment.get("sentiment"))
    sector = str(trade.get("sector") or "Unknown")
    strategy = _normalise_label(trade.get("strategy"))

    if sentiment_label == "panic_risk_off":
        return "proxy_panic_risk_off", ["sentiment_proxy:panic_risk_off"]
    if sentiment_label == "volatile_rebound":
        return "proxy_volatile_rebound", ["sentiment_proxy:volatile_rebound"]
    if sentiment_label == "choppy_uncertain":
        return "proxy_choppy_uncertain", ["sentiment_proxy:choppy_uncertain"]
    if sentiment_label in {"healthy_trend", "low_vol_grind"}:
        return "proxy_broad_risk_on", [f"sentiment_proxy:{sentiment_label}"]
    if sentiment_label == "theme_mania":
        if sector == "Technology":
            suffix = "breakout" if "breakout" in strategy else "trend"
            return f"proxy_theme_mania_growth_{suffix}", [
                "sentiment_proxy:theme_mania",
                f"sector:{sector}",
                f"strategy:{strategy}",
            ]
        if sector in {"Communication Services", "Consumer Discretionary"}:
            return "proxy_theme_mania_consumer_platform", [
                "sentiment_proxy:theme_mania",
                f"sector:{sector}",
            ]
        if sector == "Financials":
            return "proxy_theme_mania_financial_leadership", [
                "sentiment_proxy:theme_mania",
                "sector:Financials",
            ]
        if sector in {"Commodities", "Energy"}:
            return "proxy_theme_mania_reflation_or_commodity", [
                "sentiment_proxy:theme_mania",
                f"sector:{sector}",
            ]
        return "proxy_theme_mania_other", [
            "sentiment_proxy:theme_mania",
            f"sector:{sector}",
        ]

    return MARKET_STATE_BASELINE, ["sentiment_proxy_unmapped"]


def infer_trade_market_state(trade):
    """Infer market state while preserving provenance.

    The returned state is only strategy-usable when `point_in_time_safe` is true.
    Canonical historical artifacts often lack entry-day market context; in that
    case this function emits a clearly marked regime-exit proxy for attribution
    only.
    """
    explicit_context, explicit_sources, has_entry_context = _explicit_market_state_context(trade)
    if has_entry_context:
        market_state, why = _classify_explicit_market_state(explicit_context)
        return {
            "market_state": market_state,
            "market_state_confidence": 0.8 if market_state != MARKET_STATE_BASELINE else 0.45,
            "market_state_why": why,
            "market_state_source": "entry_visible_context",
            "point_in_time_safe": True,
            "prediction_usable": True,
            "entry_context": explicit_context,
            "entry_context_sources": explicit_sources,
        }

    sentiment = infer_trade_sentiment(trade)
    market_state, why = _proxy_market_state_from_sentiment(trade, sentiment)
    return {
        "market_state": market_state,
        "market_state_confidence": min(_float(sentiment.get("confidence"), 0.35), 0.65),
        "market_state_why": list(sentiment.get("why") or []) + why + [
            "fallback_from_regime_exit_bucket",
        ],
        "market_state_source": "regime_exit_proxy",
        "point_in_time_safe": False,
        "prediction_usable": False,
        "entry_context": {
            "regime_exit_bucket": trade.get("regime_exit_bucket"),
            "strategy": trade.get("strategy"),
            "sector": trade.get("sector"),
        },
        "entry_context_sources": {
            "regime_exit_bucket": "regime_exit_bucket",
            "strategy": "strategy",
            "sector": "sector",
        },
    }


def annotate_trades_with_sentiment(result):
    trades = []
    for trade in result.get("trades", []):
        out = dict(trade)
        sentiment = infer_trade_sentiment(trade)
        market_state = infer_trade_market_state(trade)
        out["sentiment_surface"] = sentiment["sentiment"]
        out["sentiment_confidence"] = sentiment["confidence"]
        out["sentiment_why"] = sentiment["why"]
        out.update(market_state)
        trades.append(out)
    return trades


def _aggregate_by_fields(trades, fields):
    buckets = OrderedDict()
    for trade in trades or []:
        key = tuple(str(_nested_get(trade, field, "unknown") or "unknown") for field in fields)
        bucket = buckets.setdefault(
            key,
            {
                "trades": 0,
                "wins": 0,
                "total_pnl": 0.0,
                "pnl_values": [],
                "tickers": set(),
                "strategies": set(),
                "sectors": set(),
                "point_in_time_safe_trades": 0,
                "prediction_usable_trades": 0,
                "source_counts": {},
                "worst_trade": None,
                "best_trade": None,
            },
        )
        pnl = _trade_pnl(trade)
        bucket["trades"] += 1
        bucket["wins"] += 1 if pnl > 0 else 0
        bucket["total_pnl"] += pnl
        bucket["pnl_values"].append(pnl)
        bucket["tickers"].add(str(trade.get("ticker") or ""))
        bucket["strategies"].add(str(trade.get("strategy") or ""))
        bucket["sectors"].add(str(trade.get("sector") or ""))
        if trade.get("point_in_time_safe"):
            bucket["point_in_time_safe_trades"] += 1
        if trade.get("prediction_usable"):
            bucket["prediction_usable_trades"] += 1
        source = str(trade.get("market_state_source") or "unknown")
        bucket["source_counts"][source] = bucket["source_counts"].get(source, 0) + 1
        worst = bucket["worst_trade"]
        best = bucket["best_trade"]
        if worst is None or pnl < worst["pnl"]:
            bucket["worst_trade"] = {
                "trade_key": _trade_key(trade),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "pnl": round(pnl, 2),
            }
        if best is None or pnl > best["pnl"]:
            bucket["best_trade"] = {
                "trade_key": _trade_key(trade),
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "pnl": round(pnl, 2),
            }

    rows = []
    for key, bucket in buckets.items():
        trades_n = bucket["trades"]
        pnl_values = bucket["pnl_values"]
        row = {field: value for field, value in zip(fields, key)}
        row.update(
            {
                "trades": trades_n,
                "win_rate": round(bucket["wins"] / trades_n, 4) if trades_n else 0.0,
                "total_pnl": round(bucket["total_pnl"], 2),
                "avg_pnl": round(bucket["total_pnl"] / trades_n, 2) if trades_n else 0.0,
                "worst_trade_pnl": round(min(pnl_values), 2) if pnl_values else None,
                "best_trade_pnl": round(max(pnl_values), 2) if pnl_values else None,
                "tickers": sorted(value for value in bucket["tickers"] if value),
                "strategies": sorted(value for value in bucket["strategies"] if value),
                "sectors": sorted(value for value in bucket["sectors"] if value),
                "point_in_time_safe_trades": bucket["point_in_time_safe_trades"],
                "prediction_usable_trades": bucket["prediction_usable_trades"],
                "market_state_source_counts": dict(sorted(bucket["source_counts"].items())),
                "worst_trade": bucket["worst_trade"],
                "best_trade": bucket["best_trade"],
            }
        )
        rows.append(row)

    return sorted(rows, key=lambda row: row["total_pnl"], reverse=True)


def _prediction_readiness(trades):
    total = len(trades or [])
    if not total:
        return {
            "status": "no_trades",
            "trade_count": 0,
            "point_in_time_safe_coverage": 0.0,
            "prediction_usable_coverage": 0.0,
            "recommendation": "No trades available for market-state attribution.",
        }
    pit = sum(1 for trade in trades if trade.get("point_in_time_safe"))
    usable = sum(1 for trade in trades if trade.get("prediction_usable"))
    source_counts = {}
    for trade in trades:
        source = str(trade.get("market_state_source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    pit_coverage = pit / total
    usable_coverage = usable / total
    if pit_coverage >= 0.8:
        status = "research_ready"
        recommendation = (
            "Entry-visible market-state coverage is high enough for a separate "
            "single-variable policy experiment."
        )
    else:
        status = "attribution_only"
        recommendation = (
            "Do not promote a market-state policy from this report alone. Persist "
            "entry-day state features in backtest artifacts first."
        )
    return {
        "status": status,
        "trade_count": total,
        "point_in_time_safe_trades": pit,
        "prediction_usable_trades": usable,
        "point_in_time_safe_coverage": round(pit_coverage, 4),
        "prediction_usable_coverage": round(usable_coverage, 4),
        "market_state_source_counts": dict(sorted(source_counts.items())),
        "recommendation": recommendation,
    }


def _state_policy_research_hints(market_state_rows, readiness):
    """Return non-executable policy research hints from attribution rows."""
    rows = [row for row in market_state_rows if row.get("trades", 0) >= 2]
    positive = [
        row
        for row in rows
        if _float(row.get("total_pnl"), 0.0) > 0 and _float(row.get("win_rate"), 0.0) >= 0.5
    ]
    fragile = [
        row
        for row in rows
        if _float(row.get("total_pnl"), 0.0) < 0 or _float(row.get("win_rate"), 0.0) < 0.45
    ]
    positive = sorted(
        positive,
        key=lambda row: (_float(row.get("avg_pnl"), 0.0), _float(row.get("total_pnl"), 0.0)),
        reverse=True,
    )
    fragile = sorted(
        fragile,
        key=lambda row: (_float(row.get("avg_pnl"), 0.0), _float(row.get("total_pnl"), 0.0)),
    )
    policy_ready = readiness.get("status") == "research_ready"
    return {
        "policy_ready": policy_ready,
        "status": (
            "ready_for_single_variable_experiment"
            if policy_ready
            else "measurement_first"
        ),
        "constructive_state_candidates": positive[:5],
        "fragile_state_candidates": fragile[:5],
        "next_step": (
            "Choose one state x strategy or state x sector variable and run the "
            "standard three-window Gate 1-4 protocol."
            if policy_ready
            else "Persist entry-day market-state fields in trade artifacts before changing strategy policy."
        ),
    }


def _serialise_trade_for_report(trade):
    fields = [
        "trade_key",
        "ticker",
        "entry_date",
        "exit_date",
        "strategy",
        "sector",
        "pnl",
        "regime_exit_bucket",
        "sentiment_surface",
        "sentiment_confidence",
        "market_state",
        "market_state_confidence",
        "market_state_source",
        "point_in_time_safe",
        "prediction_usable",
        "market_state_why",
        "entry_context",
    ]
    row = {field: trade.get(field) for field in fields if field != "trade_key"}
    row["trade_key"] = _trade_key(trade)
    return row


def build_sentiment_report(result, include_trades=False):
    trades = annotate_trades_with_sentiment(result)
    attribution = build_sentiment_trade_attribution(trades)
    market_state_attribution = _aggregate_by_fields(trades, ["market_state"])
    market_state_strategy_attribution = _aggregate_by_fields(
        trades,
        ["market_state", "strategy"],
    )
    market_state_sector_attribution = _aggregate_by_fields(
        trades,
        ["market_state", "sector"],
    )
    prediction_readiness = _prediction_readiness(trades)

    report = {
        "schema_version": 2,
        "read_only": True,
        "source_period": result.get("period"),
        "source_expected_value_score": result.get("expected_value_score"),
        "trade_count": len(trades),
        "sentiment_trade_attribution": attribution,
        "market_state_trade_attribution": market_state_attribution,
        "market_state_strategy_attribution": market_state_strategy_attribution,
        "market_state_sector_attribution": market_state_sector_attribution,
        "prediction_readiness": prediction_readiness,
        "state_policy_research_hints": _state_policy_research_hints(
            market_state_attribution,
            prediction_readiness,
        ),
        "notes": [
            "This is a replay-side market-state and sentiment attribution layer only.",
            "Market-state policy is safe to research only from point_in_time_safe rows.",
            "Rows sourced from regime_exit_proxy are attribution-only and must not be treated as tradable prediction features.",
            "Use this for exploratory attribution before introducing any market-state-conditioned sizing overlays.",
        ],
    }
    if include_trades:
        report["annotated_trades"] = [_serialise_trade_for_report(trade) for trade in trades]
    else:
        ranked = sorted(trades, key=lambda trade: abs(_trade_pnl(trade)), reverse=True)
        report["largest_abs_pnl_annotated_trades"] = [
            _serialise_trade_for_report(trade) for trade in ranked[:10]
        ]
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json")
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--include-trades",
        action="store_true",
        help="Include every annotated trade instead of only the largest abs-PnL sample.",
    )
    args = parser.parse_args()

    path = Path(args.result_json)
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    report = build_sentiment_report(result, include_trades=args.include_trades)

    output = Path(args.output) if args.output else path.with_name(path.stem + "_sentiment.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
