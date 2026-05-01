import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from sources import get_all_sources  # noqa: E402


def test_get_all_sources_adds_extra_ticker_google_feeds():
    sources = get_all_sources(extra_tickers=["INTC", "LITE", "BE"])
    urls = [source["url"] for source in sources]

    assert any("q=INTC+stock" in url for url in urls)
    assert any("q=LITE+stock" in url for url in urls)
    assert any("q=BE+stock" in url for url in urls)


def test_get_all_sources_does_not_duplicate_existing_google_feed():
    sources = get_all_sources(extra_tickers=["AMD"])
    amd_sources = [
        source for source in sources
        if source.get("metadata", {}).get("keywords") == ["AMD"]
    ]

    assert len(amd_sources) == 1
