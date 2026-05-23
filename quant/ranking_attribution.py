"""Read-only attribution for continuous cross-sectional ranking.

This module evaluates whether alpha_score from cross_sectional_ranking_surface
contains predictive information in historical/replay artifacts.

It does not change signals, ranking, sizing, or orders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _extract_rank_map(ranking_surface):
    rows = []
    if isinstance(ranking_surface, dict):
        rows.extend(ranking_surface.get("leaders") or [])
        rows.extend(ranking_surface.get("laggards") or [])
        rows.extend(ranking_surface.get("rows") or [])
    by_ticker = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        old = by_ticker.get(ticker)
        if old is None or row.get("alpha_score") is not None:
            by_ticker[ticker] = row
    return by_ticker


def _r_multiple(trade):
    entry = _float(trade.get("entry_price"))
    stop = _float(trade.get("stop_price"))
    shares = _float(trade.get("shares"))
    pnl = _float(trade.get("pnl"), None)
    if pnl is None:
        pnl = _float(trade.get("profit_loss"), None)
    if entry is None or stop is None or shares is None or pnl is None:
        return None
    if entry <= stop or shares <= 0:
        return None
    risk = (entry - stop) * shares
    if risk <= 0:
        return None
    return pnl / risk


def _bucket_for_percentile(rank_pct):
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


def annotate_trades_with_ranking(result, ranking_surface):
    rank_map = _extract_rank_map(ranking_surface)
    ordered = sorted(
        rank_map.values(),
        key=lambda row: _float(row.get("alpha_score"), -999),
        reverse=True,
    )
    rank_pct = {}
    n = len(ordered)
    for idx, row in enumerate(ordered):
        ticker = str(row.get("ticker") or "").upper()
        rank_pct[ticker] = (idx + 1) / n if n else None

    trades = []
    for trade in result.get("trades", []):
        out = dict(trade)
        ticker = str(out.get("ticker") or "").upper()
        rank_row = rank_map.get(ticker) or {}
        pct = rank_pct.get(ticker)
        out["alpha_score"] = rank_row.get("alpha_score")
        out["alpha_score_components"] = rank_row.get("components")
        out["alpha_score_rank_pct"] = round(pct, 4) if pct is not None else None
        out["alpha_score_bucket"] = _bucket_for_percentile(pct)
        out["r_multiple"] = _r_multiple(out)
        trades.append(out)
    return trades


def _compact_trade_for_validation(trade):
    """Keep validation payload useful without duplicating huge trade blobs."""
    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "pnl": trade.get("pnl") if trade.get("pnl") is not None else trade.get("profit_loss"),
        "profit_loss": trade.get("profit_loss"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "stop_price": trade.get("stop_price"),
        "shares": trade.get("shares"),
        "r_multiple": trade.get("r_multiple"),
        "alpha_score": trade.get("alpha_score"),
        "alpha_score_components": trade.get("alpha_score_components"),
        "alpha_score_rank_pct": trade.get("alpha_score_rank_pct"),
        "alpha_score_bucket": trade.get("alpha_score_bucket"),
    }


def _summarize_bucket(trades):
    pnl_values = []
    r_values = []
    wins = 0
    for trade in trades:
        pnl = _float(trade.get("pnl"), None)
        if pnl is None:
            pnl = _float(trade.get("profit_loss"), None)
        if pnl is None:
            continue
        pnl_values.append(pnl)
        if pnl > 0:
            wins += 1
        r = trade.get("r_multiple") if trade.get("r_multiple") is not None else _r_multiple(trade)
        if r is not None:
            r_values.append(r)
    n = len(pnl_values)
    return {
        "trades": n,
        "win_rate": round(wins / n, 4) if n else None,
        "total_pnl": round(sum(pnl_values), 2) if pnl_values else 0.0,
        "avg_pnl": round(sum(pnl_values) / n, 2) if n else None,
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "worst_trade": round(min(pnl_values), 2) if pnl_values else None,
        "best_trade": round(max(pnl_values), 2) if pnl_values else None,
    }


def build_ranking_attribution(result, ranking_surface, *, include_annotated_trades=True):
    annotated = annotate_trades_with_ranking(result, ranking_surface)
    buckets = {}
    for trade in annotated:
        bucket = trade.get("alpha_score_bucket") or "unknown"
        buckets.setdefault(bucket, []).append(trade)

    bucket_rows = []
    for bucket, trades in buckets.items():
        row = {"bucket": bucket, **_summarize_bucket(trades)}
        bucket_rows.append(row)

    bucket_order = {
        "top_decile": 0,
        "top_quartile": 1,
        "upper_mid": 2,
        "lower_mid": 3,
        "bottom_quartile": 4,
        "unknown": 5,
    }

    component_attribution = {}
    for trade in annotated:
        components = trade.get("alpha_score_components") or {}
        pnl = _float(trade.get("pnl"), None)
        if pnl is None:
            pnl = _float(trade.get("profit_loss"), None)
        if pnl is None:
            continue
        for key, value in components.items():
            bucket = "high" if _float(value, 0.0) >= 0.70 else "low" if _float(value, 0.0) <= 0.30 else "mid"
            component_attribution.setdefault(key, {}).setdefault(bucket, []).append({"pnl": pnl, "r": trade.get("r_multiple")})

    component_summary = {}
    for component, by_bucket in component_attribution.items():
        component_summary[component] = {}
        for bucket, rows in by_bucket.items():
            pnl_values = [r["pnl"] for r in rows]
            r_values = [r["r"] for r in rows if r["r"] is not None]
            component_summary[component][bucket] = {
                "trades": len(rows),
                "avg_pnl": round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
                "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
                "total_pnl": round(sum(pnl_values), 2) if pnl_values else 0.0,
            }

    report = {
        "schema_version": 2,
        "read_only": True,
        "source_period": result.get("period"),
        "source_expected_value_score": result.get("expected_value_score"),
        "ranking_universe_count": ranking_surface.get("universe_count") if isinstance(ranking_surface, dict) else None,
        "bucket_attribution": sorted(bucket_rows, key=lambda r: bucket_order.get(r["bucket"], 99)),
        "component_attribution": component_summary,
        "coverage": {
            "trades_total": len(result.get("trades", [])),
            "trades_with_alpha_score": sum(1 for t in annotated if t.get("alpha_score") is not None),
        },
        "notes": [
            "Read-only attribution of continuous alpha_score vs realized replay trades.",
            "Use this to decide whether the ranking surface deserves a future default-off sizing experiment.",
            "Annotated trades are compact and included only to support longitudinal validation.",
        ],
    }
    if include_annotated_trades:
        report["annotated_trades"] = [_compact_trade_for_validation(t) for t in annotated]
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json")
    parser.add_argument("ranking_surface_json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-annotated-trades", action="store_true")
    args = parser.parse_args()

    result = _load_json(args.result_json)
    ranking_surface = _load_json(args.ranking_surface_json)
    report = build_ranking_attribution(
        result,
        ranking_surface,
        include_annotated_trades=not args.no_annotated_trades,
    )

    result_path = Path(args.result_json)
    output = Path(args.output) if args.output else result_path.with_name(result_path.stem + "_ranking_attribution.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
