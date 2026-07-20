"""Pure SEC Schedule TO cash-tender lifecycle parsing and paper policy.

The module deliberately has no network or filesystem side effects.  Callers
must inject a ``fetcher(url)`` and decide whether/how fetched bytes are cached.
Every semantic field that can affect the locked paper policy is accompanied by
an immutable source URL, SHA-256 hash, and a bounded evidence span.

This is a default-off research surface.  Nothing in this module creates an
order and every snapshot explicitly reports ``trade_enabled=False``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, timedelta
import hashlib
import html
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urljoin


RULE_VERSION = "sec_cash_tender_lifecycle_v3"
SCHEMA_VERSION = "sec_cash_tender_lifecycle_snapshot_v1"
SEC_ARCHIVES_ROOT = "https://www.sec.gov/Archives/"

CANONICAL_WINDOWS: tuple[tuple[str, str], ...] = (
    ("2024-10-02", "2025-04-22"),
    ("2025-04-23", "2025-10-22"),
    ("2025-10-23", "2026-04-21"),
)

INITIAL_FORM = "SC TO-T"
AMENDMENT_FORM = "SC TO-T/A"
_ALLOWED_FORMS = frozenset({INITIAL_FORM, AMENDMENT_FORM})
TARGET_EVENT_FORMS = frozenset({"8-K", "8-K/A"})
_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "caption",
        "center",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "title",
        "tr",
        "ul",
    }
)
_HEADING_TAGS = frozenset({"title", "h1", "h2", "h3", "h4", "h5", "h6", "center"})
_SKIP_TAGS = frozenset({"script", "style", "ix:header", "noscript"})

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_TOKEN = "(?:" + "|".join(_MONTHS) + ")"
_WRITTEN_DATE_RE = re.compile(
    rf"\b({_MONTH_TOKEN})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b",
    re.I,
)
_REVERSED_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_TOKEN})[,]?\s+(20\d{{2}})\b",
    re.I,
)
_ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")

Fetcher = Callable[[str], Any]


class _TenderHtmlParser(HTMLParser):
    """Extract readable text plus explicit/visual heading blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.headings: list[str] = []
        self._skip_depth = 0
        self._heading_stack: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lowered in _BLOCK_TAGS:
            self.parts.append("\n")
        attrs_map = {str(key).lower(): str(value or "") for key, value in attrs}
        visual_heading = (
            lowered in _HEADING_TAGS
            or attrs_map.get("align", "").lower() == "center"
            or "text-align:center" in attrs_map.get("style", "").replace(" ", "").lower()
        )
        if visual_heading:
            self._heading_stack.append((lowered, []))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if self._heading_stack and self._heading_stack[-1][0] == lowered:
            _, pieces = self._heading_stack.pop()
            heading = _normalise_inline(" ".join(pieces))
            if heading:
                self.headings.append(heading)
        if lowered in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data:
            return
        self.parts.append(data)
        for _, pieces in self._heading_stack:
            pieces.append(data)

    def result(self) -> tuple[str, list[str]]:
        text = _normalise_document_text("".join(self.parts))
        headings = _dedupe_preserving_order(
            heading for heading in self.headings if len(heading) >= 4
        )
        return text, headings


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value or "")


def _raw_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return _decode(value).encode("utf-8")


def _normalise_inline(value: str) -> str:
    value = html.unescape(str(value or "")).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def _normalise_document_text(value: str) -> str:
    value = html.unescape(str(value or "")).replace("\xa0", " ")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[\t \f\v]+", " ", line).strip() for line in value.split("\n")]
    compact: list[str] = []
    for line in lines:
        if line:
            compact.append(line)
        elif compact and compact[-1] != "":
            compact.append("")
    return "\n".join(compact).strip()


def _dedupe_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize_html_text(value: str | bytes) -> str:
    """Return stable readable filing text while dropping active markup."""

    raw = _decode(value)
    parser = _TenderHtmlParser()
    try:
        parser.feed(raw)
        parser.close()
        text, _ = parser.result()
        return text
    except Exception:
        fallback = re.sub(r"<(?:script|style|noscript)[^>]*>[\s\S]*?</(?:script|style|noscript)>", " ", raw, flags=re.I)
        fallback = re.sub(r"<[^>]+>", "\n", fallback)
        return _normalise_document_text(fallback)


def _normalise_html_with_headings(value: str | bytes) -> tuple[str, list[str]]:
    raw = _decode(value)
    parser = _TenderHtmlParser()
    try:
        parser.feed(raw)
        parser.close()
        text, headings = parser.result()
    except Exception:
        text, headings = normalize_html_text(raw), []
    if not headings:
        headings = [line for line in text.splitlines()[:80] if 4 <= len(line) <= 1500]
    return text, headings


def _sha256(value: Any) -> str:
    return hashlib.sha256(_raw_bytes(value)).hexdigest()


def _fetch_bytes(fetcher: Fetcher, url: str) -> bytes:
    """Adapt small fake fetchers, requests-like responses, and file-like values."""

    result = fetcher(url)
    if hasattr(result, "read"):
        result = result.read()
    elif isinstance(result, Mapping):
        for key in ("content", "body", "data", "text"):
            if key in result:
                result = result[key]
                break
    elif hasattr(result, "content"):
        result = result.content
    elif hasattr(result, "text"):
        result = result.text
    return _raw_bytes(result)


def _normalise_windows(
    windows: Sequence[tuple[str, str] | Mapping[str, Any]] | None,
) -> tuple[tuple[str, str], ...]:
    normalised: list[tuple[str, str]] = []
    for raw in windows or CANONICAL_WINDOWS:
        if isinstance(raw, Mapping):
            start, end = str(raw.get("start") or "")[:10], str(raw.get("end") or "")[:10]
        else:
            start, end = str(raw[0])[:10], str(raw[1])[:10]
        if not _valid_iso_date(start) or not _valid_iso_date(end) or start > end:
            raise ValueError(f"invalid evaluation window: {raw!r}")
        normalised.append((start, end))
    return tuple(normalised)


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return len(value) == 10


def _date_in_windows(value: str, windows: Sequence[tuple[str, str]]) -> bool:
    return any(start <= value <= end for start, end in windows)


def _quarter(day: str) -> tuple[int, int]:
    parsed = date.fromisoformat(day)
    return parsed.year, (parsed.month - 1) // 3 + 1


def canonical_master_index_urls(
    windows: Sequence[tuple[str, str] | Mapping[str, Any]] | None = None,
) -> list[str]:
    """Return each EDGAR quarterly master index needed by the windows."""

    quarters: set[tuple[int, int]] = set()
    for start, end in _normalise_windows(windows):
        year, qtr = _quarter(start)
        end_year, end_qtr = _quarter(end)
        while (year, qtr) <= (end_year, end_qtr):
            quarters.add((year, qtr))
            qtr += 1
            if qtr == 5:
                year, qtr = year + 1, 1
    return [
        f"{SEC_ARCHIVES_ROOT}edgar/full-index/{year}/QTR{qtr}/master.idx"
        for year, qtr in sorted(quarters)
    ]


def _accession_from_filename(filename: str) -> str | None:
    match = re.search(r"(\d{10}-\d{2}-\d{6})", filename)
    if match:
        return match.group(1)
    basename = filename.rsplit("/", 1)[-1]
    compact = re.sub(r"\D", "", basename.rsplit(".", 1)[0])
    if len(compact) == 18:
        return f"{compact[:10]}-{compact[10:12]}-{compact[12:]}"
    return None


def _normalise_cik(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits or int(digits) <= 0 or len(digits) > 10:
        return None
    return digits.zfill(10)


def parse_master_index(
    payload: str | bytes,
    *,
    source_url: str | None = None,
    windows: Sequence[tuple[str, str] | Mapping[str, Any]] | None = None,
    forms: Iterable[str] = _ALLOWED_FORMS,
) -> list[dict[str, Any]]:
    """Parse and accession-dedupe EDGAR master-index Schedule TO rows.

    EDGAR can index the same submission for both the filer and subject.  The
    full set is retained in ``index_entities`` while exactly one row is emitted
    for each accession.
    """

    allowed = {str(form).strip().upper() for form in forms}
    date_windows = _normalise_windows(windows)
    raw = _raw_bytes(payload)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for line_number, raw_line in enumerate(_decode(raw).splitlines(), start=1):
        parts = [part.strip() for part in raw_line.split("|", 4)]
        if len(parts) != 5:
            continue
        cik_raw, company_name, form_type, filing_date, filename = parts
        form = form_type.upper()
        if form not in allowed or not _valid_iso_date(filing_date):
            continue
        if not _date_in_windows(filing_date, date_windows):
            continue
        accession = _accession_from_filename(filename)
        if not accession:
            continue
        entity = {
            "cik": _normalise_cik(cik_raw),
            "company_name": _normalise_inline(company_name),
            "form_type": form,
            "filing_date": filing_date,
            "filename": filename.lstrip("/"),
            "line_number": line_number,
        }
        grouped.setdefault(accession, []).append(entity)

    rows: list[dict[str, Any]] = []
    index_hash = hashlib.sha256(raw).hexdigest()
    for accession, entities in grouped.items():
        entities.sort(key=lambda row: (row["cik"] or "", row["company_name"], row["line_number"]))
        preferred = entities[0]
        form_types = sorted({str(row["form_type"]) for row in entities})
        rows.append(
            {
                "accession_number": accession,
                "form_type": form_types[0],
                "filing_date": preferred["filing_date"],
                "master_filename": preferred["filename"],
                "raw_submission_url": urljoin(SEC_ARCHIVES_ROOT, preferred["filename"]),
                "master_index_url": source_url,
                "master_index_sha256": index_hash,
                "index_entities": entities,
                "index_ciks": sorted({row["cik"] for row in entities if row["cik"]}),
                "duplicate_index_row_count": len(entities) - 1,
            }
        )
    rows.sort(key=lambda row: (row["filing_date"], row["accession_number"]))
    return rows


def extract_subject_company(raw_submission: str | bytes) -> dict[str, Any]:
    """Extract the target (not filer) identity from an EDGAR submission header."""

    raw = _decode(raw_submission)
    header_match = re.search(r"<SEC-HEADER>([\s\S]*?)</SEC-HEADER>", raw, re.I)
    header = header_match.group(1) if header_match else raw[:100_000]
    subject_match = re.search(
        r"(?:^|\n)\s*SUBJECT COMPANY:\s*([\s\S]*?)(?=\n\s*(?:FILED BY|FILER|REPORTING-OWNER|ISSUER|FORMER COMPANY):|\Z)",
        header,
        re.I,
    )
    subject = subject_match.group(1) if subject_match else ""
    if not subject:
        tagged = re.search(r"<SUBJECT-COMPANY>([\s\S]*?)(?:</SUBJECT-COMPANY>|<FILED-BY>)", header, re.I)
        subject = tagged.group(1) if tagged else ""

    name_match = re.search(r"COMPANY CONFORMED NAME:\s*([^\r\n<]+)", subject, re.I)
    if not name_match:
        name_match = re.search(r"<CONFORMED-NAME>\s*([^\r\n<]+)", subject, re.I)
    cik_match = re.search(r"CENTRAL INDEX KEY:\s*(\d{1,10})", subject, re.I)
    if not cik_match:
        cik_match = re.search(r"<CIK>\s*(\d{1,10})", subject, re.I)
    accepted_match = re.search(r"(?:<ACCEPTANCE-DATETIME>|ACCEPTANCE-DATETIME:\s*)(\d{14})", header, re.I)
    accepted_raw = accepted_match.group(1) if accepted_match else None
    accepted_at = None
    if accepted_raw:
        accepted_at = (
            f"{accepted_raw[:4]}-{accepted_raw[4:6]}-{accepted_raw[6:8]}"
            f"T{accepted_raw[8:10]}:{accepted_raw[10:12]}:{accepted_raw[12:14]}"
        )
    return {
        "subject_company_name": _normalise_inline(name_match.group(1)) if name_match else None,
        "subject_cik": _normalise_cik(cik_match.group(1)) if cik_match else None,
        "accepted_at": accepted_at,
        "accepted_at_raw": accepted_raw,
        "subject_header_found": bool(subject_match or subject),
    }


def extract_filing_person_ciks(raw_submission: str | bytes) -> list[str]:
    """Extract offeror/filer CIKs for lifecycle identity matching."""

    raw = _decode(raw_submission)
    header_match = re.search(r"<SEC-HEADER>([\s\S]*?)</SEC-HEADER>", raw, re.I)
    header = header_match.group(1) if header_match else raw[:100_000]
    sections = re.findall(
        r"(?:^|\n)\s*(?:FILED BY|FILER):\s*([\s\S]*?)"
        r"(?=\n\s*(?:FILED BY|FILER|SUBJECT COMPANY|REPORTING-OWNER|ISSUER|FORMER COMPANY):|\Z)",
        header,
        re.I,
    )
    tagged = re.findall(r"<FILED-BY>([\s\S]*?)(?:</FILED-BY>|<SUBJECT-COMPANY>|\Z)", header, re.I)
    ciks: set[str] = set()
    for section in [*sections, *tagged]:
        for value in re.findall(r"(?:CENTRAL INDEX KEY:|<CIK>)\s*(\d{1,10})", section, re.I):
            cik = _normalise_cik(value)
            if cik:
                ciks.add(cik)
    return sorted(ciks)


def _sgml_value(block: str, field: str) -> str | None:
    match = re.search(rf"<{re.escape(field)}>\s*([^\r\n<]+)", block, re.I)
    return _normalise_inline(match.group(1)) if match else None


def _document_archive_url(raw_url: str, accession: str, filename: str) -> str:
    match = re.search(r"/edgar/data/(\d+)/", raw_url, re.I)
    if match:
        return (
            f"{SEC_ARCHIVES_ROOT}edgar/data/{int(match.group(1))}/"
            f"{accession.replace('-', '')}/{filename.lstrip('/')}"
        )
    return urljoin(raw_url.rsplit("/", 1)[0] + "/", filename)


def find_tender_document_links(
    raw_submission: str | bytes,
    *,
    raw_submission_url: str,
    accession_number: str,
) -> dict[str, Any]:
    """Locate the primary Schedule TO and offer-to-purchase exhibit."""

    raw = _decode(raw_submission)
    documents: list[dict[str, Any]] = []
    for block_number, match in enumerate(
        re.finditer(r"<DOCUMENT>([\s\S]*?)</DOCUMENT>", raw, re.I), start=1
    ):
        block = match.group(1)
        filename = _sgml_value(block, "FILENAME")
        if not filename:
            continue
        text_match = re.search(r"<TEXT>([\s\S]*?)(?:</TEXT>|\Z)", block, re.I)
        document = {
            "document_type": (_sgml_value(block, "TYPE") or "").upper(),
            "sequence": _sgml_value(block, "SEQUENCE"),
            "filename": filename,
            "description": _sgml_value(block, "DESCRIPTION"),
            "source_url": _document_archive_url(raw_submission_url, accession_number, filename),
            "embedded_content": text_match.group(1) if text_match else None,
            "block_number": block_number,
        }
        documents.append(document)

    def primary_rank(row: Mapping[str, Any]) -> tuple[int, int, str]:
        doc_type = str(row.get("document_type") or "").upper()
        desired = 0 if doc_type in {INITIAL_FORM, AMENDMENT_FORM} else 1
        try:
            sequence = int(str(row.get("sequence") or "9999"))
        except ValueError:
            sequence = 9999
        return desired, sequence, str(row.get("filename") or "")

    primary = next(
        (row for row in sorted(documents, key=primary_rank) if row["document_type"] in _ALLOWED_FORMS),
        None,
    )
    offer_candidates = []
    for row in documents:
        description = str(row.get("description") or "")
        filename = str(row.get("filename") or "")
        doc_type = str(row.get("document_type") or "")
        combined = f"{description} {filename}".lower()
        explicit = "offer to purchase" in combined
        normalised_type = re.sub(r"[^A-Z0-9]", "", doc_type.upper())
        # Regulation M-A assigns the offer-to-purchase disclosure document to
        # exhibit (a)(1)(i).  Some EDGAR submissions encode the last component
        # as letter A instead of roman I; admit only those exact exhibit slots,
        # never arbitrary EX-99 attachments.
        standard_offer_rank = (
            0 if normalised_type == "EX99A1I"
            else 1 if normalised_type == "EX99A1A"
            else None
        )
        if standard_offer_rank is not None or explicit:
            rank = standard_offer_rank if standard_offer_rank is not None else 2
            offer_candidates.append((rank, primary_rank(row), row))
    offer = sorted(offer_candidates, key=lambda item: (item[0], item[1]))[0][2] if offer_candidates else None
    return {
        "primary_schedule_to": primary,
        "offer_to_purchase_exhibit": offer,
        "documents": documents,
    }


# Friendly alias used by callers that think in documents rather than links.
find_tender_documents = find_tender_document_links


def _source_document(
    content: str | bytes,
    *,
    source_url: str | None,
    role: str,
    filename: str | None = None,
) -> dict[str, Any]:
    raw = _raw_bytes(content)
    text, headings = _normalise_html_with_headings(raw)
    return {
        "role": role,
        "filename": filename,
        "source_url": source_url,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_content": _decode(raw),
        "text": text,
        "headings": headings,
    }


def _coerce_sources(
    documents: Any,
    *,
    source_url: str | None = None,
    source_sha256: str | None = None,
) -> list[dict[str, Any]]:
    if isinstance(documents, (str, bytes, bytearray)):
        sources = [_source_document(documents, source_url=source_url, role="document")]
    elif isinstance(documents, Mapping):
        if isinstance(documents.get("sources"), Sequence):
            return _coerce_sources(documents["sources"])
        content = documents.get("raw_content", documents.get("content", documents.get("text", "")))
        item = _source_document(
            content,
            source_url=str(documents.get("source_url") or source_url or "") or None,
            role=str(documents.get("role") or "document"),
            filename=str(documents.get("filename") or "") or None,
        )
        if documents.get("headings"):
            item["headings"] = [_normalise_inline(value) for value in documents["headings"]]
        if documents.get("source_sha256"):
            item["source_sha256"] = str(documents["source_sha256"])
        sources = [item]
    else:
        sources = []
        for item in documents or []:
            sources.extend(_coerce_sources(item))
    if source_sha256 and len(sources) == 1:
        sources[0]["source_sha256"] = source_sha256
    return sources


def _evidence(
    field: str,
    value: Any,
    source: Mapping[str, Any],
    start: int,
    end: int,
    *,
    matched_text: str | None = None,
) -> dict[str, Any]:
    text = str(source.get("text") or "")
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))
    context_start, context_end = max(0, start - 180), min(len(text), end + 180)
    return {
        "field": field,
        "value": value,
        "source_role": source.get("role"),
        "source_url": source.get("source_url"),
        "source_sha256": source.get("source_sha256"),
        "text_start": start,
        "text_end": end,
        "matched_text": _normalise_inline(matched_text if matched_text is not None else text[start:end]),
        "evidence_span": _normalise_inline(text[context_start:context_end]),
    }


def _first_pattern_evidence(
    field: str,
    value: Any,
    sources: Sequence[Mapping[str, Any]],
    patterns: Sequence[re.Pattern[str]],
) -> dict[str, Any] | None:
    for source in sources:
        text = str(source.get("text") or "")
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return _evidence(field, value, source, *match.span(), matched_text=match.group(0))
    return None


def _parse_date_text(value: str) -> str | None:
    match = _WRITTEN_DATE_RE.search(value)
    if match:
        month, day, year = _MONTHS[match.group(1).lower()], int(match.group(2)), int(match.group(3))
    else:
        match = _REVERSED_DATE_RE.search(value)
        if match:
            day, month, year = int(match.group(1)), _MONTHS[match.group(2).lower()], int(match.group(3))
        else:
            match = _ISO_DATE_RE.search(value)
            if not match:
                return None
            year, month, day = map(int, match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _extract_offer_price(
    sources: Sequence[Mapping[str, Any]],
) -> tuple[float | None, bool, list[dict[str, Any]]]:
    candidates: list[tuple[float, dict[str, Any]]] = []
    price_re = re.compile(
        r"(?:\bat\b|purchase\s+price(?:\s+of|\s+equal\s+to)?|\bfor\b)\s*"
        r"(?:US\s*)?\$\s*([0-9]{1,5}(?:,[0-9]{3})*(?:\.[0-9]{1,4})?)"
        r"(?:\s+(?:net(?:\s+in\s+cash)?|in\s+cash))*\s+per\s+share\b",
        re.I,
    )
    offer_re = re.compile(r"\b(?:offer\s+to\s+purchase|cash\s+tender\s+offer|tender\s+offer)\b", re.I)
    for source in sources:
        text = str(source.get("text") or "")
        regions: list[tuple[int, str]] = []
        for heading in source.get("headings") or []:
            heading_text = _normalise_inline(heading)
            if offer_re.search(heading_text):
                offset = text.casefold().find(heading_text.casefold())
                regions.append((max(offset, 0), heading_text))
        for offer_match in list(offer_re.finditer(text))[:12]:
            regions.append((offer_match.start(), text[offer_match.start():offer_match.start() + 1600]))
        for region_start, region in regions:
            if not re.search(r"\bcash\b", region, re.I):
                continue
            for match in price_re.finditer(region):
                vicinity = region[max(0, match.start() - 40):match.end() + 40]
                if re.search(r"\bpar\s+value\b", vicinity, re.I):
                    continue
                try:
                    price = float(match.group(1).replace(",", ""))
                except ValueError:
                    continue
                start, end = region_start + match.start(), region_start + match.end()
                candidates.append(
                    (
                        price,
                        _evidence(
                            "offer_price_usd",
                            price,
                            source,
                            start,
                            end,
                            matched_text=match.group(0),
                        ),
                    )
                )
    distinct = sorted({round(price, 6) for price, _ in candidates})
    if len(distinct) != 1:
        return None, len(distinct) > 1, [evidence for _, evidence in candidates]
    price = distinct[0]
    matching = [evidence for candidate, evidence in candidates if round(candidate, 6) == price]
    return price, False, matching[:3]


def _extract_scheduled_expiration(
    sources: Sequence[Mapping[str, Any]],
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    patterns = (
        re.compile(
            rf"(?:offer|tender\s+offer)[\s\S]{{0,240}}?(?:scheduled\s+to\s+)?expire[sd]?"
            rf"[\s\S]{{0,260}}?({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})",
            re.I,
        ),
        re.compile(
            rf"expiration\s+(?:date|time)[\s\S]{{0,260}}?({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})",
            re.I,
        ),
    )
    for source in sources:
        text = str(source.get("text") or "")
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            expiration_date = _parse_date_text(match.group(1))
            if expiration_date:
                return (
                    expiration_date,
                    _normalise_inline(match.group(0)),
                    _evidence("scheduled_expiration_date", expiration_date, source, *match.span()),
                )
    return None, None, None


def _extract_agreement_date(
    sources: Sequence[Mapping[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    patterns = (
        re.compile(
            rf"(?:agreement\s+and\s+plan\s+of\s+merger|merger\s+agreement|purchase\s+agreement)"
            rf"[^.\n]{{0,100}}?(?:dated(?:\s+as\s+of)?|entered\s+into\s+on)\s+"
            rf"({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})",
            re.I,
        ),
        re.compile(
            rf"(?:entered\s+into|executed)\s+(?:a\s+)?(?:definitive\s+)?(?:agreement\s+and\s+plan\s+of\s+merger|merger\s+agreement|purchase\s+agreement)"
            rf"\s+(?:on|dated)\s+({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})",
            re.I,
        ),
        re.compile(
            rf"(?:announced|publicly\s+announced)\s+(?:on\s+)?({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})"
            rf"[^.\n]{{0,180}}?(?:merger|acquisition|tender\s+offer|definitive\s+agreement)",
            re.I,
        ),
    )
    for source in sources:
        text = str(source.get("text") or "")
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            agreement_date = _parse_date_text(match.group(1))
            if agreement_date:
                return agreement_date, _evidence(
                    "agreement_or_announcement_date", agreement_date, source, *match.span()
                )
    return None, None


def _normalise_exchange(value: str) -> tuple[str | None, bool | None]:
    lowered = _normalise_inline(value).lower()
    if "nasdaq" in lowered:
        return "NASDAQ", True
    if "nyse american" in lowered or "american stock exchange" in lowered:
        return "NYSE_AMERICAN", True
    if "new york stock exchange" in lowered or re.search(r"\bnyse\b", lowered):
        return "NYSE", True
    if "cboe" in lowered or "bats" in lowered:
        return "CBOE", True
    if "otc" in lowered or "pink" in lowered:
        return "OTC", False
    return None, None


def _extract_listing_identity(
    sources: Sequence[Mapping[str, Any]],
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    exchange_token = (
        r"(?:Nasdaq(?:\s+(?:Global\s+Select|Global|Capital)\s+Market)?|"
        r"New\s+York\s+Stock\s+Exchange|NYSE(?:\s+American)?|"
        r"American\s+Stock\s+Exchange|Cboe(?:\s+BZX)?|BATS|"
        r"OTC(?:QX|QB|\s+Markets?)?|Pink\s+(?:Sheets|Open\s+Market))"
    )
    patterns = (
        re.compile(
            rf"\b(?:common\s+stock|shares?)\b[^.]{{0,260}}?"
            rf"(?:list(?:ed|s)|trad(?:e|ed|es)|quot(?:e|ed|es))\s+on\s+(?:the\s+)?(?P<exchange>{exchange_token})"
            rf"[^.]{{0,120}}?under\s+(?:the\s+)?(?:ticker\s+)?symbol\s+[\"'“”‘’]?(?P<ticker>[A-Z][A-Z0-9.\-]{{0,9}})\b",
            re.I,
        ),
        re.compile(
            rf"\b(?:common\s+stock|shares?)\b[^.]{{0,260}}?"
            rf"(?:list(?:ed|s)|trad(?:e|ed|es)|quot(?:e|ed|es))\s+under\s+(?:the\s+)?(?:ticker\s+)?symbol\s+[\"'“”‘’]?(?P<ticker>[A-Z][A-Z0-9.\-]{{0,9}})\b"
            rf"[^.]{{0,120}}?(?:on|of)\s+(?:the\s+)?(?P<exchange>{exchange_token})",
            re.I,
        ),
    )
    for source in sources:
        text = str(source.get("text") or "")
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            exchange, listed = _normalise_exchange(match.group("exchange"))
            ticker = match.group("ticker").upper().rstrip(".")
            value = {
                "target_ticker": ticker,
                "target_exchange": exchange,
                "is_listed_common_stock": listed,
                "is_otc": exchange == "OTC" if exchange else None,
            }
            return ticker, exchange, _evidence(
                "listed_common_stock_evidence", value, source, *match.span()
            )
    return None, None, None


def _extract_financing(
    sources: Sequence[Mapping[str, Any]],
) -> tuple[bool, str, dict[str, Any] | None]:
    cash_patterns = (
        re.compile(
            r"(?:has|have|with|from|using)\s+(?:sufficient\s+)?(?:cash\s+on\s+hand|available\s+(?:cash|funds))"
            r"[^.]{0,180}?(?:sufficient|fund|finance|pay|purchase|consummate)",
            re.I,
        ),
        re.compile(
            r"(?:cash\s+on\s+hand|available\s+(?:cash|funds))[^.]{0,160}?"
            r"(?:is|are|will\s+be)\s+sufficient\s+to\s+(?:pay|purchase|fund|consummate)",
            re.I,
        ),
        re.compile(
            r"(?:has|have|with)\s+sufficient\s+(?:cash|funds)\s+available[^.]{0,160}?"
            r"(?:purchase|pay|fund|offer|transaction)",
            re.I,
        ),
        re.compile(
            r"(?:has|have|will\s+have)\s+(?:sufficient\s+)?(?:cash\s+resources|cash\s+and\s+cash\s+equivalents|"
            r"available\s+cash|cash\s+on\s+hand)[^.]{0,180}?(?:sufficient|fund|purchase|pay|offer|transaction)",
            re.I,
        ),
        re.compile(
            r"(?:has|have)\s+or\s+will\s+have\s+(?:such\s+)?funds\s+available[^.]{0,220}?"
            r"including\s+cash\s+on\s+hand[^.]{0,180}?(?:offer|closing|purchase|payment|merger)",
            re.I,
        ),
        re.compile(
            r"(?:will|shall)\s+provide[^.]{0,100}?sufficient\s+funds[^.]{0,140}?"
            r"(?:purchase|pay|fund|offer|transaction)",
            re.I,
        ),
        re.compile(r"sufficient\s+funds\s+(?:are|will\s+be)\s+available[^.]{0,120}?(?:purchase|pay|offer)", re.I),
    )
    commitment_patterns = (
        re.compile(
            r"(?:entered\s+into|executed|delivered|received)\s+(?:an?\s+)?(?:(?:executed|binding)\s+)?"
            r"(?:debt|equity|financing)?\s*commitment\s+letter[^.]{0,260}?"
            r"(?:committed|commitment|provide|fund)",
            re.I,
        ),
        re.compile(
            r"(?:lender|financing\s+source|equity\s+sponsor)s?\s+(?:has|have)\s+committed\s+"
            r"(?:to\s+provide|funds?\s+of)[^.]{0,220}?(?:offer|merger|purchase|transaction)",
            re.I,
        ),
        re.compile(r"binding\s+(?:debt|equity|financing)\s+commitment[^.]{0,220}", re.I),
    )
    weak_re = re.compile(
        r"(?:highly\s+confident|reasonably\s+confident|expects?\s+to\s+obtain|"
        r"anticipates?\s+(?:obtaining|that)|may\s+obtain|seeking\s+financing)",
        re.I,
    )
    for kind, patterns in (("cash_on_hand", cash_patterns), ("binding_commitment", commitment_patterns)):
        for source in sources:
            text = str(source.get("text") or "")
            for pattern in patterns:
                for match in pattern.finditer(text):
                    vicinity = text[max(0, match.start() - 100):match.end() + 100]
                    if weak_re.search(vicinity):
                        continue
                    return True, kind, _evidence(
                        "binding_committed_financing", True, source, *match.span()
                    )
    weak = _first_pattern_evidence("binding_committed_financing", False, sources, (weak_re,))
    return False, "unclear", weak


def extract_tender_terms(
    documents: Any,
    *,
    source_url: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Extract deterministic initial cash-tender terms from filing documents."""

    sources = _coerce_sources(documents, source_url=source_url, source_sha256=source_sha256)
    evidence: list[dict[str, Any]] = []
    offer_price, offer_price_ambiguous, price_evidence = _extract_offer_price(sources)
    evidence.extend(price_evidence)

    all_outstanding_patterns = (
        re.compile(r"\ball\s+(?:of\s+)?the\s+outstanding\s+shares\b", re.I),
        re.compile(r"\bany\s+and\s+all\s+outstanding\s+shares\b", re.I),
        re.compile(r"\ball\s+outstanding\s+shares\b", re.I),
    )
    all_outstanding_evidence = _first_pattern_evidence(
        "all_outstanding_shares", True, sources, all_outstanding_patterns
    )
    all_outstanding = all_outstanding_evidence is not None
    if all_outstanding_evidence:
        evidence.append(all_outstanding_evidence)

    exclusion_patterns: dict[str, tuple[re.Pattern[str], ...]] = {
        "has_cvr_consideration": (
            re.compile(
                r"\bat\s+(?:US\s*)?\$\s*[0-9][0-9,]*(?:\.[0-9]+)?"
                r"[\s\S]{0,200}?per\s+(?:company\s+)?share[\s\S]{0,220}?\bplus\b"
                r"[\s\S]{0,80}?(?:contingent\s+value\s+rights?|\bCVRs?\b)",
                re.I,
            ),
            re.compile(
                r"\bat\s+(?:US\s*)?\$\s*[0-9][0-9,]*(?:\.[0-9]+)?"
                r"[^.\n]{0,100}?per\s+share[^.\n]{0,120}?"
                r"(?:plus|and)[^.\n]{0,80}?(?:contingent\s+value\s+rights?|\bCVRs?\b)",
                re.I,
            ),
            re.compile(
                r"\b(?:offer\s+price|consideration\s+(?:payable|offered)|"
                r"holders?\s+(?:will|would)\s+receive)[^.\n]{0,220}?"
                r"(?:contingent\s+value\s+rights?|\bCVRs?\b)",
                re.I,
            ),
            re.compile(
                r"\b(?:contingent\s+value\s+rights?|CVRs?)\b[^.\n]{0,220}?"
                r"(?:as|part\s+of)\s+(?:the\s+)?(?:offer\s+price|consideration)",
                re.I,
            ),
        ),
        "has_stock_consideration": (
            re.compile(
                r"\b(?:offer\s+price|consideration\s+payable\s+in\s+the\s+offer|"
                r"holders?\s+(?:will|would)\s+receive)[^.\n]{0,220}?"
                r"(?:stock\s+consideration|shares?\s+of\s+(?:parent|purchaser|buyer))\b",
                re.I,
            ),
            re.compile(
                r"\b(?:stock|shares?)\b[^.\n]{0,160}?"
                r"(?:as|in)\s+(?:the\s+)?consideration\s+(?:payable\s+)?(?:in|for)\s+the\s+offer\b",
                re.I,
            ),
        ),
        "is_partial_offer": (
            re.compile(r"\boffer\s+to\s+purchase\s+(?:up\s+to|approximately|not\s+more\s+than)\b", re.I),
            re.compile(r"\b(?:offer|tender\s+offer)\s+is\s+for\s+(?:up\s+to|not\s+more\s+than)\b", re.I),
            re.compile(r"\bnot\s+all\s+(?:of\s+)?the\s+outstanding\s+shares\b", re.I),
        ),
        "is_mini_tender": (
            re.compile(r"\bmini[-\s]?tender\b", re.I),
            re.compile(r"\bless\s+than\s+(?:five|5)\s*(?:percent|%)\s+of[^.]{0,100}?outstanding\s+shares\b", re.I),
        ),
    }
    exclusions: dict[str, bool] = {}
    for field, patterns in exclusion_patterns.items():
        hit = _first_pattern_evidence(field, True, sources, patterns)
        exclusions[field] = hit is not None
        if hit:
            evidence.append(hit)

    negative_board_patterns = (
        re.compile(r"board\s+of\s+directors[^.]{0,220}?recommends?\s+that[^.]{0,120}?(?:not\s+tender|reject)", re.I),
        re.compile(r"board\s+of\s+directors[^.]{0,160}?does\s+not\s+recommend[^.]{0,100}?tender", re.I),
    )
    positive_board_patterns = (
        re.compile(r"board\s+of\s+directors[^.]{0,260}?recommends?\s+that[^.]{0,180}?(?:accept|tender)", re.I),
        re.compile(
            r"board\s+of\s+directors[\s\S]{0,1000}?resolv(?:ed|es)\s+to\s+recommend"
            r"[\s\S]{0,260}?(?:accept|tender)",
            re.I,
        ),
        re.compile(r"\bboard\s+(?:unanimously\s+)?recommends?\s+that[^.]{0,220}?(?:accept|tender)", re.I),
        re.compile(
            r"board\s+of\s+directors\s+of\s+[^.\n]{1,160}?\bhas\s+unanimously\b"
            r"[\s\S]{0,1800}?(?:resolved[\s\S]{0,360}?to\s+recommend|recommended)\s+that"
            r"[\s\S]{0,260}?(?:accept\s+the\s+offer|tender\s+(?:their|the)\s+shares)",
            re.I,
        ),
        re.compile(
            r"\b(?:[A-Z][A-Za-z0-9&.'\-]*\s+){1,6}board\s+has\s+unanimously\b"
            r"[\s\S]{0,1800}?(?:resolved[\s\S]{0,360}?to\s+recommend|recommended)\s+that"
            r"[\s\S]{0,260}?(?:accept\s+the\s+offer|tender\s+(?:their|the)\s+shares)",
            re.I,
        ),
    )
    negative_board = _first_pattern_evidence(
        "target_board_recommends_tender", False, sources, negative_board_patterns
    )
    positive_board = _first_pattern_evidence(
        "target_board_recommends_tender", True, sources, positive_board_patterns
    )
    if negative_board:
        board_recommendation: bool | None = False
        evidence.append(negative_board)
    elif positive_board:
        board_recommendation = True
        evidence.append(positive_board)
    else:
        board_recommendation = None

    definitive_patterns = (
        re.compile(r"\bdefinitive\s+(?:agreement\s+and\s+plan\s+of\s+merger|merger\s+agreement)\b", re.I),
        re.compile(r"\bagreement\s+and\s+plan\s+of\s+merger\b", re.I),
        re.compile(r"\bentered\s+into\s+(?:a\s+)?(?:definitive\s+)?merger\s+agreement\b", re.I),
        re.compile(r"\bpursuant\s+to\s+the\s+merger\s+agreement\b", re.I),
        re.compile(r"\boffer\s+is\s+being\s+made\s+pursuant\s+to\s+the\s+purchase\s+agreement\b", re.I),
    )
    definitive_evidence = _first_pattern_evidence(
        "definitive_agreement", True, sources, definitive_patterns
    )
    definitive_agreement = definitive_evidence is not None
    if definitive_evidence:
        evidence.append(definitive_evidence)

    no_financing_patterns = (
        re.compile(r"\b(?:offer|tender\s+offer)\s+is\s+not\s+subject\s+to\s+(?:any\s+)?financing\s+condition\b", re.I),
        re.compile(r"\bthere\s+is\s+no\s+financing\s+condition\s+to\s+(?:the\s+)?offer\b", re.I),
        re.compile(r"\bnot\s+conditioned\s+upon\s+(?:the\s+)?(?:receipt|availability)\s+of\s+financing\b", re.I),
        re.compile(
            r"\b(?:neither\s+)?(?:the\s+)?(?:consummation\s+of\s+(?:the\s+)?)?"
            r"(?:offer|tender\s+offer)(?:\s+nor\s+(?:the\s+)?merger)?\s+is\s+not\s+"
            r"(?:subject\s+to|conditioned\s+upon)(?:\s*,?\s*or\s+(?:contingent|conditioned)\s+upon\s*,?)?"
            r"\s+(?:any\s+)?financing\s+condition\b",
            re.I,
        ),
        re.compile(r"\boffer\s+is\s+not\s+conditioned\s+on\s+obtaining\s+financing(?:\s+or\s+the\s+funding\s+thereof)?\b", re.I),
    )
    no_financing_evidence = _first_pattern_evidence(
        "no_financing_condition", True, sources, no_financing_patterns
    )
    no_financing_condition = no_financing_evidence is not None
    if no_financing_evidence:
        evidence.append(no_financing_evidence)

    binding_financing, financing_kind, financing_evidence = _extract_financing(sources)
    if financing_evidence:
        evidence.append(financing_evidence)

    expiration_date, expiration_text, expiration_evidence = _extract_scheduled_expiration(sources)
    if expiration_evidence:
        evidence.append(expiration_evidence)
    agreement_date, agreement_evidence = _extract_agreement_date(sources)
    if agreement_evidence:
        evidence.append(agreement_evidence)
    target_ticker, target_exchange, listing_evidence = _extract_listing_identity(sources)
    if listing_evidence:
        evidence.append(listing_evidence)
    bankruptcy_patterns = (
        re.compile(
            r"\b(?:the\s+)?(?:company|target|subject\s+company)\s+(?:has\s+)?"
            r"(?:filed|commenced|initiated)[^.]{0,120}?(?:chapter\s+(?:7|11)|bankruptcy)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:chapter\s+(?:7|11)|bankruptcy)\s+(?:case|proceeding|protection)"
            r"[^.]{0,120}?(?:the\s+)?(?:company|target|subject\s+company)\b",
            re.I,
        ),
        re.compile(r"\b(?:the\s+)?(?:company|target)\s+is\s+(?:a\s+)?debtor[-\s]in[-\s]possession\b", re.I),
    )
    bankruptcy_evidence = _first_pattern_evidence(
        "bankruptcy_indicated", True, sources, bankruptcy_patterns
    )
    bankruptcy_indicated = bankruptcy_evidence is not None
    if bankruptcy_evidence:
        evidence.append(bankruptcy_evidence)

    fixed_cash_offer = bool(
        offer_price is not None
        and not offer_price_ambiguous
        and not exclusions["has_cvr_consideration"]
        and not exclusions["has_stock_consideration"]
    )
    return {
        "offer_price_usd": offer_price,
        "offer_price": offer_price,
        "offer_price_ambiguous": offer_price_ambiguous,
        "fixed_cash_offer": fixed_cash_offer,
        "all_outstanding_shares": all_outstanding,
        **exclusions,
        "target_board_recommends_tender": board_recommendation,
        "hostile_offer": board_recommendation is False,
        "definitive_agreement": definitive_agreement,
        "no_financing_condition": no_financing_condition,
        "binding_committed_financing": binding_financing,
        "financing_evidence_kind": financing_kind,
        "scheduled_expiration_date": expiration_date,
        "expiration_date": expiration_date,
        "scheduled_expiration_text": expiration_text,
        "agreement_or_announcement_date": agreement_date,
        "announcement_or_agreement_date": agreement_date,
        "target_ticker": target_ticker,
        "target_exchange": target_exchange,
        "listed_common_stock_evidence": listing_evidence,
        "bankruptcy_indicated": bankruptcy_indicated,
        "bankruptcy_evidence": bankruptcy_evidence,
        "evidence_spans": evidence,
        "source_documents": [
            {
                "role": source.get("role"),
                "filename": source.get("filename"),
                "source_url": source.get("source_url"),
                "source_sha256": source.get("source_sha256"),
                "text_length": len(str(source.get("text") or "")),
            }
            for source in sources
        ],
    }


def extract_amendment_outcome(
    documents: Any,
    *,
    source_url: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Classify one SC TO-T/A without inferring an unspoken deal outcome."""

    sources = _coerce_sources(documents, source_url=source_url, source_sha256=source_sha256)
    completion_patterns = (
        re.compile(
            r"\b(?:purchaser|parent\s+and\s+purchaser|[A-Z][A-Za-z0-9&.'\- ]{1,80}\s+and\s+purchaser)"
            r"\s+(?:has|have)?\s*(?:irrevocably\s+)?accepted\s+for\s+(?:payment|purchase)\b"
            r"[\s\S]{0,300}?\ball\s+(?:such\s+)?(?:shares|securities)\b"
            r"[\s\S]{0,180}?\b(?:validly\s+tendered|tendered)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:purchaser|offeror|merger\s+sub)\s+(?:has\s+)?(?:irrevocably\s+)?accepted\s+all\s+"
            r"(?:such\s+)?(?:shares|securities)[\s\S]{0,180}?\bvalidly\s+tendered\b"
            r"(?:[\s\S]{0,180}?(?:\b(?:will|has)\b[\s\S]{0,80}?\bpay\b|"
            r"\bpayment\b[\s\S]{0,80}?\bwill\s+be\s+made\b))?",
            re.I,
        ),
        re.compile(r"\baccepted\s+for\s+payment\s+(?:all\s+)?(?:such\s+)?(?:shares|securities)[^.]{0,160}?(?:validly\s+tendered|tendered)\b", re.I),
        re.compile(r"\b(?:successfully\s+)?completed\s+(?:the\s+)?(?:cash\s+)?tender\s+offer\b", re.I),
        re.compile(r"\bconsummated\s+(?:the\s+)?(?:offer|tender\s+offer|acquisition)\b", re.I),
    )
    termination_patterns = (
        re.compile(
            r"\b(?:company|parties|parent|purchaser|offeror|board|we|they|[A-Z][A-Za-z0-9&.'\- ]{1,80})"
            r"\s+(?:has|have)?\s*terminated\s+(?:the\s+)?"
            r"(?:merger\s+agreement|tender\s+offer|offer)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:merger\s+agreement|tender\s+offer|offer)\s+"
            r"(?:has\s+been|have\s+been|was|were|is)\s+(?:terminated|withdrawn)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:company|parties|parent|purchaser|offeror|we|they)\s+"
            r"(?:is|are)\s+terminating\s+(?:the\s+)?"
            r"(?:merger\s+agreement|tender\s+offer|offer)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:announce[sd]?|announcing|report(?:s|ed|ing)?|effected)\s+"
            r"(?:the\s+)?termination\s+of\s+(?:the\s+)?"
            r"(?:merger\s+agreement|tender\s+offer|offer)\b",
            re.I,
        ),
        re.compile(r"\bwithdrew\s+(?:the\s+)?(?:tender\s+offer|offer)\b", re.I),
    )
    competing_patterns = (
        re.compile(r"\b(?:superior|higher|competing)\s+(?:proposal|offer|bid|transaction)\b", re.I),
        re.compile(
            r"\b(?:in\s+connection\s+with|in\s+order\s+to\s+accept)\s+(?:a\s+)?"
            r"(?:superior|higher|competing)[^.]{0,140}?(?:proposal|offer|bid|transaction)\b",
            re.I,
        ),
        re.compile(r"\breceived\s+(?:an?\s+)?(?:unsolicited\s+)?(?:higher|superior|competing)[^.]{0,80}?(?:offer|proposal|bid)\b", re.I),
    )
    price_raise_patterns = (
        re.compile(
            r"\b(?:increased?|raised?|revised)\s+(?:the\s+)?(?:offer\s+price|purchase\s+price)"
            r"\s+from\s+\$\s*[0-9]{1,5}(?:\.[0-9]{1,4})?\s+to\s+"
            r"\$\s*(?P<new_price>[0-9]{1,5}(?:\.[0-9]{1,4})?)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:increased?|raised?|revised)\s+(?:the\s+)?(?:offer\s+price|purchase\s+price)"
            r"[^.]{0,100}?\$\s*([0-9]{1,5}(?:\.[0-9]{1,4})?)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:offer\s+price|purchase\s+price)\s+(?:has\s+been|was)\s+(?:increased|raised|revised)"
            r"[^.]{0,100}?\$\s*([0-9]{1,5}(?:\.[0-9]{1,4})?)\b",
            re.I,
        ),
    )
    extension_patterns = (
        re.compile(r"\b(?:extended|extension\s+of)\s+(?:the\s+)?(?:expiration\s+(?:date|time)|tender\s+offer)[^.]{0,220}", re.I),
        re.compile(r"\bextended\s+(?:the\s+)?expiration\s+of\s+(?:the\s+)?offer[^.]{0,220}", re.I),
        re.compile(r"\btender\s+offer\s+will\s+now\s+expire[^.]{0,180}", re.I),
    )

    completion = _first_pattern_evidence("outcome", "completed", sources, completion_patterns)
    termination = _first_pattern_evidence("outcome", "terminated_negative", sources, termination_patterns)
    competing = _first_pattern_evidence("higher_bid", True, sources, competing_patterns)
    extension = _first_pattern_evidence("outcome", "extended_pending", sources, extension_patterns)
    price_raise: dict[str, Any] | None = None
    higher_price: float | None = None
    higher_bidder_name: str | None = None
    higher_bidder_evidence: dict[str, Any] | None = None
    for source in sources:
        text = str(source.get("text") or "")
        for pattern in price_raise_patterns:
            match = pattern.search(text)
            if match:
                captured = match.groupdict().get("new_price") or match.group(1)
                higher_price = float(captured)
                price_raise = _evidence("higher_bid_price_usd", higher_price, source, *match.span())
                break
        if price_raise:
            break
    bidder_pattern = re.compile(
        r"\b(?:superior\s+proposal|higher\s+(?:offer|bid)|competing\s+(?:offer|bid|proposal))"
        r"\s+from\s+([A-Z][A-Za-z0-9&'()\- ]{1,79}?)(?=[,.;]|\s+(?:that|which)\b)",
        re.I,
    )
    for source in sources:
        text = str(source.get("text") or "")
        match = bidder_pattern.search(text)
        if match:
            higher_bidder_name = _normalise_inline(match.group(1))
            higher_bidder_evidence = _evidence(
                "higher_bidder_name", higher_bidder_name, source, *match.span()
            )
            break

    expiration_date, expiration_text, expiration_evidence = _extract_scheduled_expiration(sources)
    if termination and competing:
        outcome_type, decisive = "terminated_higher_bid", termination
    elif termination:
        outcome_type, decisive = "terminated_negative", termination
    elif completion:
        outcome_type, decisive = "completed", completion
    elif competing or price_raise:
        outcome_type, decisive = "higher_bid_pending", competing or price_raise
    elif extension:
        outcome_type, decisive = "extended_pending", extension
    else:
        outcome_type, decisive = "pending", None

    evidence = [
        item
        for item in (
            decisive,
            competing,
            price_raise,
            higher_bidder_evidence,
            extension,
            expiration_evidence,
        )
        if item
    ]
    unique_evidence: list[dict[str, Any]] = []
    seen_evidence: set[tuple[Any, ...]] = set()
    for item in evidence:
        key = (item.get("field"), item.get("source_sha256"), item.get("text_start"), item.get("text_end"))
        if key not in seen_evidence:
            seen_evidence.add(key)
            unique_evidence.append(item)
    return {
        "outcome_type": outcome_type,
        "completed": outcome_type == "completed",
        "terminated": outcome_type in {"terminated_negative", "terminated_higher_bid"},
        "higher_bid_identified": bool(competing or price_raise),
        "higher_bid_price_usd": higher_price,
        "higher_bidder_name": higher_bidder_name,
        "cash_price_usd": None,
        "outcome_date": None,
        "scheduled_expiration_date": expiration_date,
        "scheduled_expiration_text": expiration_text,
        "evidence_spans": unique_evidence,
        "source_documents": [
            {
                "role": source.get("role"),
                "filename": source.get("filename"),
                "source_url": source.get("source_url"),
                "source_sha256": source.get("source_sha256"),
            }
            for source in sources
        ],
    }


def extract_amendment_policy_delta(
    documents: Any,
    *,
    source_url: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Detect explicit amendment changes that violate the locked entry contract."""

    sources = _coerce_sources(documents, source_url=source_url, source_sha256=source_sha256)
    terms = extract_tender_terms(sources)
    reason_fields = (
        ("has_cvr_consideration", "cvr_consideration_added"),
        ("has_stock_consideration", "stock_consideration_added"),
        ("is_partial_offer", "offer_became_partial"),
        ("is_mini_tender", "offer_became_mini_tender"),
        ("bankruptcy_indicated", "target_bankruptcy_indicated"),
    )
    reasons = [reason for field, reason in reason_fields if terms.get(field) is True]
    if terms.get("target_board_recommends_tender") is False:
        reasons.append("target_board_recommendation_withdrawn")
    offer_price = terms.get("offer_price_usd")
    if isinstance(offer_price, (int, float)) and not isinstance(offer_price, bool) and offer_price <= 1.0:
        reasons.append("revised_offer_price_not_above_one_dollar")
    financing_added_patterns = (
        re.compile(
            r"\b(?:offer|merger)\s+(?:is\s+now|will\s+be)\s+(?:subject\s+to|conditioned\s+upon)"
            r"[^.]{0,100}?\bfinancing\s+condition\b",
            re.I,
        ),
        re.compile(r"\bfinancing\s+condition\s+(?:has\s+been|was)\s+added\b", re.I),
    )
    financing_evidence = _first_pattern_evidence(
        "financing_condition_added",
        True,
        sources,
        financing_added_patterns,
    )
    if financing_evidence:
        reasons.append("financing_condition_added")
    relevant_fields = {
        "has_cvr_consideration",
        "has_stock_consideration",
        "is_partial_offer",
        "is_mini_tender",
        "bankruptcy_indicated",
        "target_board_recommends_tender",
        "offer_price_usd",
    }
    evidence = [
        row for row in terms.get("evidence_spans") or [] if row.get("field") in relevant_fields
    ]
    if financing_evidence:
        evidence.append(financing_evidence)
    return {
        "invalidates_policy": bool(reasons),
        "invalidation_reasons": sorted(set(reasons)),
        "evidence_spans": evidence,
    }


def _target_event_item_201_source(source: Mapping[str, Any]) -> dict[str, Any] | None:
    text = str(source.get("text") or "")
    headings = tuple(
        re.finditer(
            r"\bItem\s+2\.01\b[\s\S]{0,180}?Completion\s+of\s+Acquisition\s+or\s+Disposition\s+of\s+Assets",
            text,
            re.I,
        )
    )
    if headings:
        start = headings[0].start()
        next_item = re.search(r"\bItem\s+(?!2\.01\b)\d+\.\d+\b", text[headings[0].end():], re.I)
        end = headings[0].end() + next_item.start() if next_item else len(text)
        section_name = "item_2_01"
    else:
        intro = re.search(r"\bIntroductory\s+Note\b", text, re.I)
        if not intro:
            return None
        start = intro.start()
        next_item = re.search(r"\bItem\s+\d+\.\d+\b", text[intro.end():], re.I)
        end = intro.end() + next_item.start() if next_item else len(text)
        section_name = "introductory_note"
    return {**dict(source), "text": text[start:end], "section_name": section_name}


def _text_mentions_cash_price(text: str, expected_cash_price_usd: float) -> bool:
    whole = f"{expected_cash_price_usd:.2f}"
    compact = whole.rstrip("0").rstrip(".")
    price = rf"(?:{re.escape(whole)}|{re.escape(compact)})"
    return bool(
        re.search(
            rf"\$\s*{price}\s+(?:net\s+)?(?:per\s+(?:common\s+)?share|a\s+share)",
            text,
            re.I,
        )
    )


def _explicit_event_date(text: str) -> str | None:
    patterns = (
        re.compile(
            rf"\b(?:accepted|completed|consummated)[^.\n]{{0,180}}?\bon\s+"
            rf"({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})",
            re.I,
        ),
        re.compile(
            rf"\bon\s+({_MONTH_TOKEN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}})"
            rf"[^.\n]{{0,220}}?\b(?:accepted|completed|consummated)\b",
            re.I,
        ),
    )
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            parsed = _parse_date_text(match.group(1))
            if parsed:
                return parsed
    return None


def extract_target_event_outcome(
    documents: Any,
    *,
    expected_cash_price_usd: float,
    source_url: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    """Parse a target 8-K only under the locked Item 2.01 cash-tender contract."""

    sources = _coerce_sources(documents, source_url=source_url, source_sha256=source_sha256)
    section_sources = [
        section
        for source in sources
        if (section := _target_event_item_201_source(source)) is not None
    ]
    base = extract_amendment_outcome(section_sources)
    section_text = "\n".join(str(row.get("text") or "") for row in section_sources)
    has_equity_offer = bool(
        re.search(r"\b(?:shares?|common\s+stock)\b", section_text, re.I)
        and re.search(r"\b(?:tender\s+offer|the\s+offer)\b", section_text, re.I)
    )
    price_matches = _text_mentions_cash_price(section_text, float(expected_cash_price_usd))
    terminal = base.get("outcome_type") in {
        "completed",
        "terminated_negative",
        "terminated_higher_bid",
    }
    contract_passed = bool(section_sources and has_equity_offer and price_matches and terminal)
    if not contract_passed:
        base.update(
            {
                "outcome_type": "pending",
                "completed": False,
                "terminated": False,
                "cash_price_usd": None,
                "evidence_spans": [],
            }
        )
    base["source_contract_passed"] = contract_passed
    base["source_contract"] = {
        "target_form": sorted(TARGET_EVENT_FORMS),
        "section": "Item 2.01 or Introductory Note",
        "equity_offer_language_found": has_equity_offer,
        "expected_cash_price_usd": float(expected_cash_price_usd),
        "cash_price_matches": price_matches,
        "explicit_past_terminal_language": terminal,
    }
    base["outcome_date"] = _explicit_event_date(section_text) if contract_passed else None
    return base


def _load_document_source(
    descriptor: Mapping[str, Any] | None,
    *,
    fetcher: Fetcher,
    role: str,
) -> dict[str, Any] | None:
    if not descriptor:
        return None
    source_url = str(descriptor.get("source_url") or "")
    embedded_content = descriptor.get("embedded_content")
    content: Any = embedded_content
    fetch_error: str | None = None
    if content is None and source_url:
        try:
            content = _fetch_bytes(fetcher, source_url)
        except Exception as exc:
            fetch_error = f"{type(exc).__name__}: {exc}"
    if content is None:
        return None
    source = _source_document(
        content,
        source_url=source_url or None,
        role=role,
        filename=str(descriptor.get("filename") or "") or None,
    )
    source["document_type"] = descriptor.get("document_type")
    source["description"] = descriptor.get("description")
    source["fetch_error"] = fetch_error
    source["used_embedded_content"] = embedded_content is not None
    source["used_embedded_fallback"] = False
    return source


def parse_sc_to_t_filing(
    index_row: Mapping[str, Any],
    *,
    fetcher: Fetcher,
) -> dict[str, Any]:
    """Fetch and parse one accession using only the injected fetcher."""

    raw_url = str(index_row.get("raw_submission_url") or "")
    if not raw_url:
        raise ValueError("index row is missing raw_submission_url")
    raw = _fetch_bytes(fetcher, raw_url)
    accession = str(index_row.get("accession_number") or _accession_from_filename(raw_url) or "")
    if not accession:
        raise ValueError("index row is missing accession_number")
    subject = extract_subject_company(raw)
    links = find_tender_document_links(
        raw,
        raw_submission_url=raw_url,
        accession_number=accession,
    )
    primary = _load_document_source(links.get("primary_schedule_to"), fetcher=fetcher, role="primary_schedule_to")
    offer = _load_document_source(
        links.get("offer_to_purchase_exhibit"), fetcher=fetcher, role="offer_to_purchase_exhibit"
    )
    sources = [source for source in (primary, offer) if source]
    form_type = str(index_row.get("form_type") or "").upper()
    result: dict[str, Any] = {
        **dict(index_row),
        **subject,
        "filed_by_ciks": extract_filing_person_ciks(raw),
        "rule_version": RULE_VERSION,
        "accession_number": accession,
        "form_type": form_type,
        "raw_submission_url": raw_url,
        "raw_submission_sha256": hashlib.sha256(raw).hexdigest(),
        "primary_schedule_to": _public_source(primary),
        "offer_to_purchase_exhibit": _public_source(offer),
        "document_links": {
            "primary_schedule_to_url": (links.get("primary_schedule_to") or {}).get("source_url"),
            "offer_to_purchase_url": (links.get("offer_to_purchase_exhibit") or {}).get("source_url"),
        },
    }
    if form_type == AMENDMENT_FORM:
        # Outcomes can be disclosed in a press release exhibit.  Parse all
        # textual SGML documents, without treating graphics as evidence.
        amendment_sources = list(sources)
        used_urls = {str(source.get("source_url") or "") for source in amendment_sources}
        for descriptor in links.get("documents") or []:
            url = str(descriptor.get("source_url") or "")
            filename = str(descriptor.get("filename") or "")
            if url in used_urls or re.search(r"\.(?:jpg|jpeg|gif|png|pdf|xls|xlsx|zip)$", filename, re.I):
                continue
            source = _load_document_source(descriptor, fetcher=fetcher, role="amendment_exhibit")
            if source:
                amendment_sources.append(source)
                used_urls.add(url)
        result["outcome"] = extract_amendment_outcome(amendment_sources)
        result["policy_delta"] = extract_amendment_policy_delta(amendment_sources)
        result["invalidates_policy"] = bool(result["policy_delta"]["invalidates_policy"])
        if result["invalidates_policy"]:
            result["policy_eligible"] = False
    else:
        result["terms"] = extract_tender_terms(sources)
        result["eligibility"] = evaluate_locked_policy_eligibility(result)
        result["policy_eligible"] = result["eligibility"]["eligible"]
        result["document_policy_eligible"] = result["eligibility"]["document_policy_eligible"]
    return result


def parse_target_event_filing(
    index_row: Mapping[str, Any],
    *,
    fetcher: Fetcher,
    expected_cash_price_usd: float,
) -> dict[str, Any]:
    """Parse a target 8-K companion without expanding the entry population."""

    form_type = str(index_row.get("form_type") or "").upper()
    if form_type not in TARGET_EVENT_FORMS:
        raise ValueError(f"unsupported target event form: {form_type}")
    raw_url = str(index_row.get("raw_submission_url") or "")
    if not raw_url:
        raise ValueError("target event row is missing raw_submission_url")
    raw = _fetch_bytes(fetcher, raw_url)
    accession = str(index_row.get("accession_number") or _accession_from_filename(raw_url) or "")
    if not accession:
        raise ValueError("target event row is missing accession_number")
    accepted = extract_subject_company(raw)
    links = find_tender_document_links(
        raw,
        raw_submission_url=raw_url,
        accession_number=accession,
    )
    descriptors = [
        row
        for row in links.get("documents") or []
        if str(row.get("document_type") or "").upper() in TARGET_EVENT_FORMS
    ]
    descriptors.sort(
        key=lambda row: (
            int(str(row.get("sequence") or "9999"))
            if str(row.get("sequence") or "").isdigit()
            else 9999,
            str(row.get("filename") or ""),
        )
    )
    if not descriptors:
        raise ValueError("target event filing has no primary 8-K document")
    primary = _load_document_source(
        descriptors[0],
        fetcher=fetcher,
        role="target_event_primary",
    )
    if not primary:
        raise ValueError("target event primary document is unavailable")
    outcome = extract_target_event_outcome(
        primary,
        expected_cash_price_usd=float(expected_cash_price_usd),
    )
    return {
        **dict(index_row),
        "accession_number": accession,
        "form_type": form_type,
        "accepted_at": accepted.get("accepted_at"),
        "accepted_at_raw": accepted.get("accepted_at_raw"),
        "raw_submission_url": raw_url,
        "raw_submission_sha256": hashlib.sha256(raw).hexdigest(),
        "primary_event_document": _public_source(primary),
        "expected_cash_price_usd": float(expected_cash_price_usd),
        "outcome": outcome,
    }


def _filing_offeror_ciks(row: Mapping[str, Any]) -> set[str]:
    subject_cik = str(row.get("subject_cik") or "")
    values = {
        str(value)
        for value in [*(row.get("index_ciks") or []), *(row.get("filed_by_ciks") or [])]
        if value
    }
    values.discard(subject_cik)
    return values


def _attach_amendments_to_episodes(
    episodes: Sequence[dict[str, Any]],
    amendments: Sequence[dict[str, Any]],
) -> None:
    """Attach amendments by target plus offeror identity, failing closed on ambiguity."""

    initial_by_cik: dict[str, list[dict[str, Any]]] = {}
    for episode in episodes:
        episode["amendments"] = []
        cik = str(episode.get("subject_cik") or "")
        if cik:
            initial_by_cik.setdefault(cik, []).append(episode)
    for candidates in initial_by_cik.values():
        candidates.sort(
            key=lambda row: (
                str(row.get("filing_date") or ""),
                str(row.get("accession_number") or ""),
            )
        )

    for amendment in amendments:
        cik = str(amendment.get("subject_cik") or "")
        filing_date = str(amendment.get("filing_date") or "")
        candidates = [
            episode
            for episode in initial_by_cik.get(cik, [])
            if str(episode.get("filing_date") or "") <= filing_date
        ]
        if not candidates:
            continue
        amendment_offerors = _filing_offeror_ciks(amendment)
        identity_matches = [
            episode
            for episode in candidates
            if amendment_offerors and (_filing_offeror_ciks(episode) & amendment_offerors)
        ]
        if identity_matches:
            selected = identity_matches[-1]
            mode = "offeror_cik_overlap"
        elif len(candidates) == 1:
            selected = candidates[0]
            mode = "single_target_episode_fallback"
        else:
            latest = candidates[-1]
            latest["amendment_association_ambiguous"] = True
            latest.setdefault("unassociated_target_amendments", []).append(
                {
                    "accession_number": amendment.get("accession_number"),
                    "filing_date": amendment.get("filing_date"),
                    "subject_cik": cik,
                    "offeror_ciks": sorted(amendment_offerors),
                    "reason": "multiple_preceding_target_offers_without_offeror_identity_match",
                }
            )
            continue
        amendment["association"] = {
            "mode": mode,
            "initial_accession_number": selected.get("accession_number"),
            "subject_cik": cik,
            "offeror_cik_overlap": sorted(_filing_offeror_ciks(selected) & amendment_offerors),
        }
        selected.setdefault("amendments", []).append(amendment)


def _public_source(source: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not source:
        return None
    return {
        key: source.get(key)
        for key in (
            "role",
            "filename",
            "document_type",
            "description",
            "source_url",
            "source_sha256",
            "fetch_error",
            "used_embedded_content",
            "used_embedded_fallback",
        )
    }


def _market_context_value(context: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in context:
            return context[key]
    return None


def evaluate_locked_policy_eligibility(
    episode: Mapping[str, Any],
    *,
    security_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the preregistered document/identity gate with explicit failures."""

    terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else episode
    context = dict(security_context or {})
    failures: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            failures.append(reason)

    require(str(episode.get("form_type") or "").upper() == INITIAL_FORM, "not_initial_sc_to_t")
    require(bool(episode.get("accession_number")), "missing_accession_number")
    require(bool(episode.get("subject_cik")), "missing_subject_cik")
    require(bool(episode.get("subject_company_name")), "missing_subject_company_name")
    require(bool(episode.get("raw_submission_url")), "missing_raw_submission_url")
    require(bool(episode.get("raw_submission_sha256")), "missing_raw_submission_sha256")
    require(bool(episode.get("primary_schedule_to")), "missing_primary_schedule_to")
    require(bool(episode.get("offer_to_purchase_exhibit")), "missing_offer_to_purchase_exhibit")

    price = terms.get("offer_price_usd")
    require(isinstance(price, (int, float)) and not isinstance(price, bool), "missing_exact_offer_price")
    if isinstance(price, (int, float)) and not isinstance(price, bool):
        require(float(price) > 1.0, "offer_price_not_above_one_dollar")
    require(terms.get("offer_price_ambiguous") is False, "ambiguous_offer_price")
    require(terms.get("fixed_cash_offer") is True, "not_fixed_all_cash_consideration")
    require(terms.get("all_outstanding_shares") is True, "not_all_outstanding_shares")
    require(terms.get("has_cvr_consideration") is False, "cvr_consideration_excluded")
    require(terms.get("has_stock_consideration") is False, "stock_or_exchange_consideration_excluded")
    require(terms.get("is_partial_offer") is False, "partial_offer_excluded")
    require(terms.get("is_mini_tender") is False, "mini_tender_excluded")
    require(terms.get("hostile_offer") is False, "hostile_offer_excluded")
    require(terms.get("target_board_recommends_tender") is True, "missing_target_board_recommendation")
    require(terms.get("definitive_agreement") is True, "missing_definitive_agreement")
    require(terms.get("no_financing_condition") is True, "missing_explicit_no_financing_condition")
    require(terms.get("binding_committed_financing") is True, "missing_binding_committed_financing")
    require(
        terms.get("financing_evidence_kind") in {"cash_on_hand", "binding_commitment"},
        "financing_evidence_unclear",
    )
    require(bool(terms.get("scheduled_expiration_date")), "missing_scheduled_expiration")

    ticker = _market_context_value(context, "ticker", "symbol") or terms.get("target_ticker")
    listed_common = _market_context_value(
        context, "is_listed_common_stock", "listed_common_stock", "security_is_listed_common_stock"
    )
    if listed_common is None and terms.get("listed_common_stock_evidence"):
        _, inferred_listed = _normalise_exchange(str(terms.get("target_exchange") or ""))
        listed_common = inferred_listed
    is_otc = _market_context_value(context, "is_otc", "otc")
    if is_otc is None and terms.get("listed_common_stock_evidence"):
        exchange, _ = _normalise_exchange(str(terms.get("target_exchange") or ""))
        is_otc = exchange == "OTC" if exchange else None
    is_bankrupt = _market_context_value(context, "is_bankrupt", "bankrupt")
    if is_bankrupt is None and "bankruptcy_indicated" in terms:
        is_bankrupt = terms.get("bankruptcy_indicated")
    require(bool(ticker), "missing_target_ticker")
    require(listed_common is True, "listed_common_stock_not_verified")
    require(is_otc is False, "otc_status_not_verified_false")
    require(is_bankrupt is False, "bankruptcy_status_not_verified_false")

    document_failures = [
        reason
        for reason in failures
        if reason
        not in {
            "missing_target_ticker",
            "listed_common_stock_not_verified",
            "otc_status_not_verified_false",
            "bankruptcy_status_not_verified_false",
        }
    ]
    market_failures = [reason for reason in failures if reason not in document_failures]
    return {
        "policy_version": RULE_VERSION,
        "eligible": not failures,
        "document_policy_eligible": not document_failures,
        "market_identity_eligible": not market_failures,
        "fail_closed_reasons": failures,
        "ticker": str(ticker).upper() if ticker else None,
        "trade_enabled": False,
        "alters_orders": False,
    }


# Concise alias for callers and tests.
locked_policy_eligibility = evaluate_locked_policy_eligibility


def _context_for_episode(
    episode: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, Any]] | None,
) -> Mapping[str, Any] | None:
    if not contexts:
        return None
    keys = (
        str(episode.get("accession_number") or ""),
        str(episode.get("subject_cik") or ""),
        str(episode.get("subject_cik") or "").lstrip("0"),
    )
    for key in keys:
        if key and key in contexts:
            return contexts[key]
    return None


def build_daily_default_off_candidate_snapshot(
    *,
    as_of: str,
    episodes: Sequence[Mapping[str, Any]],
    security_context_by_cik: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic exact-filing-day, no-order candidate snapshot."""

    day = str(as_of)[:10]
    if not _valid_iso_date(day):
        raise ValueError(f"invalid as_of: {as_of!r}")
    candidates: list[dict[str, Any]] = []
    for episode in episodes:
        if str(episode.get("form_type") or "").upper() != INITIAL_FORM:
            continue
        if str(episode.get("filing_date") or "")[:10] != day:
            continue
        context = _context_for_episode(episode, security_context_by_cik)
        eligibility = evaluate_locked_policy_eligibility(episode, security_context=context)
        candidates.append(
            {
                "candidate_id": f"{RULE_VERSION}:{episode.get('accession_number')}",
                "accession_number": episode.get("accession_number"),
                "filing_date": str(episode.get("filing_date") or "")[:10],
                "accepted_at": episode.get("accepted_at"),
                "subject_cik": episode.get("subject_cik"),
                "subject_company_name": episode.get("subject_company_name"),
                "ticker": eligibility.get("ticker"),
                "terms": episode.get("terms"),
                "eligibility": eligibility,
                "eligible": eligibility["eligible"],
                "policy_eligible": eligibility["eligible"],
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    candidates.sort(key=lambda row: (str(row.get("accepted_at") or ""), str(row["accession_number"])))
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "as_of": day,
        "status": "ready",
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "alters_orders": False,
        "orders": [],
        "candidate_count": len(candidates),
        "eligible_candidate_count": sum(bool(row["eligible"]) for row in candidates),
        "candidates": candidates,
        "next_action": "paper_observe_only_no_orders",
        "production_impact": {
            "shared_policy_changed": True,
            "default_off_paper_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "uses_llm": False,
        },
    }


# Naming variants used by existing sleeve code conventions.
build_daily_candidate_snapshot = build_daily_default_off_candidate_snapshot
build_sec_cash_tender_lifecycle_snapshot = build_daily_default_off_candidate_snapshot


def _error_episode(row: Mapping[str, Any], exc: Exception) -> dict[str, Any]:
    episode = {
        **dict(row),
        "rule_version": RULE_VERSION,
        "subject_company_name": None,
        "subject_cik": None,
        "raw_submission_sha256": None,
        "primary_schedule_to": None,
        "offer_to_purchase_exhibit": None,
        "terms": {},
        "parse_error": f"{type(exc).__name__}: {exc}",
    }
    episode["eligibility"] = evaluate_locked_policy_eligibility(episode)
    episode["policy_eligible"] = False
    episode["document_policy_eligible"] = False
    return episode


def _aggregate_episode_outcome(
    amendments: Sequence[Mapping[str, Any]],
    *,
    initial_offer_price_usd: float | None = None,
) -> dict[str, Any]:
    if not amendments:
        return {
            "outcome_type": "pending",
            "completed": False,
            "terminated": False,
            "higher_bid_identified": False,
            "higher_bid_price_usd": None,
            "higher_bid_prices": [],
            "cash_price_usd": None,
            "initial_offer_price_usd": initial_offer_price_usd,
            "evidence_spans": [],
            "amendment_accession_number": None,
            "amendment_filing_date": None,
            "outcome_date": None,
        }
    ordered = sorted(
        amendments,
        key=lambda row: (str(row.get("filing_date") or ""), str(row.get("accepted_at") or ""), str(row.get("accession_number") or "")),
    )
    terminal_types = {"completed", "terminated_negative", "terminated_higher_bid"}
    terminal = [
        row
        for row in ordered
        if str((row.get("outcome") or {}).get("outcome_type") or "") in terminal_types
    ]
    selected = terminal[-1] if terminal else ordered[-1]
    outcome = dict(selected.get("outcome") or {})
    price_rows: list[dict[str, Any]] = []
    for amendment in ordered:
        amendment_outcome = amendment.get("outcome") or {}
        price = amendment_outcome.get("higher_bid_price_usd")
        if isinstance(price, (int, float)) and not isinstance(price, bool):
            price_rows.append(
                {
                    "price_usd": float(price),
                    "accession_number": amendment.get("accession_number"),
                    "filing_date": amendment.get("filing_date"),
                    "evidence_spans": [
                        row
                        for row in amendment_outcome.get("evidence_spans") or []
                        if row.get("field") == "higher_bid_price_usd"
                    ],
                }
            )
    latest_higher_price = price_rows[-1]["price_usd"] if price_rows else None
    if latest_higher_price is not None:
        outcome["higher_bid_price_usd"] = latest_higher_price
        outcome["higher_bid_identified"] = True
    outcome["higher_bid_prices"] = price_rows
    outcome["initial_offer_price_usd"] = initial_offer_price_usd
    outcome["cash_price_usd"] = (
        latest_higher_price if latest_higher_price is not None else initial_offer_price_usd
    ) if outcome.get("outcome_type") == "completed" else None
    outcome["amendment_accession_number"] = selected.get("accession_number")
    outcome["amendment_filing_date"] = selected.get("filing_date")
    outcome["terminal_source_accession_number"] = selected.get("accession_number")
    outcome["terminal_source_form_type"] = selected.get("form_type")
    outcome["terminal_source_filing_date"] = selected.get("filing_date")
    outcome["knowledge_at"] = selected.get("accepted_at") or selected.get("filing_date")
    outcome["outcome_date"] = outcome.get("outcome_date") or selected.get("filing_date")
    return outcome


def aggregate_episode_outcome(
    amendments: Sequence[Mapping[str, Any]],
    *,
    initial_offer_price_usd: float | None = None,
) -> dict[str, Any]:
    """Public terminal-aware amendment aggregation for replay/daily parity."""

    return _aggregate_episode_outcome(
        amendments,
        initial_offer_price_usd=initial_offer_price_usd,
    )


def load_initial_sc_to_t_episodes(
    *,
    fetcher: Fetcher,
    windows: Sequence[tuple[str, str] | Mapping[str, Any]] | None = None,
    include_amendments: bool = True,
    strict: bool = True,
) -> list[dict[str, Any]]:
    """Load canonical-window initial episodes and attach target amendments.

    ``strict=False`` keeps malformed filings as explicitly ineligible rows so
    historical coverage cannot be silently improved by parser survivorship.
    """

    date_windows = _normalise_windows(windows)
    index_rows: list[dict[str, Any]] = []
    for url in canonical_master_index_urls(date_windows):
        try:
            payload = _fetch_bytes(fetcher, url)
        except Exception:
            if strict:
                raise
            continue
        index_rows.extend(
            parse_master_index(
                payload,
                source_url=url,
                windows=date_windows,
                forms=(*_ALLOWED_FORMS, *TARGET_EVENT_FORMS),
            )
        )

    # Quarterly files do not overlap, but keep a final accession guard for
    # caller-supplied or mirrored indexes.
    by_accession: dict[str, dict[str, Any]] = {}
    for row in index_rows:
        accession = str(row["accession_number"])
        if accession not in by_accession:
            by_accession[accession] = row
        else:
            current = by_accession[accession]
            current["index_entities"] = list(current.get("index_entities") or []) + list(
                row.get("index_entities") or []
            )
            current["duplicate_index_row_count"] = len(current["index_entities"]) - 1

    initial_rows = [row for row in by_accession.values() if row["form_type"] == INITIAL_FORM]
    amendment_rows = [row for row in by_accession.values() if row["form_type"] == AMENDMENT_FORM]
    target_event_rows = [
        row for row in by_accession.values() if row["form_type"] in TARGET_EVENT_FORMS
    ]
    episodes: list[dict[str, Any]] = []
    amendments: list[dict[str, Any]] = []
    for row, destination in ((row, episodes) for row in initial_rows):
        try:
            destination.append(parse_sc_to_t_filing(row, fetcher=fetcher))
        except Exception as exc:
            if strict:
                raise
            destination.append(_error_episode(row, exc))
    if include_amendments:
        for row in amendment_rows:
            try:
                amendments.append(parse_sc_to_t_filing(row, fetcher=fetcher))
            except Exception as exc:
                if strict:
                    raise
                amendments.append({**dict(row), "subject_cik": None, "parse_error": f"{type(exc).__name__}: {exc}"})

    _attach_amendments_to_episodes(episodes, amendments)
    for episode in episodes:
        episode["amendments"] = sorted(
            episode.get("amendments") or [],
            key=lambda row: (str(row.get("filing_date") or ""), str(row.get("accession_number") or "")),
        )
        terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else {}
        initial_price = terms.get("offer_price_usd")
        episode["outcome"] = _aggregate_episode_outcome(
            episode["amendments"],
            initial_offer_price_usd=(
                float(initial_price)
                if isinstance(initial_price, (int, float)) and not isinstance(initial_price, bool)
                else None
            ),
        )
        episode["target_event_filings"] = []

    target_event_rows.sort(
        key=lambda row: (str(row.get("filing_date") or ""), str(row.get("accession_number") or ""))
    )
    for event_row in target_event_rows:
        event_ciks = {str(value) for value in event_row.get("index_ciks") or [] if value}
        event_date_text = str(event_row.get("filing_date") or "")
        if not _valid_iso_date(event_date_text):
            continue
        event_day = date.fromisoformat(event_date_text)
        candidates: list[dict[str, Any]] = []
        for episode in episodes:
            if not bool(episode.get("policy_eligible")):
                continue
            current_outcome = str((episode.get("outcome") or {}).get("outcome_type") or "pending")
            if current_outcome not in {"pending", "extended_pending"}:
                continue
            subject_cik = str(episode.get("subject_cik") or "")
            if not subject_cik or subject_cik not in event_ciks:
                continue
            amendment_dates = [
                str(row.get("filing_date") or "")
                for row in episode.get("amendments") or []
                if _valid_iso_date(str(row.get("filing_date") or ""))
            ]
            terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else {}
            anchor_text = (
                max(amendment_dates)
                if amendment_dates
                else str(terms.get("scheduled_expiration_date") or episode.get("filing_date") or "")
            )
            if not _valid_iso_date(anchor_text):
                continue
            anchor = date.fromisoformat(anchor_text)
            if anchor <= event_day <= anchor + timedelta(days=10):
                candidates.append(episode)
        if len(candidates) != 1:
            if candidates:
                for episode in candidates:
                    episode["target_event_association_ambiguous"] = True
                    episode.setdefault("unassociated_target_event_filings", []).append(
                        {
                            "accession_number": event_row.get("accession_number"),
                            "form_type": event_row.get("form_type"),
                            "filing_date": event_row.get("filing_date"),
                            "reason": "multiple_pending_target_cash_tender_episodes",
                        }
                    )
            continue
        episode = candidates[0]
        terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else {}
        aggregate = episode.get("outcome") if isinstance(episode.get("outcome"), Mapping) else {}
        revised_price = aggregate.get("higher_bid_price_usd")
        expected_price = revised_price if isinstance(revised_price, (int, float)) else terms.get("offer_price_usd")
        if not isinstance(expected_price, (int, float)) or isinstance(expected_price, bool):
            continue
        try:
            target_event = parse_target_event_filing(
                event_row,
                fetcher=fetcher,
                expected_cash_price_usd=float(expected_price),
            )
        except Exception as exc:
            if strict:
                raise
            target_event = {
                **dict(event_row),
                "parse_error": f"{type(exc).__name__}: {exc}",
                "outcome": {"outcome_type": "pending", "source_contract_passed": False},
            }
        episode.setdefault("target_event_filings", []).append(target_event)
        if str((target_event.get("outcome") or {}).get("outcome_type") or "pending") in {
            "completed",
            "terminated_negative",
            "terminated_higher_bid",
        }:
            initial_price = terms.get("offer_price_usd")
            episode["outcome"] = _aggregate_episode_outcome(
                [*(episode.get("amendments") or []), *(episode.get("target_event_filings") or [])],
                initial_offer_price_usd=(
                    float(initial_price)
                    if isinstance(initial_price, (int, float)) and not isinstance(initial_price, bool)
                    else None
                ),
            )
    episodes.sort(key=lambda row: (str(row.get("filing_date") or ""), str(row.get("accession_number") or "")))
    return episodes


# Descriptive aliases for experiment runners.
load_sc_to_t_lifecycles = load_initial_sc_to_t_episodes
parse_canonical_window_initial_episodes = load_initial_sc_to_t_episodes


__all__ = [
    "AMENDMENT_FORM",
    "CANONICAL_WINDOWS",
    "INITIAL_FORM",
    "RULE_VERSION",
    "SCHEMA_VERSION",
    "TARGET_EVENT_FORMS",
    "aggregate_episode_outcome",
    "build_daily_candidate_snapshot",
    "build_daily_default_off_candidate_snapshot",
    "build_sec_cash_tender_lifecycle_snapshot",
    "canonical_master_index_urls",
    "evaluate_locked_policy_eligibility",
    "extract_amendment_outcome",
    "extract_amendment_policy_delta",
    "extract_filing_person_ciks",
    "extract_target_event_outcome",
    "extract_subject_company",
    "extract_tender_terms",
    "find_tender_document_links",
    "find_tender_documents",
    "load_initial_sc_to_t_episodes",
    "load_sc_to_t_lifecycles",
    "locked_policy_eligibility",
    "normalize_html_text",
    "parse_canonical_window_initial_episodes",
    "parse_master_index",
    "parse_sc_to_t_filing",
    "parse_target_event_filing",
]
