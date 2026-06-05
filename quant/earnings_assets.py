"""Helpers for assets that do not have company earnings calendars."""

from __future__ import annotations


NON_EARNINGS_ASSET_TICKERS = frozenset(
    {
        # Broad-market ETFs used as benchmarks or tradable overlays.
        "SPY",
        "QQQ",
        "IWM",
        # Commodity ETFs.
        "GLD",
        "IAU",
        "SLV",
        # Cash-like / short-duration treasury holding.
        "SNXX",
    }
)


def normalize_ticker(ticker) -> str:
    return str(ticker or "").strip().upper()


def is_non_earnings_asset(ticker) -> bool:
    """Return True when a ticker should not query company earnings sources."""
    return normalize_ticker(ticker) in NON_EARNINGS_ASSET_TICKERS


def empty_earnings_data() -> dict:
    """Return the neutral earnings-data shape expected by feature builders."""
    return {
        "next_earnings_date": None,
        "days_to_earnings": None,
        "last_earnings_date": None,
        "days_since_last_earnings": None,
        "post_earnings_continuation_confirmed": False,
        "post_earnings_event_date": None,
        "eps_estimate": None,
        "eps_actual_last": None,
        "historical_surprise_pct": [],
        "avg_historical_surprise_pct": None,
    }
