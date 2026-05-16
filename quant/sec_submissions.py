from __future__ import annotations

import gzip
import json
import time
import urllib.request
from pathlib import Path

from sec_ticker_map import normalize_cik


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
DEFAULT_FORMS = {"8-K", "10-Q", "10-K"}


def submission_cache_path(cik: str, cache_dir: Path | str | None = None) -> Path:
    cik_norm = normalize_cik(cik)
    if not cik_norm:
        raise ValueError(f"invalid cik: {cik!r}")
    return Path(cache_dir or DEFAULT_CACHE_DIR) / f"CIK{cik_norm}.json"


def fetch_submission(
    cik: str,
    *,
    cache_dir: Path | str | None = None,
    refresh: bool = False,
    user_agent: str = "ginger-research/1.0 contact: research@example.com",
    sleep_seconds: float = 0.11,
) -> dict:
    """Fetch or read a cached SEC company submissions JSON payload."""
    cik_norm = normalize_cik(cik)
    if not cik_norm:
        raise ValueError(f"invalid cik: {cik!r}")
    path = submission_cache_path(cik_norm, cache_dir=cache_dir)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    request = urllib.request.Request(
        SEC_SUBMISSIONS_URL.format(cik=cik_norm),
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return payload


def _recent_filings(payload: dict) -> dict:
    filings = payload.get("filings") if isinstance(payload, dict) else {}
    recent = filings.get("recent") if isinstance(filings, dict) else {}
    return recent if isinstance(recent, dict) else {}


def _recent_row_count(recent: dict) -> int:
    lengths = [len(value) for value in recent.values() if isinstance(value, list)]
    return max(lengths) if lengths else 0


def _recent_value(recent: dict, field: str, idx: int):
    values = recent.get(field)
    if not isinstance(values, list) or idx >= len(values):
        return None
    return values[idx]


def parse_recent_filings(
    payload: dict,
    *,
    ticker: str | None = None,
    cik: str | None = None,
    forms: set[str] | tuple[str, ...] | list[str] | None = None,
    max_filings: int | None = None,
) -> list[dict]:
    """Parse recent SEC submissions rows into compact filing event records."""
    allowed = {str(form).upper() for form in (forms or DEFAULT_FORMS)}
    cik_norm = normalize_cik(cik or payload.get("cik"))
    recent = _recent_filings(payload)
    rows = []
    for idx in range(_recent_row_count(recent)):
        form = str(_recent_value(recent, "form", idx) or "").upper()
        if form not in allowed:
            continue
        accession = _recent_value(recent, "accessionNumber", idx)
        filing_date = _recent_value(recent, "filingDate", idx)
        if not accession or not filing_date:
            continue
        primary_doc = _recent_value(recent, "primaryDocument", idx)
        accession_nodash = str(accession).replace("-", "")
        cik_archive = str(int(cik_norm)) if cik_norm else ""
        archive_url = None
        if cik_archive and primary_doc:
            archive_url = (
                "https://www.sec.gov/Archives/edgar/data/"
                f"{cik_archive}/{accession_nodash}/{primary_doc}"
            )
        rows.append({
            "ticker": str(ticker).upper() if ticker else None,
            "cik": cik_norm,
            "filing_type": form,
            "filing_date": str(filing_date)[:10],
            "accession_number": str(accession),
            "primary_document": primary_doc,
            "report_date": _recent_value(recent, "reportDate", idx),
            "archive_url": archive_url,
            "source": "sec_submissions",
        })
        if max_filings is not None and len(rows) >= max_filings:
            break
    return rows
