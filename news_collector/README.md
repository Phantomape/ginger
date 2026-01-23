# News Collector

A minimal, reliable news collection module for stock market news aggregation.

## Overview

This project collects recent stock market news from free, public RSS sources and normalizes them into a clean JSON format. It is designed to provide clean, auditable input data for trading decision systems.

**This module does NOT:**
- Perform sentiment analysis
- Add trading logic or signals
- Rank or score news importance
- Call any LLMs or external APIs requiring authentication

## Features

- Fetches news from Google News RSS feeds (keyword-based)
- Fetches recent SEC filings (8-K, 10-Q, 10-K)
- Normalizes all news into a standard JSON format
- Extracts stock tickers using simple keyword matching
- Deduplicates items by title and URL
- Saves one JSON file per day
- Handles errors gracefully without crashing
- **Filtering pipeline** for news hygiene and trade-focused filtering
- Recency filtering (72-hour window)
- Watchlist-based filtering
- Event keyword filtering (earnings, guidance, etc.)
- Automatic logging of filtering statistics

## Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`:
  - `feedparser` - RSS feed parsing
  - `requests` - HTTP requests
  - `python-dateutil` - Date parsing and normalization

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the complete pipeline
python run_pipeline.py
```

## Usage

### Quick Start (Recommended)

Run the complete pipeline with a single command:

```bash
python run_pipeline.py
```

This will:
1. Fetch news from all configured RSS sources
2. Parse and normalize items into standard format
3. Deduplicate by (title + url)
4. Sort by publication date (newest first)
5. Save raw output to `data/news_YYYYMMDD.json`
6. Apply hygiene filters and save to `data/clean_news_YYYYMMDD.json`
7. Apply trade-focused filters and save to `data/clean_trade_news_YYYYMMDD.json`
8. Display filtering statistics for both pipelines

### Advanced Usage (Individual Scripts)

If you need more control, you can run the steps separately:

**Step 1: Fetch News Only**
```bash
python fetch_news.py
```

**Step 2: Filter Existing News**
```bash
python clean_news.py [optional_input_file]
```

## Project Structure

```
news_collector/
├── run_pipeline.py             # Unified pipeline (recommended)
├── fetch_news.py               # News collection only
├── clean_news.py               # Filtering only
├── sources.py                  # RSS source definitions
├── parser.py                   # RSS parsing & normalization
├── tickers.py                  # Simple ticker extraction
├── filter.py                   # News filtering & hygiene
├── requirements.txt            # Python dependencies
├── README.md                  # This file
└── data/                      # Output directory
    ├── news_YYYYMMDD.json              # Raw collected news
    ├── clean_news_YYYYMMDD.json        # Hygiene-filtered news
    └── clean_trade_news_YYYYMMDD.json  # Trade-focused filtered news
```

## Output Format

Each news item in the output JSON has the following structure:

```json
{
  "source": "google_news | sec",
  "title": "Article title",
  "summary": "Article summary or description",
  "url": "https://...",
  "published_at": "2024-01-15T10:30:00",
  "tickers": ["AAPL", "MSFT"],
  "raw_source": "https://... (original RSS feed URL)"
}
```

### Field Descriptions

- **source**: Source type (`google_news` or `sec`)
- **title**: News article title or filing name
- **summary**: Article summary or description (HTML tags removed)
- **url**: Link to the full article or filing
- **published_at**: Publication timestamp in ISO-8601 format (UTC)
- **tickers**: List of stock ticker symbols found (may be empty)
- **raw_source**: Original RSS feed URL for audit trail

## Filtering Pipeline

The filtering system provides two levels of news filtering:

### Hygiene Filtering (Basic)

Output: `data/clean_news_YYYYMMDD.json`

Applies basic hygiene rules to clean the news data:

1. **Recency Filter**: Drops items older than 72 hours
2. **Ticker Presence**: Drops items with empty ticker lists
3. **Deduplication**: Deduplicates by (ticker + source), keeping most recent

### Trade Filtering (Focused)

Output: `data/clean_trade_news_YYYYMMDD.json`

Applies stricter, trade-focused filters:

1. **Recency Filter**: Drops items older than 72 hours
2. **Ticker Presence**: Drops items with empty ticker lists
3. **Watchlist Filter**: Keeps only items matching the watchlist (NVDA, META, AMD, QQQ, TSLA, MCD, CRDO, IAU, NFLX, APP, GOOG, COIN, MU)
4. **Event Keyword Filter**:
   - **Keeps** items with important trading signals: earnings, guidance, forecast, acquisition, lawsuit, investigation, approval, downgrade, upgrade, raises, cuts
   - **Drops** market summary items: dow, s&p, nasdaq, market, stocks rally, live updates
5. **Deduplication**: Deduplicates by (ticker + source), keeping most recent

### Filtering Statistics

The filtering pipeline logs detailed statistics:

```
==================================================
  Hygiene Filtering Results
==================================================
  Input items:                150
  Dropped (old):              23
  Dropped (no tickers):       45
  Dropped (duplicates):       12
  Output items:               70
==================================================
```

All filtering is deterministic and does not use any LLMs or machine learning.

## Data Sources

### Google News RSS
Keyword-based RSS feeds covering:
- Individual stocks (NVDA, AAPL, MSFT)
- Market indices
- Federal Reserve and economic news

### SEC RSS
Recent filings from the SEC EDGAR database:
- **8-K**: Current reports (material events)
- **10-Q**: Quarterly reports
- **10-K**: Annual reports

## Configuration

### News Sources

To add or modify news sources, edit [sources.py](news_collector/sources.py):

- **GOOGLE_NEWS_FEEDS**: List of Google News RSS URLs with keyword hints
- **SEC_FEEDS**: List of SEC EDGAR RSS URLs with filing types

### Filtering Rules

To customize filtering behavior, edit [filter.py](news_collector/filter.py):

- **WATCHLIST**: List of tickers to focus on (from open_positions.json: NVDA, META, AMD, QQQ, TSLA, MCD, CRDO, IAU, NFLX, APP, GOOG, COIN, MU)
- **EVENT_KEYWORDS**: Keywords that indicate important trading events
- **MARKET_SUMMARY_KEYWORDS**: Keywords that indicate generic market news to filter out
- **Recency window**: Modify `max_hours` parameter in filtering functions (default: 72)

## Ticker Extraction

Tickers are extracted using simple keyword matching against a predefined list of common stock symbols. The extraction logic in [tickers.py](news_collector/tickers.py) uses:

- Word boundary matching to avoid partial matches
- A curated list of major tickers (FAANG, major indices, etc.)
- Optional keyword hints from the RSS source

**Note**: Ticker extraction prioritizes accuracy over completeness. It's acceptable for some items to have empty ticker lists.

## Error Handling

The system is designed to be resilient:
- If one RSS source fails, others continue processing
- Malformed RSS items are logged and skipped
- All errors are logged to stdout
- The script never crashes due to a single bad feed or entry

## Logging

Progress and errors are logged to stdout with timestamps:

```
2024-01-15 10:30:00 - INFO - Starting news collection from 8 sources
2024-01-15 10:30:02 - INFO - Fetching google_news feed: https://...
2024-01-15 10:30:03 - INFO - Parsed 25 items from google_news feed
...
```

## Extending the Project

To add new features:

1. **New RSS sources**: Add to [sources.py](news_collector/sources.py)
2. **More tickers**: Extend the `COMMON_TICKERS` list in [tickers.py](news_collector/tickers.py)
3. **Custom parsing**: Modify `normalize_entry()` in [parser.py](news_collector/parser.py)
4. **Additional filters**: Add new filtering functions to [filter.py](news_collector/filter.py)
5. **Custom watchlists**: Modify the `WATCHLIST` constant or pass custom lists to filtering functions

## Assumptions

- RSS feeds are publicly accessible without authentication
- News items have at minimum a title and URL
- Publication dates may be missing for some items (these are dropped during filtering)
- Ticker extraction uses a fixed list of known symbols
- Output files are overwritten if run multiple times per day
- The 72-hour recency window is calculated from the current system time
- Filtering is deterministic and reproducible (no randomness or LLMs)

## License

This is an internal MVP module. No external license specified.
