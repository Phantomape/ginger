"""Read-only market-state snapshot for production and replay artifacts.

This module wires the existing regime and sentiment classifiers into a single
daily analysis payload. It does not change signal eligibility, ranking, sizing,
exits, or order generation.
"""

from __future__ import annotations

from collections import Counter

from regime_engine import classify_market_regime
from sentiment_surface import classify_sentiment_surface


THEME_SECTORS = {
    "Communication Services",
    "Consumer Discretionary",
    "Technology",
}


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _signal_strategy(signal):
    return str((signal or {}).get("strategy") or "unknown")


def _signal_sector(signal):
    return str((signal or {}).get("sector") or "Unknown")


def _signal_mix(signals):
    rows = [s for s in (signals or []) if isinstance(s, dict)]
    by_strategy = Counter(_signal_strategy(s) for s in rows)
    by_sector = Counter(_signal_sector(s) for s in rows)
    breakout_count = sum(
        1 for s in rows if "breakout" in _signal_strategy(s).lower()
    )
    ai_count = sum(1 for s in rows if _signal_sector(s) == "Technology")
    theme_count = sum(1 for s in rows if _signal_sector(s) in THEME_SECTORS)

    return {
        "total_signals": len(rows),
        "breakout_signal_count": breakout_count,
        "ai_signal_count": ai_count,
        "theme_signal_count": theme_count,
        "by_strategy": dict(sorted(by_strategy.items())),
        "by_sector": dict(sorted(by_sector.items())),
    }


def _context_with_signal_mix(market_context, signals):
    context = dict(market_context or {})
    mix = _signal_mix(signals)

    for key in ("breakout_signal_count", "ai_signal_count", "theme_signal_count"):
        context.setdefault(key, mix[key])

    spy20 = _float(context.get("spy_20d_return"))
    qqq20 = _float(context.get("qqq_20d_return"))
    if context.get("qqq_minus_spy_ret20") is None and spy20 is not None and qqq20 is not None:
        context["qqq_minus_spy_ret20"] = round(qqq20 - spy20, 4)

    return context, mix


def _context_coverage(context):
    required_for_full_state = [
        "market_regime",
        "spy_pct_from_ma",
        "qqq_pct_from_ma",
        "spy_10d_return",
        "qqq_10d_return",
        "spy_20d_return",
        "qqq_20d_return",
        "vix",
        "qqq_minus_spy_ret20",
        "breakout_signal_count",
        "theme_signal_count",
    ]
    present = [key for key in required_for_full_state if context.get(key) is not None]
    missing = [key for key in required_for_full_state if context.get(key) is None]
    return {
        "required_fields": required_for_full_state,
        "present_fields": present,
        "missing_fields": missing,
        "coverage_fraction": round(len(present) / len(required_for_full_state), 4),
    }


def build_market_state_snapshot(market_context=None, signals=None, source="unknown"):
    """Build a read-only market-state analysis payload.

    The payload is intentionally observational. It can support future alpha
    hypotheses, but no caller should use it as an executable trading rule
    without a separate Gate 1-4 experiment.
    """
    context, mix = _context_with_signal_mix(market_context, signals)
    regime_report = classify_market_regime(context)
    sentiment_report = classify_sentiment_surface(context)

    return {
        "schema_version": 1,
        "read_only": True,
        "diagnostic_only": True,
        "source": source,
        "market_regime_report": regime_report,
        "sentiment_surface": sentiment_report,
        "signal_mix": mix,
        "context_coverage": _context_coverage(context),
        "notes": [
            "Read-only snapshot using existing regime_engine and sentiment_surface classifiers.",
            "No entry, ranking, sizing, exit, heat, LLM, news, or order behavior is changed.",
            "Missing context lowers confidence; policy use requires a separate replay-safe experiment.",
        ],
    }
