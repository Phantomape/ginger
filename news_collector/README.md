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
- **Trend-following signals** using 20-day breakout system (deterministic, no ML)
- **LLM-powered investment advisor** using OpenAI for actionable recommendations

## Requirements

- Python 3.10+
- OpenAI API key (for investment advice feature)
- Dependencies listed in `requirements.txt`:
  - `feedparser` - RSS feed parsing
  - `requests` - HTTP requests
  - `python-dateutil` - Date parsing and normalization
  - `openai` - OpenAI API client for investment advice
  - `yfinance` - Market data for trend signals
  - `pandas` - Data manipulation for technical analysis

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY=your_api_key_here

# Run the complete pipeline
python run_pipeline.py
```

**Windows users:**
```bash
# Set environment variable on Windows
set OPENAI_API_KEY=your_api_key_here
```

## Usage

### Quick Start (Recommended)

Run the complete pipeline with a single command:

```bash
export OPENAI_API_KEY=your_api_key_here
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
9. **Generate trend signals using 20-day breakout system**
10. Save trend signals to `data/trend_signals_YYYYMMDD.json`
11. **Analyze trade news + trend signals with LLM and get investment advice**
12. Save investment advice to `data/investment_advice_YYYYMMDD.json` (or prompt to `data/llm_prompt_YYYYMMDD.txt`)

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
├── trend_signals.py            # 20-day breakout trend signals
├── llm_advisor.py              # OpenAI integration for investment advice
├── sources.py                  # RSS source definitions
├── parser.py                   # RSS parsing & normalization
├── tickers.py                  # Simple ticker extraction
├── filter.py                   # News filtering & hygiene
├── requirements.txt            # Python dependencies
├── README.md                  # This file
└── data/                      # Output directory
    ├── news_YYYYMMDD.json                # Raw collected news
    ├── clean_news_YYYYMMDD.json          # Hygiene-filtered news
    ├── clean_trade_news_YYYYMMDD.json    # Trade-focused filtered news
    ├── trend_signals_YYYYMMDD.json       # Technical trend signals
    ├── llm_prompt_YYYYMMDD.txt           # LLM prompt (if not calling API)
    ├── investment_advice_YYYYMMDD.json   # LLM investment advice (if calling API)
    └── open_positions.json               # Current portfolio positions
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

## Trend Signal Module

The trend signal module generates technical trading signals using a simple 20-day breakout system. This is completely separate from news analysis and provides pure price-action signals.

### System Rules

**Entry Signal (Breakout):**
- Today's close > highest high of previous 20 trading days

**Exit Signal (Breakdown):**
- Today's close < lowest low of previous 20 trading days

**Hard Stop (annotation only):**
- -12% from entry price (for reference, not execution)

### Trading Universe

The module analyzes tickers from:
1. WATCHLIST defined in [filter.py](news_collector/filter.py)
2. Current positions in `data/open_positions.json`
3. Union of both (all unique tickers)

### Data Source

- Uses `yfinance` to download daily OHLCV data
- Lookback: 60 calendar days for reliable 20-day rolling windows
- Gracefully handles missing data (skips with warning)

### Output Format

Saved to `data/trend_signals_YYYYMMDD.json`:

```json
{
  "generated_at": "2026-02-14T10:30:00",
  "asof_date": "2026-02-14",
  "window": 20,
  "universe": ["NVDA", "META", "AMD", ...],
  "signals": {
    "NVDA": {
      "close": 123.45,
      "20d_high": 125.00,
      "20d_low": 110.00,
      "breakout": false,
      "breakdown": false,
      "position": {
        "shares": 41,
        "avg_cost": 102.17,
        "unrealized_pnl_pct": 0.2078,
        "distance_to_hard_stop_pct": 0.1200,
        "hard_stop_price": 89.91
      }
    }
  }
}
```

### Position Context

If a ticker is held (found in `open_positions.json`), the signal includes:
- **shares**: Current position size
- **avg_cost**: Average entry price
- **unrealized_pnl_pct**: Current profit/loss percentage
- **distance_to_hard_stop_pct**: Distance to -12% stop from avg_cost
- **hard_stop_price**: Actual stop price level

### Characteristics

- **Deterministic**: No machine learning or optimization
- **Pure technical**: Does NOT use news or fundamentals
- **Simple**: Single rule-based system
- **Transparent**: All calculations visible in output

### Running Standalone

```bash
python trend_signals.py
```

This generates signals for the current universe and saves to the daily output file.

## LLM Investment Advisor

After filtering the trade news and generating trend signals, the pipeline combines all inputs for comprehensive investment analysis.

### Features

The LLM advisor analyzes:
- Your current portfolio positions (from `data/open_positions.json`)
- Recent trade-filtered news (last 72 hours, event-driven)
- Technical trend signals (20-day breakout system, price-action)
- Event significance and impact on holdings

### Output Format

The advice is saved to `data/investment_advice_YYYYMMDD.json`:

```json
{
  "timestamp": "2026-01-23T10:30:00",
  "advice": "Investment advice text...",
  "token_usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801
  }
}
```

### Investment Advice Structure

The LLM provides:
1. **Key Insights**: Most important developments for your portfolio
2. **Risk Assessment**: Immediate risks or concerns for current positions
3. **Actionable Recommendations**:
   - HOLD: Positions to maintain
   - REDUCE/TRIM: Positions to reduce
   - WATCH: Positions needing close monitoring
   - OPPORTUNITIES: Potential buying opportunities
4. **Priority Actions**: What to do first (in order)

### Configuration

- **Model**: Default is `gpt-4o` (latest and most capable, configurable in [llm_advisor.py](news_collector/llm_advisor.py))
- **API Key**: Set via `OPENAI_API_KEY` environment variable
- **Temperature**: 0.3 (lower for more focused, consistent advice)
- **Max Tokens**: 2000 (configurable)

### Skipping LLM Analysis

The LLM advisor is skipped if:
- No trade-filtered news items are found
- `OPENAI_API_KEY` environment variable is not set

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
