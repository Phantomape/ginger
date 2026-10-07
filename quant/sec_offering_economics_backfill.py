from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from sec_filing_text_backfill import html_to_text, normalize_text


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec_offering_economics"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
WINDOWS = (
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
)
FORMS = {"S-1", "S-1/A", "F-1", "F-1/A"}
SCHEMA_VERSION = "sec_offering_economics_v1"
MIN_TEXT_ROWS_PER_WINDOW = 100
MIN_PARSED_ECON_ROWS_PER_WINDOW = 50

_ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
_CELL_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.I | re.S)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_ACCEPTED_RE = re.compile(
    r'<div\s+class=["\']infoHead["\']>Accepted</div>\s*'
    r'<div\s+class=["\']info["\']>([^<]+)</div>',
    re.I,
)
_MONEY_RE = re.compile(
    r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|bn|million|mm|m)?",
    re.I,
)
_AMOUNT_CONTEXT_RE = re.compile(
    r"proposed maximum aggregate offering price|maximum aggregate offering price|"
    r"aggregate offering price|gross proceeds|aggregate principal amount",
    re.I,
)
_RESALE_PATTERNS = (
    re.compile(r"\b(?:selling stockholders|selling shareholders) may (?:offer|sell)\b", re.I),
    re.compile(r"\bshares? (?:are |being )?offered by (?:the )?selling (?:stockholders|shareholders)\b", re.I),
    re.compile(r"\bresale (?:by .{0,80})?of (?:the )?(?:shares|securities)\b", re.I),
    re.compile(r"\bwe will not receive any proceeds from .{0,120}(?:selling stockholders|selling shareholders)\b", re.I),
)
_PRIMARY_PATTERNS = (
    re.compile(r"\bwe are offering\b", re.I),
    re.compile(r"\bshares? offered by (?:the registrant|us)\b", re.I),
    re.compile(r"\bwe intend to use the net proceeds (?:from|of) (?:this|the) offering\b", re.I),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def window_of(date_text: str) -> str | None:
    value = str(date_text or "")[:10]
    for name, start, end in WINDOWS:
        if start <= value <= end:
            return name
    return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def eligible_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        accession = str(row.get("accession") or "")
        if (
            accession
            and row.get("ticker_status") == "resolved"
            and str(row.get("form_type") or "") in FORMS
            and window_of(str(row.get("filed_date") or ""))
        ):
            deduped.setdefault(accession, row)
    return list(deduped.values())


def _rank(row: dict[str, Any]) -> str:
    window = window_of(str(row.get("filed_date") or "")) or ""
    accession = str(row.get("accession") or "")
    return hashlib.sha256(f"{window}|{accession}".encode()).hexdigest()


def select_rows(rows: list[dict[str, Any]], limit_per_window: int | None) -> list[dict[str, Any]]:
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows(rows):
        by_window[window_of(str(row.get("filed_date") or "")) or ""].append(row)

    selected: list[dict[str, Any]] = []
    for window, _start, _end in WINDOWS:
        ranked = sorted(by_window.get(window, []), key=_rank)
        if limit_per_window is None:
            selected.extend(ranked)
            continue
        chosen: list[dict[str, Any]] = []
        seen_tickers: set[str] = set()
        for row in ranked:
            ticker = str(row.get("ticker") or "").upper()
            if not ticker or ticker in seen_tickers:
                continue
            chosen.append(row)
            seen_tickers.add(ticker)
            if len(chosen) >= limit_per_window:
                break
        if len(chosen) < limit_per_window:
            chosen_accessions = {str(row.get("accession")) for row in chosen}
            for row in ranked:
                if str(row.get("accession")) in chosen_accessions:
                    continue
                chosen.append(row)
                if len(chosen) >= limit_per_window:
                    break
        selected.extend(chosen)
    return selected


def filing_index_url(row: dict[str, Any]) -> str:
    cik = str(row.get("cik") or "").lstrip("0") or "0"
    accession = str(row.get("accession") or "")
    accession_plain = accession.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_plain}/"
        f"{accession}-index.html"
    )


def parse_filing_index(index_html: str, form_type: str) -> dict[str, str | None]:
    primary_href: str | None = None
    for row_html in _ROW_RE.findall(index_html):
        cells = _CELL_RE.findall(row_html)
        if len(cells) < 4:
            continue
        row_type = normalize_text(_TAG_RE.sub(" ", cells[3]))
        href_match = _HREF_RE.search(cells[2])
        if row_type.upper() == form_type.upper() and href_match:
            primary_href = href_match.group(1)
            break
    accepted_match = _ACCEPTED_RE.search(index_html)
    accepted_at = None
    if accepted_match:
        parsed = datetime.strptime(normalize_text(accepted_match.group(1)), "%Y-%m-%d %H:%M:%S")
        accepted_at = (
            parsed.replace(tzinfo=ZoneInfo("America/New_York"))
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return {"primary_href": primary_href, "accepted_at_sec_display": accepted_at}


def primary_document_url(primary_href: str) -> str:
    absolute = urllib.request.urljoin("https://www.sec.gov", primary_href)
    parsed = urllib.parse.urlparse(absolute)
    document = urllib.parse.parse_qs(parsed.query).get("doc", [])
    if parsed.path in {"/ix", "/ixviewer/doc/action"} and document:
        return urllib.request.urljoin("https://www.sec.gov", document[0])
    return absolute


def _evidence(text: str, match: re.Match[str], radius: int = 220) -> dict[str, Any]:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    excerpt = normalize_text(text[start:end])
    return {
        "start": start,
        "end": end,
        "excerpt": excerpt,
        "excerpt_sha256": sha256_bytes(excerpt.encode()),
    }


def _first_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> re.Match[str] | None:
    hits = [match for pattern in patterns if (match := pattern.search(text))]
    return min(hits, key=lambda match: match.start()) if hits else None


def _money_value(match: re.Match[str]) -> float | None:
    value = float(match.group(1).replace(",", ""))
    unit = str(match.group(2) or "").lower()
    if unit in {"billion", "bn"}:
        value *= 1_000_000_000
    elif unit in {"million", "mm", "m"}:
        value *= 1_000_000
    if 1_000_000 <= value <= 100_000_000_000:
        return value
    return None


def extract_offering_economics(raw_html: str) -> dict[str, Any]:
    text = html_to_text(raw_html)
    resale = _first_match(text, _RESALE_PATTERNS)
    primary = _first_match(text, _PRIMARY_PATTERNS)
    if resale and primary:
        offering_type = "mixed_primary_and_resale"
    elif resale:
        offering_type = "resale"
    elif primary:
        offering_type = "primary"
    else:
        offering_type = None

    amount: float | None = None
    amount_evidence: dict[str, Any] | None = None
    for context in _AMOUNT_CONTEXT_RE.finditer(text):
        start = max(0, context.start() - 120)
        end = min(len(text), context.end() + 260)
        span = text[start:end]
        values = [
            (parsed, money_match)
            for money_match in _MONEY_RE.finditer(span)
            if (parsed := _money_value(money_match)) is not None
        ]
        if not values:
            continue
        parsed, money_match = max(values, key=lambda item: item[0])
        amount = parsed
        absolute_start = start + money_match.start()
        proxy = re.compile(re.escape(text[absolute_start : start + money_match.end()])).search(
            text, absolute_start
        )
        if proxy:
            amount_evidence = _evidence(text, proxy)
        break

    return {
        "text_char_count": len(text),
        "resale_vs_primary": offering_type,
        "selling_holder_present": resale is not None,
        "registered_or_offering_amount_usd": amount,
        "resale_evidence": _evidence(text, resale) if resale else None,
        "primary_evidence": _evidence(text, primary) if primary else None,
        "amount_evidence": amount_evidence,
    }


def request_bytes(url: str, user_agent: str, attempts: int = 3) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable")


def _cache_path(raw_dir: Path, accession: str) -> Path:
    return raw_dir / f"{accession}.html.gz"


def fetch_one(
    row: dict[str, Any],
    *,
    raw_dir: Path,
    user_agent: str,
    request_delay_sec: float,
    refresh: bool,
) -> dict[str, Any]:
    accession = str(row.get("accession") or "")
    index_url = filing_index_url(row)
    try:
        index_raw = request_bytes(index_url, user_agent)
        time.sleep(request_delay_sec)
        index = parse_filing_index(index_raw.decode("utf-8", errors="replace"), str(row.get("form_type")))
        primary_href = str(index.get("primary_href") or "")
        if not primary_href:
            raise ValueError("primary form document missing from filing index")
        primary_url = primary_document_url(primary_href)
        cache_path = _cache_path(raw_dir, accession)
        if cache_path.exists() and not refresh:
            with gzip.open(cache_path, "rb") as handle:
                raw = handle.read()
            if len(raw) < 10_000:
                raw = request_bytes(primary_url, user_agent)
                with gzip.open(cache_path, "wb", compresslevel=6) as handle:
                    handle.write(raw)
                time.sleep(request_delay_sec)
        else:
            raw = request_bytes(primary_url, user_agent)
            raw_dir.mkdir(parents=True, exist_ok=True)
            with gzip.open(cache_path, "wb", compresslevel=6) as handle:
                handle.write(raw)
            time.sleep(request_delay_sec)
        economics = extract_offering_economics(raw.decode("utf-8", errors="replace"))
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "window": window_of(str(row.get("filed_date") or "")),
            "ticker": row.get("ticker"),
            "cik": row.get("cik"),
            "accession": accession,
            "form_type": row.get("form_type"),
            "filed_date": row.get("filed_date"),
            "accepted_at": index.get("accepted_at_sec_display"),
            "index_url": index_url,
            "primary_document_url": primary_url,
            "primary_document_sha256": sha256_bytes(raw),
            "raw_cache_file": cache_path.resolve().relative_to(REPO_ROOT).as_posix(),
            "raw_char_count": len(raw),
            "pit_contract": "SEC filing accepted timestamp; decision clock is the first regular session strictly after accepted_at",
            **economics,
        }
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "fetch_or_parse_failed",
            "window": window_of(str(row.get("filed_date") or "")),
            "ticker": row.get("ticker"),
            "cik": row.get("cik"),
            "accession": accession,
            "form_type": row.get("form_type"),
            "filed_date": row.get("filed_date"),
            "index_url": index_url,
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_manifest(
    *,
    events_path: Path,
    selected: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    output_dir: Path,
    selection_manifest: Path | None = None,
) -> dict[str, Any]:
    coverage: dict[str, dict[str, Any]] = {}
    for window, _start, _end in WINDOWS:
        selected_window = [row for row in selected if window_of(str(row.get("filed_date"))) == window]
        output_window = [row for row in rows if row.get("window") == window]
        ok = [row for row in output_window if row.get("status") == "ok"]
        parsed = [row for row in ok if row.get("resale_vs_primary")]
        coverage[window] = {
            "selected_accessions": len(selected_window),
            "selected_tickers": len({row.get("ticker") for row in selected_window}),
            "text_rows": len(ok),
            "parsed_resale_vs_primary_rows": len(parsed),
            "parsed_amount_rows": sum(
                1 for row in ok if row.get("registered_or_offering_amount_usd") is not None
            ),
            "status_counts": dict(Counter(str(row.get("status")) for row in output_window)),
            "text_ready": len(ok) >= MIN_TEXT_ROWS_PER_WINDOW,
            "economics_ready": len(parsed) >= MIN_PARSED_ECON_ROWS_PER_WINDOW,
        }
    selection_projection = [
        {
            "window": window_of(str(row.get("filed_date") or "")),
            "ticker": row.get("ticker"),
            "accession": row.get("accession"),
        }
        for row in selected
    ]
    selection_hash = sha256_bytes(
        json.dumps(selection_projection, sort_keys=True, separators=(",", ":")).encode()
    )
    ready = all(item["text_ready"] and item["economics_ready"] for item in coverage.values())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "SEC EDGAR public filing index plus primary S-1/F-1 document",
        "source_events_file": events_path.resolve().relative_to(REPO_ROOT).as_posix(),
        "source_events_sha256": sha256_file(events_path),
        "selection_rule": "sha256(window|accession), one accession per ticker first, then deterministic fill",
        "selection_hash": selection_hash,
        "coverage": coverage,
        "readiness": "ready_for_outcome_blind_candidate_design" if ready else "insufficient_coverage",
        "reopen_thresholds": {
            "min_text_rows_per_window": MIN_TEXT_ROWS_PER_WINDOW,
            "min_parsed_economics_rows_per_window": MIN_PARSED_ECON_ROWS_PER_WINDOW,
        },
        "output_rows_file": (output_dir / "rows.jsonl").resolve().relative_to(REPO_ROOT).as_posix(),
        "outcome_fields_read": False,
        "trade_enabled": False,
    }
    if selection_manifest is not None:
        manifest.update(
            {
                "selection_rule": "all rows from the frozen outcome-blind selection manifest",
                "selection_manifest": selection_manifest.resolve().relative_to(REPO_ROOT).as_posix(),
                "selection_manifest_sha256": sha256_file(selection_manifest),
                "coverage_gate_applicable": False,
                "readiness": "requires_exact_touch_roster",
            }
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize an outcome-blind SEC S-1/F-1 offering-economics sidecar."
    )
    parser.add_argument("--events", default=str(DEFAULT_EVENTS))
    parser.add_argument(
        "--selection-manifest",
        help="Optional outcome-blind manifest with a rows array; bypasses readiness sampling.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--raw-dir",
        help="Optional shared raw cache directory; defaults to <output-dir>/raw.",
    )
    parser.add_argument("--limit-per-window", type=int, default=110)
    parser.add_argument("--request-delay-sec", type=float, default=0.12)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    events_path = Path(args.events).resolve()
    output_dir = Path(args.output_dir).resolve()
    raw_dir = Path(args.raw_dir).resolve() if args.raw_dir else output_dir / "raw"
    selection_manifest = Path(args.selection_manifest).resolve() if args.selection_manifest else None
    if selection_manifest:
        selection_payload = json.loads(selection_manifest.read_text(encoding="utf-8"))
        selected = list(selection_payload.get("rows") or [])
    else:
        selected = select_rows(load_jsonl(events_path), args.limit_per_window)
    def fetch_selected(row: dict[str, Any]) -> dict[str, Any]:
        return fetch_one(
                row,
                raw_dir=raw_dir,
                user_agent=args.user_agent,
                request_delay_sec=args.request_delay_sec,
                refresh=args.refresh,
            )

    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        for index, result in enumerate(executor.map(fetch_selected, selected), start=1):
            rows.append(result)
            if index % 10 == 0 or index == len(selected):
                print(f"processed {index}/{len(selected)}")

    write_jsonl(output_dir / "rows.jsonl", rows)
    manifest = build_manifest(
        events_path=events_path,
        selected=selected,
        rows=rows,
        output_dir=output_dir,
        selection_manifest=selection_manifest,
    )
    write_json(output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
