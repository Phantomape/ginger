"""Daily PIT-safe-ish non-OHLCV snapshot refresh for production runs.

This module keeps the forward event queues from depending on stale historical
backfill files. It writes date-stamped SEC filing, SEC filing text, and Form 4
artifacts that `run.py` can consume on the same day, similar to
`earnings_snapshot_YYYYMMDD.json`.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from form4_backfill import (
        DEFAULT_USER_AGENT as FORM4_USER_AGENT,
        DEFAULT_XML_CACHE_DIR,
        backfill_form4_transactions,
    )
    from sec_filing_backfill import (
        DEFAULT_CACHE_DIR as SEC_SUBMISSIONS_CACHE_DIR,
        DEFAULT_FORMS as SEC_DEFAULT_FORMS,
        DEFAULT_USER_AGENT as SEC_USER_AGENT,
        backfill_sec_filing_events,
    )
    from sec_filing_text_backfill import (
        DEFAULT_CACHE_DIR as SEC_TEXT_CACHE_DIR,
        build_rows as build_sec_filing_text_rows,
        write_json as write_sec_filing_text_summary,
        write_jsonl as write_sec_filing_text_jsonl,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.form4_backfill import (
        DEFAULT_USER_AGENT as FORM4_USER_AGENT,
        DEFAULT_XML_CACHE_DIR,
        backfill_form4_transactions,
    )
    from quant.sec_filing_backfill import (
        DEFAULT_CACHE_DIR as SEC_SUBMISSIONS_CACHE_DIR,
        DEFAULT_FORMS as SEC_DEFAULT_FORMS,
        DEFAULT_USER_AGENT as SEC_USER_AGENT,
        backfill_sec_filing_events,
    )
    from quant.sec_filing_text_backfill import (
        DEFAULT_CACHE_DIR as SEC_TEXT_CACHE_DIR,
        build_rows as build_sec_filing_text_rows,
        write_json as write_sec_filing_text_summary,
        write_jsonl as write_sec_filing_text_jsonl,
    )


DEFAULT_DATA_DIR = Path("data/non_ohlcv")
DEFAULT_LOOKBACK_DAYS = 10
DEFAULT_SEGMENTS = ["core", "pilot", "observation"]


def persist_daily_non_ohlcv_snapshots(
    *,
    as_of: str | date | datetime,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    logger: Any = None,
    refresh_sec_submissions: bool = True,
    refresh_sec_text: bool = False,
    refresh_form4_submissions: bool = True,
    refresh_form4_xml: bool = False,
    sleep_seconds: float = 0.11,
    request_delay_sec: float = 0.11,
    max_ciks: int | None = None,
) -> dict[str, Any]:
    """Write date-stamped SEC and Form 4 inputs for today's forward queues.

    The generated files are intentionally default-off data artifacts. They do
    not alter strategy behavior by themselves; queue/sleeve consumers decide
    what to do with the data.
    """

    as_of_date = _parse_as_of(as_of)
    tag = as_of_date.strftime("%Y%m%d")
    start_date = as_of_date - timedelta(days=max(0, int(lookback_days)))
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)

    paths = {
        "sec_filing_events": root / f"sec_filing_events_{tag}.jsonl",
        "sec_filing_summary": root / f"sec_filing_backfill_summary_{tag}.json",
        "sec_filing_text": root / f"sec_filing_text_{tag}.jsonl",
        "sec_filing_text_summary": root / f"sec_filing_text_backfill_summary_{tag}.json",
        "form4_transactions": root / f"form4_transactions_{tag}.jsonl",
        "form4_summary": root / f"form4_backfill_summary_{tag}.json",
        "summary": root / f"daily_non_ohlcv_snapshot_{tag}.json",
    }

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asof_date": as_of_date.isoformat(),
        "date_tag": tag,
        "lookback_days": int(lookback_days),
        "date_range": {
            "start": start_date.isoformat(),
            "end": as_of_date.isoformat(),
        },
        "paths": {key: _path_text(path) for key, path in paths.items()},
        "status": "started",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "daily_non_ohlcv_data_refresh_only",
        },
    }

    sec_summary = _run_sec_filing_events(
        paths=paths,
        start_date=start_date,
        as_of_date=as_of_date,
        refresh_sec_submissions=refresh_sec_submissions,
        sleep_seconds=sleep_seconds,
        max_ciks=max_ciks,
    )
    snapshot["sec_filing_events"] = sec_summary

    if sec_summary.get("status") == "ok":
        snapshot["sec_filing_text"] = _run_sec_filing_text(
            paths=paths,
            refresh_sec_text=refresh_sec_text,
            request_delay_sec=request_delay_sec,
        )
    else:
        snapshot["sec_filing_text"] = {
            "status": "skipped",
            "reason": "sec_filing_events_failed",
        }

    snapshot["form4_transactions"] = _run_form4_transactions(
        paths=paths,
        start_date=start_date,
        as_of_date=as_of_date,
        refresh_form4_submissions=refresh_form4_submissions,
        refresh_form4_xml=refresh_form4_xml,
        sleep_seconds=sleep_seconds,
        max_ciks=max_ciks,
    )

    statuses = [
        snapshot["sec_filing_events"].get("status"),
        snapshot["sec_filing_text"].get("status"),
        snapshot["form4_transactions"].get("status"),
    ]
    if all(status == "ok" for status in statuses):
        snapshot["status"] = "ok"
    elif any(status == "ok" for status in statuses):
        snapshot["status"] = "partial"
    else:
        snapshot["status"] = "failed"

    _write_json(paths["summary"], snapshot)
    if logger:
        logger.info(
            "Daily non-OHLCV snapshot: status=%s sec_rows=%s sec_text_rows=%s form4_rows=%s",
            snapshot["status"],
            snapshot["sec_filing_events"].get("rows_written"),
            snapshot["sec_filing_text"].get("rows_written"),
            snapshot["form4_transactions"].get("rows_written"),
        )
    return snapshot


def _run_sec_filing_events(
    *,
    paths: dict[str, Path],
    start_date: date,
    as_of_date: date,
    refresh_sec_submissions: bool,
    sleep_seconds: float,
    max_ciks: int | None,
) -> dict[str, Any]:
    try:
        args = argparse.Namespace(
            start=start_date.isoformat(),
            end=as_of_date.isoformat(),
            segments=list(DEFAULT_SEGMENTS),
            tickers=None,
            include_etfs=False,
            max_ciks=max_ciks,
            forms=[",".join(SEC_DEFAULT_FORMS)],
            cache_dir=str(SEC_SUBMISSIONS_CACHE_DIR),
            refresh_submissions=refresh_sec_submissions,
            refresh_chunks=False,
            fetch_all_overlap_chunks=False,
            no_fetch_overlap_chunks=True,
            sleep_seconds=sleep_seconds,
            user_agent=SEC_USER_AGENT,
            output=str(paths["sec_filing_events"]),
            summary_output=str(paths["sec_filing_summary"]),
        )
        summary = backfill_sec_filing_events(args)
        return {"status": "ok", **summary}
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "output_path": _path_text(paths["sec_filing_events"]),
            "summary_output": _path_text(paths["sec_filing_summary"]),
        }


def _run_sec_filing_text(
    *,
    paths: dict[str, Path],
    refresh_sec_text: bool,
    request_delay_sec: float,
) -> dict[str, Any]:
    try:
        args = argparse.Namespace(
            events=str(paths["sec_filing_events"]),
            output=str(paths["sec_filing_text"]),
            summary_output=str(paths["sec_filing_text_summary"]),
            cache_dir=str(SEC_TEXT_CACHE_DIR),
            forms=["8-K"],
            item_codes=["all"],
            max_documents=4,
            max_chars_per_doc=180000,
            limit=None,
            refresh=refresh_sec_text,
            request_delay_sec=request_delay_sec,
            user_agent=SEC_USER_AGENT,
        )
        rows, summary = build_sec_filing_text_rows(args)
        write_sec_filing_text_jsonl(paths["sec_filing_text"], rows)
        write_sec_filing_text_summary(paths["sec_filing_text_summary"], summary)
        return {"status": "ok", **summary}
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "output_path": _path_text(paths["sec_filing_text"]),
            "summary_output": _path_text(paths["sec_filing_text_summary"]),
        }


def _run_form4_transactions(
    *,
    paths: dict[str, Path],
    start_date: date,
    as_of_date: date,
    refresh_form4_submissions: bool,
    refresh_form4_xml: bool,
    sleep_seconds: float,
    max_ciks: int | None,
) -> dict[str, Any]:
    try:
        args = argparse.Namespace(
            start=start_date.isoformat(),
            end=as_of_date.isoformat(),
            segments=list(DEFAULT_SEGMENTS),
            tickers=None,
            include_etfs=False,
            include_external_issuers=False,
            max_ciks=max_ciks,
            max_filings_per_cik=None,
            no_fetch_xml=False,
            refresh_submissions=refresh_form4_submissions,
            refresh_xml=refresh_form4_xml,
            sleep_seconds=sleep_seconds,
            user_agent=FORM4_USER_AGENT,
            xml_cache_dir=str(DEFAULT_XML_CACHE_DIR),
            output=str(paths["form4_transactions"]),
            summary_output=str(paths["form4_summary"]),
        )
        summary = backfill_form4_transactions(args)
        return {"status": "ok", **summary}
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "output_path": _path_text(paths["form4_transactions"]),
            "summary_output": _path_text(paths["form4_summary"]),
        }


def _parse_as_of(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _path_text(path: Path) -> str:
    return str(path).replace("\\", "/")
