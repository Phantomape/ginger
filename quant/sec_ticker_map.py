from __future__ import annotations

import json
import re
import urllib.request
import gzip
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = REPO_ROOT / "data" / "sec_company_tickers.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_TITLE_RE = re.compile(
    r"^\s*(?P<form>[A-Z0-9/-]+)\s+-\s+(?P<company>.*?)\s+\((?P<cik>\d{1,10})\)\s+\((?P<role>[^)]*)\)",
    re.IGNORECASE,
)


def normalize_cik(cik) -> str | None:
    if cik is None:
        return None
    digits = re.sub(r"\D", "", str(cik))
    if not digits:
        return None
    return digits.zfill(10)


def parse_sec_title(title: str | None) -> dict:
    text = (title or "").strip()
    match = SEC_TITLE_RE.search(text)
    if not match:
        return {}
    cik = normalize_cik(match.group("cik"))
    return {
        "filing_form": match.group("form").upper(),
        "company_name": match.group("company").strip(),
        "cik": cik,
        "filer_role": match.group("role").strip(),
    }


def _iter_company_ticker_rows(payload):
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, dict):
                yield value
    elif isinstance(payload, list):
        for value in payload:
            if isinstance(value, dict):
                yield value


def load_company_ticker_map(cache_path: Path | str | None = None) -> dict[str, dict]:
    path = Path(cache_path or DEFAULT_CACHE_PATH)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for row in _iter_company_ticker_rows(payload):
        cik = normalize_cik(row.get("cik_str") or row.get("cik"))
        ticker = row.get("ticker")
        if not cik or not ticker:
            continue
        out[cik] = {
            "ticker": str(ticker).upper(),
            "company_title": row.get("title") or row.get("name"),
            "cik": cik,
        }
    return out


def lookup_ticker_by_cik(cik, cache_path: Path | str | None = None) -> dict | None:
    cik_norm = normalize_cik(cik)
    if not cik_norm:
        return None
    return load_company_ticker_map(cache_path).get(cik_norm)


def enrich_sec_item(item: dict, cache_path: Path | str | None = None) -> dict:
    enriched = dict(item)
    metadata = dict(enriched.get("source_metadata") or {})
    title_meta = parse_sec_title(enriched.get("title"))
    if title_meta:
        enriched["sec_cik"] = title_meta["cik"]
        enriched["sec_company_name"] = title_meta["company_name"]
        metadata.update({
            "sec_cik": title_meta["cik"],
            "sec_company_name": title_meta["company_name"],
            "sec_filing_form": title_meta["filing_form"],
            "sec_filer_role": title_meta["filer_role"],
        })

        mapping = lookup_ticker_by_cik(title_meta["cik"], cache_path=cache_path)
        if mapping:
            tickers = [str(t).upper() for t in enriched.get("tickers") or []]
            if mapping["ticker"] not in tickers:
                tickers.append(mapping["ticker"])
            enriched["tickers"] = tickers
            metadata["sec_ticker"] = mapping["ticker"]
            metadata["sec_company_title"] = mapping.get("company_title")

    enriched["source_metadata"] = metadata
    return enriched


def refresh_company_tickers(
    cache_path: Path | str | None = None,
    *,
    url: str = SEC_COMPANY_TICKERS_URL,
    user_agent: str = "ginger-research/1.0 contact: research@example.com",
) -> Path:
    path = Path(cache_path or DEFAULT_CACHE_PATH)
    request = urllib.request.Request(
        url,
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
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
