"""
RSS feed source definitions for news collection.
"""

# Google News RSS feeds using keyword-based queries (aligned with open_positions.json)
GOOGLE_NEWS_FEEDS = [
    {
        "url": "https://news.google.com/rss/search?q=NVDA+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["NVDA"]
    },
    {
        "url": "https://news.google.com/rss/search?q=META+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["META"]
    },
    {
        "url": "https://news.google.com/rss/search?q=AMD+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["AMD"]
    },
    {
        "url": "https://news.google.com/rss/search?q=TSLA+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["TSLA"]
    },
    {
        "url": "https://news.google.com/rss/search?q=GOOG+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["GOOG", "GOOGL"]
    },
    {
        "url": "https://news.google.com/rss/search?q=NFLX+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["NFLX"]
    },
    {
        "url": "https://news.google.com/rss/search?q=MCD+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["MCD"]
    },
    {
        "url": "https://news.google.com/rss/search?q=COIN+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["COIN"]
    },
    {
        "url": "https://news.google.com/rss/search?q=MU+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["MU"]
    },
    {
        "url": "https://news.google.com/rss/search?q=APP+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["APP"]
    },
    {
        "url": "https://news.google.com/rss/search?q=CRDO+stock&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["CRDO"]
    },
    {
        "url": "https://news.google.com/rss/search?q=QQQ+ETF&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["QQQ"]
    },
    {
        "url": "https://news.google.com/rss/search?q=IAU+gold+ETF&hl=en-US&gl=US&ceid=US:en",
        "keywords": ["IAU"]
    },
    {
        "url": "https://news.google.com/rss/search?q=Federal+Reserve+rates&hl=en-US&gl=US&ceid=US:en",
        "keywords": []
    },
]

# SEC RSS feeds for filings
SEC_FEEDS = [
    {
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=8-K&company=&dateb=&owner=exclude&start=0&count=100&output=atom",
        "filing_type": "8-K"
    },
    {
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=10-Q&company=&dateb=&owner=exclude&start=0&count=100&output=atom",
        "filing_type": "10-Q"
    },
    {
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=10-K&company=&dateb=&owner=exclude&start=0&count=100&output=atom",
        "filing_type": "10-K"
    },
]


def get_all_sources():
    """
    Returns all RSS feeds to fetch.

    Returns:
        list: List of dicts with 'url' and 'source_type'
    """
    sources = []

    # Add Google News feeds
    for feed in GOOGLE_NEWS_FEEDS:
        sources.append({
            "url": feed["url"],
            "source_type": "google_news",
            "metadata": {"keywords": feed.get("keywords", [])}
        })

    # Add SEC feeds
    for feed in SEC_FEEDS:
        sources.append({
            "url": feed["url"],
            "source_type": "sec",
            "metadata": {"filing_type": feed.get("filing_type", "")}
        })

    return sources
