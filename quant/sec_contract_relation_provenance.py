"""SEC 8-K Item 1.01 contract-relation provenance surface.

The surface is observer-only. It converts locally cached SEC filing text into
replayable evidence rows that a later, separately gated candidate-pool alpha can
use when testing entity/customer/supplier propagation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text


log = logging.getLogger(__name__)

OBSERVER_NAME = "sec_contract_relation_provenance"
SCHEMA_VERSION = "sec_contract_relation_provenance_v1"
ARTIFACT_ROOT = "non_ohlcv/sec_contract_relation_provenance"
ITEM_CODE = "1.01"


BUCKET_PATTERNS: dict[str, tuple[str, ...]] = {
    "customer_or_revenue_contract": (
        r"\bcustomer agreement\b",
        r"\bcustomer contract\b",
        r"\bcommercial agreement\b",
        r"\bmaster services agreement\b",
        r"\bservice agreement\b",
        r"\bservices agreement\b",
        r"\bcustomer\b",
    ),
    "supplier_or_supply_contract": (
        r"\bsupply agreement\b",
        r"\bsupplier agreement\b",
        r"\bmaster supply agreement\b",
        r"\bsupply arrangement\b",
        r"\bofftake agreement\b",
        r"\bpower purchase agreement\b",
        r"\bcapacity agreement\b",
        r"\bprocurement agreement\b",
        r"\bsupplier\b",
    ),
    "purchase_or_sales_agreement": (
        r"\bpurchase agreement\b",
        r"\basset purchase agreement\b",
        r"\bunit purchase agreement\b",
        r"\bsecurities purchase agreement\b",
        r"\bshare purchase agreement\b",
        r"\bstock purchase agreement\b",
        r"\bsales agreement\b",
    ),
    "credit_or_financing_agreement": (
        r"\bcredit agreement\b",
        r"\bloan agreement\b",
        r"\bfinancing agreement\b",
        r"\bdebt financing\b",
        r"\bpromissory note\b",
        r"\bconvertible note\b",
        r"\brevolving credit\b",
    ),
    "license_or_collaboration_agreement": (
        r"\blicense agreement\b",
        r"\blicensing agreement\b",
        r"\bcollaboration agreement\b",
        r"\bjoint development agreement\b",
        r"\bco-development agreement\b",
    ),
    "lease_or_real_estate_agreement": (
        r"\blease agreement\b",
        r"\bsublease agreement\b",
        r"\breal estate purchase agreement\b",
    ),
    "general_material_agreement": (
        r"\bmaterial definitive agreement\b",
        r"\bdefinitive agreement\b",
        r"\bagreement\b",
        r"\bcontract\b",
    ),
}

SPECIFIC_BUCKETS = tuple(
    bucket for bucket in BUCKET_PATTERNS if bucket != "general_material_agreement"
)

COUNTERPARTY_PATTERNS = (
    re.compile(
        r"\b(?:with|from|to|between|among)\s+"
        r"(?P<name>[A-Z][A-Za-z0-9&.,'() -]{2,96})"
    ),
    re.compile(
        r"\bby and between\s+"
        r"(?P<name>[A-Z][A-Za-z0-9&.,'() -]{2,96})"
    ),
)
COUNTERPARTY_STOPWORDS = {
    "Company",
    "Registrant",
    "Issuer",
    "Borrower",
    "Lender",
    "Purchaser",
    "Seller",
    "Buyer",
    "Agent",
    "Trustee",
    "Item",
    "Exhibit",
}

AMOUNT_RE = re.compile(
    r"(?ix)"
    r"(?:\$|US\$|USD\s*)\s*\d+(?:,\d{3})*(?:\.\d+)?"
    r"(?:\s*(?:million|billion|mm|bn))?"
    r"|"
    r"\b\d+(?:\.\d+)?\s*(?:million|billion)\s+(?:dollars|usd)\b"
)
DURATION_RE = re.compile(
    r"(?ix)"
    r"\b(?:term|period)\s+of\s+\d+(?:\.\d+)?\s*(?:year|years|month|months)\b"
    r"|"
    r"\b\d+(?:\.\d+)?\s*(?:year|years|month|months)\s+"
    r"(?:term|period|agreement|lease|contract)\b"
    r"|"
    r"\b(?:expires?|expiration|terminates?|through|until)\s+(?:on\s+)?"
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}\b"
)


def _date_tag(value: str | date | datetime | None = None) -> str:
    if value is None:
        return date.today().strftime("%Y%m%d")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise ValueError(f"unsupported date tag: {value!r}")


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(DATA_ROOT.parent.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _snippet(text: str, start: int, end: int, *, radius: int = 220) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip(" ;,.")


def _text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _remove_write_temps(path: Path) -> None:
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def _write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        _remove_write_temps(path)
        return
    except PermissionError:
        log.warning("Atomic write failed for %s; falling back to direct write", path)
    path.write_text(text, encoding="utf-8")
    _remove_write_temps(path)


def _write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_json(payload, path, default=str)
        _remove_write_temps(path)
        return
    except PermissionError:
        log.warning("Atomic JSON write failed for %s; falling back to direct write", path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    _remove_write_temps(path)


def _item_codes(row: dict[str, Any]) -> set[str]:
    codes = row.get("eight_k_item_codes") or []
    if isinstance(codes, str):
        return {part.strip() for part in codes.split(",") if part.strip()}
    return {str(code).strip() for code in codes if str(code).strip()}


def is_item_101_8k(row: dict[str, Any]) -> bool:
    form_type = str(row.get("form_type") or "").upper()
    form_base = str(row.get("form_base") or "").upper()
    return (form_base == "8-K" or form_type.startswith("8-K")) and ITEM_CODE in _item_codes(row)


def _counterparty_candidates(snippet: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for pattern in COUNTERPARTY_PATTERNS:
        for match in pattern.finditer(snippet):
            raw = match.group("name")
            name = re.split(
                r"\s+(?:and|dated|pursuant|as|for|under|whereby|which|to|from)\b",
                raw,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            name = re.sub(r"\s+", " ", name).strip(" ,.;:-()")
            if not name or len(name) < 3:
                continue
            if name.split()[0].strip(" ,.;:-()") in COUNTERPARTY_STOPWORDS:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(name[:96])
    return candidates[:5]


def _evidence_text(row: dict[str, Any]) -> str:
    snippets = row.get("evidence_snippets") or []
    parts: list[str] = []
    if isinstance(snippets, list):
        for item in snippets:
            if isinstance(item, dict):
                parts.append(str(item.get("snippet") or ""))
                parts.append(str(item.get("matched_text") or ""))
            elif item:
                parts.append(str(item))
    return "\n".join(part for part in parts if part)


def extract_contract_economics(row: dict[str, Any]) -> dict[str, Any]:
    """Extract fixed observer-only economic term tags from relation evidence."""
    text = _evidence_text(row)
    amount_matches = sorted({match.group(0).strip() for match in AMOUNT_RE.finditer(text)})
    duration_matches = sorted(
        {match.group(0).strip() for match in DURATION_RE.finditer(text)}
    )
    counterparties = [
        str(value).strip()
        for value in (row.get("counterparty_candidates") or [])
        if str(value).strip()
    ]
    counterparty_examples = sorted(set(counterparties))
    has_amount = bool(amount_matches)
    has_duration = bool(duration_matches)
    normalized_counterparty_count = len(counterparty_examples)
    if has_amount or has_duration:
        bucket = "amount_or_duration"
    else:
        bucket = "no_amount_or_duration"
    if has_amount and has_duration:
        detail_bucket = "amount_and_duration"
    elif has_amount:
        detail_bucket = "amount_only"
    elif has_duration:
        detail_bucket = "duration_only"
    elif normalized_counterparty_count:
        detail_bucket = "named_counterparty_only"
    else:
        detail_bucket = "no_machine_economics"
    return {
        "contract_amount_count": len(amount_matches),
        "contract_amount_examples": amount_matches[:5],
        "contract_duration_count": len(duration_matches),
        "contract_duration_examples": duration_matches[:5],
        "normalized_counterparty_count": normalized_counterparty_count,
        "counterparty_examples": counterparty_examples[:5],
        "economic_terms_bucket": bucket,
        "economic_terms_detail_bucket": detail_bucket,
        "has_contract_amount": has_amount,
        "has_contract_duration": has_duration,
        "has_named_counterparty": normalized_counterparty_count > 0,
    }


def relation_evidence(text: str, *, max_snippets_per_bucket: int = 4) -> dict[str, list[dict[str, Any]]]:
    """Return matched relation evidence grouped by fixed bucket."""
    clean = _normalize_ws(text)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for bucket, patterns in BUCKET_PATTERNS.items():
        bucket_rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for index, pattern in enumerate(patterns):
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(clean):
                snippet = _snippet(clean, match.start(), match.end())
                key = (pattern, snippet.casefold())
                if key in seen:
                    continue
                seen.add(key)
                bucket_rows.append(
                    {
                        "bucket": bucket,
                        "pattern_id": f"{bucket}:{index}",
                        "pattern": pattern,
                        "matched_text": match.group(0)[:120],
                        "start_char": match.start(),
                        "snippet": snippet,
                        "counterparty_candidates": _counterparty_candidates(snippet),
                    }
                )
                if len(bucket_rows) >= max_snippets_per_bucket:
                    break
            if len(bucket_rows) >= max_snippets_per_bucket:
                break
        if bucket_rows:
            grouped[bucket] = bucket_rows
    if any(bucket in grouped for bucket in SPECIFIC_BUCKETS):
        grouped.pop("general_material_agreement", None)
    return grouped


def build_rows_from_record(
    row: dict[str, Any],
    *,
    source_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    if not is_item_101_8k(row):
        return []
    text = str(row.get("combined_text") or "")
    evidence_by_bucket = relation_evidence(text)
    if not evidence_by_bucket:
        return []
    text_hash = _text_hash(text)
    source = Path(source_path) if source_path is not None else None
    rows: list[dict[str, Any]] = []
    for bucket, evidence in evidence_by_bucket.items():
        quality = (
            "specific_relation_phrase"
            if bucket != "general_material_agreement"
            else "generic_agreement_only"
        )
        counterparties: list[str] = []
        seen_counterparties: set[str] = set()
        for item in evidence:
            for candidate in item.get("counterparty_candidates") or []:
                key = str(candidate).casefold()
                if key not in seen_counterparties:
                    seen_counterparties.add(key)
                    counterparties.append(candidate)
        output_row = {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "observer_only": True,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "data_source": "sec_filing_text_item_1_01",
            "relation_bucket": bucket,
            "relation_quality": quality,
            "ticker": row.get("ticker"),
            "cik": row.get("cik"),
            "accession_number": row.get("accession_number"),
            "form_type": row.get("form_type"),
            "form_base": row.get("form_base"),
            "filing_date": row.get("filing_date"),
            "usable_trade_date": row.get("usable_trade_date"),
            "accepted_at": row.get("accepted_at"),
            "eight_k_item_codes": sorted(_item_codes(row)),
            "primary_document": row.get("primary_document"),
            "index_url": row.get("index_url"),
            "source_path": _repo_rel(source) if source is not None else None,
            "source_text_hash16": text_hash,
            "source_text_char_count": row.get("text_char_count") or len(text),
            "source_text_word_count": row.get("text_word_count"),
            "evidence_phrase_count": len(evidence),
            "evidence_snippets": evidence,
            "counterparty_candidates": counterparties[:10],
            "pit_source": row.get("pit_source") or "sec_archive_public_filing_text",
            "pit_caveat": row.get("pit_caveat")
            or (
                "SEC public archive text fetched after the fact and keyed "
                "by accepted_at/usable_trade_date; replayable public-PIT "
                "proxy, not proof the production pipeline observed the document."
            ),
        }
        output_row.update(extract_contract_economics(output_row))
        rows.append(output_row)
    return rows


def load_jsonl(path: Path | str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = Path(path)
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Skipping invalid JSONL line in %s", path)
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def build_surface_from_paths(paths: Iterable[Path | str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_rows: list[dict[str, Any]] = []
    source_files = [Path(path) for path in paths]
    input_rows = 0
    item_101_rows = 0
    for path in source_files:
        records = load_jsonl(path)
        input_rows += len(records)
        for record in records:
            if is_item_101_8k(record):
                item_101_rows += 1
            output_rows.extend(build_rows_from_record(record, source_path=path))
    output_rows = _dedupe_rows(output_rows)
    summary = summarize_rows(
        output_rows,
        source_file_count=len(source_files),
        input_rows=input_rows,
        item_101_input_rows=item_101_rows,
    )
    return output_rows, summary


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("accession_number") or ""),
        str(row.get("relation_bucket") or ""),
        str(row.get("source_text_hash16") or ""),
    )


def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return sorted(
        unique,
        key=lambda row: (
            str(row.get("usable_trade_date") or row.get("filing_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("accession_number") or ""),
            str(row.get("relation_bucket") or ""),
        ),
    )


def _existing_keys(rows_path: Path) -> set[tuple[str, str, str]]:
    if not rows_path.exists():
        return set()
    return {_row_key(row) for row in load_jsonl(rows_path)}


def append_rows(rows_path: Path, rows: Iterable[dict[str, Any]]) -> int:
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_keys(rows_path)
    fresh = []
    for row in _dedupe_rows(rows):
        key = _row_key(row)
        if key in existing:
            continue
        existing.add(key)
        fresh.append(row)
    if not fresh:
        return 0
    with rows_path.open("a", encoding="utf-8") as handle:
        for row in fresh:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(fresh)


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in _dedupe_rows(rows)
    )
    _write_text(text, path)


def _paths(data_dir: str | Path | None = None) -> dict[str, Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    base = root / ARTIFACT_ROOT
    return {
        "base": base,
        "rows": base / "rows.jsonl",
        "manifest": base / "manifest.json",
        "latest_summary": base / "latest_summary.json",
    }


def _daily_paths(date_tag: str, data_dir: str | Path | None = None) -> dict[str, Path]:
    base = _paths(data_dir)["base"] / "daily"
    return {
        "rows": base / f"{OBSERVER_NAME}_{date_tag}.jsonl",
        "summary": base / f"{OBSERVER_NAME}_summary_{date_tag}.json",
    }


def source_text_path(today: str | date | datetime, data_dir: str | Path | None = None) -> Path:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    return root / "non_ohlcv" / f"sec_filing_text_{_date_tag(today)}.jsonl"


def source_text_glob(data_dir: str | Path | None = None) -> list[Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    return sorted((root / "non_ohlcv").glob("sec_filing_text_*.jsonl"))


def summarize_rows(
    rows: list[dict[str, Any]],
    *,
    source_file_count: int,
    input_rows: int,
    item_101_input_rows: int,
    date_tag: str | None = None,
) -> dict[str, Any]:
    bucket_counts = Counter(str(row.get("relation_bucket") or "") for row in rows)
    quality_counts = Counter(str(row.get("relation_quality") or "") for row in rows)
    economics_bucket_counts = Counter(
        str(row.get("economic_terms_bucket") or "") for row in rows
    )
    economics_detail_counts = Counter(
        str(row.get("economic_terms_detail_bucket") or "") for row in rows
    )
    accessions = {str(row.get("accession_number") or "") for row in rows}
    tickers = {str(row.get("ticker") or "") for row in rows if row.get("ticker")}
    counterparty_rows = sum(1 for row in rows if row.get("counterparty_candidates"))
    return {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "status": "ok",
        "date": date_tag,
        "source_file_count": source_file_count,
        "input_row_count": input_rows,
        "item_101_input_row_count": item_101_input_rows,
        "provenance_row_count": len(rows),
        "unique_accession_count": len(accessions),
        "unique_ticker_count": len(tickers),
        "specific_relation_row_count": sum(
            1 for row in rows if row.get("relation_quality") == "specific_relation_phrase"
        ),
        "generic_relation_row_count": sum(
            1 for row in rows if row.get("relation_quality") == "generic_agreement_only"
        ),
        "counterparty_candidate_row_count": counterparty_rows,
        "contract_amount_row_count": sum(1 for row in rows if row.get("has_contract_amount")),
        "contract_duration_row_count": sum(
            1 for row in rows if row.get("has_contract_duration")
        ),
        "economic_terms_bucket_counts": dict(sorted(economics_bucket_counts.items())),
        "economic_terms_detail_counts": dict(sorted(economics_detail_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "quality_counts": dict(sorted(quality_counts.items())),
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }


def write_full_surface(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    data_dir: str | Path | None = None,
) -> dict[str, Any]:
    paths = _paths(data_dir)
    write_jsonl(rows, paths["rows"])
    manifest = dict(summary)
    manifest.update(
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "rows_path": _repo_rel(paths["rows"]),
            "manifest_path": _repo_rel(paths["manifest"]),
            "latest_summary_path": _repo_rel(paths["latest_summary"]),
            "write_mode": "replace_full_surface",
        }
    )
    _write_json(manifest, paths["manifest"])
    _write_json(manifest, paths["latest_summary"])
    return manifest


def persist_sec_contract_relation_provenance(
    today: str | date | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Append the current daily SEC text file to the observer-only surface."""
    date_tag = _date_tag(today)
    source = Path(source_path) if source_path is not None else source_text_path(date_tag, data_dir)
    daily = _daily_paths(date_tag, data_dir)
    paths = _paths(data_dir)
    if not source.exists():
        summary = {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "status": "missing_source",
            "date": date_tag,
            "source_path": _repo_rel(source),
            "provenance_row_count": 0,
            "rows_appended": 0,
            "observer_only": True,
            "strategy_behavior_changed": False,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        }
        _write_json(summary, daily["summary"])
        _write_json(summary, paths["latest_summary"])
        return summary

    rows, summary = build_surface_from_paths([source])
    appended = append_rows(paths["rows"], rows)
    daily_summary = dict(summary)
    daily_summary.update(
        {
            "date": date_tag,
            "source_path": _repo_rel(source),
            "rows_path": _repo_rel(paths["rows"]),
            "daily_rows_path": _repo_rel(daily["rows"]),
            "daily_summary_path": _repo_rel(daily["summary"]),
            "rows_appended": appended,
            "write_mode": "append_daily",
        }
    )
    write_jsonl(rows, daily["rows"])
    _write_json(daily_summary, daily["summary"])

    existing_rows = load_jsonl(paths["rows"])
    manifest = summarize_rows(
        existing_rows,
        source_file_count=None or 0,
        input_rows=None or 0,
        item_101_input_rows=None or 0,
        date_tag=date_tag,
    )
    manifest.update(
        {
            "status": "ok",
            "last_daily_source_path": _repo_rel(source),
            "last_daily_rows_path": _repo_rel(daily["rows"]),
            "last_daily_summary_path": _repo_rel(daily["summary"]),
            "rows_path": _repo_rel(paths["rows"]),
            "manifest_path": _repo_rel(paths["manifest"]),
            "latest_summary_path": _repo_rel(paths["latest_summary"]),
            "rows_appended": appended,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "write_mode": "append_daily",
        }
    )
    _write_json(manifest, paths["manifest"])
    _write_json(daily_summary, paths["latest_summary"])
    return daily_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", default=None)
    parser.add_argument("--all-local", action="store_true")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--source-path", default=None)
    args = parser.parse_args(argv)

    if args.all_local:
        rows, summary = build_surface_from_paths(source_text_glob(args.data_dir))
        result = write_full_surface(rows, summary, data_dir=args.data_dir)
    else:
        result = persist_sec_contract_relation_provenance(
            args.date,
            data_dir=args.data_dir,
            source_path=args.source_path,
        )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
