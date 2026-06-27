from __future__ import annotations

import argparse
from collections import Counter
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
DEFAULT_FORMS = ("8-K", "6-K", "10-K", "10-Q")
DEFAULT_ITEM_CODES = ("2.02",)
DEI_COVER_STATUS_FIELDS = (
    "large_accelerated_filer",
    "accelerated_filer",
    "non_accelerated_filer",
    "smaller_reporting_company",
    "emerging_growth_company",
    "shell_company",
)

_DEI_FILER_CATEGORY_PATTERNS = (
    re.compile(r"(?:dei[:_])?EntityFilerCategory[^>]*>\s*([^<]+?)\s*<", re.I),
    re.compile(
        r"['\"]?dei[:_]EntityFilerCategory['\"]?\s*[:=]\s*['\"]([^'\"]+?)['\"]",
        re.I,
    ),
)

_DEI_BOOLEAN_FACT_PATTERNS = {
    "emerging_growth_company": (
        re.compile(r"(?:dei[:_])?EntityEmergingGrowthCompany[^>]*>\s*(true|false|1|0)\s*<", re.I),
        re.compile(
            r"['\"]?dei[:_]EntityEmergingGrowthCompany['\"]?\s*[:=]\s*['\"]?(true|false|1|0)['\"]?",
            re.I,
        ),
    ),
    "shell_company": (
        re.compile(r"(?:dei[:_])?EntityShellCompany[^>]*>\s*(true|false|1|0)\s*<", re.I),
        re.compile(
            r"['\"]?dei[:_]EntityShellCompany['\"]?\s*[:=]\s*['\"]?(true|false|1|0)['\"]?",
            re.I,
        ),
    ),
}

_COVER_STATUS_LABELS = {
    "large_accelerated_filer": "large accelerated filer",
    "accelerated_filer": "accelerated filer",
    "non_accelerated_filer": "non-accelerated filer",
    "smaller_reporting_company": "smaller reporting company",
    "emerging_growth_company": "emerging growth company",
    "shell_company": "shell company",
}

_CHECKED_TOKENS = ("\u2612", "\u2611", "\u00fe", "[x]", "[X]")
_UNCHECKED_TOKENS = ("\u2610", "\u00a8", "[ ]")
_CHECKBOX_TOKEN_RE = re.compile(
    r"\u2612|\u2611|\u00fe|\u2610|\u00a8|\[x\]|\[X\]|\[ \]"
)
_COLUMN_STATUS_FIELDS = (
    "large_accelerated_filer",
    "accelerated_filer",
    "non_accelerated_filer",
    "smaller_reporting_company",
    "emerging_growth_company",
)
_COLUMN_STATUS_PATTERNS = {
    "large_accelerated_filer": re.compile(r"large\s+accelerated\s+filer", re.I),
    "accelerated_filer": re.compile(r"(?<!large\s)(?<!non[-\s])accelerated\s+filer", re.I),
    "non_accelerated_filer": re.compile(r"non[-\s]accelerated\s+filer", re.I),
    "smaller_reporting_company": re.compile(r"smaller\s+reporting\s+company", re.I),
    "emerging_growth_company": re.compile(r"emerging\s+growth\s+company", re.I),
}


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


def _bool_from_token(value: str) -> bool | None:
    lowered = str(value or "").strip().lower()
    if lowered in {"true", "1"}:
        return True
    if lowered in {"false", "0"}:
        return False
    return None


def _normalize_filer_category(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s+", " ", raw.strip().lower())
    value = value.replace("_", " ").replace("-", " ")
    if "large accelerated filer" in value:
        return "large_accelerated_filer"
    if "non accelerated filer" in value:
        return "non_accelerated_filer"
    if "accelerated filer" in value:
        return "accelerated_filer"
    if "smaller reporting company" in value:
        return "smaller_reporting_company"
    return None


def _extract_dei_filer_category(text: str) -> str | None:
    for pattern in _DEI_FILER_CATEGORY_PATTERNS:
        match = pattern.search(text)
        if match:
            category = _normalize_filer_category(html.unescape(match.group(1)))
            if category:
                return category
    return None


def _extract_dei_boolean_facts(text: str) -> dict[str, bool]:
    facts: dict[str, bool] = {}
    for field, patterns in _DEI_BOOLEAN_FACT_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            value = _bool_from_token(match.group(1))
            if value is not None:
                facts[field] = value
                break
    return facts


def _status_booleans_from_facts(
    category: str | None,
    boolean_facts: dict[str, bool],
) -> dict[str, bool | None]:
    statuses = {field: None for field in DEI_COVER_STATUS_FIELDS}
    if category in {
        "large_accelerated_filer",
        "accelerated_filer",
        "non_accelerated_filer",
        "smaller_reporting_company",
    }:
        for field in (
            "large_accelerated_filer",
            "accelerated_filer",
            "non_accelerated_filer",
            "smaller_reporting_company",
        ):
            statuses[field] = field == category
    for field, value in boolean_facts.items():
        statuses[field] = value
    return statuses


def _token_state_near_label(text: str, position: int, label: str) -> bool | None:
    prefix = text[max(0, position - 8):position]
    suffix = text[position + len(label):position + len(label) + 8]
    for window in (prefix, suffix):
        checked = any(token in window for token in _CHECKED_TOKENS)
        unchecked = any(token in window for token in _UNCHECKED_TOKENS)
        if checked and not unchecked:
            return True
        if unchecked and not checked:
            return False
    checked = any(token in prefix + suffix for token in _CHECKED_TOKENS)
    unchecked = any(token in prefix + suffix for token in _UNCHECKED_TOKENS)
    if checked and not unchecked:
        return True
    if unchecked and not checked:
        return False
    return None


def _checkbox_token_to_bool(token: str) -> bool | None:
    if token in _CHECKED_TOKENS:
        return True
    if token in _UNCHECKED_TOKENS:
        return False
    return None


def _find_cover_status_label(text: str, field: str, label: str) -> int:
    if field == "accelerated_filer":
        pattern = re.compile(r"(?<!large\s)(?<!non-)accelerated filer", re.I)
    elif field == "non_accelerated_filer":
        pattern = re.compile(r"non[-\s]accelerated filer", re.I)
    else:
        pattern = re.compile(re.escape(label), re.I)
    match = pattern.search(text)
    return -1 if not match else match.start()


def _ordered_column_label_match(
    text: str,
    fields: tuple[str, ...],
) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    for first in _COLUMN_STATUS_PATTERNS[fields[0]].finditer(text):
        cursor = first.end()
        matched = True
        end = cursor
        for field in fields[1:]:
            match = _COLUMN_STATUS_PATTERNS[field].search(text, cursor)
            if not match:
                matched = False
                break
            cursor = match.end()
            end = cursor
        if matched:
            candidate = (first.start(), end)
            if best is None or candidate[1] > best[1]:
                best = candidate
    return best


def _extract_column_checkbox_statuses(text: str) -> tuple[dict[str, bool | None], dict[str, Any]]:
    statuses = {field: None for field in DEI_COVER_STATUS_FIELDS}
    token_matches = list(_CHECKBOX_TOKEN_RE.finditer(text))
    token_groups: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    previous_end: int | None = None
    for match in token_matches:
        if current and previous_end is not None and match.start() - previous_end > 80:
            token_groups.append(current)
            current = []
        current.append(match)
        previous_end = match.end()
    if current:
        token_groups.append(current)

    matched_fields: tuple[str, ...] = ()
    for group in token_groups:
        if len(group) < 4:
            continue
        before = text[max(0, group[0].start() - 360):group[0].start()]
        for width in (5, 4):
            fields = _COLUMN_STATUS_FIELDS[: min(width, len(group))]
            if len(fields) < 4:
                continue
            label_span = _ordered_column_label_match(before, fields)
            if not label_span:
                continue
            values = [_checkbox_token_to_bool(match.group(0)) for match in group[: len(fields)]]
            if any(value is None for value in values):
                continue
            for field, value in zip(fields, values):
                statuses[field] = value
            matched_fields = fields
            break
        if matched_fields:
            break

    diagnostics = {
        "column_layout_token_groups": len(token_groups),
        "column_layout_fields": list(matched_fields),
        "column_layout_parsed_fields": sum(value is not None for value in statuses.values()),
    }
    return statuses, diagnostics


def _extract_shell_company_yes_no(text: str) -> bool | None:
    pattern = re.compile(
        rf"shell\s+company[\s\S]{{0,220}}?yes\s*({_CHECKBOX_TOKEN_RE.pattern})\s*"
        rf"no\s*({_CHECKBOX_TOKEN_RE.pattern})",
        re.I,
    )
    for match in pattern.finditer(text):
        yes_value = _checkbox_token_to_bool(match.group(1))
        no_value = _checkbox_token_to_bool(match.group(2))
        if yes_value is True and no_value is not True:
            return True
        if no_value is True and yes_value is not True:
            return False
    return None


def _extract_checkbox_statuses(text: str) -> tuple[dict[str, bool | None], dict[str, Any]]:
    statuses = {field: None for field in DEI_COVER_STATUS_FIELDS}
    checked_count = sum(text.count(token) for token in _CHECKED_TOKENS)
    unchecked_count = sum(text.count(token) for token in _UNCHECKED_TOKENS)
    labels_found = 0
    for field, label in _COVER_STATUS_LABELS.items():
        position = _find_cover_status_label(text, field, label)
        if position < 0:
            continue
        labels_found += 1
        statuses[field] = _token_state_near_label(text, position, label)
    column_statuses, column_diagnostics = _extract_column_checkbox_statuses(text)
    for field, value in column_statuses.items():
        if statuses.get(field) is None and value is not None:
            statuses[field] = value
    shell_value = _extract_shell_company_yes_no(text)
    if statuses.get("shell_company") is None and shell_value is not None:
        statuses["shell_company"] = shell_value
    parsed_count = sum(value is not None for value in statuses.values())
    diagnostics = {
        "labels_found": labels_found,
        "checked_token_count": checked_count,
        "unchecked_token_count": unchecked_count,
        "parsed_checkbox_fields": parsed_count,
        "shell_yes_no_parsed": shell_value is not None,
        **column_diagnostics,
    }
    return statuses, diagnostics


def parse_dei_cover_status(text: str) -> dict[str, Any]:
    """Parse SEC cover-page DEI filer-status fields from raw iXBRL or text.

    This is read-only measurement plumbing. It does not decide whether any
    filing should become a candidate; it only preserves replayable status facts.
    """
    source = text or ""
    category = _extract_dei_filer_category(source)
    boolean_facts = _extract_dei_boolean_facts(source)
    fact_statuses = _status_booleans_from_facts(category, boolean_facts)
    fact_fields = [field for field, value in fact_statuses.items() if value is not None]
    checkbox_statuses, checkbox_diagnostics = _extract_checkbox_statuses(source)
    checkbox_fields = [
        field for field, value in checkbox_statuses.items() if value is not None
    ]

    if fact_fields:
        statuses = fact_statuses
        source_kind = "dei_machine_readable_fact"
        parse_status = "parsed_machine_readable_dei_fact"
    elif checkbox_fields:
        statuses = checkbox_statuses
        source_kind = "cover_page_checkbox_text"
        parse_status = "parsed_cover_page_checkbox_text"
    else:
        statuses = fact_statuses
        source_kind = "none"
        lower = source.lower()
        cover_terms_present = any(label in lower for label in _COVER_STATUS_LABELS.values())
        if cover_terms_present:
            parse_status = "blocked_cover_terms_without_parseable_status"
        else:
            parse_status = "blocked_no_cover_page_status_terms"

    fields = [field for field, value in statuses.items() if value is not None]
    lower = source.lower()
    return {
        "schema_version": 1,
        "parse_status": parse_status,
        "source": source_kind,
        "filer_category": category,
        "boolean_facts": boolean_facts,
        "status_booleans": statuses,
        "machine_readable_status_fields": fields,
        "status_field_count": len(fields),
        "cover_terms_present": any(label in lower for label in _COVER_STATUS_LABELS.values()),
        "checkbox_diagnostics": checkbox_diagnostics,
    }


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


def _is_cover_xbrl_text_document(name: str) -> bool:
    lowered = name.lower()
    return bool(re.fullmatch(r"r1\.html?", lowered)) or lowered.endswith("_htm.xml")


def _is_text_document(name: str) -> bool:
    lowered = name.lower()
    if _is_cover_xbrl_text_document(name):
        return True
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
    if _is_cover_xbrl_text_document(name):
        score += 70
    if lowered.endswith(".txt"):
        score -= 20
    if "8k" in lowered:
        score += 10
    return (-score, lowered)


def _event_form_base(row: dict[str, Any]) -> str:
    return str(row.get("form_base") or row.get("form_type") or "").upper().replace("/A", "")


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
    form_base = _event_form_base(row)
    if form_base not in forms:
        return False
    if item_codes is None:
        return True
    if form_base != "8-K":
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
    parser_parts: list[str] = []
    for name in names:
        url = f"{base}/{name}"
        try:
            raw = request_text(url, user_agent)
            if len(raw) > max_chars_per_doc:
                raw = raw[:max_chars_per_doc]
            text = html_to_text(raw)
            parser_parts.append(raw)
            parser_parts.append(text)
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
    dei_cover_status = parse_dei_cover_status("\n".join(parser_parts + [combined_text]))
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
        "dei_cover_status": dei_cover_status,
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
    all_events = load_jsonl(events_path)
    matched_events = [row for row in all_events if _event_matches(row, forms, item_codes)]
    events = matched_events
    if args.limit:
        events = events[: args.limit]
    source_form_counts = Counter(_event_form_base(row) or "UNKNOWN" for row in all_events)
    matched_form_counts = Counter(_event_form_base(row) or "UNKNOWN" for row in matched_events)
    selected_form_counts = Counter(_event_form_base(row) or "UNKNOWN" for row in events)

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
        "source_events_input": len(all_events),
        "events_input": len(events),
        "matched_events_input": len(matched_events),
        "rows_written": len(rows),
        "status_counts": {},
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "accessions": len({row.get("accession_number") for row in rows if row.get("accession_number")}),
        "documents_fetched": sum(int(row.get("documents_fetched") or 0) for row in rows),
        "text_char_count": sum(int(row.get("text_char_count") or 0) for row in rows),
        "rows_with_dei_cover_status": sum(
            1
            for row in rows
            if int((row.get("dei_cover_status") or {}).get("status_field_count") or 0) > 0
        ),
        "dei_cover_status_parse_counts": dict(
            Counter(
                str((row.get("dei_cover_status") or {}).get("parse_status") or "missing")
                for row in rows
            )
        ),
        "forms": sorted(forms),
        "source_form_counts": dict(sorted(source_form_counts.items())),
        "matched_form_counts": dict(sorted(matched_form_counts.items())),
        "selected_form_counts": dict(sorted(selected_form_counts.items())),
        "selected_periodic_rows": sum(
            int(count)
            for form, count in selected_form_counts.items()
            if form in {"10-K", "10-Q"}
        ),
        "limit": args.limit,
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
