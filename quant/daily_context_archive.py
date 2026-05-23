"""Daily context archive for data-edge accumulation.

This module builds a replayable, append-only context snapshot covering:
  - Earnings Estimate Revision
  - Breadth / Internal Structure
  - Post-Earnings Drift state
  - Theme Density
  - Relative Strength Surface

It is passive intelligence: it must not alter entries, exits, ranking, sizing,
or orders. Production run.py can call persist_daily_context_archive(...) once
per run to create a daily JSON artifact for future attribution.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_DIR = DEFAULT_ROOT / "data" / "daily" / "context"

THEME_TICKERS = {
    "ai": {
        "NVDA", "AMD", "AVGO", "TSM", "ASML", "AMAT", "LRCX", "MU",
        "SMCI", "DELL", "ARM", "CRDO", "ANET", "MRVL", "LITE", "COHR",
    },
    "ai_power": {"VST", "TLN", "CEG", "BE", "GEV", "ETN"},
    "crypto": {"COIN", "MSTR", "MARA", "RIOT", "IREN", "CIFR", "WULF", "CLSK"},
    "space": {"RKLB", "ASTS", "LUNR", "PL", "IRDM", "VSAT"},
    "mega_cap": {"META", "GOOG", "GOOGL", "AMZN", "MSFT", "AAPL", "NVDA", "TSLA"},
    "gold": {"GLD", "IAU", "GDX", "NEM", "AEM"},
}


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value):
    return bool(value) if value is not None else False


def _round(value, digits=4):
    value = _float(value, None)
    return round(value, digits) if value is not None else None


def _safe_feature(features, key):
    if not isinstance(features, dict):
        return None
    return features.get(key)


def _ticker_theme(ticker):
    ticker = str(ticker or "").upper()
    return [theme for theme, tickers in THEME_TICKERS.items() if ticker in tickers]


def build_earnings_estimate_revision_context(
    features_dict,
    earnings_dict=None,
    estimate_revision_summary=None,
):
    rows = []
    for ticker, features in sorted((features_dict or {}).items()):
        if not features:
            continue
        earnings = (earnings_dict or {}).get(ticker) or {}
        eps_estimate = _safe_feature(features, "eps_estimate")
        avg_surprise = _safe_feature(features, "avg_historical_surprise_pct")
        days_to_earnings = _safe_feature(features, "days_to_earnings")
        if eps_estimate is None and avg_surprise is None and days_to_earnings is None:
            continue
        rows.append({
            "ticker": str(ticker).upper(),
            "eps_estimate": _round(eps_estimate),
            "eps_actual_last": _round(earnings.get("eps_actual_last")),
            "avg_historical_surprise_pct": _round(avg_surprise),
            "positive_surprise_history": _safe_feature(features, "positive_surprise_history"),
            "days_to_earnings": days_to_earnings,
            "next_earnings_date": _safe_feature(features, "next_earnings_date"),
        })

    return {
        "available_rows": len(rows),
        "rows": rows,
        "ledger_summary": estimate_revision_summary or {},
        "note": (
            "This captures current expectation fields plus the existing estimate "
            "revision ledger summary. Longitudinal drift comes from daily archives."
        ),
    }


def build_breadth_context(features_dict):
    rows = [f for f in (features_dict or {}).values() if isinstance(f, dict)]
    n = len(rows)
    if n == 0:
        return {"universe_count": 0}

    def frac(predicate):
        return round(sum(1 for f in rows if predicate(f)) / n, 4)

    breakout_rows = [f for f in rows if _bool(f.get("breakout_20d"))]
    breakdown_rows = [f for f in rows if _bool(f.get("breakdown_20d"))]
    momentum20_positive = [f for f in rows if (_float(f.get("momentum_20d_pct"), 0.0) > 0)]
    above_200ma = [f for f in rows if f.get("above_200ma") is True]

    sector_map = {}
    # Most feature rows do not carry sector; keep this hook for future enrichment.
    for f in rows:
        sector = str(f.get("sector") or "unknown")
        sector_map.setdefault(sector, {"count": 0, "breakouts": 0, "mom20_positive": 0})
        sector_map[sector]["count"] += 1
        sector_map[sector]["breakouts"] += 1 if _bool(f.get("breakout_20d")) else 0
        sector_map[sector]["mom20_positive"] += 1 if _float(f.get("momentum_20d_pct"), 0.0) > 0 else 0

    return {
        "universe_count": n,
        "above_200ma_fraction": round(len(above_200ma) / n, 4),
        "breakout_20d_fraction": round(len(breakout_rows) / n, 4),
        "breakdown_20d_fraction": round(len(breakdown_rows) / n, 4),
        "momentum_20d_positive_fraction": round(len(momentum20_positive) / n, 4),
        "volume_spike_fraction": frac(lambda f: _bool(f.get("volume_spike"))),
        "avg_trend_score": _round(sum(_float(f.get("trend_score"), 0.0) for f in rows) / n),
        "sector_participation": {
            sector: {
                "count": data["count"],
                "breakout_fraction": round(data["breakouts"] / data["count"], 4) if data["count"] else None,
                "mom20_positive_fraction": round(data["mom20_positive"] / data["count"], 4) if data["count"] else None,
            }
            for sector, data in sorted(sector_map.items())
        },
        "leaders_by_momentum_20d": [
            {
                "ticker": f.get("ticker"),
                "momentum_20d_pct": _round(f.get("momentum_20d_pct")),
                "trend_score": _round(f.get("trend_score")),
            }
            for f in sorted(rows, key=lambda x: _float(x.get("momentum_20d_pct"), -999), reverse=True)[:10]
        ],
    }


def build_theme_density_context(features_dict):
    rows = [f for f in (features_dict or {}).values() if isinstance(f, dict)]
    theme_summary = {}
    for theme in THEME_TICKERS:
        theme_rows = [f for f in rows if theme in _ticker_theme(f.get("ticker"))]
        n = len(theme_rows)
        if n == 0:
            theme_summary[theme] = {
                "members_in_universe": 0,
                "breakout_count": 0,
                "mom20_positive_count": 0,
                "avg_momentum_20d_pct": None,
            }
            continue
        theme_summary[theme] = {
            "members_in_universe": n,
            "breakout_count": sum(1 for f in theme_rows if _bool(f.get("breakout_20d"))),
            "mom20_positive_count": sum(1 for f in theme_rows if _float(f.get("momentum_20d_pct"), 0.0) > 0),
            "volume_spike_count": sum(1 for f in theme_rows if _bool(f.get("volume_spike"))),
            "avg_momentum_20d_pct": _round(sum(_float(f.get("momentum_20d_pct"), 0.0) for f in theme_rows) / n),
            "avg_trend_score": _round(sum(_float(f.get("trend_score"), 0.0) for f in theme_rows) / n),
            "members": sorted(str(f.get("ticker")).upper() for f in theme_rows if f.get("ticker")),
        }

    crowded_themes = [
        theme for theme, data in theme_summary.items()
        if data.get("members_in_universe", 0) >= 3
        and data.get("breakout_count", 0) >= 2
    ]
    return {
        "themes": theme_summary,
        "crowded_themes": crowded_themes,
    }


def build_relative_strength_surface(features_dict, benchmark_tickers=("SPY", "QQQ")):
    rows = [f for f in (features_dict or {}).values() if isinstance(f, dict)]
    benchmark_features = {
        ticker: (features_dict or {}).get(ticker) or (features_dict or {}).get(ticker.lower())
        for ticker in benchmark_tickers
    }
    qqq_mom20 = _float(_safe_feature(benchmark_features.get("QQQ"), "momentum_20d_pct"), None)
    spy_mom20 = _float(_safe_feature(benchmark_features.get("SPY"), "momentum_20d_pct"), None)

    rs_rows = []
    for f in rows:
        ticker = str(f.get("ticker") or "").upper()
        mom20 = _float(f.get("momentum_20d_pct"), None)
        mom60 = _float(f.get("momentum_60d_pct"), None)
        if mom20 is None:
            continue
        rs_rows.append({
            "ticker": ticker,
            "momentum_20d_pct": _round(mom20),
            "momentum_60d_pct": _round(mom60),
            "ret20_excess_spy": _round(mom20 - spy_mom20) if spy_mom20 is not None else None,
            "ret20_excess_qqq": _round(mom20 - qqq_mom20) if qqq_mom20 is not None else None,
            "themes": _ticker_theme(ticker),
            "breakout_20d": _bool(f.get("breakout_20d")),
            "trend_score": _round(f.get("trend_score")),
        })

    return {
        "benchmarks": {
            "SPY_momentum_20d_pct": _round(spy_mom20),
            "QQQ_momentum_20d_pct": _round(qqq_mom20),
        },
        "leaders_vs_spy": sorted(
            [r for r in rs_rows if r.get("ret20_excess_spy") is not None],
            key=lambda r: r["ret20_excess_spy"],
            reverse=True,
        )[:15],
        "leaders_vs_qqq": sorted(
            [r for r in rs_rows if r.get("ret20_excess_qqq") is not None],
            key=lambda r: r["ret20_excess_qqq"],
            reverse=True,
        )[:15],
        "laggards_vs_spy": sorted(
            [r for r in rs_rows if r.get("ret20_excess_spy") is not None],
            key=lambda r: r["ret20_excess_spy"],
        )[:10],
    }


def build_post_earnings_drift_context(features_dict, earnings_dict=None):
    rows = []
    for ticker, features in sorted((features_dict or {}).items()):
        if not features:
            continue
        dte = _safe_feature(features, "days_to_earnings")
        avg_surprise = _safe_feature(features, "avg_historical_surprise_pct")
        mom10 = _safe_feature(features, "momentum_10d_pct")
        mom20 = _safe_feature(features, "momentum_20d_pct")
        # Current data_layer mostly stores upcoming earnings, not exact days-since-last.
        # This still archives PEAD-relevant state so future snapshots can link
        # post-event momentum with surprise history and estimate revisions.
        if avg_surprise is None and dte is None:
            continue
        rows.append({
            "ticker": str(ticker).upper(),
            "days_to_next_earnings": dte,
            "avg_historical_surprise_pct": _round(avg_surprise),
            "positive_surprise_history": _safe_feature(features, "positive_surprise_history"),
            "momentum_10d_pct": _round(mom10),
            "momentum_20d_pct": _round(mom20),
            "post_event_followthrough_proxy": (
                "positive" if _float(mom10, 0.0) > 0 and _float(avg_surprise, 0.0) > 0
                else "negative" if _float(mom10, 0.0) < 0 and _float(avg_surprise, 0.0) < 0
                else "mixed"
            ),
        })

    return {
        "available_rows": len(rows),
        "rows": rows,
        "note": (
            "This is a PEAD-ready archive. Add days_since_last_earnings later "
            "for cleaner T+2/T+15 post-earnings lifecycle attribution."
        ),
    }


def build_daily_context_archive(
    *,
    as_of_date,
    universe,
    features_dict,
    earnings_dict=None,
    market_regime=None,
    estimate_revision_summary=None,
):
    return {
        "schema_version": 1,
        "as_of_date": as_of_date,
        "generated_at": datetime.now().isoformat(),
        "read_only": True,
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "universe": sorted(str(t).upper() for t in (universe or [])),
        "market_regime": market_regime or {},
        "earnings_estimate_revision": build_earnings_estimate_revision_context(
            features_dict,
            earnings_dict=earnings_dict,
            estimate_revision_summary=estimate_revision_summary,
        ),
        "breadth_internal_structure": build_breadth_context(features_dict),
        "theme_density": build_theme_density_context(features_dict),
        "relative_strength_surface": build_relative_strength_surface(features_dict),
        "post_earnings_drift": build_post_earnings_drift_context(
            features_dict,
            earnings_dict=earnings_dict,
        ),
        "notes": [
            "Passive daily context archive for future replay/attribution.",
            "The archive intentionally does not affect production trading decisions.",
            "Fields are designed to become proprietary history as daily snapshots accumulate.",
        ],
    }


def persist_daily_context_archive(
    *,
    as_of_date,
    universe,
    features_dict,
    earnings_dict=None,
    market_regime=None,
    estimate_revision_summary=None,
    output_dir=DEFAULT_CONTEXT_DIR,
):
    payload = build_daily_context_archive(
        as_of_date=as_of_date,
        universe=universe,
        features_dict=features_dict,
        earnings_dict=earnings_dict,
        market_regime=market_regime,
        estimate_revision_summary=estimate_revision_summary,
    )
    date_key = str(as_of_date).replace("-", "")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"context_{date_key}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {
        "status": "ok",
        "path": str(path),
        "as_of_date": as_of_date,
        "universe_count": len(payload["universe"]),
        "breadth": payload["breadth_internal_structure"],
        "theme_density_summary": {
            theme: {
                "members_in_universe": data.get("members_in_universe"),
                "breakout_count": data.get("breakout_count"),
                "mom20_positive_count": data.get("mom20_positive_count"),
            }
            for theme, data in payload["theme_density"]["themes"].items()
        },
    }
