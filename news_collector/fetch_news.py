#!/usr/bin/env python3
"""
Main entry point for news collection.

Usage:
    python fetch_news.py
"""

import json
import logging
import os
from datetime import datetime

from sources import get_all_sources
from parser import parse_feed, deduplicate_items, sort_items_by_date


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


def save_to_file(items, output_dir="data"):
    """
    Save news items to a daily JSON file.

    Args:
        items (list): List of news items to save
        output_dir (str): Directory to save the file in

    Returns:
        str: Path to the saved file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate filename with today's date
    today = datetime.now().strftime("%Y%m%d")
    filename = f"news_{today}.json"
    filepath = os.path.join(output_dir, filename)

    # Save to JSON file
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(items)} items to {filepath}")
    return filepath


def main():
    """
    Main function to orchestrate news collection.
    """
    logger.info("=" * 50)
    logger.info("Starting News Collection")
    logger.info("=" * 50)

    try:
        # Step 1: Fetch all news
        all_items = fetch_all_news()

        if not all_items:
            logger.warning("No news items collected")
            return

        # Step 2: Deduplicate
        unique_items = deduplicate_items(all_items)

        # Step 3: Sort by date (newest first)
        sorted_items = sort_items_by_date(unique_items)

        # Step 4: Save to file
        filepath = save_to_file(sorted_items)

        logger.info("=" * 50)
        logger.info(f"News collection complete!")
        logger.info(f"Total items: {len(sorted_items)}")
        logger.info(f"Output file: {filepath}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
