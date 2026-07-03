"""SEC corporate event stream from EDGAR daily form indexes.

Experiment: exp-20260702-008 (measurement_repair, alpha-enabling data source).

Why this exists: the per-CIK submissions pipeline (`sec_submissions.py`,
`sec_filing_backfill.py`) can only see issuers we already track. IPO
registrations (S-1 / F-1) and merger communications (425) are filed by
entities that are often NOT yet in any tradable universe, which is exactly
the primary-entity side of the entity->listed-peer propagation direction in
`docs/alpha_next_direction_20260701.md`. The EDGAR daily form index
enumerates every filing by form type per day, so it can discover those
events without knowing CIKs in advance.

Output surface (append-only, PIT-keyed by accession + filed date):
  data/non_ohlcv/sec_corporate_event_stream/rows.jsonl
  data/non_ohlcv/sec_corporate_event_stream/manifest.json

This module changes no trading behavior. Rows are observation evidence for
a later, separately gated alpha experiment.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from data_paths import atomic_write_json, atomic_write_text
from sec_ticker_map import load_company_ticker_map, normalize_cik

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUT_DIR = DATA_DIR / "non_ohlcv" / "sec_corporate_event_stream"
DEFAULT_CACHE_DIR = DATA_DIR / "cache" / "sec" / "daily_index"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
DAILY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/form.{stamp}.idx"
)
QUARTERLY_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
)

# Fixed predeclared form set for this surface. Do not widen ad hoc; a wider
# set is a new surface version, not a tweak.
EVENT_FORMS: dict[str, dict[str, Any]] = {
    "S-1": {"event_class": "ipo_registration", "is_amendment": False},
    "S-1/A": {"event_class": "ipo_registration", "is_amendment": True},
    "F-1": {"event_class": "ipo_registration", "is_amendment": False},
    "F-1/A": {"event_class": "ipo_registration", "is_amendment": True},
    "425": {"event_class": "merger_communication", "is_amendment": False},
}
SCHEMA_VERSION = "sec_corporate_event_stream_v1"


def daily_index_url(day: date) -> str:
    quarter = (day.month - 1) // 3 + 1
    return DAILY_INDEX_URL.format(
        year=day.year, quarter=quarter, stamp=day.strftime("%Y%m%d")
    )


def index_cache_path(day: date, cache_dir: Path | str | None = None) -> Path:
    base = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    return base / f"form.{day.strftime('%Y%m%d')}.idx"


def fetch_daily_index(
    day: date,
    *,
    cache_dir: Path | str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 30.0,
    force: bool = False,
) -> str | None:
    """Return the raw form index text for `day`, or None when absent (holiday).

    Responses are cached; a cached miss is recorded as an empty file so
    holidays are not refetched on every backfill run.
    """
    cache_path = index_cache_path(day, cache_dir)
    if cache_path.exists() and not force:
        text = cache_path.read_text(encoding="latin-1")
        return text if text.strip() else None
    request = urllib.request.Request(
        daily_index_url(day), headers={"User-Agent": user_agent}
    )
    text = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("latin-1")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text("", cache_path)
                return None
            # 403/429/5xx: SEC throttling — back off and retry
            if exc.code in (403, 429, 500, 502, 503) and attempt < 4:
                time.sleep(10.0 * (attempt + 1))
                continue
            raise
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(text, cache_path)
    return text


# Daily indexes use `20260701`, quarterly indexes use `2024-12-27`; header
# column offsets do NOT align with data rows in the quarterly files, so rows
# are parsed with a right-anchored regex instead of fixed-width slicing.
_INDEX_ROW_RE = re.compile(
    r"^(?P<form_type>\S.*?)\s{2,}"
    r"(?P<company_name>\S.*?)\s{2,}"
    r"(?P<cik>\d{1,10})\s{2,}"
    r"(?P<date_filed>\d{4}-\d{2}-\d{2}|\d{8})\s{2,}"
    r"(?P<file_name>edgar/\S+)\s*$"
)


def parse_daily_index(text: str) -> list[dict[str, str]]:
    """Parse a form.*.idx document (daily or quarterly) into raw filing dicts."""
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        match = _INDEX_ROW_RE.match(line.rstrip("\r"))
        if match is None:
            continue
        rows.append(match.groupdict())
    return rows


def _accession_from_file_name(file_name: str) -> str | None:
    stem = file_name.rsplit("/", 1)[-1]
    if stem.endswith(".txt"):
        stem = stem[: -len(".txt")]
    return stem or None


def _normalize_filed_date(value: str) -> str | None:
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def build_event_rows(
    raw_rows: Iterable[dict[str, str]],
    *,
    source_index_file: str,
    ticker_map: dict[str, dict] | None = None,
) -> list[dict[str, Any]]:
    """Filter raw index rows to the predeclared event forms and enrich."""
    events: list[dict[str, Any]] = []
    for raw in raw_rows:
        form_type = raw["form_type"].upper()
        spec = EVENT_FORMS.get(form_type)
        if spec is None:
            continue
        accession = _accession_from_file_name(raw["file_name"])
        filed_date = _normalize_filed_date(raw["date_filed"])
        if accession is None or filed_date is None:
            continue
        cik = normalize_cik(raw["cik"])
        mapped = (ticker_map or {}).get(cik or "")
        ticker = (mapped or {}).get("ticker")
        events.append(
            {
                "schema_version": SCHEMA_VERSION,
                "accession": accession,
                "form_type": form_type,
                "event_class": spec["event_class"],
                "is_amendment": spec["is_amendment"],
                "filed_date": filed_date,
                "cik": cik,
                "company_name": raw["company_name"],
                "ticker": ticker,
                "ticker_status": "resolved" if ticker else "unresolved",
                "source_index_file": source_index_file,
                "edgar_path": raw["file_name"],
            }
        )
    return events


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    # One accession can legitimately appear under several CIKs (e.g. a 425
    # indexed for both acquirer and target), so cik is part of the identity.
    return (
        str(row.get("accession")),
        str(row.get("form_type")),
        str(row.get("cik")),
    )


def load_existing_keys(rows_path: Path) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    if not rows_path.exists():
        return keys
    with rows_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add(_row_key(row))
    return keys


def append_rows(rows_path: Path, rows: list[dict[str, Any]]) -> int:
    """Append rows not already present. Returns number appended."""
    existing = load_existing_keys(rows_path)
    fresh = []
    for row in rows:
        key = _row_key(row)
        if key in existing:
            continue
        existing.add(key)
        fresh.append(row)
    if not fresh:
        return 0
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    fresh.sort(key=lambda r: (r.get("filed_date") or "", r.get("accession") or ""))
    with rows_path.open("a", encoding="utf-8") as handle:
        for row in fresh:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(fresh)


def _quarters(start: date, end: date) -> list[tuple[int, int]]:
    quarters = []
    year, quarter = start.year, (start.month - 1) // 3 + 1
    while (year, quarter) <= (end.year, (end.month - 1) // 3 + 1):
        quarters.append((year, quarter))
        quarter += 1
        if quarter > 4:
            year, quarter = year + 1, 1
    return quarters


def quarterly_index_url(year: int, quarter: int) -> str:
    return QUARTERLY_INDEX_URL.format(year=year, quarter=quarter)


def quarterly_cache_path(
    year: int, quarter: int, cache_dir: Path | str | None = None
) -> Path:
    base = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    return base / f"form.{year}QTR{quarter}.idx"


def fetch_quarterly_index(
    year: int,
    quarter: int,
    *,
    cache_dir: Path | str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 120.0,
    force: bool = False,
) -> str | None:
    """Return the quarterly form index text, cached like the daily variant."""
    cache_path = quarterly_cache_path(year, quarter, cache_dir)
    if cache_path.exists() and not force:
        text = cache_path.read_text(encoding="latin-1")
        return text if text.strip() else None
    request = urllib.request.Request(
        quarterly_index_url(year, quarter), headers={"User-Agent": user_agent}
    )
    text = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("latin-1")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text("", cache_path)
                return None
            if exc.code in (403, 429, 500, 502, 503) and attempt < 4:
                time.sleep(10.0 * (attempt + 1))
                continue
            raise
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(text or "", cache_path)
    return text


def ingest_range(
    start: date,
    end: date,
    *,
    out_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_seconds: float = 1.0,
    ticker_map: dict[str, dict] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Fetch quarterly form indexes covering [start, end] and append events.

    One request per quarter (~8 for the full canonical history) instead of one
    per business day, which stays far under SEC rate limits. Completed past
    quarters are cached permanently; the current quarter is refetched on every
    run because its full-index file grows nightly.
    """
    out_base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    rows_path = out_base / "rows.jsonl"
    manifest_path = out_base / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    quarter_status: dict[str, Any] = dict(manifest.get("quarter_status") or {})

    now = today or date.today()
    current_quarter = (now.year, (now.month - 1) // 3 + 1)
    appended_total = 0
    fetched = 0
    for year, quarter in _quarters(start, end):
        qkey = f"{year}QTR{quarter}"
        is_current = (year, quarter) >= current_quarter
        prior = quarter_status.get(qkey) or {}
        if prior.get("status") == "ingested" and prior.get("complete"):
            continue
        cache_path = quarterly_cache_path(year, quarter, cache_dir)
        needs_fetch = is_current or not cache_path.exists()
        text = fetch_quarterly_index(
            year,
            quarter,
            cache_dir=cache_dir,
            user_agent=user_agent,
            force=is_current,
        )
        if needs_fetch:
            fetched += 1
            time.sleep(sleep_seconds)
        if text is None:
            quarter_status[qkey] = {"status": "no_index", "complete": False}
            continue
        events = [
            row
            for row in build_event_rows(
                parse_daily_index(text),
                source_index_file=quarterly_index_url(year, quarter),
                ticker_map=ticker_map,
            )
            if start.isoformat() <= row["filed_date"] <= end.isoformat()
        ]
        appended = append_rows(rows_path, events)
        appended_total += appended
        quarter_status[qkey] = {
            "status": "ingested",
            "complete": not is_current,
            "event_rows": len(events),
            "appended": appended,
        }

    manifest.update(
        {
            "schema_version": SCHEMA_VERSION,
            "forms": sorted(EVENT_FORMS),
            "quarter_status": dict(sorted(quarter_status.items())),
            "last_run_utc": datetime.now(timezone.utc).isoformat(),
            "rows_file": str(rows_path.relative_to(REPO_ROOT)).replace("\\", "/")
            if rows_path.is_relative_to(REPO_ROOT)
            else str(rows_path),
        }
    )
    out_base.mkdir(parents=True, exist_ok=True)
    atomic_write_json(manifest, manifest_path)
    return {
        "quarters_considered": len(_quarters(start, end)),
        "quarters_fetched": fetched,
        "rows_appended": appended_total,
        "rows_path": str(rows_path),
    }


def _parse_cli_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=_parse_cli_date, default=None)
    parser.add_argument("--end", type=_parse_cli_date, default=None)
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Refresh the current quarter (idempotent daily mode; one request).",
    )
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    if args.daily:
        end = date.today()
        start = date(end.year, ((end.month - 1) // 3) * 3 + 1, 1)
    else:
        if not args.start or not args.end:
            parser.error("--start and --end are required unless --daily is set")
        start, end = args.start, args.end
    if start > end:
        parser.error("--start must be <= --end")

    ticker_map = load_company_ticker_map()
    summary = ingest_range(
        start,
        end,
        out_dir=args.out_dir,
        cache_dir=args.cache_dir,
        user_agent=args.user_agent,
        sleep_seconds=args.sleep_seconds,
        ticker_map=ticker_map,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
