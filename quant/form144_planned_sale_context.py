"""Form 144 planned-sale context logger.

The helper is data-only. It builds point-in-time context rows from local EDGAR
Form 144 index files and parses planned-sale fields when a cached filing text is
available. It does not rank candidates, size positions, or place orders.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "non_ohlcv"
DEFAULT_FORM_INDEX_DIR = REPO_ROOT / "data" / "cache" / "sec" / "form_index"
DEFAULT_COMPANY_TICKERS_PATH = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
DEFAULT_DOCUMENT_CACHE_DIRS = [
    REPO_ROOT / "data" / "cache" / "sec" / "form144_documents",
    REPO_ROOT / "data" / "cache" / "sec" / "edgar",
    REPO_ROOT / "data" / "cache" / "sec",
]
DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR = DEFAULT_DOCUMENT_CACHE_DIRS[0]
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"

SCHEMA_VERSION = 1
RULE_VERSION = "form144_planned_sale_float_context_logger_v1"
DEFAULT_LOOKBACK_DAYS = 90

OUTCOME_JOIN_SCHEMA = {
    "join_keys": [
        "ticker",
        "entry_date",
        "usable_trade_date_lte_entry_date",
        "form144_accession_number",
    ],
    "forward_outcome_fields": [
        "cash_replacement_value_10d",
        "cash_replacement_value_20d",
        "spy_replacement_value_10d",
        "spy_replacement_value_20d",
        "qqq_replacement_value_10d",
        "qqq_replacement_value_20d",
        "closed_forward_row",
    ],
    "pit_guard": (
        "Only rows with usable_trade_date <= entry_date are eligible for an "
        "entry context join."
    ),
}

FORWARD_REOPEN_GATE = {
    "closed_forward_rows_min": 25,
    "high_planned_sale_float_bucket_rows_min": 8,
    "single_ticker_share_max": 0.40,
    "required_replacement_values": ["cash", "SPY", "QQQ"],
    "park_after_materialization_runs_without_new_closable_rows": 3,
}

FORM_LINE_RE = re.compile(
    r"^(?P<form>144(?:/A)?)\s+"
    r"(?P<company>.+?)\s+"
    r"(?P<cik>\d{1,10})\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<file>edgar/data/\d+/\S+\.txt)\s*$",
    re.IGNORECASE,
)


def persist_form144_planned_sale_context(
    *,
    as_of: str | date | datetime,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    form_index_dir: str | Path = DEFAULT_FORM_INDEX_DIR,
    company_tickers_path: str | Path = DEFAULT_COMPANY_TICKERS_PATH,
    document_cache_dirs: list[str | Path] | None = None,
    float_shares_by_ticker: dict[str, float] | None = None,
    adv20_shares_by_ticker: dict[str, float] | None = None,
    adv20_dollars_by_ticker: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Write the date-stamped Form 144 planned-sale context ledger."""

    as_of_date = parse_date(as_of)
    if as_of_date is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    tag = as_of_date.strftime("%Y%m%d")
    root = Path(data_dir)
    rows_path = root / f"form144_planned_sale_context_{tag}.jsonl"
    summary_path = root / f"form144_planned_sale_context_summary_{tag}.json"
    rows, build_summary = build_form144_context_rows(
        as_of=as_of_date,
        lookback_days=lookback_days,
        form_index_dir=form_index_dir,
        company_tickers_path=company_tickers_path,
        document_cache_dirs=document_cache_dirs,
        float_shares_by_ticker=float_shares_by_ticker,
        adv20_shares_by_ticker=adv20_shares_by_ticker,
        adv20_dollars_by_ticker=adv20_dollars_by_ticker,
    )
    write_jsonl(rows_path, rows)
    summary = {
        **build_summary,
        "status": "ok",
        "asof_date": as_of_date.isoformat(),
        "lookback_days": int(lookback_days),
        "output_path": path_text(rows_path),
        "summary_output": path_text(summary_path),
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "daily_snapshot_wired": True,
        "entry_context_schema": entry_context_schema(),
        "outcome_join_schema": OUTCOME_JOIN_SCHEMA,
        "forward_reopen_gate": FORWARD_REOPEN_GATE,
        "production_impact": production_impact("form144_planned_sale_context_collection"),
    }
    write_json(summary_path, summary)
    return summary


def build_form144_context_rows(
    *,
    as_of: str | date | datetime,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    form_index_dir: str | Path = DEFAULT_FORM_INDEX_DIR,
    company_tickers_path: str | Path = DEFAULT_COMPANY_TICKERS_PATH,
    document_cache_dirs: list[str | Path] | None = None,
    float_shares_by_ticker: dict[str, float] | None = None,
    adv20_shares_by_ticker: dict[str, float] | None = None,
    adv20_dollars_by_ticker: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    as_of_date = parse_date(as_of)
    if as_of_date is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    start_date = as_of_date - timedelta(days=max(0, int(lookback_days)))
    form_index_dir = Path(form_index_dir)
    company_tickers_path = Path(company_tickers_path)
    cache_dirs = [Path(p) for p in (document_cache_dirs or DEFAULT_DOCUMENT_CACHE_DIRS)]
    ticker_map = load_cik_ticker_map(company_tickers_path)
    events, index_audit = load_form144_index_events(
        form_index_dir=form_index_dir,
        company_tickers_path=company_tickers_path,
        start_date=start_date,
        as_of_date=as_of_date,
        ticker_map=ticker_map,
    )

    rows: list[dict[str, Any]] = []
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for event in events:
        document_path = find_cached_document(event["file_name"], cache_dirs)
        parsed: dict[str, Any]
        document_status: str
        if document_path is None:
            parsed = empty_parse_result("missing_cached_primary_document")
            document_status = "missing_cache"
        else:
            try:
                parsed = parse_form144_text(document_path.read_text(encoding="utf-8-sig", errors="replace"))
                document_status = "parsed" if parsed["parse_status"] == "parsed" else "parse_failed"
            except OSError as exc:
                parsed = empty_parse_result(f"document_read_error:{exc}")
                document_status = "read_failed"

        ticker = str(event["ticker"]).upper()
        ratios = compute_planned_sale_ratios(
            planned_sale_shares=parsed.get("planned_sale_shares"),
            planned_sale_value_usd=parsed.get("planned_sale_value_usd"),
            ticker=ticker,
            float_shares_by_ticker=float_shares_by_ticker,
            adv20_shares_by_ticker=adv20_shares_by_ticker,
            adv20_dollars_by_ticker=adv20_dollars_by_ticker,
        )
        row = {
            "schema_version": SCHEMA_VERSION,
            "rule_version": RULE_VERSION,
            "asof_date": as_of_date.isoformat(),
            "generated_at": generated_at,
            "ticker": ticker,
            "ticker_mapping_count": event["ticker_mapping_count"],
            "ticker_mapping_source": path_text(company_tickers_path),
            "cik": event["cik"],
            "company_name": event["company_name"],
            "form_type": event["form_type"],
            "filing_date": event["filing_date"],
            "accepted_at": None,
            "usable_trade_date": conservative_usable_trade_date(event["filing_date"]),
            "accession_number": event["accession_number"],
            "file_name": event["file_name"],
            "archive_url": archive_url(event["file_name"]),
            "source_index_file": event["source_index_file"],
            "primary_document_status": document_status,
            "primary_document_cache_path": path_text(document_path) if document_path else None,
            **parsed,
            **ratios,
        }
        row["planned_sale_high_bucket"] = planned_sale_bucket(row) == "high_planned_sale_overhang"
        row["planned_sale_bucket"] = planned_sale_bucket(row)
        row["machine_parseable_planned_sale_ratio"] = bool(
            row.get("planned_sale_to_float") is not None
            or row.get("planned_sale_to_adv20") is not None
        )
        rows.append(row)

    rows.sort(
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("accession_number") or ""),
        )
    )
    summary = summarize_rows(rows, index_audit=index_audit, cache_dirs=cache_dirs)
    return rows, summary


def load_form144_index_events(
    *,
    form_index_dir: Path,
    company_tickers_path: Path,
    start_date: date,
    as_of_date: date,
    ticker_map: dict[int, set[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ticker_map = ticker_map if ticker_map is not None else load_cik_ticker_map(company_tickers_path)
    events: list[dict[str, Any]] = []
    raw_144_rows = 0
    malformed_144_rows = 0
    unmapped_rows = 0
    index_files = sorted(form_index_dir.glob("form_*.idx"))
    for path in index_files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.startswith("144"):
                continue
            raw_144_rows += 1
            parsed = parse_form_index_line(line, source_index_file=path_text(path))
            if parsed is None:
                malformed_144_rows += 1
                continue
            filing_day = parse_date(parsed["filing_date"])
            if filing_day is None or filing_day < start_date or filing_day > as_of_date:
                continue
            tickers = sorted(ticker_map.get(int(parsed["cik"]), set()))
            if not tickers:
                unmapped_rows += 1
                continue
            for ticker in tickers:
                events.append(
                    {
                        **parsed,
                        "ticker": ticker,
                        "ticker_mapping_count": len(tickers),
                    }
                )
    audit = {
        "source_form_index_dir": path_text(form_index_dir),
        "source_company_ticker_map": path_text(company_tickers_path),
        "source_index_file_count": len(index_files),
        "raw_form144_rows": raw_144_rows,
        "malformed_form144_rows": malformed_144_rows,
        "unmapped_form144_rows_in_window": unmapped_rows,
        "mapped_form144_rows_in_window": len(events),
        "ticker_count_in_window": len({row["ticker"] for row in events}),
        "start_date": start_date.isoformat(),
        "end_date": as_of_date.isoformat(),
    }
    return events, audit


def parse_form_index_line(line: str, *, source_index_file: str) -> dict[str, Any] | None:
    match = FORM_LINE_RE.match(line.rstrip())
    if not match:
        return None
    file_name = match.group("file")
    return {
        "form_type": match.group("form").upper(),
        "company_name": " ".join(match.group("company").split()),
        "cik": int(match.group("cik")),
        "filing_date": match.group("date"),
        "file_name": file_name,
        "accession_number": Path(file_name).stem,
        "source_index_file": source_index_file,
    }


def parse_form144_text(text: str) -> dict[str, Any]:
    plain = normalize_text(text)
    shares = first_number_after(
        plain,
        [
            r"number of shares(?: or other units)?(?: to be sold)?",
            r"securities to be sold",
            r"shares(?: or units)? to be sold",
        ],
    )
    value = first_number_after(
        plain,
        [
            r"aggregate market value",
            r"approximate market value",
            r"market value of securities to be sold",
            r"value of securities to be sold",
        ],
    )
    start = first_date_after(
        plain,
        [
            r"approximate date of sale",
            r"date of sale",
            r"planned sale date",
        ],
    )
    end = first_date_after(
        plain,
        [
            r"ending date of sale",
            r"sale end date",
            r"through date",
        ],
    )
    seller = first_text_after(
        plain,
        [
            r"name of person(?:\(s\))? for whose account(?: the securities)?(?: are)?(?: to be sold)?",
            r"person for whose account the securities are to be sold",
            r"seller name",
        ],
    )
    role = first_text_after(
        plain,
        [
            r"relationship to issuer",
            r"relationship of seller to issuer",
            r"holder role",
        ],
    )
    title = first_text_after(
        plain,
        [
            r"title of the class of securities",
            r"title of class",
            r"class of securities",
        ],
    )
    found_fields = [
        shares is not None,
        value is not None,
        start is not None,
        seller is not None,
        role is not None,
    ]
    parse_status = "parsed" if any(found_fields) else "no_planned_sale_fields"
    return {
        "parse_status": parse_status,
        "parse_confidence": round(sum(1 for item in found_fields if item) / len(found_fields), 3),
        "planned_sale_shares": shares,
        "planned_sale_value_usd": value,
        "planned_sale_period_start": start,
        "planned_sale_period_end": end,
        "seller_name": seller,
        "holder_role": role,
        "relationship_to_issuer": role,
        "security_title": title,
    }


def normalize_text(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def empty_parse_result(status: str) -> dict[str, Any]:
    return {
        "parse_status": status,
        "parse_confidence": 0.0,
        "planned_sale_shares": None,
        "planned_sale_value_usd": None,
        "planned_sale_period_start": None,
        "planned_sale_period_end": None,
        "seller_name": None,
        "holder_role": None,
        "relationship_to_issuer": None,
        "security_title": None,
    }


def compute_planned_sale_ratios(
    *,
    planned_sale_shares: Any,
    planned_sale_value_usd: Any,
    ticker: str,
    float_shares_by_ticker: dict[str, float] | None,
    adv20_shares_by_ticker: dict[str, float] | None,
    adv20_dollars_by_ticker: dict[str, float] | None,
) -> dict[str, Any]:
    ticker_key = ticker.upper()
    shares = finite_float(planned_sale_shares)
    value = finite_float(planned_sale_value_usd)
    float_shares = finite_float((float_shares_by_ticker or {}).get(ticker_key))
    adv_shares = finite_float((adv20_shares_by_ticker or {}).get(ticker_key))
    adv_dollars = finite_float((adv20_dollars_by_ticker or {}).get(ticker_key))
    to_float = shares / float_shares if shares is not None and float_shares else None
    to_adv = None
    if shares is not None and adv_shares:
        to_adv = shares / adv_shares
    elif value is not None and adv_dollars:
        to_adv = value / adv_dollars
    return {
        "float_shares_source_value": round_float(float_shares, 4),
        "adv20_shares_source_value": round_float(adv_shares, 4),
        "adv20_dollars_source_value": round_float(adv_dollars, 2),
        "planned_sale_to_float": round_float(to_float, 8),
        "planned_sale_to_adv20": round_float(to_adv, 8),
    }


def planned_sale_bucket(row: dict[str, Any]) -> str:
    to_float = finite_float(row.get("planned_sale_to_float"))
    to_adv = finite_float(row.get("planned_sale_to_adv20"))
    if (to_float is not None and to_float >= 0.01) or (to_adv is not None and to_adv >= 0.50):
        return "high_planned_sale_overhang"
    if row.get("planned_sale_shares") is not None or row.get("planned_sale_value_usd") is not None:
        return "planned_sale_size_parseable_no_denominator"
    if str(row.get("primary_document_status") or "") == "missing_cache":
        return "form144_index_only_document_missing"
    return "form144_no_parseable_planned_sale"


def latest_form144_context_for_entry(
    *,
    rows: list[dict[str, Any]],
    ticker: str,
    entry_date: str | date | datetime,
    lookback_days: int = 30,
) -> dict[str, Any]:
    entry_day = parse_date(entry_date)
    if entry_day is None:
        return empty_entry_context(ticker=ticker, entry_date=None, reason="invalid_entry_date")
    start_day = entry_day - timedelta(days=max(0, int(lookback_days)))
    selected = []
    for row in rows:
        if str(row.get("ticker") or "").upper() != ticker.upper():
            continue
        usable = parse_date(row.get("usable_trade_date"))
        if usable is not None and start_day <= usable <= entry_day:
            selected.append(row)
    if not selected:
        return empty_entry_context(ticker=ticker, entry_date=entry_day.isoformat(), reason="no_pit_form144_context")
    selected.sort(key=lambda item: (str(item.get("usable_trade_date") or ""), str(item.get("accession_number") or "")))
    high_rows = [row for row in selected if row.get("planned_sale_bucket") == "high_planned_sale_overhang"]
    max_to_float = max_optional(row.get("planned_sale_to_float") for row in selected)
    max_to_adv = max_optional(row.get("planned_sale_to_adv20") for row in selected)
    latest = selected[-1]
    return {
        "ticker": ticker.upper(),
        "entry_date": entry_day.isoformat(),
        "lookback_days": int(lookback_days),
        "form144_context_rows": len(selected),
        "form144_high_planned_sale_rows": len(high_rows),
        "form144_latest_usable_trade_date": latest.get("usable_trade_date"),
        "form144_latest_accession_number": latest.get("accession_number"),
        "form144_max_planned_sale_to_float": max_to_float,
        "form144_max_planned_sale_to_adv20": max_to_adv,
        "form144_planned_sale_bucket": "high_planned_sale_overhang"
        if high_rows
        else "planned_sale_context_present",
        "eligible_for_forward_outcome_join": True,
    }


def materialize_form144_primary_documents(
    *,
    context_path: str | Path,
    cache_dir: str | Path = DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR,
    max_documents: int | None = 10,
    sleep_seconds: float = 0.11,
    user_agent: str = DEFAULT_USER_AGENT,
    refresh: bool = False,
    fetcher: Any = None,
) -> dict[str, Any]:
    """Download missing Form 144 primary filing texts referenced by a context ledger."""

    context_path = Path(context_path)
    cache_dir = Path(cache_dir)
    rows = load_context_rows(context_path)
    seen_files: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        file_name = str(row.get("file_name") or "").replace("\\", "/").lstrip("/")
        if not file_name or file_name in seen_files:
            continue
        seen_files.add(file_name)
        candidates.append(row)

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "context_path": path_text(context_path),
        "cache_dir": path_text(cache_dir),
        "source_rows": len(rows),
        "unique_primary_documents": len(candidates),
        "max_documents": max_documents,
        "refresh": bool(refresh),
        "sleep_seconds": float(sleep_seconds),
        "user_agent": user_agent,
        "attempted_downloads": 0,
        "downloaded": 0,
        "already_cached": 0,
        "failed": 0,
        "sample_downloaded": [],
        "sample_failed": [],
        "sample_cached": [],
        "trade_enabled": False,
        "production_impact": production_impact("form144_primary_document_cache_materialization"),
    }
    fetch = fetcher or fetch_url_bytes
    for row in candidates:
        if max_documents is not None and summary["attempted_downloads"] >= int(max_documents):
            break
        file_name = str(row.get("file_name") or "").replace("\\", "/").lstrip("/")
        target_path = primary_document_cache_path(file_name, cache_dir)
        if target_path.exists() and not refresh:
            summary["already_cached"] += 1
            append_sample(summary["sample_cached"], cache_record(row, target_path))
            continue
        url = archive_url(file_name)
        summary["attempted_downloads"] += 1
        try:
            content = fetch(url=url, user_agent=user_agent)
            if not content:
                raise ValueError("empty_response")
            write_bytes_atomic(target_path, content)
            summary["downloaded"] += 1
            append_sample(summary["sample_downloaded"], cache_record(row, target_path, url=url))
        except Exception as exc:  # noqa: BLE001 - cache materialization is best-effort.
            summary["failed"] += 1
            append_sample(
                summary["sample_failed"],
                {
                    **cache_record(row, target_path, url=url),
                    "error": str(exc)[:300],
                },
            )
        if sleep_seconds and sleep_seconds > 0:
            time.sleep(float(sleep_seconds))
    summary["cache_ready_for_parser"] = summary["downloaded"] + summary["already_cached"] > 0
    summary["status"] = (
        "ok"
        if summary["failed"] == 0
        else "partial"
        if summary["downloaded"] or summary["already_cached"]
        else "blocked"
    )
    return summary


def load_context_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def primary_document_cache_path(file_name: str, cache_dir: str | Path) -> Path:
    normalized = file_name.replace("\\", "/").lstrip("/")
    return Path(cache_dir).joinpath(*normalized.split("/"))


def fetch_url_bytes(*, url: str, user_agent: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"http_{exc.code}:{exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"url_error:{exc.reason}") from exc


def write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(content)
    temp.replace(path)


def cache_record(row: dict[str, Any], path: Path, *, url: str | None = None) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "cik": row.get("cik"),
        "filing_date": row.get("filing_date"),
        "accession_number": row.get("accession_number"),
        "file_name": row.get("file_name"),
        "url": url,
        "cache_path": path_text(path),
    }


def append_sample(items: list[dict[str, Any]], item: dict[str, Any], *, limit: int = 10) -> None:
    if len(items) < limit:
        items.append(item)


def empty_entry_context(*, ticker: str, entry_date: str | None, reason: str) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "entry_date": entry_date,
        "lookback_days": None,
        "form144_context_rows": 0,
        "form144_high_planned_sale_rows": 0,
        "form144_latest_usable_trade_date": None,
        "form144_latest_accession_number": None,
        "form144_max_planned_sale_to_float": None,
        "form144_max_planned_sale_to_adv20": None,
        "form144_planned_sale_bucket": "no_pit_form144_context",
        "eligible_for_forward_outcome_join": False,
        "reason": reason,
    }


def entry_context_schema() -> dict[str, Any]:
    return {
        "keys": ["ticker", "entry_date"],
        "pit_filter": "usable_trade_date <= entry_date",
        "context_fields": [
            "form144_context_rows",
            "form144_high_planned_sale_rows",
            "form144_latest_usable_trade_date",
            "form144_latest_accession_number",
            "form144_max_planned_sale_to_float",
            "form144_max_planned_sale_to_adv20",
            "form144_planned_sale_bucket",
        ],
    }


def summarize_rows(
    rows: list[dict[str, Any]],
    *,
    index_audit: dict[str, Any],
    cache_dirs: list[Path],
) -> dict[str, Any]:
    bucket_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        bucket_counts[str(row.get("planned_sale_bucket") or "unknown")] += 1
    usable_days = [row.get("usable_trade_date") for row in rows if row.get("usable_trade_date")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_written": len(rows),
        "ticker_count": len({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}),
        "rows_with_cached_primary_document": sum(1 for row in rows if row.get("primary_document_status") != "missing_cache"),
        "rows_with_parseable_planned_sale_shares": sum(1 for row in rows if row.get("planned_sale_shares") is not None),
        "rows_with_parseable_planned_sale_value": sum(1 for row in rows if row.get("planned_sale_value_usd") is not None),
        "rows_with_parseable_planned_sale_to_float": sum(1 for row in rows if row.get("planned_sale_to_float") is not None),
        "rows_with_parseable_planned_sale_to_adv20": sum(1 for row in rows if row.get("planned_sale_to_adv20") is not None),
        "rows_with_machine_parseable_ratio": sum(1 for row in rows if row.get("machine_parseable_planned_sale_ratio")),
        "planned_sale_bucket_counts": dict(sorted(bucket_counts.items())),
        "min_usable_trade_date": min(usable_days) if usable_days else None,
        "max_usable_trade_date": max(usable_days) if usable_days else None,
        "index_audit": index_audit,
        "document_cache_dirs": [path_text(path) for path in cache_dirs],
    }


def load_cik_ticker_map(path: str | Path = DEFAULT_COMPANY_TICKERS_PATH) -> dict[int, set[str]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    values = raw.values() if isinstance(raw, dict) else raw
    by_cik: dict[int, set[str]] = defaultdict(set)
    for item in values:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        try:
            cik = int(item.get("cik_str"))
        except (TypeError, ValueError):
            continue
        by_cik[cik].add(ticker)
    return by_cik


def find_cached_document(file_name: str, cache_dirs: list[Path]) -> Path | None:
    normalized = file_name.replace("\\", "/").lstrip("/")
    rel = Path(*normalized.split("/"))
    accession = Path(file_name).stem
    candidates: list[Path] = []
    for root in cache_dirs:
        candidates.extend(
            [
                root / rel,
                root / rel.name,
                root / accession / rel.name,
                root / f"{accession}.txt",
            ]
        )
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def conservative_usable_trade_date(filing_date: str) -> str | None:
    day = parse_date(filing_date)
    if day is None:
        return None
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.isoformat()


def archive_url(file_name: str) -> str:
    return f"https://www.sec.gov/Archives/{file_name.lstrip('/')}"


def first_number_after(text: str, label_patterns: list[str]) -> float | None:
    for label in label_patterns:
        pattern = re.compile(
            rf"{label}\s*(?:[:\-]|is|are)?\s*\$?\s*(?P<number>\(?[0-9][0-9,]*(?:\.\d+)?\)?)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            value = parse_number(match.group("number"))
            if value is not None:
                return value
    return None


def first_date_after(text: str, label_patterns: list[str]) -> str | None:
    for label in label_patterns:
        pattern = re.compile(
            rf"{label}\s*(?:[:\-]|is|are)?\s*(?P<date>[A-Za-z]+\.?\s+\d{{1,2}},\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            parsed = parse_date(match.group("date"))
            if parsed is not None:
                return parsed.isoformat()
    return None


def first_text_after(text: str, label_patterns: list[str]) -> str | None:
    stop_words = (
        " relationship ",
        " title ",
        " number of ",
        " aggregate ",
        " approximate ",
        " date of ",
    )
    for label in label_patterns:
        pattern = re.compile(
            rf"{label}\s*(?:[:\-]|is|are)?\s*(?P<value>[A-Za-z0-9][A-Za-z0-9 .,&'/()_-]{{1,120}})",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            continue
        value = " ".join(match.group("value").split()).strip(" -:")
        lower_value = f" {value.lower()} "
        cut_at = len(value)
        for stop in stop_words:
            pos = lower_value.find(stop)
            if pos > 0:
                cut_at = min(cut_at, max(0, pos - 1))
        value = value[:cut_at].strip(" -:")
        if value:
            return value[:120]
    return None


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()").replace("$", "").replace(",", "").strip()
    try:
        number = float(raw)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return -number if negative else number


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(".", "")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text[:30], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def round_float(value: Any, digits: int = 6) -> float | None:
    number = finite_float(value)
    if number is None:
        return None
    return round(number, digits)


def max_optional(values: Any) -> float | None:
    numbers = [finite_float(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    return round_float(max(numbers), 8) if numbers else None


def production_impact(scope: str) -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "scope": scope,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def path_text(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return str(path).replace("\\", "/")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write Form 144 planned-sale context rows.")
    parser.add_argument("--as-of", required=True, help="As-of date YYYY-MM-DD")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--form-index-dir", default=str(DEFAULT_FORM_INDEX_DIR))
    parser.add_argument("--company-tickers-path", default=str(DEFAULT_COMPANY_TICKERS_PATH))
    parser.add_argument("--materialize-primary-docs", action="store_true")
    parser.add_argument("--context-path", default=None)
    parser.add_argument("--primary-document-cache-dir", default=str(DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR))
    parser.add_argument("--max-documents", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    parser.add_argument("--refresh", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.materialize_primary_docs:
        context_path = args.context_path
        if context_path is None:
            as_of_date = parse_date(args.as_of)
            if as_of_date is None:
                raise ValueError(f"invalid --as-of date: {args.as_of!r}")
            context_path = (
                Path(args.data_dir)
                / f"form144_planned_sale_context_{as_of_date:%Y%m%d}.jsonl"
            )
        summary = materialize_form144_primary_documents(
            context_path=context_path,
            cache_dir=args.primary_document_cache_dir,
            max_documents=args.max_documents,
            sleep_seconds=args.sleep_seconds,
            user_agent=args.user_agent,
            refresh=args.refresh,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))
        return 0 if summary["status"] in {"ok", "partial"} else 2
    summary = persist_form144_planned_sale_context(
        as_of=args.as_of,
        data_dir=args.data_dir,
        lookback_days=args.lookback_days,
        form_index_dir=args.form_index_dir,
        company_tickers_path=args.company_tickers_path,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
