"""
RSS parsing and normalization to standard JSON format.
"""

import feedparser
import logging
from datetime import datetime
from dateutil import parser as date_parser
from tickers import extract_tickers_with_hints

logger = logging.getLogger(__name__)


def parse_feed(url, source_type, metadata=None):
    """
    Parse an RSS feed and return normalized news items.

    Args:
        url (str): RSS feed URL
        source_type (str): Type of source ('google_news' or 'sec')
        metadata (dict): Optional metadata (keywords, filing_type, etc.)

    Returns:
        list: List of normalized news items (dicts)
    """
    if metadata is None:
        metadata = {}

    try:
        logger.info(f"Fetching {source_type} feed: {url}")
        feed = feedparser.parse(url)

        if feed.bozo:
            logger.warning(f"Feed has malformed XML: {url} - {feed.bozo_exception}")

        items = []
        for entry in feed.entries:
            try:
                item = normalize_entry(entry, url, source_type, metadata)
                if item:
                    items.append(item)
            except Exception as e:
                logger.warning(f"Failed to parse entry from {url}: {e}")
                continue

        logger.info(f"Parsed {len(items)} items from {source_type} feed")
        return items

    except Exception as e:
        logger.error(f"Failed to fetch feed {url}: {e}")
        return []


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

    # Extract tickers
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
        "raw_source": feed_url
    }

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
