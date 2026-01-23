#!/usr/bin/env python3
"""
Unified news collection and filtering pipeline.

This script combines news fetching and filtering into a single command:
1. Fetches news from all RSS sources
2. Applies hygiene filtering
3. Applies trade-focused filtering
4. Saves all outputs

Usage:
    python run_pipeline.py
"""

import json
import logging
import os
import sys
from datetime import datetime

from sources import get_all_sources
from parser import parse_feed, deduplicate_items, sort_items_by_date
from filter import apply_hygiene_filters, apply_trade_filters


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_all_news():
    """
    Fetch news from all sources and return normalized items.

    Returns:
        list: List of all news items from all sources
    """
    all_items = []
    sources = get_all_sources()

    logger.info(f"Starting news collection from {len(sources)} sources")

    for source in sources:
        url = source["url"]
        source_type = source["source_type"]
        metadata = source.get("metadata", {})

        try:
            items = parse_feed(url, source_type, metadata)
            all_items.extend(items)
        except Exception as e:
            logger.error(f"Failed to process source {url}: {e}")
            # Continue with other sources
            continue

    logger.info(f"Collected {len(all_items)} total items before deduplication")
    return all_items


def save_to_file(items, filepath):
    """
    Save news items to a JSON file.

    Args:
        items (list): List of news items to save
        filepath (str): Path to save the file

    Returns:
        bool: True if successful
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(items)} items to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save file {filepath}: {e}")
        return False


def print_stats(stats, title):
    """
    Print filtering statistics in a readable format.

    Args:
        stats (dict): Statistics dictionary
        title (str): Title for the stats section
    """
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print(f"  Input items:                {stats['input_count']}")
    print(f"  Dropped (old):              {stats['dropped_old']}")
    print(f"  Dropped (no tickers):       {stats['dropped_no_tickers']}")

    if "dropped_not_in_watchlist" in stats:
        print(f"  Dropped (not in watchlist): {stats['dropped_not_in_watchlist']}")
    if "dropped_no_event_keywords" in stats:
        print(f"  Dropped (no event keywords): {stats['dropped_no_event_keywords']}")

    print(f"  Dropped (duplicates):       {stats['dropped_duplicates']}")
    print(f"  Output items:               {stats['output_count']}")
    print("=" * 60)
    print()


def main():
    """
    Main function to run the complete news pipeline.
    """
    print()
    print("=" * 60)
    print("  NEWS COLLECTION & FILTERING PIPELINE")
    print("=" * 60)
    print()

    # Generate filenames with today's date
    today = datetime.now().strftime("%Y%m%d")
    raw_output = f"data/news_{today}.json"
    hygiene_output = f"data/clean_news_{today}.json"
    trade_output = f"data/clean_trade_news_{today}.json"

    try:
        # =====================================================
        # STEP 1: FETCH NEWS
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 1: Fetching News from RSS Sources")
        logger.info("=" * 60)

        all_items = fetch_all_news()

        if not all_items:
            logger.warning("No news items collected")
            return 1

        # Deduplicate by (title + url)
        unique_items = deduplicate_items(all_items)

        # Sort by date (newest first)
        sorted_items = sort_items_by_date(unique_items)

        # Save raw news
        if not save_to_file(sorted_items, raw_output):
            logger.error("Failed to save raw news")
            return 1

        logger.info("=" * 60)
        logger.info(f"Raw news saved: {len(sorted_items)} items")
        logger.info("=" * 60)

        # =====================================================
        # STEP 2: HYGIENE FILTERING
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 2: Applying Hygiene Filters")
        logger.info("=" * 60)

        hygiene_result = apply_hygiene_filters(sorted_items)
        hygiene_items = hygiene_result["items"]
        hygiene_stats = hygiene_result["stats"]

        # Save hygiene-filtered news
        if not save_to_file(hygiene_items, hygiene_output):
            logger.error("Failed to save hygiene-filtered news")
            return 1

        print_stats(hygiene_stats, "Hygiene Filtering Results")

        # =====================================================
        # STEP 3: TRADE FILTERING
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 3: Applying Trade-Focused Filters")
        logger.info("=" * 60)

        trade_result = apply_trade_filters(sorted_items)
        trade_items = trade_result["items"]
        trade_stats = trade_result["stats"]

        # Save trade-filtered news
        if not save_to_file(trade_items, trade_output):
            logger.error("Failed to save trade-filtered news")
            return 1

        print_stats(trade_stats, "Trade Filtering Results")

        # =====================================================
        # SUMMARY
        # =====================================================
        print()
        print("=" * 60)
        print("  PIPELINE COMPLETE")
        print("=" * 60)
        print(f"  Raw news:              {raw_output}")
        print(f"                         ({len(sorted_items)} items)")
        print()
        print(f"  Hygiene-filtered:      {hygiene_output}")
        print(f"                         ({len(hygiene_items)} items)")
        print()
        print(f"  Trade-filtered:        {trade_output}")
        print(f"                         ({len(trade_items)} items)")
        print("=" * 60)
        print()

        return 0

    except Exception as e:
        logger.error(f"Fatal error in pipeline: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
