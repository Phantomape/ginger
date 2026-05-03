"""
RSS parsing and normalization to standard JSON format.
"""

import feedparser
import logging
from datetime import datetime
from dateutil import parser as date_parser
from sec_ticker_map import enrich_sec_item
from tickers import extract_tickers_with_hints

logger = logging.getLogger(__name__)


def _request_headers(source_type, metadata):
    if source_type != "sec":
        return {}
    user_agent = (
        (metadata or {}).get("user_agent")
        or "ginger-research/1.0 contact: research@example.com"
    )
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }


def _public_metadata(metadata):
    hidden = {"company_tickers_path", "sec_company_tickers_path"}
    return {key: value for key, value in dict(metadata or {}).items() if key not in hidden}


def parse_feed(url, source_type, metadata=None):
    items, _ = parse_feed_with_diagnostics(url, source_type, metadata)
    return items


def parse_feed_with_diagnostics(url, source_type, metadata=None):
    """
    Parse an RSS feed and return normalized news items plus fetch diagnostics.

    Args:
        url (str): RSS feed URL
        source_type (str): Type of source ('google_news' or 'sec')
        metadata (dict): Optional metadata (keywords, filing_type, etc.)

    Returns:
        tuple[list, dict]: Normalized items and source diagnostics
    """
    if metadata is None:
        metadata = {}

    diagnostics = {
        "url": url,
        "source_type": source_type,
        "metadata": dict(metadata or {}),
        "request_headers_used": _request_headers(source_type, metadata),
        "status": None,
        "bozo": False,
        "bozo_exception": None,
        "entry_count": 0,
        "parsed_item_count": 0,
        "sec_items_with_cik": 0,
        "sec_items_with_ticker": 0,
        "sec_items_without_ticker": 0,
        "error": None,
    }

    try:
        logger.info(f"Fetching {source_type} feed: {url}")
        request_headers = diagnostics["request_headers_used"] or None
        feed = feedparser.parse(url, request_headers=request_headers)
        diagnostics["status"] = getattr(feed, "status", None)

        if feed.bozo:
            logger.warning(f"Feed has malformed XML: {url} - {feed.bozo_exception}")
            diagnostics["bozo"] = True
            diagnostics["bozo_exception"] = str(feed.bozo_exception)

        items = []
        diagnostics["entry_count"] = len(feed.entries)
        for entry in feed.entries:
            try:
                item = normalize_entry(entry, url, source_type, metadata)
                if item:
                    items.append(item)
            except Exception as e:
                logger.warning(f"Failed to parse entry from {url}: {e}")
                continue

        diagnostics["parsed_item_count"] = len(items)
        if source_type == "sec":
            diagnostics["sec_items_with_cik"] = sum(1 for item in items if item.get("sec_cik"))
            diagnostics["sec_items_with_ticker"] = sum(1 for item in items if item.get("tickers"))
            diagnostics["sec_items_without_ticker"] = sum(1 for item in items if not item.get("tickers"))
        logger.info(f"Parsed {len(items)} items from {source_type} feed")
        return items, diagnostics

    except Exception as e:
        logger.error(f"Failed to fetch feed {url}: {e}")
        diagnostics["error"] = str(e)
        return [], diagnostics


def normalize_entry(entry, feed_url, source_type, metadata):
    """
    Normalize a feed entry to the standard format.

    Args:
        entry: feedparser entry object
        feed_url (str): Original feed URL
        source_type (str): 'google_news' or 'sec'
        metadata (dict): Additional metadata

    Returns:
        dict: Normalized news item or None if invalid
    """
    # Extract title
    title = entry.get("title", "").strip()
    if not title:
        return None

    # Extract URL
    url = entry.get("link", "").strip()
    if not url:
        return None

    # Extract summary/description
    summary = entry.get("summary", entry.get("description", "")).strip()
    # Remove HTML tags if present
    if summary:
        import re
        summary = re.sub(r'<[^>]+>', '', summary).strip()

    # Extract published date
    published_at = extract_published_date(entry)

    # SEC issuer symbols come from CIK mapping. Generic text matching creates
    # false positives such as "/MA/" or "Corp. V" being read as tickers.
    if source_type == "sec":
        tickers = []
    else:
        search_text = f"{title} {summary}"
        hint_tickers = metadata.get("keywords", [])
        tickers = extract_tickers_with_hints(search_text, hint_tickers)

    # Build normalized item
    item = {
        "source": source_type,
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "tickers": tickers,
        "raw_source": feed_url,
        "source_metadata": _public_metadata(metadata),
    }

    filing_type = metadata.get("filing_type")
    if filing_type:
        item["filing_type"] = filing_type

    if source_type == "sec":
        cache_path = metadata.get("sec_company_tickers_path") or metadata.get("company_tickers_path")
        item = enrich_sec_item(item, cache_path=cache_path)

    return item


def extract_published_date(entry):
    """
    Extract and normalize published date to ISO-8601 UTC format.

    Args:
        entry: feedparser entry object

    Returns:
        str: ISO-8601 formatted timestamp or empty string
    """
    # Try different date fields
    date_fields = ["published", "updated", "created"]

    for field in date_fields:
        date_str = entry.get(field, "")
        if date_str:
            try:
                # Parse the date string
                dt = date_parser.parse(date_str)
                # Convert to UTC ISO format
                return dt.isoformat()
            except Exception:
                continue

    # Try published_parsed or updated_parsed (struct_time)
    for field in ["published_parsed", "updated_parsed"]:
        date_tuple = entry.get(field)
        if date_tuple:
            try:
                dt = datetime(*date_tuple[:6])
                return dt.isoformat()
            except Exception:
                continue

    # If no date found, return empty string
    return ""


def deduplicate_items(items):
    """
    Deduplicate items by (title, url) combination.

    Args:
        items (list): List of news items

    Returns:
        list: Deduplicated list of items
    """
    seen = set()
    unique_items = []

    for item in items:
        key = (item["title"], item["url"])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    logger.info(f"Deduplicated: {len(items)} -> {len(unique_items)} items")
    return unique_items


def sort_items_by_date(items):
    """
    Sort items by published_at descending (newest first).

    Args:
        items (list): List of news items

    Returns:
        list: Sorted list of items
    """
    # Sort by published_at, handling empty dates
    def get_sort_key(item):
        date_str = item.get("published_at", "")
        if date_str:
            try:
                return date_parser.parse(date_str)
            except Exception:
                pass
        # Items without valid dates go to the end
        return datetime.min

    sorted_items = sorted(items, key=get_sort_key, reverse=True)
    return sorted_items
