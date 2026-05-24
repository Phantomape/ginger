"""Point-in-time entry-day ranking and canonical-vector attribution.

This module rebuilds ranking and canonical state vectors as of the trading day
before each filled entry. It is read-only and must not alter entries, exits,
ranking, sizing, or orders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from canonical_state_vectors import build_canonical_state_vectors
from daily_context_archive import (
    build_breadth_context,
    build_earnings_estimate_revision_context,
    build_post_earnings_drift_context,
    build_theme_density_context,
)
from feature_layer import compute_features
from market_state_bundle import build_market_state_bundle


RANK_BUCKET_ORDER = {
    "top_decile": 0,
    "top_quartile": 1,
    "upper_mid": 2,
    "lower_mid": 3,
    "bottom_quartile": 4,
    "unknown": 5,
}

COMPONENT_BUCKET_ORDER = {
    "high": 0,
    "mid": 1,
    "low": 2,
    "unknown": 3,
}


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_ohlcv_snapshot(path):
    payload = _load_json(path)
    raw = payload.get("ohlcv")
    if not isinstance(raw, dict):
        raise ValueError(f"Snapshot missing 'ohlcv' dict: {path}")

    out = {}
    for ticker, rows in raw.items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        out[str(ticker).upper()] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return out


def _rank_bucket(rank_pct):
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


def _previous_trading_day(ohlcv, ticker, entry_date):
    ticker_frame = ohlcv.get(str(ticker or "").upper())
    if ticker_frame is not None:
        candidates = [idx for idx in ticker_frame.index if idx < entry_date]
        if candidates:
            return candidates[-1]

    all_dates = sorted({idx for frame in ohlcv.values() for idx in frame.index})
    candidates = [idx for idx in all_dates if idx < entry_date]
    return candidates[-1] if candidates else None


def _build_features_asof(ohlcv, asof_date):
    features = {}
    for ticker, frame in sorted(ohlcv.items()):
        data_slice = frame.loc[:asof_date]
        if len(data_slice) < 21:
            continue
        row = compute_features(ticker, data_slice, {})
        if row:
            features[ticker] = row
    return features


def _context_for_asof(ohlcv, asof_date):
    features = _build_features_asof(ohlcv, asof_date)
    breadth = build_breadth_context(features)
    theme_density = build_theme_density_context(features)
    earnings_context = build_earnings_estimate_revision_context(features)
    post_earnings = build_post_earnings_drift_context(features)
    bundle = build_market_state_bundle(
        features_dict=features,
        breadth_context=breadth,
        theme_density_context=theme_density,
        expectation_context=earnings_context,
    )
    vectors = build_canonical_state_vectors(
        market_state_bundle=bundle,
        breadth_context=breadth,
        earnings_context=earnings_context,
        post_earnings_context=post_earnings,
    )

    ranking = bundle.get("cross_sectional_ranking_surface") or {}
    ranked_rows = ranking.get("rows") or []
    rank_map = {}
    n = len(ranked_rows)
    for idx, row in enumerate(ranked_rows):
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        rank_pct = (idx + 1) / n if n else None
        rank_map[ticker] = {
            "alpha_score": row.get("alpha_score"),
            "alpha_score_components": row.get("components"),
            "alpha_score_rank_pct": round(rank_pct, 4) if rank_pct is not None else None,
            "alpha_score_bucket": _rank_bucket(rank_pct),
        }

    return {
        "asof_date": str(asof_date.date()),
        "features_ticker_count": len(features),
        "ranking_universe_count": n,
        "rank_map": rank_map,
        "ticker_vectors": vectors.get("ticker_vectors") or {},
        "summary": {
            "market_state_summary": bundle.get("summary", {}),
            "canonical_vector_summary": vectors.get("summary", {}),
        },
    }


def _trade_pnl(trade):
    pnl = _float(trade.get("pnl"), None)
    if pnl is None:
        pnl = _float(trade.get("profit_loss"), None)
    return pnl


def _r_multiple(trade):
    entry = _float(trade.get("entry_price"), None)
    stop = _float(trade.get("stop_price"), None)
    shares = _float(trade.get("shares"), None)
    pnl = _trade_pnl(trade)
    if entry is None or stop is None or shares is None or pnl is None:
        return None
    risk = (entry - stop) * shares
    if risk <= 0:
        return None
    return round(pnl / risk, 6)


def _compact_trade(trade):
    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "pnl": _trade_pnl(trade),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "stop_price": trade.get("stop_price"),
        "shares": trade.get("shares"),
        "r_multiple": trade.get("r_multiple"),
        "alpha_score": trade.get("alpha_score"),
        "alpha_score_components": trade.get("alpha_score_components"),
        "alpha_score_rank_pct": trade.get("alpha_score_rank_pct"),
        "alpha_score_bucket": trade.get("alpha_score_bucket"),
        "signal_asof_date": trade.get("signal_asof_date"),
        "point_in_time_safe": trade.get("point_in_time_safe"),
        "leadership_vector_state": trade.get("leadership_vector_state"),
        "expectation_vector_state": trade.get("expectation_vector_state"),
        "theme_structure_vector_state": trade.get("theme_structure_vector_state"),
        "risk_heat_vector_state": trade.get("risk_heat_vector_state"),
        "market_regime_vector_state": trade.get("market_regime_vector_state"),
    }


def _summarize(rows):
    pnl_values = []
    r_values = []
    wins = 0
    for row in rows:
        pnl = _trade_pnl(row)
        if pnl is None:
            continue
        pnl_values.append(pnl)
        if pnl > 0:
            wins += 1
        r = _float(row.get("r_multiple"), None)
        if r is not None:
            r_values.append(r)

    n = len(pnl_values)
    return {
        "trades": n,
        "win_rate": round(wins / n, 4) if n else None,
        "total_pnl": round(sum(pnl_values), 2) if pnl_values else 0.0,
        "avg_pnl": round(sum(pnl_values) / n, 2) if n else None,
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "best_trade": round(max(pnl_values), 2) if pnl_values else None,
        "worst_trade": round(min(pnl_values), 2) if pnl_values else None,
    }


def _aggregate_by_field(trades, field, *, order=None):
    buckets = {}
    for trade in trades:
        key = trade.get(field)
        if key is None:
            key = "unknown"
        buckets.setdefault(str(key), []).append(trade)

    def sort_key(row):
        if order:
            return order.get(row["bucket"], 99)
        return row["bucket"]

    rows = [{"bucket": bucket, **_summarize(items)} for bucket, items in buckets.items()]
    return sorted(rows, key=sort_key)


def _component_bucket(value):
    score = _float(value, None)
    if score is None:
        return "unknown"
    if score >= 0.70:
        return "high"
    if score <= 0.30:
        return "low"
    return "mid"


def _aggregate_component_attribution(trades):
    component_names = sorted({
        str(key)
        for trade in trades
        for key in (trade.get("alpha_score_components") or {}).keys()
    })
    out = {}
    total = len(trades)

    for component in component_names:
        buckets = {}
        values = []
        missing = 0
        for trade in trades:
            components = trade.get("alpha_score_components") or {}
            raw_value = components.get(component)
            value = _float(raw_value, None)
            if value is None:
                missing += 1
            else:
                values.append(value)
            bucket = _component_bucket(raw_value)
            buckets.setdefault(bucket, []).append(trade)

        rounded_values = sorted({round(value, 6) for value in values})
        out[component] = {
            "coverage": {
                "trades_total": total,
                "trades_with_component": len(values),
                "missing_trades": missing,
                "coverage": round(len(values) / total, 4) if total else 0.0,
            },
            "value_diagnostics": {
                "min": round(min(values), 6) if values else None,
                "max": round(max(values), 6) if values else None,
                "unique_value_count": len(rounded_values),
                "unique_value_sample": rounded_values[:10],
                "is_constant": bool(values and len(rounded_values) == 1),
            },
            "buckets": sorted(
                [
                    {"bucket": bucket, **_summarize(items)}
                    for bucket, items in buckets.items()
                ],
                key=lambda row: COMPONENT_BUCKET_ORDER.get(row["bucket"], 99),
            ),
        }
    return out


def annotate_trades_with_entry_day_ranking(result, ohlcv):
    contexts = {}
    annotated = []
    context_failures = {}

    for trade in result.get("trades", []):
        out = dict(trade)
        out["r_multiple"] = _r_multiple(out)
        ticker = str(out.get("ticker") or "").upper()
        entry_date_raw = out.get("entry_date")
        try:
            entry_date = pd.Timestamp(entry_date_raw)
        except Exception:
            context_failures["invalid_entry_date"] = context_failures.get("invalid_entry_date", 0) + 1
            out["point_in_time_safe"] = False
            annotated.append(out)
            continue

        asof_date = _previous_trading_day(ohlcv, ticker, entry_date)
        if asof_date is None:
            context_failures["missing_signal_asof_date"] = context_failures.get("missing_signal_asof_date", 0) + 1
            out["point_in_time_safe"] = False
            annotated.append(out)
            continue

        cache_key = str(asof_date.date())
        if cache_key not in contexts:
            contexts[cache_key] = _context_for_asof(ohlcv, asof_date)
        context = contexts[cache_key]

        rank_row = (context.get("rank_map") or {}).get(ticker) or {}
        vector_row = (context.get("ticker_vectors") or {}).get(ticker) or {}
        has_context = bool(rank_row and vector_row)

        out.update(rank_row)
        out["signal_asof_date"] = cache_key
        out["signal_asof_source"] = "previous_trading_day_before_entry"
        out["point_in_time_safe"] = bool(has_context and asof_date < entry_date)

        for vector_name in (
            "leadership_vector",
            "expectation_vector",
            "theme_structure_vector",
            "risk_heat_vector",
            "market_regime_vector",
        ):
            vector = vector_row.get(vector_name) or {}
            out[f"{vector_name}_state"] = vector.get("state")
            out[f"{vector_name}_score"] = vector.get("score")

        if not has_context:
            context_failures["missing_ticker_context"] = context_failures.get("missing_ticker_context", 0) + 1
        annotated.append(out)

    return annotated, contexts, context_failures


def build_entry_day_ranking_attribution(
    *,
    result,
    ohlcv,
    include_annotated_trades=True,
):
    annotated, contexts, context_failures = annotate_trades_with_entry_day_ranking(
        result,
        ohlcv,
    )
    total = len(annotated)
    pit_count = sum(1 for trade in annotated if trade.get("point_in_time_safe"))
    alpha_count = sum(1 for trade in annotated if trade.get("alpha_score") is not None)
    coverage = round(pit_count / total, 4) if total else 0.0

    report = {
        "schema_version": 2,
        "read_only": True,
        "source_period": result.get("period"),
        "source_expected_value_score": result.get("expected_value_score"),
        "coverage": {
            "trades_total": total,
            "point_in_time_safe_trades": pit_count,
            "trades_with_alpha_score": alpha_count,
            "point_in_time_safe_coverage": coverage,
            "policy_research_ready": bool(total and coverage >= 0.95),
            "context_failures": context_failures,
        },
        "ranking_bucket_attribution": _aggregate_by_field(
            annotated,
            "alpha_score_bucket",
            order=RANK_BUCKET_ORDER,
        ),
        "component_bucket_thresholds": {
            "high": "score >= 0.70",
            "mid": "0.30 < score < 0.70",
            "low": "score <= 0.30",
        },
        "component_attribution": _aggregate_component_attribution(annotated),
        "leadership_vector_attribution": _aggregate_by_field(
            annotated,
            "leadership_vector_state",
        ),
        "risk_heat_vector_attribution": _aggregate_by_field(
            annotated,
            "risk_heat_vector_state",
        ),
        "leadership_x_risk_attribution": _aggregate_by_field(
            [
                {
                    **trade,
                    "leadership_x_risk": (
                        f"{trade.get('leadership_vector_state') or 'unknown'}"
                        f"|{trade.get('risk_heat_vector_state') or 'unknown'}"
                    ),
                }
                for trade in annotated
            ],
            "leadership_x_risk",
        ),
        "context_dates": sorted(contexts),
        "context_date_count": len(contexts),
        "notes": [
            "Attribution rebuilds ranking/vector context as of the trading day before entry_date.",
            "Use this for predictive policy research; historical explanation-only reports do not require PIT.",
            "This module is read-only and does not alter strategy behavior.",
        ],
    }
    if include_annotated_trades:
        report["annotated_trades"] = [_compact_trade(trade) for trade in annotated]
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json")
    parser.add_argument("ohlcv_snapshot_json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-annotated-trades", action="store_true")
    args = parser.parse_args()

    result = _load_json(args.result_json)
    ohlcv = load_ohlcv_snapshot(args.ohlcv_snapshot_json)
    report = build_entry_day_ranking_attribution(
        result=result,
        ohlcv=ohlcv,
        include_annotated_trades=not args.no_annotated_trades,
    )

    input_path = Path(args.result_json)
    output = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + "_entry_day_ranking_attribution.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
