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
        # Theme / benchmark ETFs used only as breadth or benchmark inputs. They have
        # no company earnings, so yfinance 404s on their fundamentals every run.
        "ARKX",  # ARK Space Exploration & Innovation ETF
        "UFO",   # Procure Space ETF
        "SPCX",  # SPAC and New Issue ETF
        # Macro / sector / leveraged ETF overlays used as regime & breadth inputs.
        # All are ETFs with no company earnings -- skip the fundamentals request
        # entirely instead of re-discovering the 404 once per run.
        "TQQQ",  # ProShares UltraPro QQQ (3x)
        "IEF",   # iShares 7-10yr Treasury
        "TLT",   # iShares 20+yr Treasury
        "USO",   # United States Oil Fund
        "UUP",   # Invesco DB US Dollar Bullish
        "XLE",   # Energy Select Sector SPDR
        "XLP",   # Consumer Staples Select Sector SPDR
        "XLU",   # Utilities Select Sector SPDR
        "XLV",   # Health Care Select Sector SPDR
        "MUU",   # Direxion Daily MU Bull 2X (leveraged single-stock ETF)
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
