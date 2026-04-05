"""
News filtering and hygiene module.

Implements filtering rules to clean and focus news items:
- Recency filtering (72-hour window)
- Ticker presence filtering
- Watchlist filtering
- Event keyword filtering
- Deduplication by (ticker + source)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import re

logger = logging.getLogger(__name__)

# Base watchlist — the minimum universe of tickers to track.
# The effective watchlist (used at runtime) also includes any tickers held in
# open_positions.json so news for new positions isn't silently filtered out.
# Adding a ticker here ensures news is always captured, even before a position is opened.
_BASE_WATCHLIST = [
    # ── 科技 / Technology (持仓) ───────────────────────────────────────────
    "NVDA", "META", "AMD", "CRDO", "APP", "GOOG", "MU",
    # ── 科技 / Technology (备选) ───────────────────────────────────────────
    "MSFT", "AAPL", "AVGO", "TSM",   # 大型科技/半导体
    "PLTR", "DDOG", "NOW", "SNOW",   # 软件/云
    # ── 消费 / Consumer Discretionary (持仓 + 备选) ───────────────────────
    "TSLA", "MCD",
    "AMZN", "BKNG",                  # 电商/旅游
    # ── 通信 / Communication Services ─────────────────────────────────────
    "NFLX",
    "DIS", "SPOT",                   # 媒体/流媒体
    # ── 金融 / Financials ─────────────────────────────────────────────────
    "COIN",
    "V", "MA", "GS",                 # 支付/投行
    "JPM",                           # 银行
    # ── 医疗 / Healthcare ─────────────────────────────────────────────────
    "LLY", "NVO",                    # 制药/GLP-1
    "UNH", "ISRG",                   # 医疗保险/机器人手术
    # ── 能源 / Energy ─────────────────────────────────────────────────────
    "XOM", "CVX",                    # 综合能源
    # ── 工业 / Industrials ────────────────────────────────────────────────
    "CAT", "DE",                     # 重型机械
    "GE", "RTX",                     # 航空航天/国防
    # ── 大宗商品/对冲 / Commodities & Hedges ─────────────────────────────
    "IAU", "GLD",                    # 黄金
    "SLV",                           # 白银
    # ── ETF (市场方向参考) ────────────────────────────────────────────────
    "QQQ", "SPY", "IWM",
]


def _load_position_tickers():
    """Load tickers from open_positions.json, return empty set if unavailable."""
    for path in [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'open_positions.json'),
        'data/open_positions.json',
    ]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return {
                    pos['ticker'].upper()
                    for pos in data.get('positions', [])
                    if pos.get('ticker')
                }
            except Exception:
                pass
    return set()


# WATCHLIST = base tickers + any tickers currently held (loaded at import time).
# This ensures that if the user opens a position in a ticker not in _BASE_WATCHLIST,
# its news is still captured in the same pipeline run.
WATCHLIST = sorted(set(_BASE_WATCHLIST) | _load_position_tickers())

# Event keywords to keep (important trading signals)
EVENT_KEYWORDS = [
    "earnings", "guidance", "forecast", "acquisition", "lawsuit",
    "investigation", "approval", "downgrade", "upgrade", "raises", "cuts"
]

# Market summary keywords to drop (generic market-wide news, NOT stock-specific).
# Keep phrases specific enough to avoid false positives:
#   "market" alone is too broad — it matches "NVDA gains market share" or
#   "Meta dominates ad market", both of which are valid stock catalysts.
#   Use multi-word phrases that unambiguously describe index/macro summaries.
MARKET_SUMMARY_KEYWORDS = [
    "dow jones", "s&p 500", "nasdaq composite", "stock market today",
    "market rally", "market selloff", "market wrap", "stocks rally",
    "wall street today", "live updates", "markets live"
]

# ── News Tier Classification ─────────────────────────────────────────────────
# Tier 1: Actionable hard events. Only T1 can independently trigger a trade.
# Tier 2: Factual reporting from credible outlets. Can confirm signals.
# Tier 3: Opinion, analysis, valuation, fund holdings. Noise for trading purposes.

_T1_TITLE_KEYWORDS = [
    "earnings beat", "earnings miss", "quarterly results", "quarterly earnings",
    "guidance raise", "guidance cut", "guidance raised", "guidance lowered",
    "merger", "acquisition", "acquired", "takeover", "buyout",
    "fda approval", "fda approved", "regulatory approval", "approved by",
    "sec filing", "sec charges", "doj charges", "antitrust",
    "bankruptcy", "chapter 11", "chapter 7",
    "dividend cut", "dividend raise", "dividend raised",
    "ceo resign", "ceo fired", "ceo replaced", "executive departure",
    "stock split", "share buyback", "buyback program",
]

_T2_SOURCES = {
    "reuters", "bloomberg", "wsj", "wall street journal",
    "financial times", "ft.com", "associated press", "ap news",
    "cnbc", "marketwatch", "barrons", "the economist",
}

_T3_SOURCES = {
    "seekingalpha", "seeking alpha", "marketbeat", "simply wall st", "simplywall",
    "coinpaper", "motley fool", "benzinga", "finbold", "cryptoslate",
    "tipranks", "thestreet", "zacks", "valueinvestorsclub",
}

_T3_TITLE_KEYWORDS = [
    "valuation check", "price target", "analyst raises", "analyst cuts",
    "raises stock holdings", "raises stock position", "raises shares",
    "wealth management", "advisory group", "investment management raises",
    "forecast:", "outlook:", "why we think", "we think that",
    "issues underlying", "top picks", "buy these", "sell these",
]


def assign_news_tier(item: dict) -> str:
    """
    Classify a news item into Tier 1, 2, or 3.

    T1 — Hard event: earnings, M&A, regulatory, bankruptcy, executive change.
         Only T1 news can independently trigger a trade recommendation.
    T2 — Factual reporting from a credible news outlet.
         Can corroborate a quant signal but cannot stand alone.
    T3 — Opinion, analysis, fund-holding disclosure, valuation commentary.
         Treated as noise; must NOT influence trading decisions.

    Returns:
        "T1" | "T2" | "T3"
    """
    title  = (item.get("title") or "").lower()
    source = (item.get("source") or item.get("raw_source") or "").lower()

    # T1: hard event keywords in the headline
    for kw in _T1_TITLE_KEYWORDS:
        if kw in title:
            return "T1"

    # T3: known opinion/analysis sources
    for s3 in _T3_SOURCES:
        if s3 in source or s3 in title:
            return "T3"

    # T3: typical opinion/analysis headline patterns
    for kw in _T3_TITLE_KEYWORDS:
        if kw in title:
            return "T3"

    # T2: credible factual news source
    for s2 in _T2_SOURCES:
        if s2 in source:
            return "T2"

    # Default: T3 (unknown source — treat conservatively)
    return "T3"


def filter_by_recency(items, max_hours=72):
    """
    Drop news items older than specified hours.

    Args:
        items (list): List of news items
        max_hours (int): Maximum age in hours (default: 72)

    Returns:
        tuple: (filtered_items, dropped_count)
    """
    cutoff_time = datetime.now() - timedelta(hours=max_hours)
    filtered = []
    dropped = 0

    for item in items:
        published_str = item.get("published_at", "")
        if not published_str:
            # No date means we can't verify recency, drop it
            dropped += 1
            continue

        try:
            published_dt = date_parser.parse(published_str)
            # Make naive datetime timezone-unaware for comparison
            if published_dt.tzinfo:
                published_dt = published_dt.replace(tzinfo=None)

            if published_dt >= cutoff_time:
                filtered.append(item)
            else:
                dropped += 1
        except Exception as e:
            logger.warning(f"Failed to parse date '{published_str}': {e}")
            dropped += 1

    logger.info(f"Recency filter: Dropped {dropped} items older than {max_hours} hours")
    return filtered, dropped


def filter_by_ticker_presence(items):
    """
    Drop items with empty ticker lists.

    Args:
        items (list): List of news items

    Returns:
        tuple: (filtered_items, dropped_count)
    """
    filtered = []
    dropped = 0

    for item in items:
        tickers = item.get("tickers", [])
        if tickers and len(tickers) > 0:
            filtered.append(item)
        else:
            dropped += 1

    logger.info(f"Ticker presence filter: Dropped {dropped} items with empty tickers")
    return filtered, dropped


def filter_by_watchlist(items, watchlist=None):
    """
    Drop items whose tickers do not intersect with the watchlist.

    Args:
        items (list): List of news items
        watchlist (list): List of ticker symbols to keep (default: WATCHLIST)

    Returns:
        tuple: (filtered_items, dropped_count)
    """
    if watchlist is None:
        watchlist = WATCHLIST

    watchlist_set = set(ticker.upper() for ticker in watchlist)
    filtered = []
    dropped = 0

    for item in items:
        tickers = item.get("tickers", [])
        ticker_set = set(ticker.upper() for ticker in tickers)

        # Check if there's any intersection
        if ticker_set & watchlist_set:
            filtered.append(item)
        else:
            dropped += 1

    logger.info(f"Watchlist filter: Dropped {dropped} items not in watchlist {watchlist}")
    return filtered, dropped


def filter_by_event_keywords(items, event_keywords=None, market_keywords=None):
    """
    Keep items with important event keywords, drop market summary items.

    Args:
        items (list): List of news items
        event_keywords (list): Keywords to keep (default: EVENT_KEYWORDS)
        market_keywords (list): Keywords to drop (default: MARKET_SUMMARY_KEYWORDS)

    Returns:
        tuple: (filtered_items, dropped_count)
    """
    if event_keywords is None:
        event_keywords = EVENT_KEYWORDS
    if market_keywords is None:
        market_keywords = MARKET_SUMMARY_KEYWORDS

    filtered = []
    dropped = 0

    for item in items:
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        text = f"{title} {summary}"

        # First check if it contains market summary keywords (drop these)
        has_market_keyword = any(
            keyword.lower() in text for keyword in market_keywords
        )
        if has_market_keyword:
            dropped += 1
            continue

        # Then check if it contains event keywords (keep these)
        has_event_keyword = any(
            keyword.lower() in text for keyword in event_keywords
        )
        if has_event_keyword:
            filtered.append(item)
        else:
            dropped += 1

    logger.info(f"Event keyword filter: Dropped {dropped} items without relevant event keywords")
    return filtered, dropped


def deduplicate_by_ticker_source(items):
    """
    Deduplicate items by (ticker + source), keeping the most recent for each combination.

    For items with multiple tickers, this creates separate entries per ticker,
    then deduplicates, which may result in the same news item appearing multiple times
    if it references multiple tickers.

    Args:
        items (list): List of news items

    Returns:
        tuple: (filtered_items, dropped_count)
    """
    # Group items by (ticker, source) key
    groups = {}

    for item in items:
        tickers = item.get("tickers", [])
        source = item.get("source", "")

        # For each ticker in the item, create a group key
        for ticker in tickers:
            key = (ticker, source)

            # Parse the published date for comparison
            published_str = item.get("published_at", "")
            try:
                published_dt = date_parser.parse(published_str) if published_str else datetime.min
                if published_dt.tzinfo:
                    published_dt = published_dt.replace(tzinfo=None)
            except Exception:
                published_dt = datetime.min

            # Keep the most recent item for this (ticker, source) combination
            if key not in groups:
                groups[key] = (item, published_dt)
            else:
                existing_item, existing_dt = groups[key]
                if published_dt > existing_dt:
                    groups[key] = (item, published_dt)

    # Extract unique items
    # Use a set to track unique items by (title, url) to avoid duplicate news items
    seen = set()
    filtered = []

    for item, _ in groups.values():
        item_key = (item["title"], item["url"])
        if item_key not in seen:
            seen.add(item_key)
            filtered.append(item)

    original_count = len(items)
    dropped = original_count - len(filtered)

    logger.info(f"Deduplication by (ticker, source): Dropped {dropped} duplicate items")
    return filtered, dropped


def apply_hygiene_filters(items):
    """
    Apply basic hygiene filters (inst_2.txt requirements).

    Pipeline:
    1. Filter by recency (72 hours)
    2. Filter by ticker presence
    3. Deduplicate by (ticker + source)

    Args:
        items (list): List of news items

    Returns:
        dict: {
            "items": filtered items,
            "stats": filtering statistics
        }
    """
    logger.info("=" * 50)
    logger.info("Applying hygiene filters")
    logger.info(f"Starting with {len(items)} items")
    logger.info("=" * 50)

    stats = {
        "input_count": len(items),
        "dropped_old": 0,
        "dropped_no_tickers": 0,
        "dropped_duplicates": 0,
        "output_count": 0
    }

    # Step 1: Filter by recency
    items, dropped = filter_by_recency(items, max_hours=72)
    stats["dropped_old"] = dropped

    # Step 2: Filter by ticker presence
    items, dropped = filter_by_ticker_presence(items)
    stats["dropped_no_tickers"] = dropped

    # Step 3: Deduplicate by (ticker + source)
    items, dropped = deduplicate_by_ticker_source(items)
    stats["dropped_duplicates"] = dropped

    stats["output_count"] = len(items)

    logger.info("=" * 50)
    logger.info(f"Hygiene filtering complete: {stats['input_count']} -> {stats['output_count']} items")
    logger.info("=" * 50)

    return {
        "items": items,
        "stats": stats
    }


def apply_trade_filters(items, watchlist=None):
    """
    Apply trade-focused filters (inst_3.txt requirements).

    Pipeline:
    1. Filter by recency (72 hours)
    2. Filter by ticker presence
    3. Filter by watchlist
    4. Filter by event keywords
    5. Deduplicate by (ticker + source)

    Args:
        items (list): List of news items
        watchlist (list): Optional watchlist override

    Returns:
        dict: {
            "items": filtered items,
            "stats": filtering statistics
        }
    """
    if watchlist is None:
        watchlist = WATCHLIST

    logger.info("=" * 50)
    logger.info("Applying trade filters")
    logger.info(f"Starting with {len(items)} items")
    logger.info(f"Watchlist: {watchlist}")
    logger.info("=" * 50)

    stats = {
        "input_count": len(items),
        "dropped_old": 0,
        "dropped_no_tickers": 0,
        "dropped_not_in_watchlist": 0,
        "dropped_no_event_keywords": 0,
        "dropped_duplicates": 0,
        "output_count": 0
    }

    # Step 1: Filter by recency
    items, dropped = filter_by_recency(items, max_hours=72)
    stats["dropped_old"] = dropped

    # Step 2: Filter by ticker presence
    items, dropped = filter_by_ticker_presence(items)
    stats["dropped_no_tickers"] = dropped

    # Step 3: Filter by watchlist
    items, dropped = filter_by_watchlist(items, watchlist)
    stats["dropped_not_in_watchlist"] = dropped

    # Step 4: Filter by event keywords
    items, dropped = filter_by_event_keywords(items)
    stats["dropped_no_event_keywords"] = dropped

    # Step 5: Deduplicate by (ticker + source)
    items, dropped = deduplicate_by_ticker_source(items)
    stats["dropped_duplicates"] = dropped

    # Step 6: Assign news tier (T1/T2/T3) — downstream users (LLM prompt) use this
    # to distinguish actionable hard events from opinion/analysis noise.
    for item in items:
        item["tier"] = assign_news_tier(item)

    tier_counts = {"T1": 0, "T2": 0, "T3": 0}
    for item in items:
        tier_counts[item.get("tier", "T3")] += 1
    logger.info(f"News tiers: T1={tier_counts['T1']} T2={tier_counts['T2']} T3={tier_counts['T3']}")

    stats["output_count"] = len(items)
    stats["tier_counts"]  = tier_counts

    logger.info("=" * 50)
    logger.info(f"Trade filtering complete: {stats['input_count']} -> {stats['output_count']} items")
    logger.info("=" * 50)

    return {
        "items": items,
        "stats": stats
    }
