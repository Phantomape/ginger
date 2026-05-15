from __future__ import annotations

import argparse
import gzip
import json
import re
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from data_paths import resolve_daily_artifact_path
from sec_submissions import fetch_submission
from sec_ticker_map import normalize_cik


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_CACHE_DIR = DATA_DIR / "sec_submissions_cache"
DEFAULT_OUT_DIR = DATA_DIR / "non_ohlcv"
DEFAULT_START = "2024-10-02"
DEFAULT_END = "2026-04-21"
DEFAULT_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
SEC_SUBMISSION_FILE_URL = "https://data.sec.gov/submissions/{name}"
NON_COMPANY_TICKERS = {"SPY", "QQQ", "IWM", "GLD", "IAU", "SLV"}
DEFAULT_FORMS = ("8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A")


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


def parse_acceptance_datetime(value: Any) -> datetime | None:
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


def usable_trade_date(accepted_at: datetime | None, filing_date: str | None) -> str | None:
    """Conservative EOD tradability: first weekday after SEC accepted/filing date."""
    base = accepted_at.date() if accepted_at else _parse_date(filing_date)
    if base is None:
        return None
    return _next_weekday(base + timedelta(days=1)).isoformat()


def _ticker_to_cik_map() -> dict[str, str]:
    payload = _load_json(DATA_DIR / "sec_company_tickers.json", {})
    rows = payload.values() if isinstance(payload, dict) else payload
    out: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        cik = normalize_cik(row.get("cik_str") or row.get("cik"))
        if ticker and cik:
            out.setdefault(ticker, cik)
    return out


def _universe_tickers(segments: tuple[str, ...]) -> list[str]:
    state = _load_json(resolve_daily_artifact_path("universe_state", "20260501", DATA_DIR), {})
    segment_to_key = {
        "core": "core_trade_universe",
        "pilot": "pilot_trade_universe",
        "observation": "observation_universe",
    }
    tickers: set[str] = set()
    for segment in segments:
        tickers.update(str(ticker).upper() for ticker in state.get(segment_to_key[segment], []) or [])
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
    out = sorted(tickers)
    if args.max_ciks:
        out = out[: args.max_ciks]
    return out


def _filing_table(payload: dict[str, Any]) -> dict[str, Any]:
    filings = payload.get("filings") if isinstance(payload, dict) else {}
    recent = filings.get("recent") if isinstance(filings, dict) else {}
    if isinstance(recent, dict) and recent:
        return recent
    if isinstance(payload, dict) and isinstance(payload.get("accessionNumber"), list):
        return payload
    return {}


def _row_count(table: dict[str, Any]) -> int:
    lengths = [len(value) for value in table.values() if isinstance(value, list)]
    return max(lengths) if lengths else 0


def _value(table: dict[str, Any], field: str, idx: int) -> Any:
    values = table.get(field)
    if not isinstance(values, list) or idx >= len(values):
        return None
    return values[idx]


def _archive_url(cik: str | None, accession: str | None, primary_doc: str | None) -> str | None:
    cik_norm = normalize_cik(cik)
    if not cik_norm or not accession or not primary_doc:
        return None
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik_norm)}/{str(accession).replace('-', '')}/{primary_doc}"
    )


def _index_url(cik: str | None, accession: str | None) -> str | None:
    cik_norm = normalize_cik(cik)
    if not cik_norm or not accession:
        return None
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik_norm)}/{str(accession).replace('-', '')}/{accession}-index.htm"
    )


def _split_8k_items(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,;\s]+", text) if part.strip()]


def _form_base(form: str) -> str:
    return str(form or "").upper().replace("/A", "")


def parse_filing_rows(
    payload: dict[str, Any],
    *,
    ticker: str | None,
    cik: str,
    forms: set[str],
    start: date,
    end: date,
    pit_source: str,
    chunk_name: str | None = None,
) -> list[dict[str, Any]]:
    table = _filing_table(payload)
    cik_norm = normalize_cik(cik or payload.get("cik"))
    rows: list[dict[str, Any]] = []
    for idx in range(_row_count(table)):
        form = str(_value(table, "form", idx) or "").upper()
        if form not in forms:
            continue
        filing_date = str(_value(table, "filingDate", idx) or "")[:10]
        parsed_filing_date = _parse_date(filing_date)
        if parsed_filing_date is None or parsed_filing_date < start or parsed_filing_date > end:
            continue
        accession = _value(table, "accessionNumber", idx)
        primary_doc = _value(table, "primaryDocument", idx)
        accepted_raw = _value(table, "acceptanceDateTime", idx)
        accepted_at = parse_acceptance_datetime(accepted_raw)
        report_date = _value(table, "reportDate", idx)
        items_raw = _value(table, "items", idx)
        rows.append({
            "ticker": str(ticker).upper() if ticker else None,
            "cik": cik_norm,
            "form_type": form,
            "form_base": _form_base(form),
            "is_amendment": form.endswith("/A"),
            "filing_date": filing_date,
            "report_date": str(report_date)[:10] if report_date else None,
            "accepted_at": accepted_at.isoformat(timespec="seconds") if accepted_at else None,
            "acceptance_datetime_raw": accepted_raw,
            "usable_trade_date": usable_trade_date(accepted_at, filing_date),
            "accession_number": str(accession) if accession else None,
            "primary_document": primary_doc,
            "archive_url": _archive_url(cik_norm, str(accession) if accession else None, primary_doc),
            "index_url": _index_url(cik_norm, str(accession) if accession else None),
            "items_raw": items_raw,
            "eight_k_item_codes": _split_8k_items(items_raw) if _form_base(form) == "8-K" else [],
            "is_xbrl": bool(_value(table, "isXBRL", idx)),
            "is_inline_xbrl": bool(_value(table, "isInlineXBRL", idx)),
            "size": _value(table, "size", idx),
            "act": _value(table, "act", idx),
            "film_number": _value(table, "filmNumber", idx),
            "pit_source": pit_source,
            "source_chunk_name": chunk_name,
            "pit_safe_flag": accepted_at is not None,
            "pit_caveat": (
                "SEC public availability PIT proxy from EDGAR accepted_at; "
                "does not prove the local production pipeline observed this filing."
            ),
        })
    return rows


def _submission_files(payload: dict[str, Any]) -> list[dict[str, Any]]:
    filings = payload.get("filings") if isinstance(payload, dict) else {}
    files = filings.get("files") if isinstance(filings, dict) else []
    return [row for row in files if isinstance(row, dict)]


def _chunk_overlaps(row: dict[str, Any], start: date, end: date) -> bool:
    filing_from = _parse_date(row.get("filingFrom"))
    filing_to = _parse_date(row.get("filingTo"))
    if filing_from is None or filing_to is None:
        return False
    return filing_from <= end and filing_to >= start


def _chunk_cache_path(name: str, cache_dir: Path) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "__", name)
    return cache_dir / "files" / safe_name


def fetch_submission_chunk(
    name: str,
    *,
    cache_dir: Path,
    refresh: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    sleep_seconds: float = 0.11,
) -> dict[str, Any]:
    path = _chunk_cache_path(name, cache_dir)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        SEC_SUBMISSION_FILE_URL.format(name=name),
        headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
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


def _recent_min_filing_date(payload: dict[str, Any]) -> date | None:
    dates = []
    table = _filing_table(payload)
    for idx in range(_row_count(table)):
        parsed = _parse_date(_value(table, "filingDate", idx))
        if parsed:
            dates.append(parsed)
    return min(dates) if dates else None


def _should_fetch_chunks(payload: dict[str, Any], start: date, args: argparse.Namespace) -> bool:
    if args.no_fetch_overlap_chunks:
        return False
    if args.fetch_all_overlap_chunks:
        return True
    recent_min = _recent_min_filing_date(payload)
    return recent_min is not None and recent_min > start


def backfill_sec_filing_events(args: argparse.Namespace) -> dict[str, Any]:
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if start is None or end is None:
        raise ValueError("start/end must be YYYY-MM-DD")
    forms = {str(form).upper() for item in args.forms for form in item.split(",") if form.strip()}
    tickers = _resolve_tickers(args)
    ticker_to_cik = _ticker_to_cik_map()
    cache_dir = _repo_path(args.cache_dir)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    missing_cik_tickers = []
    mapped_tickers = []
    chunks_listed = 0
    chunks_overlap = 0
    chunks_read = 0
    chunks_skipped_recent_covers_window = 0

    for ticker in tickers:
        cik = ticker_to_cik.get(ticker)
        if not cik:
            missing_cik_tickers.append(ticker)
            continue
        mapped_tickers.append(ticker)
        try:
            payload = fetch_submission(
                cik,
                cache_dir=cache_dir,
                refresh=args.refresh_submissions,
                user_agent=args.user_agent,
                sleep_seconds=args.sleep_seconds,
            )
            rows.extend(parse_filing_rows(
                payload,
                ticker=ticker,
                cik=cik,
                forms=forms,
                start=start,
                end=end,
                pit_source="sec_submissions_recent",
            ))
            files = _submission_files(payload)
            chunks_listed += len(files)
            overlap_files = [row for row in files if _chunk_overlaps(row, start, end)]
            chunks_overlap += len(overlap_files)
            if not _should_fetch_chunks(payload, start, args):
                if overlap_files:
                    chunks_skipped_recent_covers_window += len(overlap_files)
                continue
            for file_row in overlap_files:
                name = file_row.get("name")
                if not name:
                    continue
                try:
                    chunk_payload = fetch_submission_chunk(
                        str(name),
                        cache_dir=cache_dir,
                        refresh=args.refresh_chunks,
                        user_agent=args.user_agent,
                        sleep_seconds=args.sleep_seconds,
                    )
                    chunks_read += 1
                    rows.extend(parse_filing_rows(
                        chunk_payload,
                        ticker=ticker,
                        cik=cik,
                        forms=forms,
                        start=start,
                        end=end,
                        pit_source="sec_submissions_file",
                        chunk_name=str(name),
                    ))
                except Exception as exc:
                    errors.append({"ticker": ticker, "cik": cik, "stage": "chunk", "name": name, "error": str(exc)})
        except Exception as exc:
            errors.append({"ticker": ticker, "cik": cik, "stage": "submission", "error": str(exc)})

    deduped: dict[tuple[str | None, str | None, str | None], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("ticker"), row.get("accession_number"), row.get("form_type"))
        previous = deduped.get(key)
        if previous is None or previous.get("pit_source") == "sec_submissions_file":
            deduped[key] = row
    out_rows = sorted(deduped.values(), key=lambda row: (
        str(row.get("usable_trade_date") or ""),
        str(row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
    ))

    output = _repo_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in out_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    by_form: dict[str, int] = {}
    by_ticker: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for row in out_rows:
        by_form[row["form_type"]] = by_form.get(row["form_type"], 0) + 1
        ticker = str(row.get("ticker") or "UNKNOWN")
        by_ticker[ticker] = by_ticker.get(ticker, 0) + 1
        source = str(row.get("pit_source") or "UNKNOWN")
        by_source[source] = by_source.get(source, 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment_id": "exp-20260503-050",
        "source": "SEC EDGAR submissions API",
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "forms": sorted(forms),
        "segments": args.segments,
        "tickers_requested": len(tickers),
        "tickers_mapped": len(mapped_tickers),
        "missing_cik_tickers": missing_cik_tickers,
        "rows_written": len(out_rows),
        "pit_safe_rows": sum(1 for row in out_rows if row.get("pit_safe_flag")),
        "row_counts_by_form": dict(sorted(by_form.items())),
        "row_counts_by_source": dict(sorted(by_source.items())),
        "row_counts_by_ticker": dict(sorted(by_ticker.items())),
        "submission_chunks_listed": chunks_listed,
        "submission_chunks_overlap_window": chunks_overlap,
        "submission_chunks_read": chunks_read,
        "submission_chunks_skipped_recent_covers_window": chunks_skipped_recent_covers_window,
        "error_count": len(errors),
        "errors": errors[:50],
        "output_path": _repo_rel(output),
        "cache_dir": _repo_rel(cache_dir),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "production_impact": "sec_public_pit_backfill_only",
        },
        "pit_caveat": (
            "This backfills SEC public availability by accepted_at/accession metadata. "
            "It is not a replay of what the local news pipeline or LLM actually observed."
        ),
    }
    summary_path = _repo_path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill SEC public-availability PIT filing events.")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--segments", nargs="+", choices=("core", "pilot", "observation"), default=["core", "pilot", "observation"])
    parser.add_argument("--tickers", action="append", help="Comma-separated ticker list. Defaults to universe_state_20260501 segments.")
    parser.add_argument("--include-etfs", action="store_true")
    parser.add_argument("--max-ciks", type=int)
    parser.add_argument("--forms", action="append", default=[",".join(DEFAULT_FORMS)])
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--refresh-submissions", action="store_true")
    parser.add_argument("--refresh-chunks", action="store_true")
    parser.add_argument("--fetch-all-overlap-chunks", action="store_true", help="Fetch all listed older chunk files that overlap the requested window.")
    parser.add_argument("--no-fetch-overlap-chunks", action="store_true", help="Do not fetch older chunk files even if recent history does not cover the start date.")
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--output", default=str(DEFAULT_OUT_DIR / "sec_filing_events_20241002_20260421.jsonl"))
    parser.add_argument("--summary-output", default=str(DEFAULT_OUT_DIR / "sec_filing_backfill_summary_20241002_20260421.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = backfill_sec_filing_events(args)
    print(json.dumps({
        "rows_written": summary["rows_written"],
        "pit_safe_rows": summary["pit_safe_rows"],
        "row_counts_by_form": summary["row_counts_by_form"],
        "submission_chunks_read": summary["submission_chunks_read"],
        "error_count": summary["error_count"],
        "output_path": summary["output_path"],
        "summary_output": _repo_rel(args.summary_output),
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
