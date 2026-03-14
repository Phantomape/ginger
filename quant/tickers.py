"""
Simple ticker extraction using keyword matching.
"""

import re

# Common stock tickers to look for
COMMON_TICKERS = [
    # Tech giants
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
    # Other major stocks
    "NFLX", "AMD", "INTC", "CSCO", "ORCL", "CRM", "ADBE", "AVGO",
    # Financial & Crypto
    "JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA", "COIN",
    # Industrial/Other
    "DIS", "BA", "CAT", "MMM", "GE", "F", "GM",
    # Retail/Consumer
    "WMT", "HD", "NKE", "SBUX", "MCD", "KO", "PEP",
    # Healthcare/Pharma
    "JNJ", "PFE", "UNH", "ABBV", "MRK", "LLY",
    # Semiconductors & Hardware
    "MU", "CRDO",
    # Software & Cloud
    "APP",
    # ETFs & Commodities
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "IAU",
]


def extract_tickers(text):
    """
    Extract stock tickers from text using simple keyword matching.

    Args:
        text (str): Text to search for tickers (title + summary combined)

    Returns:
        list: List of unique uppercase ticker symbols found
    """
    if not text:
        return []

    # Convert to uppercase for matching
    text_upper = text.upper()

    found_tickers = []

    # Look for each known ticker
    for ticker in COMMON_TICKERS:
        # Use word boundary matching to avoid partial matches
        # e.g., "MSFT" but not "MSFTA"
        pattern = r'\b' + re.escape(ticker) + r'\b'
        if re.search(pattern, text_upper):
            found_tickers.append(ticker)

    # Return unique tickers, maintaining order
    return list(dict.fromkeys(found_tickers))


def extract_tickers_with_hints(text, hint_tickers=None):
    """
    Extract tickers from text, with optional hint tickers from the source.

    Args:
        text (str): Text to search for tickers
        hint_tickers (list): Optional list of ticker hints from the source

    Returns:
        list: List of unique uppercase ticker symbols found
    """
    tickers = extract_tickers(text)

    # Add hint tickers if they appear in the text
    if hint_tickers:
        text_upper = text.upper()
        for hint in hint_tickers:
            hint_upper = hint.upper()
            if hint_upper not in tickers:
                pattern = r'\b' + re.escape(hint_upper) + r'\b'
                if re.search(pattern, text_upper):
                    tickers.append(hint_upper)

    return tickers
