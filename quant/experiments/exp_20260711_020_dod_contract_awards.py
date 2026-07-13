"""exp-20260711-020: DoD daily contract-award announcements candidate pool.

Alpha search on a genuinely new PIT data source: the official Department of
Defense/War daily "Contracts" press release (war.gov, formerly defense.gov),
published at ~17:00 ET each business day and listing every award valued at
$7.5M or more with contractor name, location, dollar value, and awarding
branch.

Data provenance (all cached under data/experiments/exp-20260711-020/cache):
- Article list + publication timestamps: ArticleCS RSS feed
  (ContentType=400, Site=945), 500 items reaching back to 2024-05-20.
- Historical article bodies: Wayback Machine snapshots (the live article
  pages are Akamai-blocked for non-browser clients; the announcement text is
  static after publication, so a later snapshot carries the identical
  content; the PIT event time remains the same-day 17:00 ET publication).

Fixed policy bundle (single decision hypothesis, no sweeping):
- Event: one contractor (mapped to a warehouse-liquid ticker) is named in
  single-awardee announcement paragraphs summing to >= $250M on one
  announcement date. Multi-awardee/IDIQ-shared paragraphs are excluded.
- Signal date: the next trading day after the announcement date (publication
  is always after the 16:00 ET close).
- The unchanged exp-20260617-024 absorption/liquidity recipe, next-open
  paper entry, 10-session close exit, costs, top-1/day, 10-day cooldown.

This runner changes no production code, orders, ranking, sizing, exits,
watchlists, or LLM behavior. implementation_mode is a private replay scout
because the data shape (Wayback-backfilled press-release parsing) was
genuinely uncertain until this materialization; a positive result is a lead
that still requires a shared default-off helper before acceptance.

Modes:
    python exp_20260711_020_dod_contract_awards.py build-events [--no-fetch]
    python exp_20260711_020_dod_contract_awards.py            # replay + gates

No JavaScript was used.
"""

from __future__ import annotations

import html as html_lib
import json
import math
import re
import sqlite3
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import exp_20260617_024_s8_employee_equity_registration_absorption_scout as runner

# Registry persistence is delegated to runner._persist, which goes through
# experiment_registry.persist_self_registered_result( ) -- the sanctioned
# enforced+propagating path. This module never writes the registry directly.


EXPERIMENT_ID = "exp-20260711-020"
STEM = "dod_contract_awards"
TRIAL_FAMILY = "dod_daily_contract_award_candidate_pool"
TRIAL_VARIANT_ID = "fixed_dod_award_total_250m_top1_10d_v1"
CHANGED_VARIABLE = "dod_daily_contract_award_large_value_candidate_pool"
RULE_VERSION = CHANGED_VARIABLE + "_v1"
OWNER = "alpha-explore"

REPO_ROOT = runner.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_020_{STEM}.json"
EVENTS_JSON = OUT_DIR / "dod_contract_award_events.json"
# Raw RSS/CDX/article HTML cache lives under the gitignored data/cache tree
# (32MB of refetchable pages); the durable parsed artifact is EVENTS_JSON.
CACHE_DIR = REPO_ROOT / "data" / "cache" / "dod_contracts"
RSS_CACHE = CACHE_DIR / "rss_contracts_max800.xml"
CDX_CACHES = (CACHE_DIR / "cdx_wargov.txt", CACHE_DIR / "cdx_defensegov.txt")
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = runner.BASE_NOTIONAL_USD
HOLD_DAYS = runner.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = runner.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = runner.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = runner.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = runner.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = runner.MIN_SIGNAL_RETURN
MIN_SIGNAL_EXCESS_SPY = runner.MIN_SIGNAL_EXCESS_SPY
MIN_CLOSE_LOCATION = runner.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = runner.MIN_VOLUME_RATIO_20D
MAX_REALIZED_VOL_20D = runner.MAX_REALIZED_VOL_20D
MIN_RET20_EXCESS_SPY = runner.MIN_RET20_EXCESS_SPY
MAX_EVENT_AGE_TRADING_DAYS = runner.MAX_EVENT_AGE_TRADING_DAYS

MIN_AWARD_TOTAL_USD = 250_000_000.0
FETCH_START = "2024-09-01"
FETCH_END = "2026-04-30"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
RSS_URL = (
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx"
    "?ContentType=400&Site=945&max=800"
)

PREDICTION = {
    "success_probability": 0.25,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "anticipated_by_market",
        "thin_sample",
        "concentration_in_few_primes",
        "not_incremental_vs_comparators",
    ],
    "confidence_reason": (
        "Genuinely new PIT data source (official DoD daily award press "
        "release, never scanned; prior rejects used SEC filing text). "
        "Publication timing is fixed 17:00 ET so next-open execution is "
        "clean. Disconfirmers: awards to primes are routine and may be "
        "fully priced; sample may concentrate in LMT/RTX/NOC."
    ),
    "recorded_at": "2026-07-11T16:21:07+00:00",
}

PRODUCTION_IMPACT = {
    **runner.base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": False,
    "uses_dod_contract_announcements": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **runner.base.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing RSS item, missing Wayback snapshot, unparsable award "
            "paragraph, unmapped contractor, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is "
        "only a replay lead until a shared default-off helper computes the "
        "same DoD award events (live RSS + article fetch), publication-time "
        "signal date, absorption gate, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: official DoD daily contract-award "
        "announcements (war.gov/defense.gov Contracts press release, "
        "published ~17:00 ET each business day, PIT-clean via RSS pubDate) "
        "naming a publicly traded liquid prime contractor with a large "
        "announced dollar value are an underreaction demand event; a fixed "
        "mapping of contractor names to tickers with next-open entry and the "
        "standard 10-day exit should add positive after-cost value versus "
        "displaced candidates across the three canonical windows."
    ),
    "2_history_check": {
        "exp-20260615-012": (
            "Rejected SEC earnings-release backlog/contract-award TEXT "
            "surface. This run does not parse SEC filings at all; it uses "
            "the awarding agency's own same-day publication with normalized "
            "dollar values, which is the materially richer provenance that "
            "reflection asked for."
        ),
        "exp-20260622-001": (
            "Rejected SEC 8-K public funding award text surface. Same "
            "boundary: this run swaps the data source to the official DoD "
            "daily award feed instead of issuer-side SEC text."
        ),
        "exp-20260617-024": (
            "The S-8 absorption scout supplies the frozen absorption/"
            "liquidity/top-1/10d recipe reused here unchanged; only the "
            "event source is swapped."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two "
        "EV-improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and "
        "accepted compression/distribution comparators must be beaten. "
        "Replay-only positives are leads until shared daily/backtest parity "
        "exists."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260711_020_dod_contract_awards.py build-events --no-fetch "
        "&& .\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260711_020_dod_contract_awards.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None

_ET = ZoneInfo("America/New_York")

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Contractor-name -> ticker patterns, matched against the normalized first
# comma-segment of a single-awardee paragraph. Ordered; first hit wins.
# Exclusions run first: private firms, foreign listings, and joint ventures
# whose economics cannot be attributed to one US-listed parent.
_EXCLUDE_PATTERNS = (
    "general atomics",
    "sierra nevada",
    "bae systems",
    "rolls-royce",
    "rolls royce",
    "airbus",
    "am general",
    "blue origin",
    "space exploration technologies",
    "spacex",
    "anduril",
    "peraton",
    "mitre",
    "aerospace corp",
    "battelle",
    "deloitte",
    "united launch alliance",
    "bell boeing",
    "boeing sikorsky",
    "lockheed martin and boeing",
    "joint venture",
)
_TICKER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("lockheed", "LMT"),
    ("sikorsky", "LMT"),
    ("raytheon", "RTX"),
    ("rtx corp", "RTX"),
    ("collins aerospace", "RTX"),
    ("pratt and whitney", "RTX"),
    ("pratt & whitney", "RTX"),
    ("northrop", "NOC"),
    ("northrup", "NOC"),  # recurring DoD typo for Northrop
    ("boeing", "BA"),
    ("insitu", "BA"),
    ("general dynamics", "GD"),
    ("gulfstream", "GD"),
    ("electric boat", "GD"),
    ("bath iron works", "GD"),
    ("national steel and shipbuilding", "GD"),
    ("nassco", "GD"),
    ("huntington ingalls", "HII"),
    ("ingalls shipbuilding", "HII"),
    ("newport news shipbuilding", "HII"),
    ("l3harris", "LHX"),
    ("l-3harris", "LHX"),
    ("l3 harris", "LHX"),
    ("harris corp", "LHX"),
    ("l3 technologies", "LHX"),
    ("textron", "TXT"),
    ("bell helicopter", "TXT"),
    ("honeywell", "HON"),
    ("general electric", "GE"),
    ("ge aerospace", "GE"),
    ("ge aviation", "GE"),
    ("leidos", "LDOS"),
    ("booz allen", "BAH"),
    ("caci", "CACI"),
    ("science applications international", "SAIC"),
    ("kbr", "KBR"),
    ("jacobs technology", "J"),
    ("jacobs engineering", "J"),
    ("parsons", "PSN"),
    ("v2x", "VVX"),
    ("vectrus", "VVX"),
    ("vertex aerospace", "VVX"),
    ("amentum", "AMTM"),
    ("aerovironment", "AVAV"),
    ("kratos", "KTOS"),
    ("rocket lab", "RKLB"),
    ("palantir", "PLTR"),
    ("oshkosh", "OSK"),
    ("curtiss-wright", "CW"),
    ("curtiss wright", "CW"),
    ("heico", "HEI"),
    ("transdigm", "TDG"),
    ("teledyne", "TDY"),
    ("mercury systems", "MRCY"),
    ("mercury mission systems", "MRCY"),
    ("ducommun", "DCO"),
    ("leonardo drs", "DRS"),
    ("howmet", "HWM"),
    ("astronics", "ATRO"),
    ("embraer", "ERJ"),
    ("cae usa", "CAE"),
    ("archer aviation", "ACHR"),
    ("intuitive machines", "LUNR"),
    ("maximus", "MMS"),
    ("icf incorporated", "ICFI"),
    ("aecom", "ACM"),
    ("fluor", "FLR"),
    ("tetra tech", "TTEK"),
    ("vse corp", "VSEC"),
    ("aar supply chain", "AIR"),
    ("aar corp", "AIR"),
    ("woodward", "WWD"),
    ("axon enterprise", "AXON"),
    ("iridium", "IRDM"),
    ("viasat", "VSAT"),
    ("hughes network", "SATS"),
    ("lumen technologies", "LUMN"),
    ("comtech", "CMTL"),
    ("dxc technology", "DXC"),
    ("unisys", "UIS"),
    ("cdw government", "CDW"),
    ("microsoft", "MSFT"),
    ("amazon web services", "AMZN"),
    ("amazon.com", "AMZN"),
    ("alphabet", "GOOGL"),
    ("google", "GOOGL"),
    ("oracle", "ORCL"),
    ("international business machines", "IBM"),
    ("ibm corp", "IBM"),
    ("dell ", "DELL"),
    ("hewlett packard enterprise", "HPE"),
    ("cisco systems", "CSCO"),
    ("at&t", "T"),
    ("at and t", "T"),
    ("verizon", "VZ"),
    ("accenture", "ACN"),
    ("motorola solutions", "MSI"),
    ("general motors", "GM"),
    ("gm defense", "GM"),
    ("ford motor", "F"),
    ("fedex", "FDX"),
    ("united parcel service", "UPS"),
    ("caterpillar", "CAT"),
    ("deere", "DE"),
    ("cummins", "CMI"),
    ("pfizer", "PFE"),
    ("moderna", "MRNA"),
    ("merck", "MRK"),
    ("johnson & johnson", "JNJ"),
    ("johnson and johnson", "JNJ"),
    ("abbott", "ABT"),
    ("great lakes dredge", "GLDD"),
    ("olin corp", "OLN"),
    ("elbit systems", "ESLT"),
    ("exxon", "XOM"),
    ("valero", "VLO"),
    ("phillips 66", "PSX"),
)

_SINGLE_AWARD_RE = re.compile(
    r"\b(?:is|was)\s+(?:being\s+)?awarded\b|\bhas\s+been\s+awarded\b",
    re.IGNORECASE,
)
_MULTI_AWARD_RE = re.compile(
    r"\bare\s+(?:being\s+)?awarded\b|\bhave\s+been\s+awarded\b|\bwill\s+compete\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"\$([0-9][0-9,]*(?:\.[0-9]+)?)\s*(million|billion)?", re.IGNORECASE
)
_ARTICLE_ID_RE = re.compile(r"/Article/(\d{5,9})/", re.IGNORECASE)
_SLUG_DATE_RE = re.compile(
    r"contracts-for-([a-z]+)-(\d{1,2})-(\d{4})", re.IGNORECASE
)
_PARAGRAPH_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return runner._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return runner._round(value, digits)


def _http_get(url: str, *, retries: int = 3, timeout: int = 90) -> bytes | None:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:  # noqa: BLE001 - retried, then recorded
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    print(f"[fetch] failed {url}: {last_error}", file=sys.stderr)
    return None


def _slug_date(url: str) -> str:
    match = _SLUG_DATE_RE.search(url)
    if not match:
        return ""
    month = _MONTHS.get(match.group(1).lower())
    if not month:
        return ""
    return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"


def _pub_datetime_et(pub_date_rfc822: str) -> str:
    try:
        parsed = datetime.strptime(pub_date_rfc822.strip(), "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError:
        return ""
    return parsed.replace(tzinfo=timezone.utc).astimezone(_ET).isoformat()


def _rss_articles() -> list[dict[str, Any]]:
    if not RSS_CACHE.exists():
        payload = _http_get(RSS_URL)
        if payload is None:
            raise RuntimeError("RSS fetch failed and no cache exists")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        RSS_CACHE.write_bytes(payload)
    text = RSS_CACHE.read_text(encoding="utf-8", errors="ignore")
    articles: list[dict[str, Any]] = []
    for item in re.findall(r"<item>(.*?)</item>", text, re.DOTALL):
        link_match = re.search(r"<link>\s*(https?://[^<\s]+)\s*</link>", item)
        pub_match = re.search(r"<pubDate>\s*([^<]+?)\s*</pubDate>", item)
        if not link_match:
            continue
        url = link_match.group(1)
        id_match = _ARTICLE_ID_RE.search(url)
        announce_date = _slug_date(url)
        if not id_match or not announce_date:
            continue
        pub_et = _pub_datetime_et(pub_match.group(1)) if pub_match else ""
        articles.append(
            {
                "article_id": id_match.group(1),
                "url": url,
                "announce_date": announce_date,
                "publication_datetime_et": pub_et,
            }
        )
    articles.sort(key=lambda row: row["announce_date"])
    return articles


def _cdx_index() -> dict[str, tuple[str, str]]:
    """Map article_id -> (earliest 200 snapshot timestamp, original URL)."""
    index: dict[str, tuple[str, str]] = {}
    for cache in CDX_CACHES:
        if not cache.exists():
            continue
        for line in cache.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            original, timestamp = parts[0].strip(), parts[1].strip()
            if not timestamp.isdigit():
                continue
            id_match = _ARTICLE_ID_RE.search(original + "/")
            if not id_match:
                continue
            article_id = id_match.group(1)
            existing = index.get(article_id)
            if existing is None or timestamp < existing[0]:
                index[article_id] = (timestamp, original)
    return index


def _fetch_one(job: tuple[Path, str, str]) -> str:
    target, timestamp, original = job
    payload = _http_get(f"http://web.archive.org/web/{timestamp}id_/{original}")
    if payload is None or len(payload) < 2000:
        return "fetch_failed"
    target.write_bytes(payload)
    return "fetched"


def _fetch_bodies(articles: list[dict[str, Any]], *, allow_fetch: bool) -> Counter:
    stats: Counter[str] = Counter()
    cdx = _cdx_index()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[Path, str, str]] = []
    for article in articles:
        date = article["announce_date"]
        if not (FETCH_START <= date <= FETCH_END):
            stats["outside_fetch_range"] += 1
            continue
        target = CACHE_DIR / f"article_{article['article_id']}.html"
        if target.exists() and target.stat().st_size > 2000:
            stats["cached"] += 1
            continue
        snapshot = cdx.get(article["article_id"])
        if snapshot is None:
            stats["no_wayback_snapshot"] += 1
            continue
        if not allow_fetch:
            stats["fetch_disabled_missing"] += 1
            continue
        jobs.append((target, snapshot[0], snapshot[1]))
    if jobs:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as pool:
            for outcome in pool.map(_fetch_one, jobs):
                stats[outcome] += 1
    return stats


def _paragraphs(html_text: str) -> list[str]:
    out: list[str] = []
    for raw in _PARAGRAPH_RE.findall(html_text):
        text = html_lib.unescape(_TAG_RE.sub(" ", raw))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text)
    return out


def _normalise_company(segment: str) -> str:
    text = segment.strip().lstrip("*").strip().lower()
    text = text.replace("&", " and ")
    return re.sub(r"\s+", " ", text)


def _map_ticker(company_segment: str) -> str | None:
    normalized = _normalise_company(company_segment)
    for pattern in _EXCLUDE_PATTERNS:
        if pattern in normalized:
            return None
    raw_lower = company_segment.lower()
    for pattern, ticker in _TICKER_PATTERNS:
        if pattern in normalized or pattern in raw_lower:
            return ticker
    return None


def _parse_amount(text: str) -> float | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    if unit == "million":
        value *= 1_000_000.0
    elif unit == "billion":
        value *= 1_000_000_000.0
    return value


def _is_branch_header(text: str) -> bool:
    if len(text) > 48 or len(text) < 3:
        return False
    letters = [ch for ch in text if ch.isalpha()]
    return bool(letters) and all(ch.isupper() for ch in letters)


def _parse_article(html_text: str) -> tuple[list[dict[str, Any]], Counter]:
    stats: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    branch = "UNKNOWN"
    for text in _paragraphs(html_text):
        if _is_branch_header(text):
            branch = text
            continue
        if _MULTI_AWARD_RE.search(text) and not _SINGLE_AWARD_RE.search(text):
            stats["multi_award_paragraph_skipped"] += 1
            continue
        if not _SINGLE_AWARD_RE.search(text):
            continue
        company_segment = text.split(",", 1)[0]
        if not company_segment or len(company_segment) > 120:
            stats["company_segment_unusable"] += 1
            continue
        amount = _parse_amount(text)
        if amount is None or amount < 1_000_000.0:
            stats["amount_missing_or_tiny"] += 1
            continue
        stats["single_award_paragraphs"] += 1
        ticker = _map_ticker(company_segment)
        if ticker is None:
            stats["unmapped_contractor"] += 1
            continue
        stats["mapped_award_rows"] += 1
        rows.append(
            {
                "ticker": ticker,
                "contractor": company_segment.strip().lstrip("*").strip(),
                "amount_usd": amount,
                "branch": branch,
                "is_modification": "modification" in text[:400].lower(),
                "excerpt": text[:240],
            }
        )
    return rows, stats


def _warehouse_liquid_tickers() -> set[str]:
    uri = (
        f"file:{Path(runner.base.framework.WAREHOUSE).resolve().as_posix()}"
        "?mode=ro&immutable=1"
    )
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
            order by u.ticker
            """
        ).fetchall()
    return {str(row[0]).upper() for row in rows}


def build_events(*, allow_fetch: bool = True) -> dict[str, Any]:
    articles = _rss_articles()
    fetch_stats = _fetch_bodies(articles, allow_fetch=allow_fetch)
    liquid = _warehouse_liquid_tickers()
    parse_stats: Counter[str] = Counter()
    events: dict[tuple[str, str], dict[str, Any]] = {}
    parsed_articles = 0
    for article in articles:
        date = article["announce_date"]
        if not (FETCH_START <= date <= FETCH_END):
            continue
        path = CACHE_DIR / f"article_{article['article_id']}.html"
        if not path.exists():
            parse_stats["article_body_missing"] += 1
            continue
        rows, stats = _parse_article(path.read_text(encoding="utf-8", errors="ignore"))
        parse_stats.update(stats)
        parsed_articles += 1
        for row in rows:
            ticker = row["ticker"]
            if ticker not in liquid:
                parse_stats["mapped_but_not_warehouse_liquid"] += 1
                continue
            key = (date, ticker)
            event = events.setdefault(
                key,
                {
                    "ticker": ticker,
                    "filing_date": date,
                    "accepted_after_close": True,
                    "acceptance_datetime": article["publication_datetime_et"]
                    or f"{date}T17:00:00-05:00",
                    "article_id": article["article_id"],
                    "article_url": article["url"],
                    "award_total_usd": 0.0,
                    "award_count": 0,
                    "max_single_award_usd": 0.0,
                    "branches": [],
                    "any_modification": False,
                    "contractors": [],
                    "largest_award_excerpt": "",
                },
            )
            event["award_total_usd"] += float(row["amount_usd"])
            event["award_count"] += 1
            if row["amount_usd"] > event["max_single_award_usd"]:
                event["max_single_award_usd"] = float(row["amount_usd"])
                event["largest_award_excerpt"] = row["excerpt"]
            if row["branch"] not in event["branches"]:
                event["branches"].append(row["branch"])
            event["any_modification"] = bool(
                event["any_modification"] or row["is_modification"]
            )
            if row["contractor"] not in event["contractors"]:
                event["contractors"].append(row["contractor"])
    all_rows = sorted(
        events.values(), key=lambda row: (row["filing_date"], row["ticker"])
    )
    qualifying = [
        row for row in all_rows if row["award_total_usd"] >= MIN_AWARD_TOTAL_USD
    ]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "rule_version": RULE_VERSION,
        "min_award_total_usd": MIN_AWARD_TOTAL_USD,
        "fetch_window": [FETCH_START, FETCH_END],
        "articles_in_rss": len(articles),
        "articles_parsed": parsed_articles,
        "fetch_stats": dict(fetch_stats),
        "parse_stats": dict(parse_stats),
        "ticker_day_rows_total": len(all_rows),
        "qualifying_event_rows": len(qualifying),
        "qualifying_tickers": sorted({row["ticker"] for row in qualifying}),
        "rows": qualifying,
        "sub_threshold_rows": [
            {
                "ticker": row["ticker"],
                "filing_date": row["filing_date"],
                "award_total_usd": row["award_total_usd"],
            }
            for row in all_rows
            if row["award_total_usd"] < MIN_AWARD_TOTAL_USD
        ],
        "no_js": True,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_JSON.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is not None:
        return _EVENT_INDEX_CACHE
    payload = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))
    index: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []):
        if float(row.get("award_total_usd") or 0.0) < MIN_AWARD_TOTAL_USD:
            continue
        index.setdefault(str(row["ticker"]).upper(), []).append(row)
    for ticker in index:
        index[ticker].sort(key=lambda event: str(event.get("filing_date") or ""))
    summary = {
        "events_artifact": _repo_rel(EVENTS_JSON),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "min_award_total_usd": MIN_AWARD_TOTAL_USD,
        "qualifying_event_rows": sum(len(v) for v in index.values()),
        "tickers_with_events": len(index),
        "articles_parsed": payload.get("articles_parsed"),
        "parse_stats": payload.get("parse_stats"),
        "fetch_stats": payload.get("fetch_stats"),
        "no_js": True,
    }
    _EVENT_INDEX_CACHE = (index, summary)
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "dod_daily_contract_award_announcements_not_companyfacts",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    shadow = runner.base.framework.shadow
    indices = {
        ticker: shadow._row_index(shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    scan["dod_award_events_total"] = sum(len(v) for v in quality_index.values())
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = runner._signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["dod_award_events_in_window"] += 1
            confirm = runner._absorption_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_absorption_or_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.60 * float(confirm["candidate_signal_excess_spy"])
                + 0.40 * float(confirm["candidate_close_location"])
                + 0.25 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                + 0.08
                * math.log10(
                    max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0)
                    / 1_000_000.0
                )
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "DOD_CONTRACT_AWARD_CANDIDATE_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": (
                        "dod_award_published_17et_prior_day_and_signal_close_"
                        "before_next_open_paper_entry"
                    ),
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_submissions": False,
                    "uses_free_sec_companyfacts": False,
                    "uses_dod_contract_announcements": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "dod_announce_date": event.get("filing_date"),
                    "dod_publication_datetime_et": event.get("acceptance_datetime"),
                    "dod_award_total_usd": event.get("award_total_usd"),
                    "dod_award_count": event.get("award_count"),
                    "dod_max_single_award_usd": event.get("max_single_award_usd"),
                    "dod_branches": event.get("branches"),
                    "dod_any_modification": event.get("any_modification"),
                    "dod_contractors": event.get("contractors"),
                    "dod_article_id": event.get("article_id"),
                    "dod_article_url": event.get("article_url"),
                    "dod_largest_award_excerpt": event.get("largest_award_excerpt"),
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(
            existing["candidate_score"]
        ):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["candidate_signal_excess_spy"] or 0.0),
            -float(row["candidate_close_location"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = scan["eligible_event_tickers"]
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "event_rule": (
            "single-awardee DoD announcement paragraphs summed per contractor "
            f"per announcement date >= ${MIN_AWARD_TOTAL_USD:,.0f}"
        ),
        "min_award_total_usd": MIN_AWARD_TOTAL_USD,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = runner.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = runner.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_dod_contract_award_candidate_pool"
        if gate["passed"]
        else "rejected_dod_contract_award_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The DoD daily contract-award source cleared the numeric "
            "three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted in this "
            "experiment."
        )
    return (
        "The DoD daily contract-award source did not clear Gate 4 "
        f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The fixed "
        "bundle tested >= $250M single-awardee announced value per contractor "
        "day plus the frozen signal-day absorption recipe. The result is not "
        "retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = _interpretation(payload)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "private_replay_scout_due_uncertain_new_source_shape",
            "implementation_mode_reason": (
                "First materialization of the war.gov/defense.gov daily "
                "Contracts press-release surface: article bodies are Akamai-"
                "blocked and had to be Wayback-backfilled, so the data shape "
                "and parse yield were genuinely uncertain before this run. A "
                "positive result requires a shared default-off helper before "
                "acceptance."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_dod_contract_award_candidate_pool",
            "new_evidence_type": "new_data_source_dod_daily_contract_announcements",
            "new_evidence_axis": (
                "New data source never ingested by any prior experiment: the "
                "official DoD/war.gov daily Contracts press-release feed "
                "(ArticleCS RSS ContentType=400) with historical bodies from "
                "Wayback snapshots. Prior contract-award experiments "
                "(exp-20260615-012, exp-20260622-001) used SEC filing text, "
                "not the awarding agency's own same-day publication."
            ),
            "nearby_prior_experiments": [
                "exp-20260615-012",
                "exp-20260622-001",
                "exp-20260617-024",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]) & set(gate4["failed_reasons"])
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_award_total_usd": MIN_AWARD_TOTAL_USD,
        "event_scope": (
            "single-awardee paragraphs only; multi-awardee/IDIQ-shared "
            "paragraphs excluded; modifications included and tagged"
        ),
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "DoD daily contract-award events are parsed from the official "
        "Contracts press release (war.gov/defense.gov). Announcement "
        "publication is ~17:00 ET after the close, so the signal date is the "
        "next trading day; the event gate is >= $250M summed single-awardee "
        "announced value per contractor per announcement date. Candidates "
        "must then show signal-day price absorption before next-open paper "
        "entry: non-negative daily return, return minus SPY >= 0.5%, close "
        "location >= 0.56, volume ratio >= 0.75, realized vol <= 12%, ret20 "
        "excess vs SPY >= -5%, price >= $10, and ADV20 >= $50M. Paper entry "
        "is the next available open with entry slippage; exit is the close "
        "10 trading days after the signal with sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["announcement_source"] = _repo_rel(EVENTS_JSON)
    payload["gate2"]["runtime_fields"] = [
        "war.gov/defense.gov Contracts RSS link + pubDate",
        "Wayback snapshot article body (contractor, dollar value, branch)",
        "curated contractor-name -> ticker mapping",
        "warehouse ticker_universe hygiene/coverage flags",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed DoD award bundle fails, do not retry by sweeping the "
        "$250M threshold, award/market-cap ratios, modification filters, "
        "branch filters, contractor lists, absorption thresholds, top-N, "
        "hold days, cooldown, or notional on these frozen windows. A valid "
        "retry needs a genuinely different response shape justified ex ante, "
        "closed forward replacement-value rows from a fixed shared helper, "
        "or materially richer PIT award economics (e.g. obligated-vs-ceiling "
        "split, new-award-vs-modification decomposition from a second "
        "source, award backlog normalization)."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping the award-value threshold, cap-relative "
            "ratios, modification/branch/contractor filters, absorption "
            "thresholds, top-N, hold days, cooldown, or notional on these "
            "frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(EVENTS_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in runner.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("dod_award_events_in_window", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} DoD Daily Contract-Award Announcements",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(EVENTS_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): runner.base.framework._sha256(CARD_MD),
        },
    }
    runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _install() -> None:
    runner.EXPERIMENT_ID = EXPERIMENT_ID
    runner.STEM = STEM
    runner.TRIAL_FAMILY = TRIAL_FAMILY
    runner.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    runner.CHANGED_VARIABLE = CHANGED_VARIABLE
    runner.RULE_VERSION = RULE_VERSION
    runner.OWNER = OWNER
    runner.OUT_DIR = OUT_DIR
    runner.OUT_JSON = OUT_JSON
    runner.LOG_JSON = LOG_JSON
    runner.TICKET_JSON = TICKET_JSON
    runner.CARD_MD = CARD_MD
    runner.MANIFEST_JSON = MANIFEST_JSON
    runner.EXPERIMENT_LOG = EXPERIMENT_LOG
    runner.REGISTRY_JSON = REGISTRY_JSON
    runner.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    runner.HOLD_DAYS = HOLD_DAYS
    runner.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    runner.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    runner.MIN_PRICE = MIN_PRICE
    runner.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    runner.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    runner.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    runner.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    runner.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    runner.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    runner.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    runner.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    runner.PREDICTION = PREDICTION
    runner.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    runner.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    runner._EVENT_INDEX_CACHE = None
    runner._load_event_index = _load_event_index
    runner._build_quality_index = _build_quality_index
    runner._candidate_rows_for_window = _candidate_rows_for_window
    runner._gate4 = _gate4
    runner._postprocess_payload = _postprocess_payload
    runner._build_card = _build_card
    runner._write_manifest = _write_manifest


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "build-events":
        allow_fetch = "--no-fetch" not in sys.argv[2:]
        payload = build_events(allow_fetch=allow_fetch)
        print(
            json.dumps(
                {
                    "articles_in_rss": payload["articles_in_rss"],
                    "articles_parsed": payload["articles_parsed"],
                    "fetch_stats": payload["fetch_stats"],
                    "parse_stats": payload["parse_stats"],
                    "ticker_day_rows_total": payload["ticker_day_rows_total"],
                    "qualifying_event_rows": payload["qualifying_event_rows"],
                    "qualifying_tickers": payload["qualifying_tickers"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    _install()
    runner.main()


if __name__ == "__main__":
    main()
