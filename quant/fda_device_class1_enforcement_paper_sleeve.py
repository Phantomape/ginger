"""Shared openFDA Device Class-I Enforcement Report paper sleeve.

Historical replay and the daily default-off surface deliberately share the
same exact firm map and candidate policy.  ``report_date`` is the only public
availability clock used by the strategy.  Historical rows must retain an
official API URL and frozen source-record hashes; recall initiation and FDA
classification dates are audit context only and never move a signal earlier.

This module cannot submit orders or alter core ranking, sizing, or exits.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError


SLEEVE_NAME = "FDA_DEVICE_CLASS1_ENFORCEMENT_PAPER"
RULE_VERSION = "fda_device_class1_report_green_spy_relative_top1_10d_v1"
SOURCE_RULE_VERSION = "openfda_device_enforcement_report_date_class1_v1"
API_BASE = "https://api.fda.gov/device/enforcement.json"

# Preregistered in exp-20260713-010. Exact matching is intentional. Adding an
# alias after seeing replay outcomes changes the tested candidate population.
# Hologic/HOLX is intentionally absent because the frozen warehouse preflight
# found no price bars for that ticker.
FIRM_TO_TICKER: dict[str, str] = {
    "Boston Scientific Corporation": "BSX",
    "Baxter Healthcare Corporation": "BAX",
    "Philips Respironics, Inc.": "PHG",
    "PHILIPS MEDICAL SYSTEMS NEDERLAND B.V.": "PHG",
    "GE Medical Systems China Co., Ltd.": "GEHC",
    "Datex-Ohmeda, Inc.": "GEHC",
    "DATEX--OHMEDA, INC.": "GEHC",
    "Smiths Medical ASD, Inc.": "ICUI",
    "Smiths Medical ASD Inc.": "ICUI",
    "Abiomed, Inc.": "JNJ",
    "Dexcom, Inc.": "DXCM",
    "Avanos Medical, Inc.": "AVNS",
    "Integra LifeSciences Corp. (NeuroSciences)": "IART",
    "Edwards Lifesciences, LLC": "EW",
    "CareFusion 303, Inc.": "BDX",
    "Abbott": "ABT",
    "Abbott Diabetes Care, Inc.": "ABT",
    "Thoratec LLC": "ABT",
    "Merit Medical Systems, Inc.": "MMSI",
    "C.R. Bard Inc": "BDX",
    "Bard Access Systems, Inc.": "BDX",
    "Bard Peripheral Vascular Inc": "BDX",
    "Tandem Diabetes Care, Inc.": "TNDM",
    "Medtronic Perfusion Systems": "MDT",
    "Medtronic MiniMed, Inc.": "MDT",
    "Covidien": "MDT",
    "Medtronic Neurosurgery": "MDT",
    "Given Imaging Ltd.": "MDT",
    "ICU Medical, Inc.": "ICUI",
    "Bausch & Lomb Surgical, Inc.": "BLCO",
    "Alcon Research LLC": "ALC",
    "Biosense Webster, Inc.": "JNJ",
    "Ethicon Endo-Surgery Inc": "JNJ",
    "Cerenovus Inc": "JNJ",
    "3M Company": "MMM",
    "Cardinal Health 200, LLC": "CAH",
}

BASE_NOTIONAL_USD = 4_000.0
ROUND_TRIP_COST_PCT = 0.0035
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_SESSIONS = 10
DAILY_ENTRY_SLOTS = 1
API_PAGE_LIMIT = 1_000


def _canonical_payload_bytes(payload: Any) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw.encode("utf-8")


def _raw_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_payload_bytes(payload)).hexdigest()


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    elif len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _as_of_iso(value: Any) -> str:
    parsed = _iso_date(value)
    if parsed is None:
        raise ValueError(f"invalid date: {value!r}")
    return parsed


def _api_date(value: Any) -> str:
    return _as_of_iso(value).replace("-", "")


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _strings(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return sorted({str(item).strip() for item in values if str(item or "").strip()})


def _get_json(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ginger-research/1.0 (openFDA PIT archive)"},
    )
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed official host
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            # openFDA represents a valid no-match query as HTTP 404.
            if exc.code == 404:
                return {"meta": {"results": {"total": 0}}, "results": []}
            last_error = exc
            if exc.code != 429 and exc.code < 500:
                raise
            retry_after = _float(exc.headers.get("Retry-After")) if exc.headers else None
            time.sleep(retry_after or min(30.0, 1.5 * (2**attempt) + random.random()))
        except URLError as exc:
            last_error = exc
            time.sleep(min(20.0, 1.0 * (2**attempt) + random.random()))
    else:
        raise last_error or RuntimeError(f"failed to fetch {url}")
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def _raw_event_row(wrapper: dict[str, Any]) -> dict[str, Any]:
    value = wrapper.get("raw_record")
    return value if isinstance(value, dict) else wrapper


def normalise_fda_device_class1_enforcement_events(
    rows: Iterable[dict[str, Any]],
    *,
    require_provenance: bool = True,
) -> list[dict[str, Any]]:
    """Normalize and event-dedupe exact openFDA Device Class-I rows.

    The strategy identity is ``(event_id, ticker, report_date)``. Product-level
    recall rows belonging to that identity are retained as audit lists but do
    not create extra trading candidates.
    """
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for wrapper in rows:
        if not isinstance(wrapper, dict):
            continue
        raw = _raw_event_row(wrapper)
        firm = str(raw.get("recalling_firm") or wrapper.get("recalling_firm") or "").strip()
        ticker = FIRM_TO_TICKER.get(firm)
        classification = str(raw.get("classification") or wrapper.get("classification") or "").strip()
        report_date = _iso_date(raw.get("report_date") or wrapper.get("report_date"))
        event_id = str(raw.get("event_id") or wrapper.get("event_id") or "").strip()
        if not ticker or classification != "Class I" or not report_date or not event_id:
            continue

        source_urls = _strings(wrapper.get("source_urls") or wrapper.get("source_url"))
        record_hashes = _strings(
            wrapper.get("source_record_sha256") or wrapper.get("raw_sha256")
        )
        if not record_hashes and not require_provenance:
            record_hashes = [_raw_sha(raw)]
        if require_provenance and (not source_urls or not record_hashes):
            continue

        key = (event_id, ticker, report_date)
        current = grouped.setdefault(
            key,
            {
                "event_id": event_id,
                "ticker": ticker,
                "recalling_firm": firm,
                "recalling_firms": set(),
                "classification": "Class I",
                "report_date": report_date,
                "recall_numbers": set(),
                "product_descriptions": set(),
                "statuses": set(),
                "recall_initiation_dates": set(),
                "center_classification_dates": set(),
                "initial_firm_notifications": set(),
                "source_urls": set(),
                "source_record_sha256": set(),
            },
        )
        current["recalling_firms"].add(firm)
        current["recall_numbers"].update(
            _strings(raw.get("recall_number") or wrapper.get("recall_numbers"))
        )
        current["product_descriptions"].update(
            _strings(raw.get("product_description") or wrapper.get("product_descriptions"))
        )
        current["statuses"].update(_strings(raw.get("status") or wrapper.get("statuses")))
        current["recall_initiation_dates"].update(
            filter(
                None,
                (
                    _iso_date(value)
                    for value in _strings(
                        raw.get("recall_initiation_date")
                        or wrapper.get("recall_initiation_dates")
                    )
                ),
            )
        )
        current["center_classification_dates"].update(
            filter(
                None,
                (
                    _iso_date(value)
                    for value in _strings(
                        raw.get("center_classification_date")
                        or wrapper.get("center_classification_dates")
                    )
                ),
            )
        )
        current["initial_firm_notifications"].update(
            _strings(
                raw.get("initial_firm_notification")
                or wrapper.get("initial_firm_notifications")
            )
        )
        current["source_urls"].update(source_urls)
        current["source_record_sha256"].update(record_hashes)

    output: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: (item[2], item[1], item[0])):
        row = grouped[key]
        for name in (
            "recalling_firms",
            "recall_numbers",
            "product_descriptions",
            "statuses",
            "recall_initiation_dates",
            "center_classification_dates",
            "initial_firm_notifications",
            "source_urls",
            "source_record_sha256",
        ):
            row[name] = sorted(row[name])
        row["recalling_firm"] = row["recalling_firms"][0]
        row["source_url"] = row["source_urls"][0]
        row["source_record_count"] = len(row["source_record_sha256"])
        row["raw_sha256"] = _raw_sha(
            {
                "event_key": list(key),
                "source_record_sha256": row["source_record_sha256"],
            }
        )
        row["source_rule_version"] = SOURCE_RULE_VERSION
        output.append(row)
    return output


def _query_url(start: str, end: str, *, skip: int) -> str:
    search = (
        f'classification:"Class I" AND '
        f"report_date:[{_api_date(start)} TO {_api_date(end)}]"
    )
    params = {"search": search, "limit": str(API_PAGE_LIMIT), "skip": str(skip)}
    return f"{API_BASE}?{urllib.parse.urlencode(params)}"


def fetch_fda_device_class1_enforcement_events(
    start: str,
    end: str,
    *,
    timeout: float = 30.0,
    archive_payload_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Fetch official report-date-bounded rows and optionally freeze raw pages."""
    start_iso, end_iso = _as_of_iso(start), _as_of_iso(end)
    if start_iso > end_iso:
        raise ValueError("start must be on or before end")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    raw_dir = Path(archive_payload_dir) if archive_payload_dir is not None else None
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)

    wrapped_rows: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    skip = 0
    while True:
        url = _query_url(start_iso, end_iso, skip=skip)
        payload = _get_json(url, timeout=timeout)
        raw_bytes = _canonical_payload_bytes(payload)
        page_sha = hashlib.sha256(raw_bytes).hexdigest()
        results = [row for row in payload.get("results") or [] if isinstance(row, dict)]
        page_name = f"openfda_device_enforcement_page_{skip:06d}.json"
        if raw_dir is not None:
            (raw_dir / page_name).write_bytes(raw_bytes)
        pages.append(
            {
                "skip": skip,
                "url": url,
                "file": page_name if raw_dir is not None else None,
                "sha256": page_sha,
                "record_count": len(results),
            }
        )
        for row in results:
            wrapped_rows.append(
                {
                    "raw_record": row,
                    "source_url": url,
                    "raw_sha256": _raw_sha(row),
                }
            )

        total = int(((payload.get("meta") or {}).get("results") or {}).get("total") or len(results))
        skip += len(results)
        if not results or skip >= total or len(results) < API_PAGE_LIMIT:
            break

    if raw_dir is not None:
        manifest = {
            "schema": "openfda_device_enforcement_fetch_manifest_v1",
            "source_rule_version": SOURCE_RULE_VERSION,
            "retrieved_at": retrieved_at,
            "start": start_iso,
            "end": end_iso,
            "page_count": len(pages),
            "raw_record_count": len(wrapped_rows),
            "pages": pages,
        }
        (raw_dir / "openfda_fetch_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return normalise_fda_device_class1_enforcement_events(
        wrapped_rows, require_provenance=True
    )


def _verify_raw_payload_archive(
    *,
    archive_path: Path,
    archive_payload: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    expected_manifest_sha = str(
        archive_payload.get("raw_payload_manifest_sha256") or ""
    ).strip()
    if not expected_manifest_sha:
        return
    raw_dir_text = str(archive_payload.get("raw_payload_dir") or "").strip()
    manifest_name = str(
        archive_payload.get("raw_payload_manifest_file")
        or "openfda_fetch_manifest.json"
    ).strip()
    if not raw_dir_text:
        raise RuntimeError("FDA enforcement archive is missing raw_payload_dir")
    raw_dir = Path(raw_dir_text)
    if not raw_dir.is_absolute():
        raw_dir = archive_path.parent / raw_dir
    manifest_path = raw_dir / manifest_name
    if not manifest_path.exists():
        raise RuntimeError(f"FDA enforcement raw manifest missing: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha:
        raise RuntimeError(f"FDA enforcement raw manifest hash mismatch: {manifest_path}")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    raw_record_hashes: set[str] = set()
    page_urls: set[str] = set()
    for page in manifest.get("pages") or []:
        if not isinstance(page, dict):
            raise RuntimeError("FDA enforcement raw manifest contains an invalid page")
        page_path = raw_dir / str(page.get("file") or "")
        if not page_path.exists():
            raise RuntimeError(f"FDA enforcement raw page missing: {page_path}")
        page_bytes = page_path.read_bytes()
        if hashlib.sha256(page_bytes).hexdigest() != str(page.get("sha256") or ""):
            raise RuntimeError(f"FDA enforcement raw page hash mismatch: {page_path}")
        payload = json.loads(page_bytes.decode("utf-8"))
        results = [row for row in payload.get("results") or [] if isinstance(row, dict)]
        if len(results) != int(page.get("record_count") or 0):
            raise RuntimeError(f"FDA enforcement raw page record-count mismatch: {page_path}")
        raw_record_hashes.update(_raw_sha(row) for row in results)
        page_urls.add(str(page.get("url") or ""))
    for event in events:
        hashes = set(_strings(event.get("source_record_sha256")))
        urls = set(_strings(event.get("source_urls") or event.get("source_url")))
        if not hashes or not hashes.issubset(raw_record_hashes):
            raise RuntimeError(
                f"FDA enforcement event/raw-record hash mismatch: {event.get('event_id')}"
            )
        if not urls or not urls.issubset(page_urls):
            raise RuntimeError(
                f"FDA enforcement event/source URL mismatch: {event.get('event_id')}"
            )


def load_fda_device_class1_enforcement_archive(path: Path | str) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    rows = payload.get("events") if isinstance(payload, dict) else payload
    events = [dict(row) for row in (rows or []) if isinstance(row, dict)]
    expected = payload.get("events_sha256") if isinstance(payload, dict) else None
    if expected and hashlib.sha256(_canonical_payload_bytes(events)).hexdigest() != expected:
        raise RuntimeError(f"FDA enforcement archive hash mismatch: {file_path}")
    if isinstance(payload, dict):
        _verify_raw_payload_archive(
            archive_path=file_path,
            archive_payload=payload,
            events=events,
        )
    return events


def save_fda_device_class1_enforcement_archive(
    path: Path | str,
    events: Iterable[dict[str, Any]],
    *,
    archive_payload_dir: Path | str | None = None,
) -> dict[str, Any]:
    file_path = Path(path)
    rows = normalise_fda_device_class1_enforcement_events(
        (dict(row) for row in events), require_provenance=True
    )
    payload = {
        "schema": "fda_device_class1_enforcement_report_archive_v1",
        "rule_version": SOURCE_RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(rows),
        "ticker_count": len({row["ticker"] for row in rows}),
        "events_sha256": hashlib.sha256(_canonical_payload_bytes(rows)).hexdigest(),
        "events": rows,
    }
    if archive_payload_dir is not None:
        raw_dir = Path(archive_payload_dir)
        manifest_path = raw_dir / "openfda_fetch_manifest.json"
        if not manifest_path.exists():
            raise RuntimeError(f"FDA enforcement raw manifest missing: {manifest_path}")
        try:
            raw_dir_reference = str(raw_dir.resolve().relative_to(file_path.parent.resolve()))
        except ValueError:
            raw_dir_reference = str(raw_dir.resolve())
        payload.update(
            {
                "raw_payload_dir": raw_dir_reference,
                "raw_payload_manifest_file": manifest_path.name,
                "raw_payload_manifest_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
            }
        )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def refresh_fda_device_class1_enforcement_archive(
    path: Path | str,
    *,
    start: str,
    end: str,
    timeout: float = 30.0,
    archive_payload_dir: Path | str | None = None,
) -> dict[str, Any]:
    events = fetch_fda_device_class1_enforcement_events(
        start,
        end,
        timeout=timeout,
        archive_payload_dir=archive_payload_dir,
    )
    return save_fda_device_class1_enforcement_archive(
        path,
        events,
        archive_payload_dir=archive_payload_dir,
    )


def _normalise_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        day = _iso_date(row.get("date") or row.get("Date"))
        close = _float(row.get("close") if "close" in row else row.get("Close"))
        open_ = _float(row.get("open") if "open" in row else row.get("Open"))
        high = _float(row.get("high") if "high" in row else row.get("High"))
        low = _float(row.get("low") if "low" in row else row.get("Low"))
        if day and close and close > 0:
            output.append(
                {"date": day, "open": open_, "high": high, "low": low, "close": close}
            )
    unique = {row["date"]: row for row in output}
    return [unique[key] for key in sorted(unique)]


def _atr_target(rows: list[dict[str, Any]], signal_idx: int, entry_price: float) -> float:
    true_ranges: list[float] = []
    for idx in range(max(0, signal_idx - 13), signal_idx + 1):
        row = rows[idx]
        high, low = row.get("high"), row.get("low")
        if high is None or low is None:
            continue
        previous = rows[idx - 1]["close"] if idx > 0 else row["close"]
        true_ranges.append(max(high - low, abs(high - previous), abs(low - previous)))
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry_price * 0.02
    return round(entry_price + 3.5 * atr, 4)


def build_fda_device_class1_enforcement_candidates(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply the fixed strict-after, green/relative, top-1/day policy."""
    start_iso, end_iso = _as_of_iso(start), _as_of_iso(end)
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    spy = bars.get("SPY") or []
    spy_dates = [row["date"] for row in spy]
    spy_pos = {day: idx for idx, day in enumerate(spy_dates)}
    ticker_pos = {
        ticker: {row["date"]: idx for idx, row in enumerate(rows)}
        for ticker, rows in bars.items()
    }
    rejects: Counter[str] = Counter()
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        firm = str(event.get("recalling_firm") or "").strip()
        ticker = str(event.get("ticker") or "").upper()
        report_date = _iso_date(event.get("report_date"))
        event_id = str(event.get("event_id") or "").strip()
        if (
            not event_id
            or not report_date
            or event.get("classification") != "Class I"
            or FIRM_TO_TICKER.get(firm) != ticker
            or not event.get("source_url")
            or not event.get("source_record_sha256")
        ):
            rejects["invalid_or_unprovenanced_event"] += 1
            continue
        key = (event_id, ticker, report_date)
        if key in deduped:
            rejects["duplicate_event_key"] += 1
            continue
        deduped[key] = dict(event)

    confirmed: list[dict[str, Any]] = []
    for event in deduped.values():
        ticker = event["ticker"]
        report_date = event["report_date"]
        # report_date has no usable intraday clock. Strictly greater prevents
        # same-day lookahead and makes the first subsequent close observable.
        signal_date = next((day for day in spy_dates if day > report_date), None)
        if not signal_date or signal_date < start_iso or signal_date > end_iso:
            rejects["outside_signal_window"] += 1
            continue
        issuer_idx = ticker_pos.get(ticker, {}).get(signal_date)
        market_idx = spy_pos.get(signal_date)
        issuer = bars.get(ticker) or []
        if issuer_idx is None or market_idx is None or issuer_idx < 1 or market_idx < 1:
            rejects["missing_price_confirmation"] += 1
            continue
        issuer_return = issuer[issuer_idx]["close"] / issuer[issuer_idx - 1]["close"] - 1.0
        spy_return = spy[market_idx]["close"] / spy[market_idx - 1]["close"] - 1.0
        excess = issuer_return - spy_return
        if issuer_return <= 0:
            rejects["issuer_not_green"] += 1
            continue
        if excess <= 0:
            rejects["not_spy_relative_positive"] += 1
            continue
        confirmed.append(
            {
                **event,
                "signal_date": signal_date,
                "issuer_signal_return": round(issuer_return, 10),
                "spy_signal_return": round(spy_return, 10),
                "excess_signal_return": round(excess, 10),
                "score": round(excess, 10),
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in confirmed:
        by_day[row["signal_date"]].append(row)
    selected: list[dict[str, Any]] = []
    next_allowed: dict[str, int] = {}
    for signal_date in sorted(by_day):
        day_rows = sorted(
            by_day[signal_date],
            key=lambda row: (-float(row["score"]), row["ticker"], row["event_id"]),
        )
        admitted = 0
        for row in day_rows:
            ticker = row["ticker"]
            position = spy_pos[signal_date]
            if position < next_allowed.get(ticker, -1):
                rejects["same_ticker_cooldown"] += 1
                continue
            if admitted >= DAILY_ENTRY_SLOTS:
                rejects["daily_top1_limit"] += 1
                continue
            selected.append(row)
            next_allowed[ticker] = position + SAME_TICKER_COOLDOWN_SESSIONS
            admitted += 1
    return selected, dict(sorted(rejects.items()))


def replay_fda_device_class1_enforcement_paper_trades(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    event_rows = normalise_fda_device_class1_enforcement_events(
        (dict(row) for row in events), require_provenance=True
    )
    bars = {
        str(ticker).upper(): _normalise_bars(rows)
        for ticker, rows in ohlcv_by_ticker.items()
    }
    selected, rejects = build_fda_device_class1_enforcement_candidates(
        events=event_rows,
        ohlcv_by_ticker=bars,
        start=start,
        end=end,
    )
    end_iso = _as_of_iso(end)
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    for candidate in selected:
        ticker = candidate["ticker"]
        rows = bars.get(ticker) or []
        index = {row["date"]: idx for idx, row in enumerate(rows)}
        signal_idx = index.get(candidate["signal_date"])
        if signal_idx is None:
            unsettled.append({**candidate, "unsettled_reason": "missing_signal_bar"})
            continue
        entry_idx = signal_idx + 1
        # The entry session is hold session 1; the tenth-session close is
        # therefore nine indexes after the entry-open bar.
        scheduled_exit_idx = entry_idx + HOLD_DAYS - 1
        if entry_idx >= len(rows) or rows[entry_idx]["date"] > end_iso:
            unsettled.append({**candidate, "unsettled_reason": "entry_outside_window"})
            continue
        exit_idx = scheduled_exit_idx
        exit_reason = "scheduled_10_session_horizon_close"
        if exit_idx >= len(rows) or rows[exit_idx]["date"] > end_iso:
            inside = [idx for idx, row in enumerate(rows) if row["date"] <= end_iso]
            if not inside or inside[-1] < entry_idx:
                unsettled.append(
                    {**candidate, "unsettled_reason": "no_window_end_liquidation_bar"}
                )
                continue
            exit_idx = inside[-1]
            exit_reason = "window_end_liquidation"
        entry_price = rows[entry_idx].get("open")
        exit_price = rows[exit_idx].get("close")
        if not entry_price or not exit_price:
            unsettled.append(
                {**candidate, "unsettled_reason": "missing_entry_or_exit_price"}
            )
            continue
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                "entry_date": rows[entry_idx]["date"],
                "exit_date": rows[exit_idx]["date"],
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "target_price": _atr_target(rows, signal_idx, entry_price),
                "hold_days": HOLD_DAYS,
                "hold_sessions_realized": exit_idx - entry_idx + 1,
                "scheduled_exit_date": (
                    rows[scheduled_exit_idx]["date"]
                    if scheduled_exit_idx < len(rows)
                    else None
                ),
                "exit_reason": exit_reason,
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(BASE_NOTIONAL_USD * net_return, 2),
            }
        )
    generated = len(event_rows)
    return {
        "trades": trades,
        "unsettled": unsettled,
        "selected_candidates": selected,
        "reject_totals": rejects,
        "signals_generated": generated,
        "signals_survived": len(selected),
        "survival_rate": round(len(selected) / generated, 6) if generated else 0.0,
    }


def empty_fda_device_class1_enforcement_paper_state() -> dict[str, Any]:
    return {"observations": [], "pending": [], "open": [], "closed": []}


def _snapshot_seed_reason(row: dict[str, Any], *, as_of: str) -> str | None:
    first_seen = _iso_date(row.get("first_seen_date"))
    report_date = _iso_date(row.get("report_date"))
    if not first_seen or not report_date:
        return "invalid_availability_clock"
    if first_seen > report_date:
        return "late_first_seen_after_report_date"
    if first_seen < report_date:
        return "first_seen_before_report_date_fail_closed"
    if report_date < as_of:
        return "timely_prior_observation_not_readmitted"
    if report_date > as_of:
        return "future_report_date_fail_closed"
    return None


def build_fda_device_class1_enforcement_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    observations: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    as_of = _as_of_iso(as_of_date)
    rows = [dict(row) for row in observations]
    pending_confirmation = [
        row
        for row in rows
        if _iso_date(row.get("first_seen_date")) == as_of
        and _iso_date(row.get("report_date")) == as_of
        and row.get("classification") == "Class I"
        and row.get("source_url")
        and row.get("source_record_sha256")
    ]
    pending_keys = {
        (row.get("event_id"), row.get("ticker"), row.get("report_date"))
        for row in pending_confirmation
    }
    seed_only_observations: list[dict[str, Any]] = []
    seed_reasons: Counter[str] = Counter()
    for row in rows:
        identity = (row.get("event_id"), row.get("ticker"), row.get("report_date"))
        if identity in pending_keys:
            continue
        reason = _snapshot_seed_reason(row, as_of=as_of) or "not_pending_fail_closed"
        seed_reasons[reason] += 1
        seed_only_observations.append({**row, "snapshot_seed_reason": reason})
    return {
        "schema": "fda_device_class1_enforcement_daily_snapshot_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "status": "ok",
        "observation_count": len(rows),
        # Source observations cannot become candidates until a strictly later
        # trading close and SPY-relative confirmation are available.
        "candidate_count": 0,
        "pending_confirmation_count": len(pending_confirmation),
        "pending_count": len(pending_confirmation),
        "settled_count": 0,
        "seed_only_count": len(seed_only_observations),
        "late_first_seen_count": seed_reasons.get(
            "late_first_seen_after_report_date", 0
        ),
        "seed_reason_counts": dict(sorted(seed_reasons.items())),
        "source_observations": pending_confirmation,
        "seed_only_observations": seed_only_observations,
        "candidates": [],
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }


def prep_and_build_fda_device_class1_enforcement_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    existing_observations: Iterable[dict[str, Any]],
    fetched_events: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    as_of = _as_of_iso(as_of_date)

    def key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(row.get("event_id") or ""),
            str(row.get("ticker") or "").upper(),
            str(_iso_date(row.get("report_date")) or ""),
        )

    indexed = {
        key(dict(row)): dict(row)
        for row in existing_observations
        if all(key(dict(row)))
    }
    for event in fetched_events:
        row = dict(event)
        identity = key(row)
        if not all(identity):
            continue
        first_seen = (
            _iso_date(indexed.get(identity, {}).get("first_seen_date")) or as_of
        )
        report_date = _iso_date(row.get("report_date"))
        if report_date and first_seen == report_date:
            forward_eligibility = "eligible_for_strict_after_confirmation"
            seed_only_reason = None
        elif report_date and first_seen > report_date:
            forward_eligibility = "seed_only"
            seed_only_reason = "late_first_seen_after_report_date"
        else:
            forward_eligibility = "seed_only"
            seed_only_reason = "availability_clock_inconsistent_fail_closed"
        indexed[identity] = {
            **indexed.get(identity, {}),
            **row,
            "first_seen_date": first_seen,
            "forward_eligibility": forward_eligibility,
            "seed_only_reason": seed_only_reason,
        }
    rows = sorted(
        indexed.values(),
        key=lambda row: (
            row.get("first_seen_date", ""),
            row.get("report_date", ""),
            row.get("ticker", ""),
            row.get("event_id", ""),
        ),
    )
    return (
        build_fda_device_class1_enforcement_paper_sleeve_snapshot(
            as_of_date=as_of, observations=rows
        ),
        rows,
    )


def materialize_daily_snapshot(*, repo_root: Path | str, as_of_date: str) -> dict[str, Any]:
    """Fetch a narrow report-date delta and persist a fail-closed snapshot."""
    root = Path(repo_root)
    as_of = _as_of_iso(as_of_date)
    base = root / "data" / "paper_sleeves" / "fda_device_class1_enforcement"
    observations_path = base / "observations.json"
    existing: list[dict[str, Any]] = []
    if observations_path.exists():
        payload = json.loads(observations_path.read_text(encoding="utf-8"))
        existing = [dict(row) for row in payload.get("observations") or []]
    meta_path = base / "observation_meta.json"
    last_successful = None
    if meta_path.exists():
        last_successful = _iso_date(
            json.loads(meta_path.read_text(encoding="utf-8")).get(
                "last_successful_observation_date"
            )
        )
    recent_start = (
        (date.fromisoformat(last_successful) - timedelta(days=7)).isoformat()
        if last_successful
        else (date.fromisoformat(as_of) - timedelta(days=14)).isoformat()
    )
    raw_dir = base / "source_raw" / as_of.replace("-", "")
    fetched = fetch_fda_device_class1_enforcement_events(
        recent_start,
        as_of,
        timeout=15.0,
        archive_payload_dir=raw_dir,
    )
    snapshot, observations = (
        prep_and_build_fda_device_class1_enforcement_paper_sleeve_snapshot(
            as_of_date=as_of,
            existing_observations=existing,
            fetched_events=fetched,
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    observations_path.write_text(
        json.dumps(
            {
                "schema": "fda_device_class1_enforcement_forward_observations_v1",
                "observations": observations,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(
            {"last_successful_observation_date": as_of}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    snapshot_path = base / f"snapshot_{as_of.replace('-', '')}.json"
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        **snapshot,
        "snapshot_path": str(snapshot_path),
        "observations_path": str(observations_path),
    }
