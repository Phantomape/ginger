#!/usr/bin/env python3
"""
Unified news collection and filtering pipeline.

This script combines news fetching, filtering, and LLM analysis into a single command:
1. Fetches news from all RSS sources
2. Applies hygiene filtering
3. Applies trade-focused filtering
4. Gets investment advice from OpenAI (requires OPENAI_API_KEY env var)
5. Saves all outputs

Usage:
    export OPENAI_API_KEY=your_api_key_here
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
from llm_advisor import get_investment_advice, save_advice
from trend_signals import generate_trend_signals, save_trend_signals


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
        # STEP 4: TREND SIGNAL GENERATION
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 4: Generating Trend Signals (20-day breakout)")
        logger.info("=" * 60)

        trend_output = f"data/trend_signals_{today}.json"
        trend_signals = None

        try:
            trend_signals = generate_trend_signals()
            save_trend_signals(trend_signals, trend_output)

            print()
            print("=" * 60)
            print("  TREND SIGNALS GENERATED")
            print("=" * 60)
            print(f"  Tickers analyzed:     {len(trend_signals.get('universe', []))}")
            print(f"  Signals generated:    {len(trend_signals.get('signals', {}))}")

            # Count breakouts and breakdowns
            breakouts = sum(1 for s in trend_signals.get('signals', {}).values() if s.get('breakout'))
            breakdowns = sum(1 for s in trend_signals.get('signals', {}).values() if s.get('breakdown'))

            print(f"  Breakouts detected:   {breakouts}")
            print(f"  Breakdowns detected:  {breakdowns}")
            print("=" * 60)
            print()

        except Exception as e:
            logger.error(f"Failed to generate trend signals: {e}")
            print()
            print("=" * 60)
            print("  TREND SIGNALS: FAILED")
            print("=" * 60)
            print(f"  Error: {e}")
            print("=" * 60)
            print()

        # =====================================================
        # STEP 5: LLM INVESTMENT ADVISOR
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 5: Getting Investment Advice from LLM")
        logger.info("=" * 60)

        advice_output = f"data/investment_advice_{today}.json"

        if len(trade_items) == 0:
            logger.warning("No trade-filtered news items. Skipping LLM advisor.")
            print()
            print("=" * 60)
            print("  LLM ADVISOR: SKIPPED")
            print("=" * 60)
            print("  Reason: No trade-filtered news items found")
            print("=" * 60)
            print()
        else:
            result = get_investment_advice(trade_items, trend_signals=trend_signals)

            if result["success"]:
                print()
                print("=" * 60)
                print("  INVESTMENT ADVICE")
                print("=" * 60)
                print()
                print(result["advice"])
                print()
                print("=" * 60)
                if result["token_usage"]:
                    print(f"  Tokens used: {result['token_usage']['total_tokens']} "
                          f"(prompt: {result['token_usage']['prompt_tokens']}, "
                          f"completion: {result['token_usage']['completion_tokens']})")
                print("=" * 60)
                print()

                # Save advice to file
                save_advice(result["advice"], advice_output, result["token_usage"])
            else:
                logger.error(f"LLM advisor failed: {result['error']}")
                print()
                print("=" * 60)
                print("  LLM ADVISOR: FAILED")
                print("=" * 60)
                print(f"  Error: {result['error']}")
                print("=" * 60)
                print()

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
        print()
        if trend_signals and os.path.exists(trend_output):
            print(f"  Trend signals:         {trend_output}")
            print(f"                         ({len(trend_signals.get('signals', {}))} tickers)")
            print()
        if len(trade_items) > 0 and os.path.exists(f"data/investment_advice_{today}.json"):
            print(f"  Investment advice:     data/investment_advice_{today}.json")
        print("=" * 60)
        print()

        return 0

    except Exception as e:
        logger.error(f"Fatal error in pipeline: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
