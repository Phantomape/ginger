from __future__ import annotations

import argparse
import gzip
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sec_submissions import fetch_submission
from sec_ticker_map import load_company_ticker_map, normalize_cik


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_XML_CACHE_DIR = DATA_DIR / "sec_form4_xml_cache"
DEFAULT_OUT_DIR = DATA_DIR / "non_ohlcv"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
DEFAULT_START = "2024-10-02"
FORM4_FORMS = {"4", "4/A"}
NON_COMPANY_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}
SEC_ARCHIVE_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_archive}/{accession_nodash}/{primary_doc}"
)


def _repo_path(path: Path | str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return REPO_ROOT / value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_acceptance_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{14}", text):
        return datetime.strptime(text, "%Y%m%d%H%M%S")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        parsed_date = _parse_date(text)
        if parsed_date:
            return datetime.combine(parsed_date, datetime.min.time())
    return None


def _next_weekday(value: date) -> date:
    current = value
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current


def conservative_usable_trade_date(accepted_at: datetime | None, filing_date: str | None = None) -> str | None:
    """Return the first next-weekday date after EDGAR acceptance.

    This is intentionally conservative for daily backtests: a filing accepted during
    the session is still treated as usable only from the following trading day.
    """
    if accepted_at is None:
        parsed_filing_date = _parse_date(filing_date)
        if parsed_filing_date is None:
            return None
        return _next_weekday(parsed_filing_date + timedelta(days=1)).isoformat()
    return _next_weekday(accepted_at.date() + timedelta(days=1)).isoformat()


def _recent_value(recent: dict[str, Any], field: str, idx: int) -> Any:
    values = recent.get(field)
    if not isinstance(values, list) or idx >= len(values):
        return None
    return values[idx]


def _recent_row_count(recent: dict[str, Any]) -> int:
    lengths = [len(value) for value in recent.values() if isinstance(value, list)]
    return max(lengths) if lengths else 0


def archive_url(cik: str | None, accession_number: str | None, primary_document: str | None) -> str | None:
    cik_norm = normalize_cik(cik)
    if not cik_norm or not accession_number or not primary_document:
        return None
    return SEC_ARCHIVE_URL.format(
        cik_archive=str(int(cik_norm)),
        accession_nodash=str(accession_number).replace("-", ""),
        primary_doc=str(primary_document),
    )


def raw_form4_primary_document(primary_document: str | None) -> str | None:
    if not primary_document:
        return None
    text = str(primary_document)
    if "/" not in text:
        return text
    prefix, rest = text.split("/", 1)
    if prefix.lower().startswith("xslf345"):
        return rest
    return text


def raw_form4_archive_url(cik: str | None, accession_number: str | None, primary_document: str | None) -> str | None:
    return archive_url(cik, accession_number, raw_form4_primary_document(primary_document))


def iter_recent_form4_filings(
    payload: dict[str, Any],
    *,
    ticker: str | None = None,
    cik: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict[str, Any]]:
    filings = payload.get("filings") if isinstance(payload, dict) else {}
    recent = filings.get("recent") if isinstance(filings, dict) else {}
    if not isinstance(recent, dict):
        return []

    cik_norm = normalize_cik(cik or payload.get("cik"))
    rows: list[dict[str, Any]] = []
    for idx in range(_recent_row_count(recent)):
        form = str(_recent_value(recent, "form", idx) or "").upper()
        if form not in FORM4_FORMS:
            continue
        filing_date = _recent_value(recent, "filingDate", idx)
        parsed_filing_date = _parse_date(filing_date)
        if parsed_filing_date is None:
            continue
        if start and parsed_filing_date < start:
            continue
        if end and parsed_filing_date > end:
            continue

        accession = _recent_value(recent, "accessionNumber", idx)
        primary_doc = _recent_value(recent, "primaryDocument", idx)
        accepted_at_raw = _recent_value(recent, "acceptanceDateTime", idx)
        accepted_at = _parse_acceptance_datetime(accepted_at_raw)
        rows.append({
            "ticker": str(ticker).upper() if ticker else None,
            "cik": cik_norm,
            "filing_type": form,
            "filing_date": parsed_filing_date.isoformat(),
            "accepted_at": accepted_at.isoformat(timespec="seconds") if accepted_at else None,
            "accession_number": str(accession) if accession else None,
            "primary_document": primary_doc,
            "report_date": _recent_value(recent, "reportDate", idx),
            "archive_url": archive_url(cik_norm, accession, primary_doc),
            "usable_trade_date": conservative_usable_trade_date(accepted_at, str(filing_date)),
            "source": "sec_submissions_form4",
        })
    return rows


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(node: ET.Element, name: str | None = None) -> list[ET.Element]:
    if name is None:
        return list(node)
    return [child for child in list(node) if _local_name(child.tag) == name]


def _child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    for child in list(node):
        if _local_name(child.tag) == name:
            return child
    return None


def _text(node: ET.Element | None, path: str) -> str | None:
    current = node
    for part in path.split("/"):
        current = _child(current, part)
        if current is None:
            return None
    if current.text is None:
        return None
    value = current.text.strip()
    return value or None


def _bool_text(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _float_text(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _all_text(node: ET.Element) -> str:
    return " ".join(text.strip() for text in node.itertext() if text and text.strip())


def _footnotes(root: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    footnotes_node = _child(root, "footnotes")
    if footnotes_node is None:
        return out
    for node in _children(footnotes_node, "footnote"):
        footnote_id = node.attrib.get("id")
        if footnote_id:
            out[footnote_id] = _all_text(node)
    return out


def _transaction_footnote_text(transaction: ET.Element, footnotes: dict[str, str]) -> str:
    ids = []
    for node in transaction.iter():
        if _local_name(node.tag) == "footnoteId":
            footnote_id = node.attrib.get("id")
            if footnote_id:
                ids.append(footnote_id)
    return " ".join(footnotes.get(footnote_id, "") for footnote_id in ids).strip()


def _owner_rows(root: ET.Element) -> list[dict[str, Any]]:
    rows = []
    for owner in _children(root, "reportingOwner"):
        owner_id = _child(owner, "reportingOwnerId")
        relationship = _child(owner, "reportingOwnerRelationship")
        rows.append({
            "owner_cik": normalize_cik(_text(owner_id, "rptOwnerCik")),
            "owner_name": _text(owner_id, "rptOwnerName"),
            "is_director": _bool_text(_text(relationship, "isDirector")),
            "is_officer": _bool_text(_text(relationship, "isOfficer")),
            "is_10pct_owner": _bool_text(_text(relationship, "isTenPercentOwner")),
            "is_other": _bool_text(_text(relationship, "isOther")),
            "officer_title": _text(relationship, "officerTitle"),
            "owner_relationship_other": _text(relationship, "otherText"),
        })
    return rows or [{
        "owner_cik": None,
        "owner_name": None,
        "is_director": False,
        "is_officer": False,
        "is_10pct_owner": False,
        "is_other": False,
        "officer_title": None,
        "owner_relationship_other": None,
    }]


def _base_xml_fields(root: ET.Element, filing: dict[str, Any]) -> dict[str, Any]:
    issuer = _child(root, "issuer")
    document_type = _text(root, "documentType")
    accepted_at = _parse_acceptance_datetime(filing.get("accepted_at"))
    issuer_symbol = _text(issuer, "issuerTradingSymbol")
    issuer_cik = normalize_cik(_text(issuer, "issuerCik"))
    submission_ticker = str(filing.get("ticker") or "").upper() or None
    submission_cik = normalize_cik(filing.get("cik"))
    return {
        "ticker": str(issuer_symbol or submission_ticker or "").upper() or None,
        "cik": issuer_cik or submission_cik,
        "submission_ticker": submission_ticker,
        "submission_cik": submission_cik,
        "issuer_name": _text(issuer, "issuerName"),
        "issuer_cik": issuer_cik,
        "issuer_trading_symbol": issuer_symbol,
        "document_type": document_type,
        "filing_type": filing.get("filing_type") or document_type,
        "period_of_report": _text(root, "periodOfReport") or filing.get("report_date"),
        "filing_date": filing.get("filing_date"),
        "accepted_at": filing.get("accepted_at"),
        "accession_number": filing.get("accession_number"),
        "primary_document": filing.get("primary_document"),
        "archive_url": filing.get("archive_url"),
        "usable_trade_date": conservative_usable_trade_date(accepted_at, filing.get("filing_date")),
        "source": "sec_form4_xml",
    }


def _transaction_row(
    *,
    transaction: ET.Element,
    table: str,
    base: dict[str, Any],
    owner: dict[str, Any],
    footnotes: dict[str, str],
    remarks: str | None,
) -> dict[str, Any]:
    transaction_code = _text(transaction, "transactionCoding/transactionCode")
    acquired_disposed = _text(transaction, "transactionAmounts/transactionAcquiredDisposedCode/value")
    shares = _float_text(_text(transaction, "transactionAmounts/transactionShares/value"))
    price = _float_text(_text(transaction, "transactionAmounts/transactionPricePerShare/value"))
    value = round(shares * price, 2) if shares is not None and price is not None else None
    footnote_text = _transaction_footnote_text(transaction, footnotes)
    text_blob = " ".join(part for part in (footnote_text, remarks, _all_text(transaction)) if part)
    ten_b5_1_flag = bool(re.search(r"10b5[- ]?1", text_blob, re.IGNORECASE))
    option_exercise_flag = str(transaction_code or "").upper() in {"M", "F"}
    open_market_purchase_flag = (
        table == "non_derivative"
        and str(transaction_code or "").upper() == "P"
        and str(acquired_disposed or "").upper() == "A"
    )
    return {
        **base,
        **owner,
        "owner_count": 1,
        "table": table,
        "security_title": (
            _text(transaction, "securityTitle/value")
            or _text(transaction, "derivativeSecurityTitle/value")
        ),
        "underlying_security_title": _text(transaction, "underlyingSecurity/underlyingSecurityTitle/value"),
        "underlying_security_shares": _float_text(_text(transaction, "underlyingSecurity/underlyingSecurityShares/value")),
        "transaction_date": _text(transaction, "transactionDate/value"),
        "transaction_code": transaction_code,
        "transaction_form_type": _text(transaction, "transactionCoding/transactionFormType"),
        "equity_swap_involved": _bool_text(_text(transaction, "transactionCoding/equitySwapInvolved")),
        "shares": shares,
        "price": price,
        "transaction_value": value,
        "acquired_disposed_code": acquired_disposed,
        "shares_owned_following_transaction": _float_text(
            _text(transaction, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        ),
        "direct_or_indirect": _text(transaction, "ownershipNature/directOrIndirectOwnership/value"),
        "ownership_nature": _text(transaction, "ownershipNature/natureOfOwnership/value"),
        "footnote_text": footnote_text or None,
        "remarks": remarks,
        "10b5_1_flag": ten_b5_1_flag,
        "option_exercise_flag": option_exercise_flag,
        "open_market_purchase_flag": open_market_purchase_flag,
        "pit_safe_flag": bool(base.get("accepted_at") and base.get("usable_trade_date")),
    }


def parse_form4_xml(xml_text: str, filing: dict[str, Any]) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    base = _base_xml_fields(root, filing)
    owners = _owner_rows(root)
    owner = dict(owners[0])
    owner["owner_count"] = len(owners)
    notes = _footnotes(root)
    remarks = _text(root, "remarks")
    rows: list[dict[str, Any]] = []

    non_derivative = _child(root, "nonDerivativeTable")
    if non_derivative is not None:
        for transaction in _children(non_derivative, "nonDerivativeTransaction"):
            row = _transaction_row(
                transaction=transaction,
                table="non_derivative",
                base=base,
                owner=owner,
                footnotes=notes,
                remarks=remarks,
            )
            row["owner_count"] = len(owners)
            rows.append(row)

    derivative = _child(root, "derivativeTable")
    if derivative is not None:
        for transaction in _children(derivative, "derivativeTransaction"):
            row = _transaction_row(
                transaction=transaction,
                table="derivative",
                base=base,
                owner=owner,
                footnotes=notes,
                remarks=remarks,
            )
            row["owner_count"] = len(owners)
            rows.append(row)

    return rows


def _safe_doc_cache_name(accession_number: str, primary_document: str) -> str:
    accession = accession_number.replace("-", "")
    safe_doc = re.sub(r"[^A-Za-z0-9._-]+", "__", primary_document)
    return f"{accession}_{safe_doc}"


def _looks_like_html_document(text: str) -> bool:
    head = text[:500].lower()
    return "<html" in head or "<!doctype html" in head


def _document_candidates(filing: dict[str, Any], cache_dir: Path) -> list[tuple[str, Path]]:
    cik = normalize_cik(filing.get("cik"))
    accession = filing.get("accession_number")
    primary_doc = filing.get("primary_document")
    if not cik or not accession or not primary_doc:
        return []

    candidates: list[tuple[str, str]] = []
    raw_doc = raw_form4_primary_document(str(primary_doc))
    if raw_doc and raw_doc != str(primary_doc):
        raw_url = raw_form4_archive_url(cik, str(accession), str(primary_doc))
        if raw_url:
            candidates.append((raw_url, f"raw__{raw_doc}"))
    original_url = archive_url(cik, str(accession), str(primary_doc))
    if original_url:
        candidates.append((original_url, str(primary_doc)))

    out: list[tuple[str, Path]] = []
    seen_urls = set()
    for url, doc_name in candidates:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        out.append((url, cache_dir / f"CIK{cik}" / _safe_doc_cache_name(str(accession), doc_name)))
    return out


def fetch_primary_document(
    filing: dict[str, Any],
    *,
    cache_dir: Path = DEFAULT_XML_CACHE_DIR,
    refresh: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_seconds: float = 0.11,
) -> tuple[str | None, Path | None]:
    candidates = _document_candidates(filing, cache_dir)
    if not candidates:
        return None, None

    last_html: tuple[str, Path] | None = None
    for url, path in candidates:
        if path.exists() and not refresh:
            text = path.read_text(encoding="utf-8", errors="replace")
            if _looks_like_html_document(text):
                last_html = (text, path)
                continue
            return text, path

        request = urllib.request.Request(
            str(url),
            headers={
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        text = raw.decode("utf-8", errors="replace")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        if _looks_like_html_document(text):
            last_html = (text, path)
            continue
        return text, path

    return last_html if last_html else (None, None)


def _ticker_to_cik_map() -> dict[str, str]:
    payload = _load_json(DATA_DIR / "sec_company_tickers.json", {})
    rows = payload.values() if isinstance(payload, dict) else payload
    direct: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        cik = normalize_cik(row.get("cik_str") or row.get("cik"))
        if ticker and cik:
            direct.setdefault(ticker, cik)
    if direct:
        return direct

    mapping: dict[str, str] = {}
    for cik, row in load_company_ticker_map().items():
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            mapping[ticker] = cik
    return mapping


def _universe_tickers(segments: tuple[str, ...]) -> list[str]:
    state = _load_json(DATA_DIR / "universe_state_20260501.json", {})
    tickers: set[str] = set()
    segment_to_key = {
        "core": "core_trade_universe",
        "pilot": "pilot_trade_universe",
        "observation": "observation_universe",
    }
    for segment in segments:
        values = state.get(segment_to_key[segment], [])
        tickers.update(str(value).upper() for value in values)
    return sorted(tickers)


def _resolve_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        tickers = {
            ticker.strip().upper()
            for item in args.tickers
            for ticker in item.split(",")
            if ticker.strip()
        }
    else:
        tickers = set(_universe_tickers(tuple(args.segments)))
    if not args.include_etfs:
        tickers -= NON_COMPANY_TICKERS
    return sorted(tickers)


def backfill_form4_transactions(args: argparse.Namespace) -> dict[str, Any]:
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if start is None or end is None:
        raise ValueError("start and end must be YYYY-MM-DD")
    output_path = _repo_path(args.output)
    summary_path = _repo_path(args.summary_output)
    xml_cache_dir = _repo_path(args.xml_cache_dir)
    ticker_to_cik = _ticker_to_cik_map()
    tickers = _resolve_tickers(args)
    if args.max_ciks:
        tickers = tickers[: args.max_ciks]
    requested_ticker_set = set(tickers)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    external_issuer_examples: list[dict[str, Any]] = []
    excluded_external_issuer_rows = 0
    filings_seen = 0
    documents_fetched_or_read = 0
    mapped = []
    missing = []

    for ticker in tickers:
        cik = ticker_to_cik.get(ticker)
        if not cik:
            missing.append(ticker)
            continue
        mapped.append(ticker)
        try:
            payload = fetch_submission(
                cik,
                refresh=args.refresh_submissions,
                user_agent=args.user_agent,
                sleep_seconds=args.sleep_seconds,
            )
            filings = iter_recent_form4_filings(payload, ticker=ticker, cik=cik, start=start, end=end)
        except Exception as exc:
            errors.append({"ticker": ticker, "cik": cik, "stage": "submission", "error": str(exc)})
            continue

        if args.max_filings_per_cik is not None:
            filings = filings[: args.max_filings_per_cik]
        filings_seen += len(filings)
        for filing in filings:
            if args.no_fetch_xml:
                rows.append({**filing, "record_type": "form4_filing_metadata"})
                continue
            try:
                xml_text, cache_path = fetch_primary_document(
                    filing,
                    cache_dir=xml_cache_dir,
                    refresh=args.refresh_xml,
                    user_agent=args.user_agent,
                    sleep_seconds=args.sleep_seconds,
                )
                if not xml_text:
                    errors.append({
                        "ticker": ticker,
                        "cik": cik,
                        "accession_number": filing.get("accession_number"),
                        "stage": "document_fetch",
                        "error": "missing archive_url or primary_document",
                    })
                    continue
                documents_fetched_or_read += 1
                parsed_rows = parse_form4_xml(xml_text, {**filing, "xml_cache_path": str(cache_path) if cache_path else None})
                for row in parsed_rows:
                    row["xml_cache_path"] = _repo_rel(cache_path) if cache_path else None
                    if (
                        not args.include_external_issuers
                        and row.get("ticker")
                        and str(row["ticker"]).upper() not in requested_ticker_set
                    ):
                        excluded_external_issuer_rows += 1
                        if len(external_issuer_examples) < 20:
                            external_issuer_examples.append({
                                "submission_ticker": row.get("submission_ticker"),
                                "issuer_ticker": row.get("ticker"),
                                "issuer_name": row.get("issuer_name"),
                                "accession_number": row.get("accession_number"),
                            })
                        continue
                    rows.append(row)
            except Exception as exc:
                errors.append({
                    "ticker": ticker,
                    "cik": cik,
                    "accession_number": filing.get("accession_number"),
                    "stage": "xml_parse",
                    "error": str(exc),
                })

    rows.sort(key=lambda row: (
        str(row.get("usable_trade_date") or ""),
        str(row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
        str(row.get("transaction_date") or ""),
        str(row.get("transaction_code") or ""),
    ))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    by_ticker = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    by_code = Counter(str(row.get("transaction_code") or "metadata_only") for row in rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "SEC EDGAR company submissions + Form 4 primary documents",
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "segments": args.segments,
        "tickers_requested": len(tickers),
        "tickers_mapped": len(mapped),
        "missing_cik_tickers": missing,
        "filings_seen": filings_seen,
        "documents_fetched_or_read": documents_fetched_or_read,
        "rows_written": len(rows),
        "excluded_external_issuer_rows": excluded_external_issuer_rows,
        "external_issuer_examples": external_issuer_examples,
        "output_path": _repo_rel(output_path),
        "xml_cache_dir": _repo_rel(xml_cache_dir),
        "errors": errors[:50],
        "error_count": len(errors),
        "transaction_code_counts": dict(sorted(by_code.items())),
        "row_counts_by_ticker": dict(sorted(by_ticker.items())),
        "open_market_purchase_count": sum(1 for row in rows if row.get("open_market_purchase_flag")),
        "option_exercise_count": sum(1 for row in rows if row.get("option_exercise_flag")),
        "ten_b5_1_count": sum(1 for row in rows if row.get("10b5_1_flag")),
        "pit_safe_count": sum(1 for row in rows if row.get("pit_safe_flag")),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "production_impact": "data_backfill_only",
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill SEC Form 4 transaction-level rows for the strategy universe.")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--segments", nargs="+", choices=("core", "pilot", "observation"), default=["core", "pilot", "observation"])
    parser.add_argument("--tickers", action="append", help="Comma-separated ticker list. Defaults to universe_state_20260501 segments.")
    parser.add_argument("--include-etfs", action="store_true")
    parser.add_argument("--include-external-issuers", action="store_true", help="Keep rows where the Form 4 XML issuer ticker is outside the requested ticker universe.")
    parser.add_argument("--max-ciks", type=int)
    parser.add_argument("--max-filings-per-cik", type=int)
    parser.add_argument("--no-fetch-xml", action="store_true", help="Write Form 4 filing metadata only; do not fetch primary documents.")
    parser.add_argument("--refresh-submissions", action="store_true")
    parser.add_argument("--refresh-xml", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--xml-cache-dir", default=str(DEFAULT_XML_CACHE_DIR))
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUT_DIR / f"form4_transactions_{DEFAULT_START.replace('-', '')}_{date.today().strftime('%Y%m%d')}.jsonl"),
    )
    parser.add_argument(
        "--summary-output",
        default=str(DEFAULT_OUT_DIR / f"form4_backfill_summary_{date.today().strftime('%Y%m%d')}.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = backfill_form4_transactions(args)
    print(json.dumps({
        "rows_written": summary["rows_written"],
        "filings_seen": summary["filings_seen"],
        "documents_fetched_or_read": summary["documents_fetched_or_read"],
        "open_market_purchase_count": summary["open_market_purchase_count"],
        "error_count": summary["error_count"],
        "output_path": summary["output_path"],
        "summary_output": _repo_rel(args.summary_output),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
