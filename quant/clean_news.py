#!/usr/bin/env python3
"""
News filtering and cleaning script.

Applies filtering rules to collected news:
- Basic hygiene filters (recency, ticker presence, deduplication)
- Trade-focused filters (watchlist, event keywords)

Usage:
    python clean_news.py [input_file]

If no input file is provided, uses today's news file: data/news_YYYYMMDD.json
"""

import json
import logging
import os
import sys
from datetime import datetime

from filter import apply_hygiene_filters, apply_trade_filters


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_news_file(filepath):
    """
    Load news items from a JSON file.

    Args:
        filepath (str): Path to the news JSON file

    Returns:
        list: List of news items
    """
    logger.info(f"Loading news from: {filepath}")

    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)
        logger.info(f"Loaded {len(items)} items")
        return items
    except Exception as e:
        logger.error(f"Failed to load file: {e}")
        return None


def save_filtered_news(items, filepath):
    """
    Save filtered news items to a JSON file.

    Args:
        items (list): List of news items
        filepath (str): Output file path

    Returns:
        bool: True if successful
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(items)} items to: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
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
    Main function to run news filtering pipeline.
    """
    # Determine input file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Use today's news file
        today = datetime.now().strftime("%Y%m%d")
        input_file = f"data/news_{today}.json"

    logger.info("=" * 60)
    logger.info("Starting News Filtering Pipeline")
    logger.info("=" * 60)

    # Load news
    items = load_news_file(input_file)
    if items is None:
        logger.error("Failed to load news items. Exiting.")
        return 1

    if len(items) == 0:
        logger.warning("No items to filter")
        return 0

    # Generate output filenames based on input filename
    base_name = os.path.basename(input_file)
    if base_name.startswith("news_"):
        date_part = base_name.replace("news_", "").replace(".json", "")
    else:
        date_part = datetime.now().strftime("%Y%m%d")

    hygiene_output = f"data/clean_news_{date_part}.json"
    trade_output = f"data/clean_trade_news_{date_part}.json"

    # Apply hygiene filters (inst_2.txt)
    logger.info("")
    logger.info("Step 1: Applying hygiene filters...")
    hygiene_result = apply_hygiene_filters(items)
    hygiene_items = hygiene_result["items"]
    hygiene_stats = hygiene_result["stats"]

    # Save hygiene-filtered news
    if save_filtered_news(hygiene_items, hygiene_output):
        print_stats(hygiene_stats, "Hygiene Filtering Results")
    else:
        logger.error("Failed to save hygiene-filtered news")

    # Apply trade filters (inst_3.txt)
    logger.info("")
    logger.info("Step 2: Applying trade-focused filters...")
    trade_result = apply_trade_filters(items)
    trade_items = trade_result["items"]
    trade_stats = trade_result["stats"]

    # Save trade-filtered news
    if save_filtered_news(trade_items, trade_output):
        print_stats(trade_stats, "Trade Filtering Results")
    else:
        logger.error("Failed to save trade-filtered news")

    # Summary
    print()
    print("=" * 60)
    print("  Filtering Complete")
    print("=" * 60)
    print(f"  Hygiene-filtered news: {hygiene_output}")
    print(f"  Trade-filtered news:   {trade_output}")
    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
