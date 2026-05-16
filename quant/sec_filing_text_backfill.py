from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from sec_ticker_map import normalize_cik


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_EVENTS = DATA_DIR / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
DEFAULT_OUTPUT = DATA_DIR / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
DEFAULT_SUMMARY = DATA_DIR / "non_ohlcv" / "sec_filing_text_backfill_summary_20241002_20260421.json"
DEFAULT_CACHE_DIR = DATA_DIR / "cache" / "sec" / "filing_text"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
DEFAULT_FORMS = ("8-K",)
DEFAULT_ITEM_CODES = ("2.02",)


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "ix:header"}:
            self._skip_depth += 1
        if lowered in {"p", "div", "br", "tr", "li", "table", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "ix:header"} and self._skip_depth:
            self._skip_depth -= 1
        if lowered in {"p", "div", "tr", "li", "table", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return normalize_text(" ".join(self.parts))


def repo_path(path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return REPO_ROOT / value


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def html_to_text(value: str) -> str:
    parser = TextExtractor()
    try:
        parser.feed(value)
        parser.close()
        return parser.text()
    except Exception:
        stripped = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
        stripped = re.sub(r"<style[\s\S]*?</style>", " ", stripped, flags=re.I)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        return normalize_text(stripped)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sec_archive_dir(cik: str | None, accession: str | None) -> str | None:
    cik_norm = normalize_cik(cik)
    if not cik_norm or not accession:
        return None
    accession_no_dash = str(accession).replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik_norm)}/{accession_no_dash}"


def sec_index_json_url(cik: str | None, accession: str | None) -> str | None:
    base = sec_archive_dir(cik, accession)
    if not base:
        return None
    return f"{base}/index.json"


def request_text(url: str, user_agent: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def request_json(url: str, user_agent: str) -> dict[str, Any]:
    return json.loads(request_text(url, user_agent))


def _document_name(item: Any) -> str | None:
    if isinstance(item, dict):
        name = item.get("name")
    else:
        name = item
    if not isinstance(name, str):
        return None
    name = name.strip()
    return name or None


def _is_text_document(name: str) -> bool:
    lowered = name.lower()
    if not lowered.endswith((".htm", ".html", ".txt")):
        return False
    excluded_tokens = (
        "-index.htm",
        "filingsummary",
        "metalinks",
        "_cal.",
        "_def.",
        "_lab.",
        "_pre.",
        ".xsd",
        ".xml",
    )
    return not any(token in lowered for token in excluded_tokens)


def _document_priority(name: str, primary_document: str | None) -> tuple[int, str]:
    lowered = name.lower()
    primary = str(primary_document or "").lower()
    score = 0
    if primary and lowered == primary:
        score += 80
    if re.search(r"(ex[-_]?99|exhibit[-_]?99|ex99|ex991|e991|exhibit99)", lowered):
        score += 100
    if "earn" in lowered or "result" in lowered or "release" in lowered:
        score += 30
    if lowered.endswith(".txt"):
        score -= 20
    if "8k" in lowered:
        score += 10
    return (-score, lowered)


def candidate_documents(
    index_payload: dict[str, Any],
    *,
    primary_document: str | None,
    max_documents: int,
) -> list[str]:
    directory = index_payload.get("directory") if isinstance(index_payload, dict) else {}
    items = directory.get("item") if isinstance(directory, dict) else []
    names = []
    for item in items or []:
        name = _document_name(item)
        if name and _is_text_document(name):
            names.append(name)
    if primary_document and _is_text_document(str(primary_document)):
        names.append(str(primary_document))
    deduped = list(dict.fromkeys(names))
    deduped.sort(key=lambda name: _document_priority(name, primary_document))
    return deduped[:max_documents]


def _cache_path(cache_dir: Path, accession: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", accession)
    return cache_dir / f"{safe}.json"


def _event_matches(row: dict[str, Any], forms: set[str], item_codes: set[str] | None) -> bool:
    form_base = str(row.get("form_base") or row.get("form_type") or "").upper().replace("/A", "")
    if form_base not in forms:
        return False
    if item_codes is None:
        return True
    codes = {str(code).strip() for code in row.get("eight_k_item_codes") or [] if str(code).strip()}
    return bool(codes & item_codes)


def fetch_filing_text(
    event: dict[str, Any],
    *,
    cache_dir: Path,
    user_agent: str,
    max_documents: int,
    max_chars_per_doc: int,
    refresh: bool = False,
    request_delay_sec: float = 0.11,
) -> dict[str, Any]:
    accession = str(event.get("accession_number") or "")
    if not accession:
        return {"status": "missing_accession", "documents": [], "combined_text": ""}
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, accession)
    if path.exists() and not refresh:
        cached = load_json(path, {})
        if isinstance(cached, dict):
            return cached

    cik = event.get("cik")
    primary_document = event.get("primary_document")
    base = sec_archive_dir(cik, accession)
    index_url = sec_index_json_url(cik, accession)
    if not base or not index_url:
        return {"status": "missing_archive_url", "documents": [], "combined_text": ""}

    documents: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        index_payload = request_json(index_url, user_agent)
        names = candidate_documents(
            index_payload,
            primary_document=str(primary_document) if primary_document else None,
            max_documents=max_documents,
        )
    except Exception as exc:
        names = [str(primary_document)] if primary_document else []
        errors.append(f"index_fetch_failed: {exc}")

    combined_parts: list[str] = []
    for name in names:
        url = f"{base}/{name}"
        try:
            raw = request_text(url, user_agent)
            if len(raw) > max_chars_per_doc:
                raw = raw[:max_chars_per_doc]
            text = html_to_text(raw)
            if text:
                combined_parts.append(f"DOCUMENT {name}\n{text}")
            documents.append({
                "name": name,
                "url": url,
                "text_char_count": len(text),
                "status": "ok" if text else "empty_text",
            })
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            documents.append({"name": name, "url": url, "text_char_count": 0, "status": "fetch_failed"})
        time.sleep(request_delay_sec)

    combined_text = normalize_text("\n\n".join(combined_parts))
    payload = {
        "status": "ok" if combined_text else "empty_text",
        "ticker": str(event.get("ticker") or "").upper() or None,
        "cik": normalize_cik(cik),
        "accession_number": accession,
        "form_type": event.get("form_type"),
        "form_base": event.get("form_base"),
        "filing_date": event.get("filing_date"),
        "usable_trade_date": event.get("usable_trade_date"),
        "accepted_at": event.get("accepted_at"),
        "eight_k_item_codes": event.get("eight_k_item_codes") or [],
        "primary_document": primary_document,
        "index_url": index_url,
        "documents": documents,
        "documents_fetched": sum(1 for doc in documents if doc.get("status") == "ok"),
        "text_char_count": len(combined_text),
        "text_word_count": len(combined_text.split()) if combined_text else 0,
        "combined_text": combined_text,
        "errors": errors,
        "pit_source": "sec_archive_public_filing_text",
        "pit_caveat": (
            "SEC public archive text fetched after the fact and keyed by accepted_at/usable_trade_date; "
            "it is a replayable public-PIT proxy, not proof the production pipeline observed the document."
        ),
    }
    write_json(path, payload)
    return payload


def build_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events_path = repo_path(args.events)
    cache_dir = repo_path(args.cache_dir)
    forms = {form.strip().upper().replace("/A", "") for form in args.forms if form.strip()}
    item_codes = None if args.item_codes == ["all"] else {code.strip() for code in args.item_codes if code.strip()}
    events = [
        row for row in load_jsonl(events_path)
        if _event_matches(row, forms, item_codes)
    ]
    if args.limit:
        events = events[: args.limit]

    rows: list[dict[str, Any]] = []
    for idx, event in enumerate(events, start=1):
        text_payload = fetch_filing_text(
            event,
            cache_dir=cache_dir,
            user_agent=args.user_agent,
            max_documents=args.max_documents,
            max_chars_per_doc=args.max_chars_per_doc,
            refresh=args.refresh,
            request_delay_sec=args.request_delay_sec,
        )
        rows.append(text_payload)
        if idx % 10 == 0:
            print(f"fetched {idx}/{len(events)} filings")

    summary = {
        "events_input": len(events),
        "rows_written": len(rows),
        "status_counts": {},
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "accessions": len({row.get("accession_number") for row in rows if row.get("accession_number")}),
        "documents_fetched": sum(int(row.get("documents_fetched") or 0) for row in rows),
        "text_char_count": sum(int(row.get("text_char_count") or 0) for row in rows),
        "forms": sorted(forms),
        "item_codes": sorted(item_codes) if item_codes is not None else ["all"],
        "source_events": str(events_path),
        "cache_dir": str(cache_dir),
    }
    for row in rows:
        status = str(row.get("status") or "unknown")
        summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill SEC archive filing text for selected filings.")
    parser.add_argument("--events", default=str(DEFAULT_EVENTS), help="Input sec_filing_events JSONL path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output filing text JSONL path.")
    parser.add_argument("--summary-output", default=str(DEFAULT_SUMMARY), help="Output summary JSON path.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Per-accession text cache dir.")
    parser.add_argument("--forms", nargs="+", default=list(DEFAULT_FORMS), help="Form bases to include.")
    parser.add_argument("--item-codes", nargs="+", default=list(DEFAULT_ITEM_CODES), help="8-K item codes, or 'all'.")
    parser.add_argument("--max-documents", type=int, default=4, help="Max text documents per filing.")
    parser.add_argument("--max-chars-per-doc", type=int, default=180000, help="Max raw chars fetched per document.")
    parser.add_argument("--limit", type=int, default=None, help="Optional filing limit for testing.")
    parser.add_argument("--refresh", action="store_true", help="Refresh cache even when present.")
    parser.add_argument("--request-delay-sec", type=float, default=0.11, help="Delay between SEC document requests.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    args = parser.parse_args()

    rows, summary = build_rows(args)
    write_jsonl(repo_path(args.output), rows)
    write_json(repo_path(args.summary_output), summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
